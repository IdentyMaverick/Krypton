from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import json
import mimetypes
import sys
import webbrowser

from .catalog import ROOT, load_catalog
from .export import slugify, write_bundle_zip
from .profile import ProfileError, resolve_profile
from .version import __version__

DESIGNER_DIR = ROOT / "designer"
CATALOG_PUBLIC = ROOT / "catalog"
ENGINE_PUBLIC = ROOT / "engine"


def json_bytes(payload: Any, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


class KryptonHandler(BaseHTTPRequestHandler):
    server_version = f"Krypton/{__version__}"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _send(self, status: int, body: bytes, content_type: str, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2_000_000:
            raise ValueError("request body is missing or too large")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            status, body, content_type = json_bytes(
                {
                    "ok": True,
                    "app": "Krypton",
                    "version": __version__,
                    "platform": sys.platform,
                    "windows": sys.platform.startswith("win"),
                    "winget": False,
                    "canInstall": False,
                    "canExport": True,
                }
            )
            self._send(status, body, content_type)
            return
        if path == "/api/catalog":
            status, body, content_type = json_bytes(load_catalog())
            self._send(status, body, content_type)
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self._read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            status, body, content_type = json_bytes({"ok": False, "error": str(exc)}, 400)
            self._send(status, body, content_type)
            return
        try:
            catalog = load_catalog()
            if path == "/api/validate":
                resolved = resolve_profile(payload, catalog)
                status, body, content_type = json_bytes({"ok": True, "profile": resolved})
                self._send(status, body, content_type)
                return
            if path == "/api/export":
                resolved = resolve_profile(payload, catalog)
                from tempfile import TemporaryDirectory

                with TemporaryDirectory() as tmp:
                    zip_path = Path(tmp) / f"KryptonSetup-{slugify(resolved['name'])}.zip"
                    write_bundle_zip(resolved, catalog, zip_path)
                    data = zip_path.read_bytes()
                filename = f"KryptonSetup-{slugify(resolved['name'])}.zip"
                self._send(
                    200,
                    data,
                    "application/zip",
                    extra_headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
                return
        except ProfileError as exc:
            status, body, content_type = json_bytes({"ok": False, "error": str(exc)}, 400)
            self._send(status, body, content_type)
            return
        status, body, content_type = json_bytes({"ok": False, "error": "unknown endpoint"}, 404)
        self._send(status, body, content_type)

    def _serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        relative = path.lstrip("/")
        if relative.startswith("catalog/"):
            root_dir = CATALOG_PUBLIC
            file_path = (CATALOG_PUBLIC / relative[len("catalog/") :]).resolve()
        elif relative.startswith("engine/"):
            root_dir = ENGINE_PUBLIC
            file_path = (ENGINE_PUBLIC / relative[len("engine/") :]).resolve()
        else:
            root_dir = DESIGNER_DIR
            file_path = (DESIGNER_DIR / relative).resolve()
        if root_dir not in file_path.parents and file_path != root_dir:
            self._send(403, b"Forbidden", "text/plain")
            return
        if not file_path.is_file():
            self._send(404, b"Not found", "text/plain")
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if file_path.suffix in {".json", ".svg", ".css", ".js", ".html", ".ps1", ".cmd", ".txt"}:
            content_type = {
                ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml",
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".html": "text/html; charset=utf-8",
                ".ps1": "text/plain; charset=utf-8",
                ".cmd": "text/plain; charset=utf-8",
                ".txt": "text/plain; charset=utf-8",
            }[file_path.suffix]
        self._send(200, file_path.read_bytes(), content_type)


def serve(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer((host, port), KryptonHandler)
    url = f"http://{host}:{port}/"
    print(f"Krypton designer is running at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
