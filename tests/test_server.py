"""
HTTP layer: routing, session isolation, static file safety, and error handling.

Runs a real `ThreadingHTTPServer` on an ephemeral port and talks to it with
`urllib`, so the tests exercise the actual request path rather than calling
handler methods directly.
"""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from incgame.server import serve


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Port 0 lets the OS pick, so the suite cannot collide with a dev server.
        cls.httpd, cls.url = serve(host="127.0.0.1", port=0)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def request(self, path, method="GET", body=None, session="test", raw=False):
        url = self.url.rstrip("/") + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-Session", session)
        if data:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = response.read()
            return payload if raw else json.loads(payload)


class TestApi(ServerTestCase):
    def test_new_game_with_a_seed_is_reproducible(self):
        first = self.request("/api/new", "POST", {"seed": 4242}, session="a")
        second = self.request("/api/new", "POST", {"seed": 4242}, session="b")
        self.assertEqual(first["title"], second["title"])
        self.assertEqual(first["seed"], 4242)
        self.assertIn("definition", first)

    def test_state_omits_the_definition_by_default(self):
        self.request("/api/new", "POST", {"seed": 1}, session="c")
        self.assertNotIn("definition", self.request("/api/state", session="c"))
        self.assertIn("definition", self.request("/api/state?full=1", session="c"))

    def test_sessions_are_isolated(self):
        one = self.request("/api/new", "POST", {"seed": 111}, session="s1")
        two = self.request("/api/new", "POST", {"seed": 222}, session="s2")
        self.assertNotEqual(one["seed"], two["seed"])
        # Acting in one session must not move the other.
        action = next(a for a in one["actions"] if a["unlocked"])
        self.request("/api/action", "POST", {"id": action["id"]}, session="s1")
        self.assertEqual(self.request("/api/state", session="s2")["stats"]["actions"], 0)

    def test_action_returns_result_and_fresh_state(self):
        state = self.request("/api/new", "POST", {"seed": 7}, session="d")
        action = next(a for a in state["actions"] if a["unlocked"])
        response = self.request("/api/action", "POST", {"id": action["id"]}, session="d")
        self.assertTrue(response["result"]["ok"])
        self.assertEqual(response["stats"]["actions"], 1)
        produced = next(iter(response["result"]["gained"]))
        amount = next(r["amount"] for r in response["resources"] if r["id"] == produced)
        self.assertGreater(amount, 0)

    def test_bad_ids_are_refused_without_a_500(self):
        self.request("/api/new", "POST", {"seed": 7}, session="e")
        for path in ("/api/action", "/api/upgrade", "/api/generator", "/api/prestige-upgrade"):
            response = self.request(path, "POST", {"id": "nope"}, session="e")
            self.assertFalse(response["result"]["ok"], path)

    def test_save_and_load_round_trip_over_http(self):
        state = self.request("/api/new", "POST", {"seed": 31337}, session="f")
        action = next(a for a in state["actions"] if a["unlocked"])
        for _ in range(5):
            self.request("/api/action", "POST", {"id": action["id"]}, session="f")

        blob = self.request("/api/save", session="f")
        loaded = self.request("/api/load", "POST", {"save": blob}, session="g")
        self.assertEqual(loaded["seed"], 31337)
        self.assertEqual(loaded["stats"]["actions"], 5)

    def test_corrupt_save_returns_a_readable_error(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/load", "POST", {"save": {"save_version": 999}}, session="h")
        self.assertEqual(caught.exception.code, 400)
        detail = json.loads(caught.exception.read())
        self.assertIn("could not load save", detail["error"])

    def test_non_integer_seed_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/new", "POST", {"seed": "banana"}, session="i")
        self.assertEqual(caught.exception.code, 400)

    def test_unknown_endpoint_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/nonsense", session="j")
        self.assertEqual(caught.exception.code, 404)

    def test_malformed_json_body_is_400_not_500(self):
        url = self.url.rstrip("/") + "/api/action"
        req = urllib.request.Request(url, data=b"{{{not json", method="POST")
        req.add_header("X-Session", "k")
        req.add_header("Content-Type", "application/json")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(caught.exception.code, 400)


class TestStatic(ServerTestCase):
    def test_index_is_served(self):
        body = self.request("/", raw=True)
        self.assertIn(b"<!doctype html>", body.lower())

    def test_assets_are_served_with_types(self):
        url = self.url.rstrip("/") + "/css/style.css"
        with urllib.request.urlopen(url, timeout=10) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("css", response.headers.get("Content-Type", ""))

    def test_path_traversal_is_blocked(self):
        # urllib normalises "..", so the escape attempt is percent-encoded to make
        # sure the check happens server-side rather than in the client.
        for attempt in ("/%2e%2e/%2e%2e/etc/passwd", "/../incgame/server.py", "/css/../../setup.py"):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.request(attempt, raw=True)
            self.assertIn(caught.exception.code, (403, 404), attempt)

    def test_missing_file_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/no/such/file.js", raw=True)
        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
