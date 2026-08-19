from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import parse_qs

from alientasks.caldav import CaldavError
from alientasks.ical import NEEDS_ACTION, Task
from alientasks.server import (
    TasksHandler,
    build_client,
    now_utc,
    parse_args,
    parse_form,
    selected_list,
)


class DummyClient:
    def __init__(self, tasks=None, error=None, toggle_error=None):
        self.collection = "/eve/tasks/"
        self.tasks = tasks or []
        self.error = error
        self.toggle_error = toggle_error
        self.toggled = []

    def list_tasks(self):
        if self.error:
            raise self.error
        return list(self.tasks)

    def toggle(self, href, completed, now):
        if self.toggle_error:
            raise self.toggle_error
        self.toggled.append((href, completed, now))


class DummyServer:
    def __init__(self, client):
        self.client = client


class Recorder:
    def __init__(self, client, path="/", body=b"", method="GET"):
        self.body = body
        self.command = method
        self.path = path
        self.headers = {"Content-Length": str(len(body))}
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


def test_post_rejects_bad_href_and_unknown_path():
    rec = Recorder(DummyClient(), "/toggle", body=b"href=/tmp/x.ics", method="POST")
    rec.handle()
    assert ("status", 400) in rec.sent

    rec = Recorder(DummyClient(), "/other", body=b"", method="POST")
    rec.handle()
    assert ("status", 404) in rec.sent


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
