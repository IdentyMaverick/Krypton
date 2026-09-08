from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"
ENGINE_DIR = ROOT / "engine"

APP_ID_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
WINGET_PACKAGE_RE = r"^[A-Za-z0-9][A-Za-z0-9.+_-]*(?:\.[A-Za-z0-9][A-Za-z0-9.+_-]*)+$"
CUSTOM_ID_PREFIX = "custom-"

REQUIRED_APP_FIELDS = {
    "id",
    "name",
    "publisher",
    "category",
    "description",
    "source",
    "package",
    "website",
}
REQUIRED_TWEAK_FIELDS = {"id", "name", "description", "risk", "scope"}
REQUIRED_PRESET_FIELDS = {"id", "name", "description", "apps", "tweaks"}
ALLOWED_SOURCES = {"winget"}
ALLOWED_RISKS = {"safe", "moderate"}
ALLOWED_SCOPES = {"current-user", "machine"}
PROFILE_SOURCES = {"winget", "url", "local"}


class CatalogError(ValueError):
    """Raised when catalog files are missing or invalid."""


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise CatalogError(f"Missing catalog file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogError(f"Invalid JSON in {path}: {exc}") from exc


def load_apps(catalog_dir: Path | None = None) -> dict[str, Any]:
    data = _read_json((catalog_dir or CATALOG_DIR) / "apps.json")
    if not isinstance(data, dict):
        raise CatalogError("apps.json must be an object")
    return data


def load_tweaks(catalog_dir: Path | None = None) -> dict[str, Any]:
    data = _read_json((catalog_dir or CATALOG_DIR) / "tweaks.json")
    if not isinstance(data, dict):
        raise CatalogError("tweaks.json must be an object")
    return data


def load_presets(catalog_dir: Path | None = None) -> dict[str, Any]:
    data = _read_json((catalog_dir or CATALOG_DIR) / "presets.json")
    if not isinstance(data, dict):
        raise CatalogError("presets.json must be an object")
    return data


def load_catalog(catalog_dir: Path | None = None) -> dict[str, Any]:
    directory = catalog_dir or CATALOG_DIR
    apps_doc = load_apps(directory)
    tweaks_doc = load_tweaks(directory)
    presets_doc = load_presets(directory)
    catalog = {
        "version": apps_doc.get("version", 1),
        "categories": apps_doc.get("categories", []),
        "apps": apps_doc.get("apps", []),
        "tweaks": tweaks_doc.get("tweaks", []),
        "presets": presets_doc.get("presets", []),
    }
    errors = validate_catalog(catalog)
    if errors:
        raise CatalogError("Catalog validation failed:\n- " + "\n- ".join(errors))
    return catalog


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    categories = catalog.get("categories")
    apps = catalog.get("apps")
    tweaks = catalog.get("tweaks")
    presets = catalog.get("presets")

    if not isinstance(categories, list) or not categories:
        errors.append("categories must be a non-empty list")
        categories = []
    if not isinstance(apps, list) or not apps:
        errors.append("apps must be a non-empty list")
        apps = []
    if not isinstance(tweaks, list) or not tweaks:
        errors.append("tweaks must be a non-empty list")
        tweaks = []
    if not isinstance(presets, list) or not presets:
        errors.append("presets must be a non-empty list")
        presets = []

    category_ids: set[str] = set()
    for index, category in enumerate(categories):
        prefix = f"categories[{index}]"
        if not isinstance(category, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("id", "name", "blurb"):
            if not isinstance(category.get(field), str) or not category[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        cat_id = category.get("id")
        if isinstance(cat_id, str):
            if cat_id in category_ids:
                errors.append(f"duplicate category id: {cat_id}")
            category_ids.add(cat_id)

    app_ids: set[str] = set()
    packages: dict[str, str] = {}

    app_id_re = re.compile(APP_ID_RE)
    winget_re = re.compile(WINGET_PACKAGE_RE)

    for index, app in enumerate(apps):
        prefix = f"apps[{index}]"
        if not isinstance(app, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_APP_FIELDS - set(app)
        if missing:
            errors.append(f"{prefix} missing fields: {sorted(missing)}")
        app_id = app.get("id")
        if not isinstance(app_id, str) or not app_id_re.match(app_id):
            errors.append(f"{prefix}.id must match {APP_ID_RE}")
        elif app_id in app_ids:
            errors.append(f"duplicate app id: {app_id}")
        else:
            app_ids.add(app_id)
        if app.get("source") not in ALLOWED_SOURCES:
            errors.append(f"{prefix}.source must be one of {sorted(ALLOWED_SOURCES)}")
        if app.get("category") not in category_ids:
            errors.append(f"{prefix}.category is not a known category: {app.get('category')}")
        package = app.get("package")
        if not isinstance(package, str) or not winget_re.match(package):
            errors.append(f"{prefix}.package is not a valid winget id: {package}")
        elif isinstance(package, str) and package in packages:
            errors.append(f"duplicate winget package {package} ({packages[package]} and {app_id})")
        elif isinstance(package, str) and isinstance(app_id, str):
            packages[package] = app_id
        website = app.get("website")
        if not isinstance(website, str) or not website.startswith("https://"):
            errors.append(f"{prefix}.website must be an https URL")

    tweak_ids: set[str] = set()
    for index, tweak in enumerate(tweaks):
        prefix = f"tweaks[{index}]"
        if not isinstance(tweak, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_TWEAK_FIELDS - set(tweak)
        if missing:
            errors.append(f"{prefix} missing fields: {sorted(missing)}")
        tweak_id = tweak.get("id")
        if not isinstance(tweak_id, str) or not app_id_re.match(tweak_id):
            errors.append(f"{prefix}.id must match {APP_ID_RE}")
        elif tweak_id in tweak_ids:
            errors.append(f"duplicate tweak id: {tweak_id}")
        else:
            tweak_ids.add(tweak_id)
        if tweak.get("risk") not in ALLOWED_RISKS:
            errors.append(f"{prefix}.risk must be one of {sorted(ALLOWED_RISKS)}")
        if tweak.get("scope") not in ALLOWED_SCOPES:
            errors.append(f"{prefix}.scope must be one of {sorted(ALLOWED_SCOPES)}")

    preset_ids: set[str] = set()
    for index, preset in enumerate(presets):
        prefix = f"presets[{index}]"
        if not isinstance(preset, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_PRESET_FIELDS - set(preset)
        if missing:
            errors.append(f"{prefix} missing fields: {sorted(missing)}")
            continue
        preset_id = preset.get("id")
        if not isinstance(preset_id, str) or not app_id_re.match(preset_id):
            errors.append(f"{prefix}.id must match {APP_ID_RE}")
        elif preset_id in preset_ids:
            errors.append(f"duplicate preset id: {preset_id}")
        else:
            preset_ids.add(preset_id)
        apps_list = preset.get("apps")
        tweaks_list = preset.get("tweaks")
        if not isinstance(apps_list, list) or not apps_list:
            errors.append(f"{prefix}.apps must be a non-empty list")
            apps_list = []
        if not isinstance(tweaks_list, list):
            errors.append(f"{prefix}.tweaks must be a list")
            tweaks_list = []
        seen_apps: set[str] = set()
        for app_id in apps_list:
            if app_id in seen_apps:
                errors.append(f"{prefix}.apps has duplicate id {app_id}")
            seen_apps.add(app_id)
            if app_id not in app_ids:
                errors.append(f"{prefix}.apps references unknown app {app_id}")
        seen_tweaks: set[str] = set()
        for tweak_id in tweaks_list:
            if tweak_id in seen_tweaks:
                errors.append(f"{prefix}.tweaks has duplicate id {tweak_id}")
            seen_tweaks.add(tweak_id)
            if tweak_id not in tweak_ids:
                errors.append(f"{prefix}.tweaks references unknown tweak {tweak_id}")

    return errors


def app_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {app["id"]: app for app in catalog["apps"]}


def tweak_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {tweak["id"]: tweak for tweak in catalog["tweaks"]}
