#!/usr/bin/env python3
"""Render QR-code images to terminal-friendly blocks."""

from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image


def _decode_bytes(image_data: bytes | str) -> bytes:
    if isinstance(image_data, bytes):
        return image_data
    payload = image_data.split(",", 1)[1] if "," in image_data else image_data
    return base64.b64decode(payload)


def render_terminal_qr(image_data: bytes | str, title: str) -> None:
    image = Image.open(BytesIO(_decode_bytes(image_data))).convert("L")
    width = 48
    height = max(1, round(image.height * (width / image.width)))
    image = image.resize((width, height))
    print(f"\n{title}\n", flush=True)
    for y in range(image.height):
        line = []
        for x in range(image.width):
            line.append("██" if image.getpixel((x, y)) < 180 else "  ")
        print("".join(line), flush=True)
    print("", flush=True)
