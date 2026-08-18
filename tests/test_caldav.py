from datetime import UTC, datetime
from io import BytesIO

import pytest

from alientasks.caldav import CaldavClient, CaldavError, is_safe_href, parse_report_xml
from alientasks.ical import COMPLETED

NOW = datetime(2026, 8, 18, 23, 40, 0, tzinfo=UTC)

REPORT = """<?xml version='1.0' encoding='utf-8'?>
<multistatus xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <response>
    <href>/eve/tasks/one.ics</href>
    <propstat>
      <prop>
        <getetag>"etag-one"</getetag>
        <C:calendar-data>BEGIN:VCALENDAR
BEGIN:VTODO
UID:one
SUMMARY:Buy milk
CATEGORIES:Default
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR</C:calendar-data>
      </prop>
    </propstat>
  </response>
  <response>
    <href>/eve/tasks/</href>
    <propstat><prop><getetag>"col"</getetag></prop></propstat>
  </response>
  <response>
    <href>/eve/tasks/skip.ics</href>
    <propstat><prop><getetag>"x"</getetag></prop></propstat>
  </response>
</multistatus>
"""


def test_is_safe_href_accepts_collection_files_only():
    col = "/eve/tasks/"
    assert is_safe_href("/eve/tasks/abc.ics", col)
    assert not is_safe_href("/eve/tasks/../secret.ics", col)
    assert not is_safe_href("/eve/other/abc.ics", col)
    assert not is_safe_href("/eve/tasks/sub/abc.ics", col)
    assert not is_safe_href("/eve/tasks/", col)
    assert not is_safe_href("/eve/tasks/abc.txt", col)


def test_is_safe_href_adds_trailing_slash_on_collection():
    assert is_safe_href("/eve/tasks/a.ics", "/eve/tasks")


def test_parse_report_xml_skips_empty_resources():
    tasks = parse_report_xml(REPORT)
    assert len(tasks) == 1
    assert tasks[0].uid == "one"
    assert tasks[0].summary == "Buy milk"
    assert tasks[0].etag == '"etag-one"'


class FakeResponse:
    def __init__(self, body: bytes, headers=None):
        self.body = body
        self.headers = headers or {}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout=30):
        self.requests.append((request, timeout))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_client_report_and_list_tasks():
    opener = FakeOpener([FakeResponse(REPORT.encode())])
    client = CaldavClient("http://127.0.0.1:5232", "/eve/tasks/", opener=opener)
    tasks = client.list_tasks()
    assert [task.uid for task in tasks] == ["one"]
    method = opener.requests[0][0].get_method()
    assert method == "REPORT"


def test_client_sends_basic_auth():
    body = b"BEGIN:VTODO\nUID:one\nEND:VTODO\n"
    opener = FakeOpener([FakeResponse(body, {"ETag": '"e"'})])
    client = CaldavClient(
        "http://127.0.0.1:5232",
        "eve/tasks",
        user="eve",
        password="secret",
        opener=opener,
    )
    etag, body = client.get("/eve/tasks/one.ics")
    assert etag == '"e"'
    assert "UID:one" in body
    assert opener.requests[0][0].headers["Authorization"].startswith("Basic ")


def test_client_get_rejects_bad_href():
    client = CaldavClient("http://127.0.0.1:5232", "/eve/tasks/")
    with pytest.raises(CaldavError, match="Refusing href"):
        client.get("/tmp/x.ics")


def test_client_put_and_toggle(monkeypatch):
    ical = "BEGIN:VTODO\nUID:one\nSTATUS:NEEDS-ACTION\nEND:VTODO\n"
    opener = FakeOpener(
        [
            FakeResponse(ical.encode(), {"ETag": '"old"'}),
            FakeResponse(b""),
        ]
    )
    client = CaldavClient("http://127.0.0.1:5232", "/eve/tasks/", opener=opener)
    client.toggle("/eve/tasks/one.ics", True, NOW)
    put_req = opener.requests[1][0]
    assert put_req.get_method() == "PUT"
    assert put_req.headers["If-match"] == '"old"'
    payload = put_req.data.decode()
    assert "STATUS:COMPLETED" in payload


def test_client_put_rejects_bad_href():
    client = CaldavClient("http://127.0.0.1:5232", "/eve/tasks/")
    with pytest.raises(CaldavError, match="Refusing href"):
        client.put("/nope.ics", '"e"', "BEGIN:VTODO\nEND:VTODO\n")


def test_client_wraps_http_and_url_errors():
    import urllib.error

    http_err = urllib.error.HTTPError(
        "http://127.0.0.1:5232/eve/tasks/",
        500,
        "Boom",
        hdrs=None,
        fp=BytesIO(b""),
    )
    opener = FakeOpener([http_err])
    client = CaldavClient("http://127.0.0.1:5232", "/eve/tasks/", opener=opener)
    with pytest.raises(CaldavError, match="500"):
        client.report()

    opener = FakeOpener([urllib.error.URLError("down")])
    client = CaldavClient("http://127.0.0.1:5232", "/eve/tasks/", opener=opener)
    with pytest.raises(CaldavError, match="Cannot reach Radicale"):
        client.report()


def test_completed_constant_used_in_sample_xml():
    xml = REPORT.replace("NEEDS-ACTION", COMPLETED)
    tasks = parse_report_xml(xml)
    assert tasks[0].completed is True
