from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


DEFAULT_PRODUCT = "buffett_lite"


class LicenseError(RuntimeError):
    pass


@dataclass
class LicenseInfo:
    license_id: str
    plan: str
    expires_at: str
    machine_code: str
    product: str


def _canonical_payload(payload: Dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def get_machine_code() -> str:
    raw = f"{platform.system()}|{platform.node()}|{uuid.getnode()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return digest[:24]


def resolve_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_public_key_path() -> Path | None:
    env_path = os.getenv("LITE_PUBLIC_KEY_PATH", "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p

    candidates = [
        resolve_project_root() / "lite_tool" / "public_key.pem",
        Path(__file__).resolve().with_name("public_key.pem"),
    ]

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        candidates.extend(
            [
                base / "lite_tool" / "public_key.pem",
                base / "public_key.pem",
            ]
        )

    for p in candidates:
        if p.exists():
            return p
    return None


def resolve_license_path() -> Path | None:
    env_path = os.getenv("LITE_LICENSE_PATH", "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p

    candidates = [
        Path.cwd() / "license.key",
        Path.home() / ".factor_lab_lite" / "license.key",
    ]

    exe_parent = Path(sys.executable).resolve().parent
    candidates.append(exe_parent / "license.key")

    for p in candidates:
        if p.exists():
            return p
    return None


def load_public_key(path: Path) -> Ed25519PublicKey:
    pem = path.read_bytes()
    pub = serialization.load_pem_public_key(pem)
    if not isinstance(pub, Ed25519PublicKey):
        raise LicenseError("public_key.pem 不是 Ed25519 公钥。")
    return pub


def verify_license_content(
    payload: Dict[str, object],
    signature_b64: str,
    public_key: Ed25519PublicKey,
    machine_code: str,
    expected_product: str = DEFAULT_PRODUCT,
) -> LicenseInfo:
    product = str(payload.get("product", "")).strip()
    if product != expected_product:
        raise LicenseError(f"授权产品不匹配：{product}")

    expires_at = str(payload.get("expires_at", "")).strip()
    if not expires_at:
        raise LicenseError("授权缺少 expires_at。")
    if date.fromisoformat(expires_at) < date.today():
        raise LicenseError(f"授权已过期：{expires_at}")

    licensed_machine = str(payload.get("machine_code", "")).strip().upper()
    if licensed_machine and licensed_machine != machine_code.upper():
        raise LicenseError("授权机器码不匹配。")

    signature = base64.urlsafe_b64decode(signature_b64.encode("utf-8"))
    message = _canonical_payload(payload)
    try:
        public_key.verify(signature, message)
    except InvalidSignature as exc:
        raise LicenseError("授权签名校验失败。") from exc

    return LicenseInfo(
        license_id=str(payload.get("license_id", "UNKNOWN")),
        plan=str(payload.get("plan", "lite")),
        expires_at=expires_at,
        machine_code=licensed_machine or machine_code.upper(),
        product=product,
    )


def verify_license_file(
    license_path: Path,
    public_key_path: Path,
    machine_code: str | None = None,
) -> LicenseInfo:
    machine = (machine_code or get_machine_code()).upper()
    try:
        raw = json.loads(license_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LicenseError("license.key 不是合法JSON。") from exc

    payload = raw.get("payload")
    signature = raw.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, str):
        raise LicenseError("license.key 缺少 payload/signature。")

    public_key = load_public_key(public_key_path)
    return verify_license_content(payload, signature, public_key, machine)


def load_private_key(path: Path) -> Ed25519PrivateKey:
    pem = path.read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise LicenseError("私钥不是 Ed25519。")
    return key


def sign_payload(payload: Dict[str, object], private_key_path: Path) -> Tuple[Dict[str, object], str]:
    key = load_private_key(private_key_path)
    message = _canonical_payload(payload)
    signature = key.sign(message)
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8")
    return payload, signature_b64

