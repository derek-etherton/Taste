"""Run Shelf scan on photos from the command line: what was read, matched and missed, and how long it took.

    python scripts/scan_photo.py samples/*.jpg
"""

import sys
import time
from pathlib import Path

from taste.model import Catalog
from taste.model.shelf import match_spines, read_spines


def main(paths: list[str]) -> None:
    cat = Catalog.load("book")
    for path in paths:
        start = time.perf_counter()
        spines = read_spines(Path(path).read_bytes())
        read_s = time.perf_counter() - start
        matches = match_spines(spines, cat)
        found = sum(m.row is not None for m in matches)
        print(f"\n== {path}: read {len(spines)} spines in {read_s:.0f}s, matched {found}")
        for m in matches:
            read = m.spine.title + (f" / {m.spine.author}" if m.spine.author else "")
            hit = f"{cat.label(m.row)} · {cat.creator(m.row)} ({m.confidence:.0f})" if m.row is not None else "-"
            print(f"  {read[:55]:55s} -> {hit}")


if __name__ == "__main__":
    main(sys.argv[1:])
