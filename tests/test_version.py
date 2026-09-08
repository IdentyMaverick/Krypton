from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

from krypton.catalog import load_catalog
from krypton.profile import load_profile, resolve_profile
from krypton.version import VERSION_FILE, get_version


ROOT = Path(__file__).resolve().parent.parent


class VersionTests(unittest.TestCase):
    def test_version_file_is_semver(self) -> None:
        version = get_version()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(VERSION_FILE.read_text(encoding="utf-8").strip(), version)

    def test_cli_prints_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "krypton", "--version"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn(get_version(), result.stdout)

    def test_resolved_profile_includes_krypton_version(self) -> None:
        catalog = load_catalog()
        profile = resolve_profile(load_profile(ROOT / "samples" / "essential.json"), catalog)
        self.assertEqual(profile["kryptonVersion"], get_version())

    def test_readme_mentions_current_version(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(get_version(), readme)
        self.assertTrue(re.search(r"github/v/release/IdentyMaverick/Krypton", readme))
