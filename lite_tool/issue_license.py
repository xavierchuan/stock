from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lite_tool.licensing import DEFAULT_PRODUCT, sign_payload


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue signed license.key for Lite executable.")
    p.add_argument("--private-key", required=True, help="Path to private_key.pem")
    p.add_argument("--license-id", required=True, help="License id, e.g. T20260212-001")
    p.add_argument("--days", type=int, default=30, help="Valid days from today")
    p.add_argument(
        "--machine-code",
        default="",
        help="Optional machine code bind. Empty means not machine-bound.",
    )
    p.add_argument("--plan", default="lite", help="Plan name")
    p.add_argument("--product", default=DEFAULT_PRODUCT, help="Product code")
    p.add_argument("--out", default="license.key", help="Output license file path")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    issued_at = date.today()
    expires_at = issued_at + timedelta(days=max(1, args.days))

    payload = {
        "product": args.product,
        "license_id": args.license_id,
        "plan": args.plan,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "machine_code": args.machine_code.strip().upper(),
    }

    payload, signature = sign_payload(payload, Path(args.private_key).expanduser().resolve())
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"payload": payload, "signature": signature}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"License created: {out_path}")
    print(f"Expires at: {payload['expires_at']}")


if __name__ == "__main__":
    main()
