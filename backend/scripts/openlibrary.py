"""Refresh the books' Open Library metadata from the newest monthly dump (see sources/openlibrary.py).

    python scripts/openlibrary.py              # does nothing if already on the newest dump
    python scripts/openlibrary.py --force      # rebuild anyway
    python scripts/openlibrary.py --dump 2026-09-30 --keep-raw

Safe to schedule weekly: it only downloads (about 18 GB) when a new dump is out. Restart the
API afterwards to pick up the new data/book/openlibrary.csv.
"""

import argparse
import json
import shutil

from sources.common import DATA, RAW
from sources.openlibrary import build, download, latest_dump

from taste.model.catalog import read_items
from taste.settings import get_settings


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dump", help="a dump date, e.g. 2026-09-30 (default: the newest)")
    p.add_argument("--force", action="store_true", help="rebuild even if already on that dump")
    p.add_argument("--keep-raw", action="store_true", help="keep the downloaded dump files")
    args = p.parse_args()

    contact = get_settings().openlibrary_contact
    agent = f"Taste/0.2 ({contact})" if contact else "Taste/0.2"
    out = DATA / "book"
    date = args.dump or latest_dump(agent)
    summary = out / "openlibrary.json"
    if summary.exists() and json.loads(summary.read_text(encoding="utf-8"))["dump"] == date and not args.force:
        print(f"Up to date (Open Library dump {date}).")
        return

    raw = RAW / "openlibrary" / date
    download(date, raw, agent)
    items = read_items(out)[["id", "title", "creator", "goodreads_id"]]
    s = build(items, raw, date, out)
    print(f"Matched {s['matched']} of {s['books']} books to Open Library ({s['by']}); "
          f"{s['first_published']} with a first-publication year. Dump {date}.")
    if not args.keep_raw:
        shutil.rmtree(raw)


if __name__ == "__main__":
    main()
