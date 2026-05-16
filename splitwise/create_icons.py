#!/usr/bin/env python3
"""
create_icons.py — Generate PNG icons for FairSplit Local without PIL.

Uses only Python stdlib (struct + zlib) to build valid PNG files.
Color: #1CC29F (the FairSplit green accent)
Sizes: 16x16, 48x48, 128x128

Run: python3 create_icons.py
"""

import struct
import zlib
import os

# FairSplit accent green: #1CC29F
ACCENT_R, ACCENT_G, ACCENT_B = 0x1C, 0xC2, 0x9F
# Darker shade for the rupee symbol area
DARK_R, DARK_G, DARK_B = 0x17, 0xA5, 0x89


def make_png(width: int, height: int) -> bytes:
    """
    Build a valid PNG from scratch.
    Draws a rounded-ish square with the accent green background
    and a simple white ₹ symbol approximation using pixel art.
    """

    # ── helpers ──────────────────────────────────────────────────────
    def rgba(r, g, b, a=255):
        return bytes([r, g, b, a])

    WHITE  = rgba(255, 255, 255)
    GREEN  = rgba(ACCENT_R, ACCENT_G, ACCENT_B)
    TRANSP = rgba(0, 0, 0, 0)

    # Build pixel grid: list of rows, each row is a list of 4-byte pixels
    pixels = [[GREEN] * width for _ in range(height)]

    # ── rounded corners (simple circle-based mask) ────────────────────
    radius = max(2, width // 6)
    for y in range(height):
        for x in range(width):
            # Check four corner regions
            corners = [
                (x < radius and y < radius, radius - 0.5, radius - 0.5),
                (x >= width - radius and y < radius, width - radius - 0.5, radius - 0.5),
                (x < radius and y >= height - radius, radius - 0.5, height - radius - 0.5),
                (x >= width - radius and y >= height - radius, width - radius - 0.5, height - radius - 0.5),
            ]
            for in_corner, cx, cy in corners:
                if in_corner:
                    dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                    if dist > radius:
                        pixels[y][x] = TRANSP

    # ── draw a simple ₹ / coin symbol in white ────────────────────────
    # Scale drawing coordinates to icon size
    def draw_pixel(px, py):
        """Draw a white pixel at logical coords (0-15 scale)."""
        sx = max(0, min(width - 1, int(px * width / 16)))
        sy = max(0, min(height - 1, int(py * height / 16)))
        if pixels[sy][sx] != TRANSP:
            pixels[sy][sx] = WHITE

    def draw_rect(lx, ly, lw, lh):
        """Draw a filled rectangle in logical coords."""
        for ry in range(lh):
            for rx in range(lw):
                draw_pixel(lx + rx, ly + ry)

    def draw_line_h(lx, ly, lw):
        draw_rect(lx, ly, lw, 1)

    def draw_line_v(lx, ly, lh):
        draw_rect(lx, ly, 1, lh)

    # Simple ₹ symbol in a 16×16 logical grid
    # Vertical bar
    draw_line_v(5, 3, 10)
    # Two horizontal bars at top
    draw_line_h(5, 3, 6)
    draw_line_h(5, 5, 6)
    # Small serifs / top cap
    draw_line_h(4, 3, 1)
    draw_line_h(4, 5, 1)
    # Diagonal stroke (₹ slash)
    for i in range(7):
        px = 5 + i
        py = 7 + i
        draw_pixel(px, py)
        draw_pixel(px + 1, py)

    # ── build raw image data (filter byte 0 = None per row) ──────────
    raw = b''
    for row in pixels:
        raw += b'\x00'  # filter type None
        for p in row:
            raw += p

    # ── assemble PNG chunks ───────────────────────────────────────────
    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    PNG_MAGIC = b'\x89PNG\r\n\x1a\n'

    # IHDR: width, height, bit_depth=8, color_type=6 (RGBA), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    idat_data = zlib.compress(raw, 9)

    return PNG_MAGIC + chunk(b'IHDR', ihdr_data) + chunk(b'IDAT', idat_data) + chunk(b'IEND', b'')


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(script_dir, 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    sizes = [16, 48, 128]
    for size in sizes:
        png_data = make_png(size, size)
        path = os.path.join(icons_dir, f'icon{size}.png')
        with open(path, 'wb') as f:
            f.write(png_data)
        print(f'Created: {path} ({size}x{size}, {len(png_data)} bytes)')

    print('\nAll icons created successfully!')
    print('Load the extension in Chrome: chrome://extensions/ → Load unpacked → select the splitwise/ folder')


if __name__ == '__main__':
    main()
