from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
import zipfile

from krypton.catalog import load_catalog
from krypton.export import write_bundle_dir, write_bundle_zip
from krypton.profile import load_profile, resolve_profile
from krypton.version import get_version


ROOT = Path(__file__).resolve().parent.parent


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_catalog()
        self.profile = load_profile(ROOT / "samples" / "essential.json")

    def test_sample_developer_profile_resolves(self) -> None:
        resolved = resolve_profile(load_profile(ROOT / "samples" / "developer.json"), self.catalog)
        custom = [app for app in resolved["apps"] if app["id"] == "custom-ripgrep"]
        self.assertEqual(custom[0]["package"], "BurntSushi.ripgrep.MSVC")

    def test_write_bundle_dir_contains_installer_and_selected_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_bundle_dir(self.profile, self.catalog, Path(tmp))
            self.assertTrue((folder / "Install.cmd").is_file())
            self.assertTrue((folder / "Install-Bundle.ps1").is_file())
            bundle = json.loads((folder / "bundle.json").read_text(encoding="utf-8"))
            names = {app["name"] for app in bundle["apps"]}
            self.assertIn("Google Chrome", names)
            self.assertIn("7-Zip", names)
            self.assertEqual(bundle["kryptonVersion"], get_version())
            self.assertTrue((folder / "VERSION").is_file())
            self.assertEqual((folder / "VERSION").read_text(encoding="utf-8").strip(), get_version())
            cmd = (folder / "Install.cmd").read_text(encoding="utf-8")
            self.assertIn("Install-Bundle.ps1", cmd)
            engine = (folder / "Install-Bundle.ps1").read_text(encoding="utf-8")
            self.assertIn("winget install", engine)
            self.assertIn("Apply-Tweak", engine)

    def test_zip_bundle_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "setup.zip"
            write_bundle_zip(self.profile, self.catalog, zip_path)
            with zipfile.ZipFile(zip_path) as archive:
                names = archive.namelist()
            self.assertTrue(any(name.endswith("bundle.json") for name in names))
            self.assertTrue(any(name.endswith("Install.cmd") for name in names))
            self.assertTrue(any(name.endswith("Install-Bundle.ps1") for name in names))
            self.assertTrue(any(name.endswith("README.txt") for name in names))
            self.assertTrue(any(name.endswith("VERSION") for name in names))


if __name__ == "__main__":
    unittest.main()
