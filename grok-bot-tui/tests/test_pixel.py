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


def test_sprite_inline_is_one_row() -> None:
    from grok_bot_tui.pixel import sprite_inline

    glyph = sprite_inline("sales-outbound", terminal_width=80, truecolor=True)
    assert "\n" not in glyph
    assert "▀" in glyph
    assert glyph.count("▀") == 4
    assert "\033[38;2;" in glyph
    assert "\033[48;2;" in glyph
    other = sprite_inline("talent-scout", terminal_width=80, truecolor=True)
    assert glyph != other
    narrow = sprite_inline("sales-outbound", terminal_width=20, truecolor=True)
    assert "[S]" in narrow or "S" in narrow
    assert "\033[" in narrow


def test_sprite_inline_uses_256_when_not_truecolor(monkeypatch) -> None:
    from grok_bot_tui.pixel import sprite_inline

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.delenv("COLORTERM", raising=False)
    glyph = sprite_inline("ops-bot", terminal_width=80, truecolor=False)
    assert "▀" in glyph
    assert "\033[38;5;" in glyph
    assert "\033[48;5;" in glyph
