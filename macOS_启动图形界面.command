#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [ ! -x .webviewvenv/bin/python ]; then
  python3 -m venv .webviewvenv
  .webviewvenv/bin/python -m pip install -r requirements-webview.txt
fi
PYTHONPATH=src exec .webviewvenv/bin/python run_webview_gui.py
