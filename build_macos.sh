#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

VERSION=1.1.0
TARGET_ARCH=${TARGET_ARCH:-$(uname -m)}

case "$TARGET_ARCH" in
  x64|x86_64|amd64)
    ASSET_ARCH=x64
    PYI_ARCH=x86_64
    PYTHON_BIN=${PYTHON_BIN:-python3}
    ;;
  arm64|aarch64)
    ASSET_ARCH=arm64
    PYI_ARCH=arm64
    if [ "$(uname -m)" = "x86_64" ] && [ -x /usr/bin/python3 ]; then
      PYTHON_BIN=${PYTHON_BIN:-/usr/bin/python3}
    else
      PYTHON_BIN=${PYTHON_BIN:-python3}
    fi
    ;;
  *)
    echo "Unsupported macOS architecture: $TARGET_ARCH" >&2
    exit 2
    ;;
esac

VENV="$ROOT/.macos-$ASSET_ARCH-venv"
DIST="$ROOT/dist/macos-$ASSET_ARCH"
WORK="$ROOT/build/macos-$ASSET_ARCH"
SPECS="$ROOT/build/spec-$ASSET_ARCH"

if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$ROOT/requirements-webview.txt"

# Intel Mac 使用 CommandLineTools 的 universal2 Python 交叉构建 arm64 时，
# pip 默认会选择 x86_64 cffi wheel。将 cffi 从源码重建为 universal2。
if [ "$(uname -m)" = "x86_64" ] && [ "$PYI_ARCH" = "arm64" ]; then
  CFFI_BINARY=$(find "$VENV/lib" -name '_cffi_backend*.so' -print -quit)
  if [ -n "$CFFI_BINARY" ] && ! lipo -archs "$CFFI_BINARY" | grep -q arm64; then
    CFFI_VERSION=$("$VENV/bin/python" -c 'import cffi; print(cffi.__version__)')
    ARCHFLAGS='-arch x86_64 -arch arm64' "$VENV/bin/python" -m pip install \
      --force-reinstall --no-binary=cffi "cffi==$CFFI_VERSION"
  fi
fi

"$VENV/bin/python" -m PyInstaller --noconfirm --clean --windowed \
  --target-arch "$PYI_ARCH" \
  --name "抖音指数查询工具" \
  --distpath "$DIST" \
  --workpath "$WORK" \
  --specpath "$SPECS" \
  --paths "$ROOT/src" \
  --hidden-import webview.platforms.cocoa \
  --icon "$ROOT/assets/douyin-index-icon.icns" \
  --add-data "$ROOT/src/douyin_index_tool/webview_ui:douyin_index_tool/webview_ui" \
  --exclude-module cefpython3 \
  "$ROOT/run_webview_gui.py"

APP="$DIST/抖音指数查询工具.app"
EXECUTABLE="$APP/Contents/MacOS/抖音指数查询工具"
test -x "$EXECUTABLE"

/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.crossplatformtools.douyinindex" "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$APP/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$APP/Contents/Info.plist"

xattr -cr "$APP"
codesign --force --deep --sign - "$APP"
plutil -lint "$APP/Contents/Info.plist"
codesign --verify --deep --strict "$APP"

ACTUAL_ARCHS=$(lipo -archs "$EXECUTABLE")
[ "$ACTUAL_ARCHS" = "$PYI_ARCH" ] || {
  echo "Unexpected architecture: $ACTUAL_ARCHS (expected $PYI_ARCH)" >&2
  exit 3
}

if [ "${SKIP_SMOKE_TEST:-0}" != "1" ] && [ "$(uname -m)" = "$PYI_ARCH" ]; then
  UI_RESULT="${TMPDIR:-/tmp}/douyin-index-ui-$ASSET_ARCH.json"
  "$EXECUTABLE" --demo --ui-self-test-output "$UI_RESULT"
  "$VENV/bin/python" - "$UI_RESULT" <<'PY'
import json, pathlib, sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert value["allPass"], value
print("macOS GUI self-test: %d/%d" % (sum(value["checks"].values()), len(value["checks"])))
PY
elif [ "${SKIP_SMOKE_TEST:-0}" != "1" ]; then
  printf 'GUI self-test deferred to native %s runner.\n' "$PYI_ARCH"
fi

printf 'macOS %s application: %s\n' "$ASSET_ARCH" "$APP"
