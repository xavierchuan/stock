from __future__ import annotations

import os
import sys
from pathlib import Path

from streamlit.web import bootstrap


def _resolve_app_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        return base / "lite_tool" / "app.py"
    return Path(__file__).resolve().with_name("app.py")


def main() -> None:
    os.environ.setdefault("LITE_REQUIRE_LICENSE", "1")
    app_path = _resolve_app_path()
    if not app_path.exists():
        raise FileNotFoundError(f"未找到 app.py: {app_path}")

    sys.argv = [
        str(app_path),
        "--server.port",
        "8510",
        "--client.toolbarMode",
        "minimal",
        "--browser.gatherUsageStats",
        "false",
    ]
    bootstrap.run(str(app_path), "", [], {})


if __name__ == "__main__":
    main()
