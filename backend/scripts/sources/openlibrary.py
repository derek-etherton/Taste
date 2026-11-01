"""Open Library: match the book catalogue to Open Library works and keep our own copy of them.

Open Library publishes full dumps monthly (archive.org collection "ol_exports", one item per
dump, e.g. ol_dump_2026-09-30). Each file is gzipped TSV: type, key, revision, last_modified,
JSON. We read them in place with DuckDB, keep everything about the books we have (works, all
their editions, authors, series, Open Library's own ratings and reading log) in
data/book/openlibrary.duckdb, and project what the app uses into data/book/openlibrary.csv
(see taste/model/openlibrary.py).

Matching: a book's Goodreads ID against editions' identifiers.goodreads; failing that, the same
main title and author surname as bookgenome.link() uses. Merged works are followed through the
redirects dump.
"""

import hashlib
import json
import re
import statistics
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from taste.model.bookgenome import norm_author, norm_title

SEARCH = ("https://archive.org/advancedsearch.php?q=collection%3Aol_exports+AND+identifier%3Aol_dump_2*"
          "&fl%5B%5D=identifier&sort%5B%5D=publicdate+desc&rows=1&output=json")
METADATA = "https://archive.org/metadata/{}"
DOWNLOAD = "https://archive.org/download/{item}/{name}"
FILES = ["works", "editions", "authors", "redirects", "other", "ratings", "reading-log"]
YEARS = (1450, None)  # first-publication years outside [1450, the dump's year] are typos
LONE = 50  # ...and so is an earliest year this far before every other edition
CAP = 8  # subjects (and places, people, times) kept per book
# Tables of openlibrary.duckdb. author_keys maps the author keys works use to the ones we have
# (Open Library merges duplicate authors).
KEEP = ["works", "editions", "authors", "author_keys", "series", "ratings", "reading_log", "meta"]

# Columns of openlibrary.csv, after "id".
COLUMNS = ["ol_work", "match", "first_published", "ol_series", "ol_series_index", "description",
           "first_sentence", "subjects", "subject_places", "subject_people", "subject_times", "authors",
           "author_birth", "author_death", "author_wikidata", "pages", "original_language", "cover_id",
           "isbn13", "links", "ol_ratings", "ol_rating_mean", "ol_readers", "ol_want", "revision"]


# --- finding and downloading a dump --------------------------------------------------------------

def _get(url: str, agent: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": agent}), timeout=60) as r:
        return r.read()


def latest_dump(agent: str) -> str:
    """The newest dump's date, e.g. "2026-09-30"."""
    docs = json.loads(_get(SEARCH, agent))["response"]["docs"]
    return docs[0]["identifier"].removeprefix("ol_dump_")


def file_name(date: str, kind: str) -> str:
    return f"ol_dump_{kind}_{date}.txt.gz"


def download(date: str, dest: Path, agent: str) -> None:
    """Every file we read from that dump into dest, resuming partial downloads, checked by md5."""
    dest.mkdir(parents=True, exist_ok=True)
    item = f"ol_dump_{date}"
    md5 = {f["name"]: f.get("md5") for f in json.loads(_get(METADATA.format(item), agent))["files"]}
    for kind in FILES:
        name, path = file_name(date, kind), dest / file_name(date, kind)
        if path.exists() and _md5(path) == md5.get(name):
            continue
        print(f"Downloading {name}...")
        have = path.stat().st_size if path.exists() else 0
        req = urllib.request.Request(DOWNLOAD.format(item=item, name=urllib.parse.quote(name)),
                                     headers={"User-Agent": agent, "Range": f"bytes={have}-"})
        with urllib.request.urlopen(req, timeout=60) as r, open(path, "ab" if r.status == 206 else "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        if md5.get(name) and _md5(path) != md5[name]:
            path.unlink()
            raise RuntimeError(f"{name}: checksum mismatch (deleted; run again)")


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 24):
            h.update(chunk)
    return h.hexdigest()


# --- matching and keeping a copy -----------------------------------------------------------------

def _dump(path: Path) -> str:
    """A dump file as a DuckDB table expression, read in place."""
    return (f"read_csv('{path.as_posix()}', delim='\t', quote='', escape='', header=false, "
            "columns={'type': 'VARCHAR', 'key': 'VARCHAR', 'revision': 'BIGINT', 'modified': 'VARCHAR', "
            "'json': 'VARCHAR'}, max_line_size=100000000)")


def _rows(path: Path, columns: list[str]) -> str:
    """One of the small key-per-line dumps (ratings, reading log) as a table expression."""
    spec = ", ".join(f"'{c}': 'VARCHAR'" for c in columns)
    return (f"read_csv('{path.as_posix()}', delim='\t', quote='', escape='', header=false, "
            f"columns={{{spec}}}, nullstr='\\N')")


# norm_title in SQL, for narrowing 40M works to candidates; norm_title then decides.
ROUGH_TITLE = r"""
    regexp_replace(trim(regexp_replace(regexp_replace(
        replace(replace(replace(
            regexp_replace(lower(strip_accents(coalesce({x}, ''))), '\s*[:;(\[].*$|\s+--?\s+.*$', ''),
            '&', ' and '), '''', ''), '-', ' '),
        '[^a-z0-9 ]+', '', 'g'), '\s+', ' ', 'g')), '^(the|a|an) ', '')
"""


def build(items: pd.DataFrame, dump_dir: Path, date: str, out: Path) -> dict:
    """Match `items` (id, title, creator, goodreads_id) to the dump in dump_dir; write
    openlibrary.duckdb, openlibrary.csv and openlibrary.json to `out`. Returns the summary."""
    f = {k: dump_dir / file_name(date, k) for k in FILES}
    db = out / "openlibrary.duckdb"
    tmp = out / "openlibrary.work.duckdb"  # scratch: matching tables, dropped once copied
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    rough = lambda x: ROUGH_TITLE.format(x=x)
    ours = items[["id", "title", "creator", "goodreads_id"]].astype(str).assign(
        rough=lambda d: d["title"].map(lambda t: norm_title(t)))
    con.register("ours_df", ours)
    con.execute("CREATE TABLE ours AS SELECT * FROM ours_df")

    print("Redirects...")
    con.execute(f"""CREATE TABLE redirects AS SELECT key, json_extract_string(json, '$.location') AS location
                    FROM {_dump(f['redirects'])} WHERE key LIKE '/works/%' OR key LIKE '/authors/%'""")

    print("Editions (1/2): Goodreads IDs and edition counts...")
    con.execute(f"""CREATE TABLE slim AS SELECT json_extract_string(json, '$.works[0].key') AS work,
                        CASE WHEN json LIKE '%"goodreads"%' THEN json_extract(json, '$.identifiers.goodreads') END AS gr
                    FROM {_dump(f['editions'])} WHERE type = '/type/edition'""")
    con.execute("CREATE TABLE edition_counts AS SELECT work, count(*) AS n FROM slim GROUP BY work")
    con.execute("""CREATE TABLE gr AS SELECT DISTINCT gid, work FROM (
                       SELECT work, unnest(from_json(gr, '["VARCHAR"]')) AS gid FROM slim WHERE gr IS NOT NULL)
                   WHERE gid IN (SELECT goodreads_id FROM ours)""")
    con.execute("DROP TABLE slim")
    _resolve(con, "gr", "work")
    # A Goodreads ID on editions of several works: the work with the most editions.
    con.execute("""CREATE TABLE gr_match AS SELECT o.id, arg_max(g.work, coalesce(c.n, 0)) AS work
                   FROM ours o JOIN gr g ON g.gid = o.goodreads_id LEFT JOIN edition_counts c ON c.work = g.work
                   GROUP BY o.id""")

    print("Works...")
    con.execute(f"""CREATE TABLE works_all AS SELECT key, revision, json FROM {_dump(f['works'])}
                    WHERE type = '/type/work' AND (key IN (SELECT work FROM gr_match)
                          OR {rough("json_extract_string(json, '$.title')")} IN (SELECT rough FROM ours))""")

    print("Authors...")
    con.execute("""CREATE TABLE author_keys AS SELECT DISTINCT raw, raw AS author FROM (
                       SELECT json_extract_string(a, '$.author.key') AS raw
                       FROM (SELECT unnest(from_json(json_extract(json, '$.authors'), '["JSON"]')) AS a FROM works_all))
                   WHERE raw IS NOT NULL""")
    _resolve(con, "author_keys", "author")  # kept: works name authors by their old keys
    con.execute(f"""CREATE TABLE authors AS SELECT key, revision, json FROM {_dump(f['authors'])}
                    WHERE type = '/type/author' AND key IN (SELECT author FROM author_keys)""")
    names = {k: json.loads(j).get("name", "") for k, j in con.execute("SELECT key, json FROM authors").fetchall()}
    redirect = dict(con.execute("SELECT key, location FROM redirects").fetchall())

    # Title + author for the books the Goodreads join missed; each work at most once.
    matched = dict(con.execute("SELECT id, work FROM gr_match").fetchall())
    counts = dict(con.execute("SELECT work, n FROM edition_counts WHERE work IN "
                              "(SELECT key FROM works_all)").fetchall())
    by_title: dict[str, list[tuple[str, set[str]]]] = {}
    for key, js in con.execute("SELECT key, json FROM works_all").fetchall():
        w = json.loads(js)
        people = [names.get(_follow(redirect, a), "") for a in _author_keys(w)]
        by_title.setdefault(norm_title(w.get("title", "")), []).append((key, {_person(n) for n in people}))
    taken = set(matched.values())
    method = {i: "goodreads" for i in matched}
    for _, b in ours[~ours["id"].isin(matched)].iterrows():
        want = _person(b["creator"])
        hits = [k for k, people in by_title.get(b["rough"], []) if k not in taken and any(_same(want, p) for p in people)]
        if hits:
            best = max(hits, key=lambda k: counts.get(k, 0))
            matched[b["id"]], method[b["id"]] = best, "title"
            taken.add(best)
    con.register("matches_df", pd.DataFrame({"id": list(matched), "work": list(matched.values()),
                                             "match": [method[i] for i in matched]}))
    con.execute("CREATE TABLE matches AS SELECT * FROM matches_df")
    con.execute("""CREATE TABLE works AS SELECT m.id, m.match, w.key, w.revision, w.json
                   FROM matches m JOIN works_all w ON w.key = m.work""")
    con.execute("DROP TABLE works_all")

    print("Editions (2/2): every edition of the matched works...")
    wanted = set(matched.values())
    sources = {w: w for w in wanted} | {k: t for k in redirect if k.startswith("/works/")
                                        and (t := _follow(redirect, k)) in wanted}
    con.register("work_keys_df", pd.DataFrame({"raw": list(sources), "work": list(sources.values())}))
    con.execute(f"""CREATE TABLE editions AS SELECT k.work, e.key, e.revision, e.json
                    FROM {_dump(f['editions'])} e
                    JOIN work_keys_df k ON k.raw = json_extract_string(e.json, '$.works[0].key')
                    WHERE e.type = '/type/edition'""")

    print("Series, ratings, reading log...")
    con.execute(f"""CREATE TABLE series AS SELECT key, json_extract_string(json, '$.name') AS name, json
                    FROM {_dump(f['other'])} WHERE type = '/type/series'""")
    con.execute(f"""CREATE TABLE ratings AS SELECT work, edition, CAST(rating AS INTEGER) AS rating, date
                    FROM {_rows(f['ratings'], ['work', 'edition', 'rating', 'date'])}
                    WHERE work IN (SELECT key FROM works)""")
    con.execute(f"""CREATE TABLE reading_log AS SELECT work, edition, shelf, date
                    FROM {_rows(f['reading-log'], ['work', 'edition', 'shelf', 'date'])}
                    WHERE work IN (SELECT key FROM works)""")
    # Authors of the matched works only (the candidates' authors were just for matching).
    con.execute("""DELETE FROM author_keys WHERE raw NOT IN (
                       SELECT json_extract_string(a, '$.author.key')
                       FROM (SELECT unnest(from_json(json_extract(json, '$.authors'), '["JSON"]')) AS a FROM works))""")
    con.execute("DELETE FROM authors WHERE key NOT IN (SELECT author FROM author_keys)")

    rows = project(con, int(date[:4]))
    summary = {"dump": date, "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "books": len(items), "matched": len(rows),
               "by": dict(Counter(r["match"] for r in rows)),
               "first_published": sum(bool(r["first_published"]) for r in rows)}
    con.execute("CREATE TABLE meta AS SELECT * FROM (VALUES (?, ?)) t(name, value)",
                ["summary", json.dumps(summary)])
    # Copy what we keep into a fresh file: DuckDB doesn't give back the space of dropped tables.
    final = out / "openlibrary.duckdb.new"
    final.unlink(missing_ok=True)
    con.execute(f"ATTACH '{final.as_posix()}' AS keep")
    for t in KEEP:
        con.execute(f"CREATE TABLE keep.{t} AS SELECT * FROM {t}")
    con.close()
    final.replace(db)
    tmp.unlink()
    pd.DataFrame(rows, columns=["id", *COLUMNS]).to_csv(out / "openlibrary.csv", index=False, encoding="utf-8")
    (out / "openlibrary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _person(name: str) -> tuple[str, str]:
    """(surname, first initial) of the first author, so "Sherrilyn Kenyon" and "Kenyon, James B."
    share a surname but not an initial. The initial is "" when there's only one name."""
    parts = name.split(",")
    name = f"{parts[1]} {parts[0]}" if len(parts) == 2 and " " not in parts[0].strip() else parts[0]
    words = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    words = re.sub(r"[^a-z ]+", " ", words).split()
    return norm_author(name), (words[0][0] if len(words) > 1 else "")


def _same(a: tuple[str, str], b: tuple[str, str]) -> bool:
    return a[0] == b[0] and (not a[1] or not b[1] or a[1] == b[1])


def _resolve(con, table: str, column: str) -> None:
    """Follow redirects (merged works and authors) in table.column, up to a few hops."""
    for _ in range(5):
        n = con.execute(f"""UPDATE {table} SET {column} = r.location FROM redirects r
                            WHERE r.key = {table}.{column}""").fetchone()[0]
        if not n:
            return


def _follow(redirect: dict[str, str], key: str) -> str:
    for _ in range(5):
        if key not in redirect:
            return key
        key = redirect[key]
    return key


def _author_keys(work: dict) -> list[str]:
    out = []
    for a in work.get("authors") or []:
        a = a.get("author", a) if isinstance(a, dict) else {}
        if isinstance(a, dict) and a.get("key"):
            out.append(a["key"])
    return out


# --- what the app uses ---------------------------------------------------------------------------

def project(con, dump_year: int) -> list[dict]:
    """One row per matched book: the fields openlibrary.csv carries."""
    found = {k: json.loads(j) for k, j in con.execute("SELECT key, json FROM authors").fetchall()}
    authors = {raw: found.get(a, {}) for raw, a in con.execute("SELECT raw, author FROM author_keys").fetchall()}
    series = dict(con.execute("SELECT key, name FROM series").fetchall())
    editions: dict[str, list[dict]] = {}
    for w, j in con.execute("SELECT work, json FROM editions").fetchall():
        editions.setdefault(w, []).append(json.loads(j))
    ratings = {w: (n, m) for w, n, m in con.execute(
        "SELECT work, count(*), avg(rating) FROM ratings GROUP BY work").fetchall()}
    shelves = {(w, s): n for w, s, n in con.execute(
        "SELECT work, shelf, count(*) FROM reading_log GROUP BY work, shelf").fetchall()}
    rows = []
    for id_, match, key, revision, js in con.execute("SELECT id, match, key, revision, json FROM works").fetchall():
        w, eds = json.loads(js), editions.get(key, [])
        people = [authors.get(k, {}) for k in _author_keys(w)]
        born = _year(people[0].get("birth_date")) if people else None
        s_name, s_index = _series(w, series)
        n, mean = ratings.get(key, (0, None))
        rows.append({
            "id": id_, "ol_work": key.removeprefix("/works/"), "match": match,
            "first_published": first_published(w, eds, dump_year, born) or "",
            "ol_series": s_name, "ol_series_index": s_index,
            "description": _text(w.get("description"))[:2000],
            "first_sentence": _first_sentence(w, eds),
            "subjects": _join([s for s in w.get("subjects") or [] if not s.lower().startswith("series:")]),
            "subject_places": _join(w.get("subject_places")), "subject_people": _join(w.get("subject_people")),
            "subject_times": _join(w.get("subject_times")),
            "authors": "|".join(_clean(p.get("name", "")) for p in people),
            "author_birth": "|".join(_clean(p.get("birth_date", "")) for p in people),
            "author_death": "|".join(_clean(p.get("death_date", "")) for p in people),
            "author_wikidata": (people[0].get("remote_ids") or {}).get("wikidata", "") if people else "",
            "pages": _pages(eds), "original_language": _language(eds), "cover_id": _cover(w, eds),
            "isbn13": _isbn(eds), "links": "|".join(f"{_clean(l.get('title', '')).replace('=', '-')}={l['url']}"
                                                    for l in w.get("links") or [] if l.get("url")),
            "ol_ratings": n, "ol_rating_mean": round(mean, 3) if mean else "",
            "ol_readers": shelves.get((key, "Already Read"), 0) + shelves.get((key, "Currently Reading"), 0),
            "ol_want": shelves.get((key, "Want to Read"), 0), "revision": revision,
        })
    return rows


def _year(date) -> int | None:
    years = [int(y) for y in re.findall(r"(?<!\d)(\d{4})(?!\d)", str(date or ""))]
    return min(years) if years else None


def first_published(work: dict, editions: list[dict], dump_year: int, born: int | None = None) -> int | None:
    """The earliest plausible year among the work's own date and its editions' dates: not
    before 1450 or the author's tenth birthday, not after the dump."""
    low = max(YEARS[0], born + 10 if born else 0)
    years = [_year(work.get("first_publish_date"))] + [_year(e.get("publish_date")) for e in editions]
    years = sorted(y for y in years if y and low <= y <= dump_year)
    # Typos ("1724" for a 2012 novel, sometimes on two editions, sometimes several such) sit far
    # before every later edition. The cost: a real first edition with no other for 50 years
    # goes too (Macbeth's 1606, next 1673).
    while years:
        rest = [y for y in years if y != years[0]]
        if not rest or len(years) - len(rest) > 2 or rest[0] - years[0] <= LONE:
            break
        years = rest
    return years[0] if years else None


def _series(work: dict, names: dict[str, str]) -> tuple[str, str]:
    for s in work.get("series") or []:
        key = (s.get("series") or {}).get("key", "")
        if names.get(key):
            pos = re.fullmatch(r"\d+(\.\d+)?", str(s.get("position", "")).strip())
            return names[key], pos.group(0) if pos else ""
    for s in work.get("subjects") or []:  # "series:Harry_Potter"
        if s.lower().startswith("series:"):
            return s.split(":", 1)[1].replace("_", " ").strip(), ""
    return "", ""


def _text(value) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    return str(value or "").replace("\r\n", "\n").strip()


def _clean(s: str) -> str:
    return " ".join(str(s or "").replace("|", "/").split())


def _join(values, cap: int = CAP) -> str:
    out = []
    for v in values or []:
        v = _clean(v)
        if v and v.lower() not in {o.lower() for o in out}:
            out.append(v)
    return "|".join(out[:cap])


def _first_sentence(work: dict, editions: list[dict]) -> str:
    for x in work.get("excerpts") or []:
        if "first sentence" in str(x.get("comment", "")).lower() and x.get("excerpt"):
            return _text(x["excerpt"])[:500]
    for e in editions:
        if e.get("first_sentence"):
            return _text(e["first_sentence"])[:500]
    return ""


def _pages(editions: list[dict]):
    pages = [e["number_of_pages"] for e in editions
             if isinstance(e.get("number_of_pages"), int) and 20 <= e["number_of_pages"] <= 5000]
    return int(statistics.median(pages)) if pages else ""


def _language(editions: list[dict]) -> str:
    """Translations name their source language; otherwise the editions' most common one."""
    src = Counter(l.get("key", "").removeprefix("/languages/") for e in editions for l in e.get("translated_from") or [])
    if src:
        return src.most_common(1)[0][0]
    langs = Counter(l.get("key", "").removeprefix("/languages/") for e in editions for l in e.get("languages") or [])
    return langs.most_common(1)[0][0] if langs else ""


def _by_date(editions: list[dict]) -> list[dict]:
    return sorted(editions, key=lambda e: _year(e.get("publish_date")) or 9999)


def _cover(work: dict, editions: list[dict]):
    for c in [*(work.get("covers") or []), *(c for e in _by_date(editions) for c in e.get("covers") or [])]:
        if isinstance(c, int) and c > 0:
            return c
    return ""


def _isbn(editions: list[dict]) -> str:
    for e in _by_date(editions):
        for i in e.get("isbn_13") or []:
            if re.fullmatch(r"97[89]\d{10}", str(i).replace("-", "")):
                return str(i).replace("-", "")
    return ""
