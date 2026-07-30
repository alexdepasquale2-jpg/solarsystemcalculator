"""
Local HTTP server: JSON API plus static frontend.

Built on `http.server` from the standard library, with no third-party
dependencies at all. That is a deliberate constraint: the game runs with a bare
Python install and `python -m incgame serve`, which means no install step between
cloning and playing, and nothing to break in CI.

It is a single-player local server. It binds to 127.0.0.1 by default, keeps
sessions in memory, and does no authentication -- do not expose it to a network
you do not control.
"""

from __future__ import annotations

import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .engine import GameEngine
from .generator import generate_game, random_seed
from .save import SaveError, dump_save, load_save
from .view import state_payload

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
# Cap request bodies. The largest legitimate POST is an imported save.
MAX_BODY_BYTES = 512 * 1024


class Sessions:
    """
    In-memory game sessions, keyed by a client-supplied id.

    A lock guards the whole map because `ThreadingHTTPServer` serves each request
    on its own thread and the engine is not thread-safe: two concurrent clicks on
    the same session would otherwise interleave inside `advance()`.
    """

    def __init__(self) -> None:
        self._games: Dict[str, GameEngine] = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str, seed: Optional[int] = None) -> GameEngine:
        with self._lock:
            engine = self._games.get(key)
            if engine is None:
                engine = GameEngine(generate_game(seed if seed is not None else random_seed()))
                self._games[key] = engine
            return engine

    def replace(self, key: str, engine: GameEngine) -> GameEngine:
        with self._lock:
            self._games[key] = engine
            return engine

    def lock_for(self, key: str) -> threading.Lock:
        return self._lock


SESSIONS = Sessions()


class GameHandler(BaseHTTPRequestHandler):
    server_version = "incgame/0.1"

    # -- plumbing ----------------------------------------------------------

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        if os.environ.get("INCGAME_VERBOSE"):
            super().log_message(format, *args)

    def _session_key(self) -> str:
        return self.headers.get("X-Session") or "local"

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        return data if isinstance(data, dict) else {}

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"ok": False, "error": message}, status=status)

    # -- routing -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        try:
            if route.startswith("/api"):
                self._handle_api_get(route, parse_qs(parsed.query))
            else:
                self._serve_static(parsed.path)
        except BrokenPipeError:
            pass  # client navigated away mid-response
        except Exception as exc:  # noqa: BLE001 - never take the server down
            self._send_error_json(f"{type(exc).__name__}: {exc}", status=500)

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path.rstrip("/") or "/"
        try:
            body = self._read_json()
        except ValueError as exc:
            self._send_error_json(str(exc))
            return
        try:
            self._handle_api_post(route, body)
        except BrokenPipeError:
            pass
        except Exception as exc:  # noqa: BLE001
            self._send_error_json(f"{type(exc).__name__}: {exc}", status=500)

    def _handle_api_get(self, route: str, query: Dict[str, list]) -> None:
        key = self._session_key()

        if route == "/api/state":
            engine = SESSIONS.get_or_create(key)
            with SESSIONS.lock_for(key):
                self._send_json(state_payload(engine, include_def="full" in query))
            return

        if route == "/api/definition":
            engine = SESSIONS.get_or_create(key)
            self._send_json(engine.game.to_dict())
            return

        if route == "/api/save":
            engine = SESSIONS.get_or_create(key)
            with SESSIONS.lock_for(key):
                self._send_json(dump_save(engine))
            return

        self._send_error_json("unknown endpoint", status=404)

    def _handle_api_post(self, route: str, body: Dict[str, Any]) -> None:
        key = self._session_key()

        if route == "/api/new":
            seed = body.get("seed")
            try:
                seed_value = int(seed) if seed not in (None, "") else random_seed()
            except (TypeError, ValueError):
                self._send_error_json("seed must be an integer")
                return
            engine = SESSIONS.replace(key, GameEngine(generate_game(seed_value)))
            self._send_json(state_payload(engine, include_def=True))
            return

        if route == "/api/load":
            try:
                engine = load_save(body.get("save") or body)
            except SaveError as exc:
                self._send_error_json(f"could not load save: {exc}")
                return
            SESSIONS.replace(key, engine)
            self._send_json(state_payload(engine, include_def=True))
            return

        engine = SESSIONS.get_or_create(key)
        handlers: Dict[str, Callable[[GameEngine, Dict[str, Any]], Dict[str, Any]]] = {
            "/api/action": lambda e, b: e.do_action(str(b.get("id", ""))),
            "/api/generator": lambda e, b: e.buy_generator(str(b.get("id", "")), b.get("count", 1)),
            "/api/upgrade": lambda e, b: e.buy_upgrade(str(b.get("id", ""))),
            "/api/prestige": lambda e, b: e.prestige(),
            "/api/prestige-upgrade": lambda e, b: e.buy_prestige_upgrade(str(b.get("id", ""))),
            "/api/tick": lambda e, b: {"ok": True},
        }
        handler = handlers.get(route)
        if handler is None:
            self._send_error_json("unknown endpoint", status=404)
            return

        with SESSIONS.lock_for(key):
            result = handler(engine, body)
            payload = state_payload(engine)
        payload["result"] = result
        self._send_json(payload)

    # -- static files ------------------------------------------------------

    def _serve_static(self, path: str) -> None:
        """
        Serve the frontend, resolving paths inside FRONTEND_DIR only.

        The containment check uses the *resolved* path, so `..` segments and
        symlinks both fail closed rather than escaping the directory.
        """
        relative = path.lstrip("/") or "index.html"
        target = (FRONTEND_DIR / relative).resolve()
        try:
            target.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._send_error_json("forbidden", status=403)
            return

        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self._send_error_json("not found", status=404)
            return

        content_type, _ = mimetypes.guess_type(str(target))
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        # The game is served from disk and reloaded constantly during development.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def serve(host: str = "127.0.0.1", port: int = 8000, seed: Optional[int] = None) -> Tuple[ThreadingHTTPServer, str]:
    """
    Start the server and return it along with its URL.

    Returns rather than blocking so tests can drive it on a background thread;
    the CLI is what calls `serve_forever()`.
    """
    if seed is not None:
        SESSIONS.replace("local", GameEngine(generate_game(seed)))
    httpd = ThreadingHTTPServer((host, port), GameHandler)
    httpd.daemon_threads = True
    actual_port = httpd.server_address[1]
    return httpd, f"http://{host}:{actual_port}/"
