"""Local HTTP server for the tasks UI."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse, urlsplit

from alientasks.caldav import CaldavClient, CaldavError, is_safe_href
from alientasks.html import (
    ALL_LIST,
    FAVICON_SVG,
    MAX_CATEGORY_CHARS,
    MAX_SUMMARY_CHARS,
    redirect_location,
    render_page,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5233
DEFAULT_RADICALE = "http://127.0.0.1:5232"
DEFAULT_COLLECTION = "/eve/tasks/"
DEFAULT_USER = "eve"

MAX_BODY_BYTES = 64 * 1024

STATIC_TYPES = {
    "style.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
STATIC_CACHE = "public, max-age=31536000, immutable"


def now_utc():
    """Return the current UTC time. Tests replace this."""
    return datetime.now(UTC)


def new_uid() -> str:
    """Return a fresh resource id for a new task."""
    return uuid.uuid4().hex


def same_origin(host: str, value: str | None) -> bool:
    """True when an Origin/Referer value matches the Host header."""
    if not value:
        return True
    try:
        netloc = urlsplit(value).netloc
    except ValueError:
        return False
    return bool(host) and netloc == host


def parse_form(body: bytes) -> dict[str, str]:
    """Parse an application/x-www-form-urlencoded body."""
    parsed = parse_qs(body.decode(), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def bind_notice(host: str) -> str | None:
    """Return a warning when the UI binds to a non-loopback address."""
    if host in {"", "localhost", "127.0.0.1", "::1"}:
        return None
    return (
        f"The UI binds to {host} and has no login. "
        "Any device that can reach this address can change your tasks."
    )


def selected_list(query: dict[str, list[str]]) -> str:
    """Read the list filter from a query string."""
    values = query.get("list", [])
    return values[-1] if values else ALL_LIST


def read_static(name: str) -> bytes:
    """Read one packaged static asset. Raise FileNotFoundError if absent."""
    return (resources.files("alientasks") / "static" / name).read_bytes()


class TasksHandler(BaseHTTPRequestHandler):
    """Serve the list page and accept checkbox toggles."""

    server_version = "Alientasks/0.1"

    def log_message(self, format, *args):
        """Write access lines to stderr."""
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    @property
    def client(self) -> CaldavClient:
        return self.server.client  # type: ignore[attr-defined]

    def _send(self, status: int, body: bytes, content_type: str, extra=None) -> None:
        headers = {"Cache-Control": "no-store", **(extra or {})}
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status: int, tasks, current: str, error: str | None = None) -> None:
        page = render_page(tasks, current, error)
        self._send(status, page.encode(), "text/html; charset=utf-8")

    def _send_static(self, name: str) -> bool:
        """Serve a whitelisted static asset. Return True when served."""
        if name not in STATIC_TYPES:
            return False
        try:
            body = read_static(name)
        except FileNotFoundError:
            return False
        self._send(200, body, STATIC_TYPES[name], {"Cache-Control": STATIC_CACHE})
        return True

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.svg":
            self._send(200, FAVICON_SVG.encode(), "image/svg+xml")
            return
        if parsed.path.startswith("/static/"):
            if not self._send_static(parsed.path.removeprefix("/static/")):
                self._send(404, b"Not found\n", "text/plain; charset=utf-8")
            return
        if parsed.path != "/":
            self._send(404, b"Not found\n", "text/plain; charset=utf-8")
            return
        current = selected_list(parse_qs(parsed.query))
        try:
            tasks = self.client.list_tasks()
        except CaldavError as exc:
            self._html(503, [], current, str(exc))
            return
        self._html(200, tasks, current)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/toggle", "/add"}:
            self._send(404, b"Not found\n", "text/plain; charset=utf-8")
            return
        form = self._read_form()
        if form is None:
            return
        current = form.get("list", ALL_LIST)
        if parsed.path == "/add":
            self._add_task(form, current)
            return
        self._toggle_task(form, current)

    def _read_form(self) -> dict[str, str] | None:
        """Read a form body. Send an error and return None when rejected."""
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        if not same_origin(self.headers.get("Host", ""), origin):
            self._send(
                403, b"Cross-origin request rejected\n", "text/plain; charset=utf-8"
            )
            return None
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            self._send(400, b"Bad Content-Length\n", "text/plain; charset=utf-8")
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            self._send(413, b"Request body too large\n", "text/plain; charset=utf-8")
            return None
        return parse_form(self.rfile.read(length))

    def _render_error(self, status: int, current: str, message: str) -> None:
        """Render the page with an alert, listing tasks when possible."""
        try:
            tasks = self.client.list_tasks()
        except CaldavError:
            tasks = []
        self._html(status, tasks, current, message)

    def _toggle_task(self, form: dict[str, str], current: str) -> None:
        href = form.get("href", "")
        completed = form.get("completed") == "1"
        if not is_safe_href(href, self.client.collection):
            self._render_error(400, current, "Invalid task link.")
            return
        try:
            self.client.toggle(href, completed, now_utc())
        except CaldavError as exc:
            self._render_error(502, current, str(exc))
            return
        location = redirect_location(current)
        self._send(303, b"", "text/plain; charset=utf-8", {"Location": location})

    def _add_task(self, form: dict[str, str], current: str) -> None:
        summary = form.get("summary", "").strip()
        category = form.get("category", "").strip()
        if not summary:
            self._render_error(400, current, "Summary is required.")
            return
        if len(summary) > MAX_SUMMARY_CHARS:
            self._render_error(400, current, "Summary is too long.")
            return
        if len(category) > MAX_CATEGORY_CHARS:
            self._render_error(400, current, "Category is too long.")
            return
        try:
            self.client.add(summary, category, now_utc(), new_uid())
        except CaldavError as exc:
            self._render_error(502, current, str(exc))
            return
        location = redirect_location(current)
        self._send(303, b"", "text/plain; charset=utf-8", {"Location": location})


def build_client(args) -> CaldavClient:
    """Build the CalDAV client from flags and the environment."""
    password = args.password or os.environ.get("RADICALE_PASSWORD")
    user = args.user
    if not password:
        user = None
    return CaldavClient(args.radicale, args.collection, user=user, password=password)


def parse_args(argv: list[str] | None = None):
    """Parse server CLI flags."""
    parser = argparse.ArgumentParser(description="MVP web UI for Radicale tasks.")
    parser.add_argument("--host", default=os.environ.get("TASKS_UI_HOST", DEFAULT_HOST))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("TASKS_UI_PORT", str(DEFAULT_PORT))),
    )
    parser.add_argument(
        "--radicale",
        default=os.environ.get("RADICALE_URL", DEFAULT_RADICALE),
    )
    parser.add_argument(
        "--collection",
        default=os.environ.get("RADICALE_COLLECTION", DEFAULT_COLLECTION),
    )
    parser.add_argument("--user", default=os.environ.get("RADICALE_USER", DEFAULT_USER))
    parser.add_argument("--password", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Start the HTTP server."""
    args = parse_args(argv)
    notice = bind_notice(args.host)
    if notice:
        print(f"WARNING: {notice}", flush=True)
    httpd = ThreadingHTTPServer((args.host, args.port), TasksHandler)
    httpd.client = build_client(args)
    print(f"Alientasks on http://{args.host}:{args.port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
