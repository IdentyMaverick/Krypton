from __future__ import annotations

import unittest

from krypton.catalog import load_catalog
from krypton.profile import ProfileError, make_custom_id, resolve_profile


class ProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_catalog()

    def test_resolve_catalog_ids(self) -> None:
        profile = resolve_profile(
            {"name": "Lab PC", "apps": ["google-chrome", "git"], "tweaks": ["dark-mode"]},
            self.catalog,
        )
        self.assertEqual(profile["apps"][0]["package"], "Google.Chrome")
        self.assertEqual(profile["apps"][1]["package"], "Git.Git")
        self.assertEqual(profile["tweaks"], ["dark-mode"])

    def test_custom_winget_app(self) -> None:
        profile = resolve_profile(
            {
                "name": "Custom",
                "apps": [
                    {
                        "id": "custom-ripgrep",
                        "name": "ripgrep",
                        "source": "winget",
                        "package": "BurntSushi.ripgrep.MSVC",
                    }
                ],
                "tweaks": [],
            },
            self.catalog,
        )
        self.assertEqual(profile["apps"][0]["id"], "custom-ripgrep")

    def test_rejects_http_url(self) -> None:
        with self.assertRaises(ProfileError):
            resolve_profile(
                {
                    "name": "Bad",
                    "apps": [
                        {
                            "id": "custom-insecure",
                            "name": "No",
                            "source": "url",
                            "url": "http://example.com/setup.exe",
                        }
                    ],
                    "tweaks": [],
                },
                self.catalog,
            )

    def test_rejects_absolute_local_path(self) -> None:
        with self.assertRaises(ProfileError):
            resolve_profile(
                {
                    "name": "Bad",
                    "apps": [
                        {
                            "id": "custom-local",
                            "name": "Local",
                            "source": "local",
                            "path": "C:\\Windows\\setup.exe",
                        }
                    ],
                    "tweaks": [],
                },
                self.catalog,
            )

    def test_accepts_relative_local_installer(self) -> None:
        profile = resolve_profile(
            {
                "name": "USB kit",
                "apps": [
                    {
                        "id": "custom-vendor",
                        "name": "Vendor setup",
                        "source": "local",
                        "path": "installers\\vendor.exe",
                        "silentArgs": "/S",
                    }
                ],
                "tweaks": [],
            },
            self.catalog,
        )
        self.assertEqual(profile["apps"][0]["path"], "installers/vendor.exe")

    def test_rejects_unknown_app(self) -> None:
        with self.assertRaises(ProfileError):
            resolve_profile({"name": "x", "apps": ["not-a-real-app"], "tweaks": []}, self.catalog)

    def test_rejects_empty_profile(self) -> None:
        with self.assertRaises(ProfileError):
            resolve_profile({"name": "Empty", "apps": [], "tweaks": []}, self.catalog)

    def test_make_custom_id_avoids_collisions(self) -> None:
        existing = {"custom-obs"}
        self.assertEqual(make_custom_id("OBS", existing), "custom-obs-2")


if __name__ == "__main__":
    unittest.main()
