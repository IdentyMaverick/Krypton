from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import zipfile

from .catalog import ENGINE_DIR, tweak_index
from .profile import resolve_profile, slugify

INSTALL_CMD = """@echo off
setlocal EnableExtensions
title Krypton Windows 11 setup
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting administrator permission...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo.
echo  Krypton setup
echo  Installing selected apps and applying Windows 11 options.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Bundle.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" (
  echo Setup finished with errors. Review the log above.
) else (
  echo Setup finished.
)
pause
exit /b %EXITCODE%
"""

README_TEMPLATE = """Krypton setup bundle
====================

Name: {name}
Created: {created}

This folder is a double-click Windows 11 setup program for the apps and
options you selected in Krypton.

How to use
----------
1. Copy this whole folder to the Windows 11 PC (USB drive is fine).
2. Right-click Install.cmd and choose "Run as administrator".
3. Leave the window open until it says setup finished.

What it installs
----------------
{apps}

Windows 11 options
------------------
{tweaks}

Notes
-----
- Apps from the catalog are installed with winget (App Installer).
- Custom https installers are downloaded, then run with the silent
  arguments you entered.
- Local installers must sit in this folder using the relative path you
  saved in the designer.
- Setup continues if one app fails so the rest of the bundle still runs.
- Logs are written to %LOCALAPPDATA%\\Krypton\\logs
"""


def _app_lines(profile: dict[str, Any]) -> str:
    lines = []
    for app in profile["apps"]:
        source = app["source"]
        if source == "winget":
            detail = f"winget {app['package']}"
        elif source == "url":
            detail = app["url"]
        else:
            detail = app["path"]
        lines.append(f"- {app['name']} ({detail})")
    return "\n".join(lines) or "- (none)"


def _tweak_lines(profile: dict[str, Any], catalog: dict[str, Any]) -> str:
    names = tweak_index(catalog)
    if not profile["tweaks"]:
        return "- (none)"
    return "\n".join(f"- {names[tweak_id]['name']}" for tweak_id in profile["tweaks"])


def read_installer_script() -> str:
    path = ENGINE_DIR / "Install-Bundle.ps1"
    if not path.is_file():
        raise FileNotFoundError(f"Missing installer engine: {path}")
    return path.read_text(encoding="utf-8")


def render_readme(profile: dict[str, Any], catalog: dict[str, Any]) -> str:
    return README_TEMPLATE.format(
        name=profile["name"],
        created=profile.get("createdAt", ""),
        apps=_app_lines(profile),
        tweaks=_tweak_lines(profile, catalog),
    )


def bundle_files(profile: dict[str, Any], catalog: dict[str, Any]) -> dict[str, str]:
    resolved = resolve_profile(profile, catalog)
    return {
        "bundle.json": json.dumps(resolved, indent=2) + "\n",
        "Install.cmd": INSTALL_CMD.replace("\n", "\r\n"),
        "Install-Bundle.ps1": read_installer_script(),
        "README.txt": render_readme(resolved, catalog).replace("\n", "\r\n"),
    }


def write_bundle_dir(profile: dict[str, Any], catalog: dict[str, Any], dest: Path) -> Path:
    resolved = resolve_profile(profile, catalog)
    folder = dest / f"KryptonSetup-{slugify(resolved['name'])}"
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in bundle_files(resolved, catalog).items():
        (folder / name).write_text(content, encoding="utf-8", newline="")
    return folder


def write_bundle_zip(profile: dict[str, Any], catalog: dict[str, Any], dest_zip: Path) -> Path:
    resolved = resolve_profile(profile, catalog)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    root_name = f"KryptonSetup-{slugify(resolved['name'])}"
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in bundle_files(resolved, catalog).items():
            archive.writestr(f"{root_name}/{name}", content)
    return dest_zip
