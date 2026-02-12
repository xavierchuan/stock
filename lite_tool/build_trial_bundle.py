from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LITE_DIR = PROJECT_ROOT / "lite_tool"
DIST_DIR = LITE_DIR / "dist"
STAGING_DIR = DIST_DIR / "staging"


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build_bundle() -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d")
    bundle_name = f"buffett_lite_trial_{timestamp}"
    bundle_dir = STAGING_DIR / bundle_name

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        PROJECT_ROOT / "requirements.txt",
        LITE_DIR / "app.py",
        LITE_DIR / "akshare_provider.py",
        LITE_DIR / "config.py",
        LITE_DIR / "limits.py",
        LITE_DIR / "scoring.py",
        LITE_DIR / "__init__.py",
        LITE_DIR / "README.md",
        LITE_DIR / "launcher" / "start_lite.command",
        LITE_DIR / "launcher" / "start_lite.bat",
        LITE_DIR / "launcher" / "README_TRIAL.md",
    ]

    for src in files_to_copy:
        rel = src.relative_to(PROJECT_ROOT)
        copy_file(src, bundle_dir / rel)

    zip_path = DIST_DIR / f"{bundle_name}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    shutil.make_archive(str(zip_path.with_suffix("")), "zip", bundle_dir)
    return zip_path


def main() -> None:
    zip_path = build_bundle()
    print(f"Bundle created: {zip_path}")


if __name__ == "__main__":
    main()
