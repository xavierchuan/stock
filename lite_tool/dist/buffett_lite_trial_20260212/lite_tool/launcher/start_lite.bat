@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%\..\.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "VENV_DIR=%PROJECT_ROOT%\.venv"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.10+。
    pause
    exit /b 1
  )
  set "PY_CMD=python"
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  %PY_CMD% -m venv "%VENV_DIR%"
)

"%VENV_DIR%\Scripts\python.exe" -c "import akshare,streamlit,pandas,numpy" >nul 2>nul
if errorlevel 1 (
  "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
  "%VENV_DIR%\Scripts\pip.exe" install -r "%PROJECT_ROOT%\requirements.txt"
)

echo 正在启动巴菲特战法 Lite 体验版...
"%VENV_DIR%\Scripts\python.exe" -m streamlit run "%PROJECT_ROOT%\lite_tool\app.py" --server.port 8510

endlocal
