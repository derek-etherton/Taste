"""Write the API's OpenAPI spec, which the frontend generates its TypeScript types from.

    python scripts/export_openapi.py            # -> ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from fastapi.openapi.utils import get_openapi

from taste.api import auth
from taste.api.routes import router
from taste.settings import ROOT


def main(out: Path) -> None:
    # Built from the routes alone, so no catalogues need loading.
    spec = get_openapi(title="Taste", version="0.2.0", routes=auth.router.routes + router.routes)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(spec['paths'])} paths to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "frontend" / "openapi.json")
