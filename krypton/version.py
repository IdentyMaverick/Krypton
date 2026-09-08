from __future__ import annotations

import re

from .catalog import ROOT

VERSION_FILE = ROOT / "VERSION"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def get_version() -> str:
    if not VERSION_FILE.is_file():
        raise RuntimeError(f"Missing version file: {VERSION_FILE}")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not VERSION_RE.match(version):
        raise RuntimeError(f"VERSION must look like 1.0.0, got {version!r}")
    return version


__version__ = get_version()
