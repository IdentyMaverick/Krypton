from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import json
import re

from .catalog import (
    CUSTOM_ID_PREFIX,
    PROFILE_SOURCES,
    WINGET_PACKAGE_RE,
    app_index,
    load_catalog,
    tweak_index,
)
from .version import get_version

PROFILE_VERSION = 1
WINGET_RE = re.compile(WINGET_PACKAGE_RE)
CUSTOM_ID_RE = re.compile(r"^custom-[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProfileError(ValueError):
    """Raised when a setup profile cannot be used."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def empty_profile(name: str = "My Windows 11 PC") -> dict[str, Any]:
    return {
        "name": name,
        "version": PROFILE_VERSION,
        "createdAt": utc_now(),
        "apps": [],
        "tweaks": [],
    }


def load_profile(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"Invalid profile JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError("Profile must be a JSON object")
    return data


def dump_profile(profile: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{field} must be a non-empty string")
    return value.strip()


def validate_custom_app(app: dict[str, Any]) -> dict[str, Any]:
    app_id = _require_string(app.get("id"), "apps[].id")
    if not CUSTOM_ID_RE.match(app_id):
        raise ProfileError(f"custom app id must match {CUSTOM_ID_RE.pattern}: {app_id}")
    name = _require_string(app.get("name"), "apps[].name")
    source = app.get("source")
    if source not in PROFILE_SOURCES:
        raise ProfileError(f"apps[].source must be one of {sorted(PROFILE_SOURCES)}")
    normalized: dict[str, Any] = {
        "id": app_id,
        "name": name,
        "source": source,
    }
    if source == "winget":
        package = _require_string(app.get("package"), "apps[].package")
        if not WINGET_RE.match(package):
            raise ProfileError(f"invalid winget package id: {package}")
        normalized["package"] = package
    elif source == "url":
        url = _require_string(app.get("url"), "apps[].url")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProfileError("custom installer URLs must be https")
        normalized["url"] = url
        if app.get("silentArgs"):
            normalized["silentArgs"] = _require_string(app.get("silentArgs"), "apps[].silentArgs")
        if app.get("fileName"):
            normalized["fileName"] = Path(_require_string(app.get("fileName"), "apps[].fileName")).name
    elif source == "local":
        local_path = _require_string(app.get("path"), "apps[].path")
        posix = local_path.replace("\\", "/")
        if (
            Path(posix).is_absolute()
            or Path(local_path).is_absolute()
            or re.match(r"^[a-zA-Z]:", local_path)
            or posix.startswith("/")
            or local_path.startswith("\\\\")
            or ".." in Path(posix).parts
        ):
            raise ProfileError("local installer path must stay inside the setup folder")
        suffix = Path(posix).suffix.lower()
        if suffix not in {".exe", ".msi", ".msix", ".appx", ".msixbundle"}:
            raise ProfileError("local installer must be .exe, .msi, .msix, .appx, or .msixbundle")
        normalized["path"] = posix
        if app.get("silentArgs"):
            normalized["silentArgs"] = _require_string(app.get("silentArgs"), "apps[].silentArgs")
    return normalized


def resolve_profile(profile: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise ProfileError("Profile must be an object")
    name = _require_string(profile.get("name", "My Windows 11 PC"), "name")
    version = profile.get("version", PROFILE_VERSION)
    if version != PROFILE_VERSION:
        raise ProfileError(f"unsupported profile version: {version}")
    catalog = catalog or load_catalog()
    known_apps = app_index(catalog)
    known_tweaks = tweak_index(catalog)
    raw_apps = profile.get("apps")
    raw_tweaks = profile.get("tweaks")
    if not isinstance(raw_apps, list):
        raise ProfileError("apps must be a list")
    if not isinstance(raw_tweaks, list):
        raise ProfileError("tweaks must be a list")
    if not raw_apps and not raw_tweaks:
        raise ProfileError("select at least one app or Windows tweak")

    resolved_apps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw_apps):
        if isinstance(entry, str):
            app_id = entry
            if app_id not in known_apps:
                raise ProfileError(f"unknown catalog app: {app_id}")
            app = {
                "id": app_id,
                "name": known_apps[app_id]["name"],
                "source": "winget",
                "package": known_apps[app_id]["package"],
            }
        elif isinstance(entry, dict):
            app_id = _require_string(entry.get("id"), f"apps[{index}].id")
            if app_id in known_apps:
                catalog_app = known_apps[app_id]
                app = {
                    "id": app_id,
                    "name": catalog_app["name"],
                    "source": "winget",
                    "package": catalog_app["package"],
                }
            else:
                app = validate_custom_app(entry)
        else:
            raise ProfileError(f"apps[{index}] must be an id or object")
        if app["id"] in seen_ids:
            raise ProfileError(f"duplicate app in profile: {app['id']}")
        seen_ids.add(app["id"])
        resolved_apps.append(app)

    resolved_tweaks: list[str] = []
    seen_tweaks: set[str] = set()
    for tweak_id in raw_tweaks:
        if not isinstance(tweak_id, str) or tweak_id not in known_tweaks:
            raise ProfileError(f"unknown tweak: {tweak_id}")
        if tweak_id in seen_tweaks:
            raise ProfileError(f"duplicate tweak in profile: {tweak_id}")
        seen_tweaks.add(tweak_id)
        resolved_tweaks.append(tweak_id)

    return {
        "name": name,
        "version": PROFILE_VERSION,
        "kryptonVersion": get_version(),
        "createdAt": profile.get("createdAt") or utc_now(),
        "apps": resolved_apps,
        "tweaks": resolved_tweaks,
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "bundle"


def make_custom_id(name: str, existing: set[str]) -> str:
    base = slugify(name)
    candidate = f"{CUSTOM_ID_PREFIX}{base}"
    suffix = 2
    while candidate in existing:
        candidate = f"{CUSTOM_ID_PREFIX}{base}-{suffix}"
        suffix += 1
    return candidate
