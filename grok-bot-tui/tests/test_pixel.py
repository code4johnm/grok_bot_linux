"""Offline: hash sprites and narrow-terminal collapse."""

from __future__ import annotations

from grok_bot_tui.pixel import bitmap_from_seed, render_sprite, sprite_column


def test_bitmap_is_8x8_deterministic() -> None:
    a = bitmap_from_seed("grok-4.6")
    b = bitmap_from_seed("grok-4.6")
    c = bitmap_from_seed("other")
    assert len(a) == 8
    assert all(len(row) == 8 for row in a)
    assert a == b
    assert a != c


def test_half_blocks_and_reset() -> None:
    lines = render_sprite("grok-4.6", truecolor=False)
    assert lines
    blob = "\n".join(lines)
    assert "\033[0m" in blob
    assert any(ch in blob for ch in "▀▄█")


def test_narrow_terminal_collapses_to_letter() -> None:
    lines = sprite_column("alpha-bot", terminal_width=20)
    assert len(lines) == 1
    assert "A" in lines[0] or "[A]" in lines[0]
