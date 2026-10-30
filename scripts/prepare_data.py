"""One-off data prep: download a domain's source dataset and compact it into data/<domain>/.

    python scripts/prepare_data.py film
    python scripts/prepare_data.py book

Source URLs are not kept in the repo: set TASTE_<DOMAIN>_URL in .env (see .env.example)
or the environment, or pass --url.
"""

import argparse
import os
import shutil

from sources import books, films
from sources.common import RAW, Source

from taste.env import load_env

ADAPTERS = {"film": films, "book": books}


def main() -> None:
    load_env()
    p = argparse.ArgumentParser()
    p.add_argument("domain", choices=ADAPTERS)
    p.add_argument("--url", help="source dataset zip (default: TASTE_<DOMAIN>_URL)")
    p.add_argument("--keep-raw", action="store_true", help="keep the downloaded zip")
    args = p.parse_args()
    adapter = ADAPTERS[args.domain]
    url = args.url or os.environ.get(adapter.URL_ENV)
    if not url:
        p.error(f"set {adapter.URL_ENV} in .env or pass --url")
    src = Source(url, args.domain)
    adapter.build(src)
    src.zip.close()
    if not args.keep_raw:
        shutil.rmtree(RAW / args.domain)


if __name__ == "__main__":
    main()
