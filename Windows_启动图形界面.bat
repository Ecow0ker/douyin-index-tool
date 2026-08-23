@echo off
setlocal
cd /d "%~dp0"
if not exist ".webviewvenv\Scripts\pythonw.exe" (
  py -3.12 -m venv .webviewvenv
  .webviewvenv\Scripts\python.exe -m pip install -r requirements-webview.txt
)
set PYTHONPATH=%CD%\src
start "" .webviewvenv\Scripts\pythonw.exe Windows_启动图形界面.pyw
