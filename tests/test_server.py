from __future__ import annotations

from http.client import HTTPConnection
from threading import Thread
import json
import unittest

from krypton.server import KryptonHandler, ThreadingHTTPServer


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), KryptonHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, bytes, str]:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"} if payload else {}
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        content_type = response.getheader("Content-Type") or ""
        conn.close()
        return response.status, data, content_type

    def test_status_and_catalog(self) -> None:
        status_code, body, _ = self.request("GET", "/api/status")
        self.assertEqual(status_code, 200)
        status = json.loads(body)
        self.assertTrue(status["ok"])
        self.assertTrue(status["canExport"])
        status_code, body, _ = self.request("GET", "/api/catalog")
        catalog = json.loads(body)
        self.assertIn("apps", catalog)
        self.assertGreater(len(catalog["apps"]), 10)

    def test_designer_home(self) -> None:
        status_code, body, content_type = self.request("GET", "/")
        self.assertEqual(status_code, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"Krypton", body)
        self.assertIn(b"Add custom app", body)

    def test_validate_and_export(self) -> None:
        profile = {
            "name": "Server test",
            "apps": ["vlc"],
            "tweaks": ["dark-mode"],
        }
        status_code, body, _ = self.request("POST", "/api/validate", profile)
        self.assertEqual(status_code, 200)
        resolved = json.loads(body)["profile"]
        self.assertEqual(resolved["apps"][0]["package"], "VideoLAN.VLC")
        status_code, body, content_type = self.request("POST", "/api/export", profile)
        self.assertEqual(status_code, 200)
        self.assertIn("zip", content_type)
        self.assertGreater(len(body), 100)
        self.assertTrue(body.startswith(b"PK"))

    def test_reject_empty_export(self) -> None:
        status_code, body, _ = self.request("POST", "/api/export", {"name": "Empty", "apps": [], "tweaks": []})
        self.assertEqual(status_code, 400)
        self.assertIn("at least one", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()
