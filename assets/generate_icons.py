"""生成项目使用的 PNG、ICO 和 macOS ICNS 图标，仅依赖 Python 标准库。"""
from __future__ import annotations

import binascii
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

SIZE = 1024
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
UI_ICON = ROOT / "src" / "douyin_index_tool" / "webview_ui" / "app-icon.png"


def inside_round_rect(x: int, y: int, left: int, top: int, right: int, bottom: int, radius: int) -> bool:
    cx = min(max(x, left + radius), right - radius)
    cy = min(max(y, top + radius), bottom - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2


def blend(canvas: bytearray, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if not (0 <= x < SIZE and 0 <= y < SIZE):
        return
    i = (y * SIZE + x) * 4
    alpha = color[3] / 255
    inverse = 1 - alpha
    canvas[i] = round(color[0] * alpha + canvas[i] * inverse)
    canvas[i + 1] = round(color[1] * alpha + canvas[i + 1] * inverse)
    canvas[i + 2] = round(color[2] * alpha + canvas[i + 2] * inverse)
    canvas[i + 3] = round(255 * (alpha + canvas[i + 3] / 255 * inverse))


def rounded_rect(canvas: bytearray, box: tuple[int, int, int, int], radius: int, color: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    for y in range(max(0, top), min(SIZE, bottom)):
        for x in range(max(0, left), min(SIZE, right)):
            if inside_round_rect(x, y, left, top, right - 1, bottom - 1, radius):
                blend(canvas, x, y, color)


def make_canvas() -> bytearray:
    canvas = bytearray(SIZE * SIZE * 4)
    for y in range(54, 970):
        shade = round(27 - 11 * (y - 54) / 916)
        for x in range(54, 970):
            if inside_round_rect(x, y, 54, 54, 969, 969, 214):
                i = (y * SIZE + x) * 4
                canvas[i:i + 4] = bytes((shade + 3, shade + 3, shade + 7, 255))

    # 红青错位的指数柱，中间白色柱表示实际数据。
    bars = [(246, 550, 366, 790), (452, 408, 572, 790), (658, 246, 778, 790)]
    for offset, color in ((-28, (37, 244, 238, 235)), (28, (254, 44, 85, 235))):
        for left, top, right, bottom in bars:
            rounded_rect(canvas, (left + offset, top, right + offset, bottom), 55, color)
    for left, top, right, bottom in bars:
        rounded_rect(canvas, (left, top, right, bottom), 52, (247, 248, 251, 255))

    # 底部基线与轻微高光。
    rounded_rect(canvas, (206, 780, 818, 822), 21, (247, 248, 251, 255))
    rounded_rect(canvas, (112, 100, 912, 124), 12, (255, 255, 255, 22))
    return canvas


def png_bytes(canvas: bytearray, width: int = SIZE, height: int = SIZE) -> bytes:
    rows = b"".join(b"\x00" + bytes(canvas[y * width * 4:(y + 1) * width * 4]) for y in range(height))

    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", binascii.crc32(name + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")


def write_icons() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    UI_ICON.parent.mkdir(parents=True, exist_ok=True)
    canvas = make_canvas()
    data = png_bytes(canvas)
    png = ASSETS / "douyin-index-icon.png"
    png.write_bytes(data)
    UI_ICON.write_bytes(data)

    ico_canvas = bytearray()
    for y in range(256):
        for x in range(256):
            offset = ((y * 4) * SIZE + x * 4) * 4
            ico_canvas.extend(canvas[offset:offset + 4])
    ico_data = png_bytes(ico_canvas, 256, 256)
    ico = ASSETS / "douyin-index-icon.ico"
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(ico_data), 22)
    ico.write_bytes(header + entry + ico_data)

    if shutil.which("iconutil") and shutil.which("sips"):
        with tempfile.TemporaryDirectory() as folder:
            iconset = Path(folder) / "douyin-index-icon.iconset"
            iconset.mkdir()
            sizes = {
                "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
                "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
                "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
                "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
                "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
            }
            for name, size in sizes.items():
                subprocess.run(["sips", "-z", str(size), str(size), str(png), "--out", str(iconset / name)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "douyin-index-icon.icns")], check=True)


if __name__ == "__main__":
    write_icons()
