#!/usr/bin/env python3
"""Start the Krypton designer: python3 tools/serve.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from krypton.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["serve", *sys.argv[1:]]))
