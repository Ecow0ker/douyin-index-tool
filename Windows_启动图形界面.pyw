import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

from douyin_index_tool.webview_gui import main

raise SystemExit(main())
