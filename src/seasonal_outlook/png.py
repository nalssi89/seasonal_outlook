from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
    length = struct.pack(">I", len(payload))
    crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return length + chunk_type + payload + struct.pack(">I", crc)


def write_png(path: Path, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    if len(pixels) != width * height:
        raise ValueError("pixel count does not match width*height")

    raw_rows = []
    for row in range(height):
        start = row * width
        end = start + width
        row_bytes = bytearray([0])
        for red, green, blue in pixels[start:end]:
            row_bytes.extend((red, green, blue))
        raw_rows.append(bytes(row_bytes))

    payload = zlib.compress(b"".join(raw_rows), level=9)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png_bytes = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", header),
            _chunk(b"IDAT", payload),
            _chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes)

