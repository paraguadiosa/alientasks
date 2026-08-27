from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import parse_qs

from alientasks.caldav import CaldavError
from alientasks.html import MAX_CATEGORY_CHARS, MAX_SUMMARY_CHARS
from alientasks.ical import NEEDS_ACTION, Task
from alientasks.server import (
    MAX_BODY_BYTES,
    TasksHandler,
    bind_notice,
    build_client,
    now_utc,
    parse_args,
    parse_form,
    same_origin,
    selected_list,
)


class DummyClient:
    def __init__(self, tasks=None, error=None, toggle_error=None, add_error=None):
        self.collection = "/eve/tasks/"
        self.tasks = tasks or []
        self.error = error
        self.toggle_error = toggle_error
        self.add_error = add_error
        self.toggled = []
        self.added = []

    def list_tasks(self):
        if self.error:
            raise self.error
        return list(self.tasks)

    def toggle(self, href, completed, now):
        if self.toggle_error:
            raise self.toggle_error
        self.toggled.append((href, completed, now))

    def add(self, summary, category, now, uid):
        if self.add_error:
            raise self.add_error
        self.added.append((summary, category, now, uid))


class DummyServer:
    def __init__(self, client):
        self.client = client


class Recorder:
    def __init__(self, client, path="/", body=b"", method="GET", headers=None):
        self.body = body
        self.command = method
        self.path = path
        self.headers = {"Content-Length": str(len(body)), **(headers or {})}
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self.server = DummyServer(client)
        self.client_address = ("127.0.0.1", 9)
        self.requestline = f"{method} {path} HTTP/1.1"
        self.request_version = "HTTP/1.1"
        self.sent = []
        self._headers = []
        self.handler = TasksHandler.__new__(TasksHandler)
        self.handler.server = self.server
        self.handler.path = path
        self.handler.headers = self.headers
        self.handler.rfile = self.rfile
        self.handler.wfile = self.wfile
        self.handler.client_address = self.client_address
        self.handler.requestline = self.requestline
        self.handler.command = method
        self.handler.request_version = "HTTP/1.1"
        self.handler.send_response = self.send_response
        self.handler.send_header = self.send_header
        self.handler.end_headers = self.end_headers
        self.handler.log_message = lambda *args, **kwargs: None

    def send_response(self, status, message=None):
        self.sent.append(("status", status))

    def send_header(self, key, value):
        self._headers.append((key, value))

    def end_headers(self):
        self.sent.append(("headers", list(self._headers)))
        self._headers = []

    def handle(self):
        if self.command == "GET":
            self.handler.do_GET()
        else:
            self.handler.do_POST()
        return self.handler


SAMPLE = [
    Task("/eve/tasks/one.ics", '"e"', "one", "Buy milk", "Default", NEEDS_ACTION, "")
]


def test_parse_form_and_selected_list():
    assert parse_form(b"href=%2Feve%2Ftasks%2Fa.ics&completed=1")["completed"] == "1"
    assert selected_list({}) == ""
    assert selected_list({"list": ["A", "B"]}) == "B"


def test_now_utc_is_timezone_aware():
    stamp = now_utc()
    assert stamp.tzinfo is UTC


def test_get_ok_and_404_and_503():
    rec = Recorder(DummyClient(SAMPLE), "/")
    rec.handle()
    assert ("status", 200) in rec.sent
    assert b"Buy milk" in rec.wfile.getvalue()

    rec = Recorder(DummyClient(SAMPLE), "/nope")
    rec.handle()
    assert ("status", 404) in rec.sent

    rec = Recorder(DummyClient(error=CaldavError("down")), "/")
    rec.handle()
    assert ("status", 503) in rec.sent
    assert b"down" in rec.wfile.getvalue()


def test_get_favicon():
    rec = Recorder(DummyClient(), "/favicon.svg")
    rec.handle()
    assert ("status", 200) in rec.sent
    headers = dict(rec.sent[-1][1])
    assert headers["Content-Type"] == "image/svg+xml"
    assert b"svg" in rec.wfile.getvalue()
    assert b"#00ff41" in rec.wfile.getvalue()


def test_get_static_assets_are_cached():
    rec = Recorder(DummyClient(), "/static/style.css?v=0.1.0")
    rec.handle()
    assert ("status", 200) in rec.sent
    headers = dict(rec.sent[-1][1])
    assert headers["Content-Type"] == "text/css; charset=utf-8"
    assert headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert b":root" in rec.wfile.getvalue()

    rec = Recorder(DummyClient(), "/static/app.js?v=0.1.0")
    rec.handle()
    assert ("status", 200) in rec.sent
    headers = dict(rec.sent[-1][1])
    assert headers["Content-Type"] == "text/javascript; charset=utf-8"
    assert b"theme-toggle" in rec.wfile.getvalue()


def test_get_static_unknown_is_404():
    for path in ["/static/nope.css", "/static/../server.py", "/static/style.css/../x"]:
        rec = Recorder(DummyClient(), path)
        rec.handle()
        assert ("status", 404) in rec.sent


def test_get_static_missing_file_is_404(monkeypatch):
    def missing(name):
        raise FileNotFoundError(name)

    monkeypatch.setattr("alientasks.server.read_static", missing)
    rec = Recorder(DummyClient(), "/static/style.css")
    rec.handle()
    assert ("status", 404) in rec.sent


def test_post_toggle_redirects(monkeypatch):
    fixed = datetime(2026, 8, 18, 23, 40, tzinfo=UTC)
    monkeypatch.setattr("alientasks.server.now_utc", lambda: fixed)
    client = DummyClient(SAMPLE)
    rec = Recorder(
        client,
        "/toggle",
        body=b"href=/eve/tasks/one.ics&completed=1&list=Default",
        method="POST",
    )
    rec.handle()
    assert ("status", 303) in rec.sent
    headers = dict(rec.sent[-1][1])
    assert headers["Location"].startswith("/?list=")
    assert client.toggled[0][0] == "/eve/tasks/one.ics"
    assert client.toggled[0][1] is True


def test_post_add_redirects(monkeypatch):
    fixed = datetime(2026, 8, 18, 23, 40, tzinfo=UTC)
    monkeypatch.setattr("alientasks.server.now_utc", lambda: fixed)
    monkeypatch.setattr("alientasks.server.new_uid", lambda: "abc123")
    client = DummyClient(SAMPLE)
    rec = Recorder(
        client,
        "/add",
        body=b"summary=Water+plants&category=Garden&list=Garden",
        method="POST",
    )
    rec.handle()
    assert ("status", 303) in rec.sent
    headers = dict(rec.sent[-1][1])
    assert headers["Location"] == "/?list=Garden"
    assert client.added[0] == ("Water plants", "Garden", fixed, "abc123")


def test_post_add_defaults_category_to_all_list(monkeypatch):
    monkeypatch.setattr("alientasks.server.new_uid", lambda: "abc123")
    client = DummyClient(SAMPLE)
    rec = Recorder(client, "/add", body=b"summary=x", method="POST")
    rec.handle()
    assert ("status", 303) in rec.sent
    assert client.added[0][1] == ""
    assert dict(rec.sent[-1][1])["Location"] == "/"


def test_post_add_requires_summary():
    client = DummyClient(SAMPLE)
    rec = Recorder(client, "/add", body=b"category=Garden", method="POST")
    rec.handle()
    assert ("status", 400) in rec.sent
    assert b"Summary is required" in rec.wfile.getvalue()
    assert client.added == []


def test_post_add_rejects_oversized_fields():
    long_summary = "x" * (MAX_SUMMARY_CHARS + 1)
    rec = Recorder(
        DummyClient(), "/add", body=f"summary={long_summary}".encode(), method="POST"
    )
    rec.handle()
    assert ("status", 400) in rec.sent
    assert b"Summary is too long" in rec.wfile.getvalue()

    long_category = "c" * (MAX_CATEGORY_CHARS + 1)
    rec = Recorder(
        DummyClient(),
        "/add",
        body=f"summary=x&category={long_category}".encode(),
        method="POST",
    )
    rec.handle()
    assert ("status", 400) in rec.sent
    assert b"Category is too long" in rec.wfile.getvalue()


def test_post_add_error_lists_when_possible():
    client = DummyClient(SAMPLE, add_error=CaldavError("read-only"))
    rec = Recorder(client, "/add", body=b"summary=x", method="POST")
    rec.handle()
    assert ("status", 502) in rec.sent
    assert b"read-only" in rec.wfile.getvalue()
    assert b"Buy milk" in rec.wfile.getvalue()


def test_post_rejects_bad_href_and_unknown_path():
    rec = Recorder(DummyClient(), "/toggle", body=b"href=/tmp/x.ics", method="POST")
    rec.handle()
    assert ("status", 400) in rec.sent

    rec = Recorder(DummyClient(), "/other", body=b"", method="POST")
    rec.handle()
    assert ("status", 404) in rec.sent


def test_same_origin_matches_host():
    assert same_origin("127.0.0.1:5233", "http://127.0.0.1:5233")
    assert same_origin("127.0.0.1:5233", "http://127.0.0.1:5233/toggle")
    assert not same_origin("127.0.0.1:5233", "https://evil.example")
    assert not same_origin("127.0.0.1:5233", "null")
    assert not same_origin("", "http://127.0.0.1:5233")
    assert same_origin("127.0.0.1:5233", None)


def test_post_rejects_cross_origin():
    rec = Recorder(
        DummyClient(),
        "/toggle",
        body=b"href=/eve/tasks/one.ics&completed=1",
        method="POST",
        headers={"Origin": "https://evil.example"},
    )
    rec.handle()
    assert ("status", 403) in rec.sent

    rec = Recorder(
        DummyClient(),
        "/toggle",
        body=b"href=/eve/tasks/one.ics&completed=1",
        method="POST",
        headers={"Referer": "https://evil.example/steal.html"},
    )
    rec.handle()
    assert ("status", 403) in rec.sent


def test_post_allows_same_origin_and_toggles():
    client = DummyClient(SAMPLE)
    rec = Recorder(
        client,
        "/toggle",
        body=b"href=/eve/tasks/one.ics&completed=1",
        method="POST",
        headers={"Origin": "http://127.0.0.1:5233", "Host": "127.0.0.1:5233"},
    )
    rec.handle()
    assert ("status", 303) in rec.sent
    assert client.toggled[0][0] == "/eve/tasks/one.ics"


def test_post_rejects_oversized_or_bad_content_length():
    rec = Recorder(
        DummyClient(),
        "/toggle",
        body=b"href=x",
        method="POST",
        headers={"Content-Length": str(MAX_BODY_BYTES + 1)},
    )
    rec.handle()
    assert ("status", 413) in rec.sent

    rec = Recorder(
        DummyClient(),
        "/toggle",
        body=b"href=x",
        method="POST",
        headers={"Content-Length": "huge"},
    )
    rec.handle()
    assert ("status", 400) in rec.sent


def test_post_toggle_error_lists_when_possible():
    client = DummyClient(SAMPLE, toggle_error=CaldavError("conflict"))
    rec = Recorder(
        client,
        "/toggle",
        body=b"href=/eve/tasks/one.ics&completed=1",
        method="POST",
    )
    rec.handle()
    assert ("status", 502) in rec.sent
    assert b"conflict" in rec.wfile.getvalue()
    assert b"Buy milk" in rec.wfile.getvalue()

    client = DummyClient(
        SAMPLE,
        error=CaldavError("down"),
        toggle_error=CaldavError("conflict"),
    )
    rec = Recorder(
        client,
        "/toggle",
        body=b"href=/eve/tasks/one.ics&completed=1",
        method="POST",
    )
    rec.handle()
    assert ("status", 502) in rec.sent


def test_parse_args_and_build_client(monkeypatch):
    args = parse_args(
        ["--host", "0.0.0.0", "--port", "5999", "--collection", "eve/tasks"]
    )
    assert args.host == "0.0.0.0"
    assert args.port == 5999
    monkeypatch.delenv("RADICALE_PASSWORD", raising=False)
    client = build_client(args)
    assert client.collection == "/eve/tasks/"
    assert client._auth is None
    monkeypatch.setenv("RADICALE_PASSWORD", "pw")
    args = parse_args([])
    client = build_client(args)
    assert client._auth is not None


def test_bind_notice_only_for_non_loopback():
    assert bind_notice("") is None
    assert bind_notice("localhost") is None
    assert bind_notice("127.0.0.1") is None
    assert bind_notice("::1") is None
    notice = bind_notice("100.99.112.42")
    assert notice is not None
    assert "no login" in notice
    assert "100.99.112.42" in notice


def test_parse_qs_used_for_list_filter():
    query = parse_qs("list=Default")
    assert selected_list(query) == "Default"


def test_handler_log_message(capsys):
    handler = TasksHandler.__new__(TasksHandler)
    handler.client_address = ("127.0.0.1", 1)
    handler.log_message("%s", "ping")
    assert "ping" in capsys.readouterr().err


def test_main_starts_and_stops(monkeypatch):
    from alientasks import server as server_mod

    class FakeServer:
        def __init__(self, addr, handler):
            self.addr = addr
            self.handler = handler
            self.client = None

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(server_mod, "ThreadingHTTPServer", FakeServer)
    server_mod.main(["--host", "127.0.0.1", "--port", "5233"])
