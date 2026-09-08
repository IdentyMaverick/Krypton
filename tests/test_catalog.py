from __future__ import annotations

import unittest

from krypton.catalog import load_catalog, validate_catalog


class CatalogTests(unittest.TestCase):
    def test_catalog_loads_and_validates(self) -> None:
        catalog = load_catalog()
        self.assertGreaterEqual(len(catalog["apps"]), 40)
        self.assertGreaterEqual(len(catalog["presets"]), 4)
        self.assertGreaterEqual(len(catalog["tweaks"]), 8)
        self.assertEqual(validate_catalog(catalog), [])

    def test_categories_cover_every_app(self) -> None:
        catalog = load_catalog()
        category_ids = {category["id"] for category in catalog["categories"]}
        for app in catalog["apps"]:
            self.assertIn(app["category"], category_ids)
            self.assertTrue(app["package"].count(".") >= 1)

    def test_preset_sizes(self) -> None:
        catalog = load_catalog()
        for preset in catalog["presets"]:
            self.assertGreaterEqual(len(preset["apps"]), 3)
            self.assertEqual(len(preset["apps"]), len(set(preset["apps"])))


if __name__ == "__main__":
    unittest.main()
