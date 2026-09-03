"""Offline: Linux version pin and official-check script. No live downloads."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_platforms_catalog() -> None:
    catalog = json.loads((REPO / "share" / "platforms.json").read_text(encoding="utf-8"))
    pin = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert catalog["internal_app"] == "sand"
    assert catalog["desktop_version"] == pin
    assert pin == "0.36.0"
    linux = catalog["linux"]
    assert "x64" in linux
    assert "arm64" in linux
    assert "{version}" in linux["x64"]["tarball"]
    assert "{version}" in linux["arm64"]["tarball"]
    assert linux["x64"]["sha256_0_36_0"]
    assert linux["arm64"]["sha256_0_36_0"]


def test_check_official_script_parses() -> None:
    script = REPO / "scripts" / "check-official.sh"
    assert script.is_file()
    proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert script.stat().st_mode & 0o111
