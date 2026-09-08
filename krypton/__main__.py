from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import CATALOG_DIR, load_catalog
from .export import slugify, write_bundle_dir, write_bundle_zip
from .profile import load_profile, resolve_profile
from .server import serve
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="krypton",
        description="Design a Windows 11 all-in-one setup bundle from selected apps.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"Krypton {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate the app catalog, presets, and tweaks")

    export = sub.add_parser("export", help="Export a double-click setup folder or zip")
    export.add_argument("profile", type=Path, help="Path to a Krypton profile JSON file")
    export.add_argument("-o", "--output", type=Path, default=Path("dist"), help="Output directory")
    export.add_argument("--zip", action="store_true", help="Write a zip file instead of a folder")

    preview = sub.add_parser("preview", help="Print the resolved bundle without writing files")
    preview.add_argument("profile", type=Path)

    server = sub.add_parser("serve", help="Open the designer in a local browser")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8787)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        catalog = load_catalog()
        print(
            f"Krypton {__version__} catalog OK: {len(catalog['apps'])} apps, "
            f"{len(catalog['presets'])} presets, {len(catalog['tweaks'])} tweaks "
            f"from {CATALOG_DIR}"
        )
        return 0
    if args.command in {"export", "preview"}:
        catalog = load_catalog()
        profile = resolve_profile(load_profile(args.profile), catalog)
        if args.command == "preview":
            json.dump(profile, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        if args.zip:
            dest = args.output
            if dest.suffix.lower() != ".zip":
                dest = dest / f"KryptonSetup-{slugify(profile['name'])}.zip"
            path = write_bundle_zip(profile, catalog, dest)
        else:
            path = write_bundle_dir(profile, catalog, args.output)
        print(f"Wrote {path}")
        return 0
    if args.command == "serve":
        serve(args.host, args.port)
        return 0
    raise AssertionError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
