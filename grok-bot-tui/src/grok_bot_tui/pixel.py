"""Hash or bitmap → small half-block pixel sprite. No Kitty/Sixel."""

from __future__ import annotations

import colorsys
import hashlib
import os
from collections.abc import Sequence

SPRITE_W = 8
SPRITE_H = 8


def _truecolor() -> bool:
    if os.environ.get("NO_COLOR", "").strip():
        return False
    term = os.environ.get("COLORTERM", "").lower()
    if "truecolor" in term or "24bit" in term:
        return True
    return os.environ.get("TERM", "").endswith("-direct")


def _use_256() -> bool:
    if os.environ.get("NO_COLOR", "").strip():
        return False
    if _truecolor():
        return True
    term = os.environ.get("TERM", "")
    if term in ("", "dumb"):
        return False
    return True


def _xterm256(r: int, g: int, b: int) -> int:
    def cube(v: int) -> int:
        if v < 48:
            return 0
        if v < 115:
            return 1
        return min(5, (v - 35) // 40)

    return 16 + 36 * cube(r) + 6 * cube(g) + cube(b)


def _hash_bytes(seed: str) -> bytes:
    return hashlib.sha256(seed.encode("utf-8")).digest()


def palette_for(seed: str) -> tuple[int, int, int]:
    digest = _hash_bytes(seed)
    hue = digest[0] / 255.0
    sat = 0.55 + (digest[1] / 255.0) * 0.4
    val = 0.75 + (digest[2] / 255.0) * 0.25
    r, g, b = colorsys.hsv_to_rgb(hue, min(sat, 1.0), min(val, 1.0))
    return int(r * 255), int(g * 255), int(b * 255)


def bitmap_from_seed(seed: str, width: int = SPRITE_W, height: int = SPRITE_H) -> list[list[int]]:
    """Deterministic 0/1 grid from name/id. Center-weighted so it reads as a face."""
    digest = _hash_bytes(seed + ":sprite")
    bits: list[int] = []
    for byte in digest:
        for shift in range(8):
            bits.append((byte >> shift) & 1)
    grid: list[list[int]] = []
    i = 0
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            on = bits[i % len(bits)]
            i += 1
            # Frame + eyes only on full 8×8. Tiny inline sprites must stay mixed.
            if width >= 8 and height >= 8:
                if x in (0, width - 1) or y in (0, height - 1):
                    on = 1 if y == 0 or y == height - 1 else on
                if y == height // 3 and x in (width // 3, (2 * width) // 3):
                    on = 1
            row.append(1 if on else 0)
        grid.append(row)
    return grid


def _fg(r: int, g: int, b: int, truecolor: bool) -> str:
    if truecolor:
        return f"\033[38;2;{r};{g};{b}m"
    if _use_256():
        return f"\033[38;5;{_xterm256(r, g, b)}m"
    idx = 90 + ((r > 127) + (g > 127) * 2 + (b > 127) * 4) % 8
    return f"\033[{idx}m"


def _bg(r: int, g: int, b: int, truecolor: bool) -> str:
    if truecolor:
        return f"\033[48;2;{r};{g};{b}m"
    if _use_256():
        return f"\033[48;5;{_xterm256(r, g, b)}m"
    idx = 100 + ((r > 127) + (g > 127) * 2 + (b > 127) * 4) % 8
    return f"\033[{idx}m"


RESET = "\033[0m"


def render_sprite(
    seed: str,
    *,
    bitmap: Sequence[Sequence[int]] | None = None,
    width: int | None = None,
    truecolor: bool | None = None,
) -> list[str]:
    """Return half-block rows (`▀`). Each line is one cell-row pair of pixels."""
    grid = [list(row) for row in bitmap] if bitmap is not None else bitmap_from_seed(seed)
    h = len(grid)
    w = len(grid[0]) if h else 0
    rgb = palette_for(seed)
    use_tc = _truecolor() if truecolor is None else truecolor
    color = _fg(*rgb, use_tc)
    lines: list[str] = []
    for y in range(0, h, 2):
        top = grid[y]
        bot = grid[y + 1] if y + 1 < h else [0] * w
        cells: list[str] = []
        for x in range(w):
            t, b = top[x], bot[x]
            if t and b:
                ch = "█"
            elif t:
                ch = "▀"
            elif b:
                ch = "▄"
            else:
                ch = " "
            cells.append(ch)
        lines.append(color + "".join(cells) + RESET)
    if width is not None and width < w + 4:
        letter = (seed.strip() or "?")[0].upper()
        return [color + f"[{letter}]" + RESET]
    return lines


def sprite_column(seed: str, *, terminal_width: int = 80) -> list[str]:
    collapse = terminal_width < 48
    return render_sprite(seed, width=4 if collapse else None)


def sprite_inline(seed: str, *, terminal_width: int = 80, truecolor: bool | None = None) -> str:
    """One-row 4-wide icon: each cell is a two-color ▀ (top fg, bottom bg)."""
    use_tc = _truecolor() if truecolor is None else truecolor
    if terminal_width < 48:
        rgb = palette_for(seed)
        letter = (seed.strip() or "?")[0].upper()
        return _fg(*rgb, use_tc) + f"[{letter}]" + RESET
    cells: list[str] = []
    for i in range(4):
        top = palette_for(f"{seed}:icon:{i}:t")
        bot = palette_for(f"{seed}:icon:{i}:b")
        cells.append(_fg(*top, use_tc) + _bg(*bot, use_tc) + "▀")
    return "".join(cells) + RESET
