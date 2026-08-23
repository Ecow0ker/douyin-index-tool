from __future__ import annotations

import base64
import json
from typing import Any

# 当前 count-fe 前端 x-encrypted 版本 1/2 的 AES-CBC 参数。
_MODES = {
    "1": (
        bytes.fromhex("91b4a33aa9fd3bb00f2ea519c5d0a44d"),
        bytes.fromhex("26e84bd5c395e491fda23cedda0d843e"),
    ),
    "2": (
        bytes.fromhex("4a35db61325bef35e8513a1289c50bdc"),
        bytes.fromhex("39e90c2e3821460f2f957fcf7a62dcf9"),
    ),
}


def decrypt_response(value: str, mode: str) -> Any:
    """Decode the creator-count x-encrypted response used by the web client."""
    try:
        key, iv = _MODES[str(mode)]
    except KeyError as exc:
        raise ValueError("暂不支持的 x-encrypted 版本：%s" % mode) from exc
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        encrypted = base64.b64decode(value, validate=True)
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(encrypted) + decryptor.finalize()
        padding = padded[-1]
        if not 1 <= padding <= 16 or padded[-padding:] != bytes([padding]) * padding:
            raise ValueError("PKCS#7 padding 无效")
        return json.loads(padded[:-padding].decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("抖音指数加密响应解码失败") from exc
