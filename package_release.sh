#!/bin/sh
set -eu

# 在当前 macOS 机器上生成可直接测试的发行目录。
# 若已运行 build_windows_python_releases.sh，会一并收录 Windows EXE。
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

VERSION=1.1.0
RELEASE="$ROOT/release"
MACHINE=$(uname -m)
case "$MACHINE" in
  x86_64) ASSET_ARCH=x64 ;;
  arm64) ASSET_ARCH=arm64 ;;
  *) echo "Unsupported architecture: $MACHINE" >&2; exit 2 ;;
esac

APP="$ROOT/dist/macos-$ASSET_ARCH/抖音指数查询工具.app"
MAC_ZIP="$RELEASE/douyin-index-tool-v${VERSION}-macos-${ASSET_ARCH}.zip"
SOURCE_ZIP="$RELEASE/douyin-index-tool-v${VERSION}-source.zip"
WIN_EXE="$ROOT/dist/douyin-index-tool-v${VERSION}-windows-x64.exe"
test -d "$APP"

mkdir -p "$RELEASE"
python3 - "$RELEASE" <<'PY'
from pathlib import Path
import shutil, sys
release = Path(sys.argv[1])
for path in release.iterdir():
    shutil.rmtree(path) if path.is_dir() else path.unlink()
PY

xattr -cr "$APP"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$MAC_ZIP"
"$ROOT/package_source_release.sh" "$SOURCE_ZIP"

NAMES="$(basename "$MAC_ZIP") $(basename "$SOURCE_ZIP")"
if [ -f "$WIN_EXE" ]; then
  cp "$WIN_EXE" "$RELEASE/$(basename "$WIN_EXE")"
  NAMES="$NAMES $(basename "$WIN_EXE")"
fi

python3 - "$RELEASE/README.md" "$VERSION" "$ASSET_ARCH" "$NAMES" <<'PY'
from pathlib import Path
import sys
target, version, architecture, raw_names = sys.argv[1:]
names = raw_names.split()
lines = [
    f"# 抖音指数查询工具 v{version}", "",
    f"- macOS {architecture}：`douyin-index-tool-v{version}-macos-{architecture}.zip`",
    f"- 源码：`douyin-index-tool-v{version}-source.zip`",
]
if f"douyin-index-tool-v{version}-windows-x64.exe" in names:
    lines.append(f"- Windows 64 位：`douyin-index-tool-v{version}-windows-x64.exe`")
else:
    lines.append("- Windows 64 位：由 GitHub Actions 或 `build_windows.ps1` 生成。")
lines += ["", "macOS 解压后右键 APP 选择“打开”。账号会话只保存在当前电脑。", ""]
Path(target).write_text("\n".join(lines), encoding="utf-8")
PY

python3 - "$RELEASE" "$VERSION" $NAMES <<'PY'
from pathlib import Path
import hashlib, sys
release, version, *names = sys.argv[1:]
root = Path(release)
lines = [f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}" for name in names]
(root / f"SHA256SUMS-v{version}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
PY

printf 'release: %s\n' "$RELEASE"
