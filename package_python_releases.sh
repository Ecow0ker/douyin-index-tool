#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RELEASE="$ROOT/release"
VERSION=1.1.0

MAC_X64_APP="$ROOT/dist/macos-x64/抖音指数查询工具.app"
MAC_ARM64_APP="$ROOT/dist/macos-arm64/抖音指数查询工具.app"
WIN_EXE="$ROOT/dist/douyin-index-tool-v${VERSION}-windows-x64.exe"
MAC_X64_ZIP="$RELEASE/douyin-index-tool-v${VERSION}-macos-x64.zip"
MAC_ARM64_ZIP="$RELEASE/douyin-index-tool-v${VERSION}-macos-arm64.zip"
WIN_RELEASE="$RELEASE/$(basename "$WIN_EXE")"
SOURCE_ZIP="$RELEASE/douyin-index-tool-v${VERSION}-source.zip"

mkdir -p "$RELEASE"
for path in "$MAC_X64_APP" "$MAC_ARM64_APP" "$WIN_EXE"; do
  test -e "$path"
done

for app in "$MAC_X64_APP" "$MAC_ARM64_APP"; do
  xattr -cr "$app"
  codesign --force --deep --sign - "$app"
  codesign --verify --deep --strict "$app"
done
[ "$(lipo -archs "$MAC_X64_APP/Contents/MacOS/抖音指数查询工具")" = "x86_64" ]
[ "$(lipo -archs "$MAC_ARM64_APP/Contents/MacOS/抖音指数查询工具")" = "arm64" ]

python3 - "$RELEASE" <<'PY'
from pathlib import Path
import shutil, sys
release = Path(sys.argv[1])
for path in release.iterdir():
    shutil.rmtree(path) if path.is_dir() else path.unlink()
PY

ditto -c -k --sequesterRsrc --keepParent "$MAC_X64_APP" "$MAC_X64_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$MAC_ARM64_APP" "$MAC_ARM64_ZIP"
cp "$WIN_EXE" "$WIN_RELEASE"

"$ROOT/package_source_release.sh" "$SOURCE_ZIP"

cat > "$RELEASE/README.md" <<'EOF'
# 抖音指数查询工具 v1.1.0

- macOS Intel：下载 `douyin-index-tool-v1.1.0-macos-x64.zip`。
- macOS M 系列：下载 `douyin-index-tool-v1.1.0-macos-arm64.zip`。
- Windows 64 位：下载 `douyin-index-tool-v1.1.0-windows-x64.exe`。
- 源码：下载 `douyin-index-tool-v1.1.0-source.zip`。

macOS 首次启动可右键 APP 选择“打开”。账号会话只保存在当前电脑。
EOF

python3 - "$RELEASE" "$VERSION" \
  "$(basename "$MAC_X64_ZIP")" "$(basename "$MAC_ARM64_ZIP")" \
  "$(basename "$WIN_RELEASE")" "$(basename "$SOURCE_ZIP")" <<'PY'
from pathlib import Path
import hashlib, sys
release, version, *names = sys.argv[1:]
root = Path(release)
lines = [f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}" for name in names]
(root / f"SHA256SUMS-v{version}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
PY

printf 'release: %s\n' "$RELEASE"
