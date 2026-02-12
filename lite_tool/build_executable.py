from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LITE_DIR = PROJECT_ROOT / "lite_tool"
DIST_DIR = PROJECT_ROOT / "lite_tool" / "dist_exec"
BUILD_DIR = PROJECT_ROOT / "lite_tool" / "build_exec"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build executable for Lite tool with license enforcement.")
    p.add_argument("--name", default="BuffettLite", help="Executable name")
    p.add_argument(
        "--clean",
        action="store_true",
        help="Clean previous build dirs before build",
    )
    return p.parse_args()


def _data_sep() -> str:
    return ";" if os.name == "nt" else ":"


def _require_public_key() -> Path:
    key_path = LITE_DIR / "public_key.pem"
    if not key_path.exists():
        raise FileNotFoundError(
            f"缺少公钥文件: {key_path}\n"
            "请先执行 generate_keys.py 生成密钥，并把 public_key.pem 复制到 lite_tool/public_key.pem"
        )
    return key_path


def main() -> None:
    args = parse_args()
    key_path = _require_public_key()

    if args.clean:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    add_data = f"{key_path}{_data_sep()}lite_tool"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name",
        args.name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(BUILD_DIR),
        "--collect-all",
        "streamlit",
        "--add-data",
        add_data,
        str(LITE_DIR / "desktop_entry.py"),
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"Build done: {DIST_DIR / args.name}")


if __name__ == "__main__":
    main()

