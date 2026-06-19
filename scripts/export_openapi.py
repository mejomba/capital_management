"""Export the FastAPI-generated OpenAPI spec to ./openapi.json (repo root).

Usage: python scripts/export_openapi.py
"""

import json
from pathlib import Path

from app.main import app


def main() -> None:
    spec = app.openapi()
    out = Path(__file__).resolve().parents[1] / "openapi.json"
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
