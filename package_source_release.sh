#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET=${1:-"$ROOT/release/douyin-index-tool-v1.1.0-source.zip"}
VERSION=1.1.0
mkdir -p "$(dirname "$TARGET")"

python3 - "$ROOT" "$TARGET" "$VERSION" <<'PY'
from pathlib import Path
import sys, zipfile

root, target, version = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
top_files = [
    ".gitattributes", ".gitignore", "AGENTS.md", "CHANGELOG.md", "Linux_命令行.sh", "README.md",
    "Windows_启动图形界面.bat", "Windows_启动图形界面.pyw",
    "build_macos.sh", "build_windows.ps1", "build_windows_python_releases.sh",
    "macOS_启动图形界面.command", "package_python_releases.sh",
    "package_release.sh", "package_source_release.sh", "pyproject.toml",
    "requirements-webview.txt", "run_webview_gui.py",
]
paths = [root / value for value in top_files]
for directory in (".github", "assets", "src", "tests", "windows_python_launcher"):
    paths.extend(path for path in (root / directory).rglob("*") if path.is_file())

def wanted(path: Path) -> bool:
    return (
        path.is_file()
        and path.name != ".DS_Store"
        and path.suffix not in {".pyc", ".pyo"}
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
    )

paths = sorted({path for path in paths if wanted(path)}, key=lambda path: path.relative_to(root).as_posix())
prefix = f"douyin-index-tool-v{version}"
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in paths:
        archive.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
print(f"source_files={len(paths)}")
print(f"source_zip_bytes={target.stat().st_size}")
PY
