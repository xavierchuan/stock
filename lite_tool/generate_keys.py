from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Ed25519 keypair for Lite licensing.")
    p.add_argument(
        "--out-dir",
        default=str(Path.home() / ".factor_lab_keys"),
        help="Output directory for private/public keys.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = out_dir / "private_key.pem"
    public_path = out_dir / "public_key.pem"
    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes)

    print(f"Private key: {private_path}")
    print(f"Public key:  {public_path}")
    print("请妥善保存 private_key.pem，不要上传到 GitHub。")


if __name__ == "__main__":
    main()

