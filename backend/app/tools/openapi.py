from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

os.environ.setdefault("APP_NAME", "OT-SOC Fusion X")
os.environ.setdefault("APP_VERSION", "1.1.1")
os.environ.setdefault("APP_ENV", "contract")
os.environ.setdefault("API_VERSION", "v1")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:5173"]')
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://contract:contract@127.0.0.1:5432/contract"
)
# Contract rendering never authenticates or serves traffic. Use a fresh process-only value so
# deterministic schema generation does not require or commit a working runtime secret.
os.environ.setdefault("AUTH_SESSION_SECRET", secrets.token_urlsafe(48))

from app.main import create_app

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "contracts" / "openapi.json"


def rendered_contract() -> str:
    schema = create_app().openapi()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate the OpenAPI contract")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = rendered_contract()
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != expected:
            raise SystemExit("OpenAPI contract is stale. Run: python -m app.tools.openapi")
        print(f"OpenAPI contract is current: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote OpenAPI contract: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
