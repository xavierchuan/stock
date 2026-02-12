#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3，请先安装 Python 3.10+ 后重试。"
  read -r -p "按回车键退出..."
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -c "import akshare,streamlit,pandas,numpy" >/dev/null 2>&1; then
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
fi

echo "正在启动巴菲特战法 Lite 体验版..."
"$VENV_DIR/bin/python" -m streamlit run "$PROJECT_ROOT/lite_tool/app.py" --server.port 8510 --client.toolbarMode minimal --browser.gatherUsageStats false
