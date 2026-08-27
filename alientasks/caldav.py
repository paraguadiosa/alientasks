"""Talk to a Radicale CalDAV collection."""

from __future__ import annotations

import base64
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from alientasks.ical import Task, parse_vtodo

DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"
NS = {"d": DAV, "c": CALDAV}

REPORT_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    f'<C:calendar-query xmlns:C="{CALDAV}" xmlns:D="{DAV}">'
    "<D:prop><D:getetag/><C:calendar-data/></D:prop>"
    '<C:filter><C:comp-filter name="VCALENDAR"/></C:filter>'
    "</C:calendar-query>"
)


def is_safe_href(href: str, collection: str) -> bool:
    """Return True when href is a file inside the given collection."""
    prefix = collection if collection.endswith("/") else collection + "/"
    if not href.startswith(prefix):
        return False
    if ".." in href:
        return False
    name = href[len(prefix) :]
    return bool(name) and "/" not in name and name.endswith(".ics")


class CaldavError(RuntimeError):
    """A CalDAV request failed."""


class CaldavClient:
    """Minimal CalDAV client for one VTODO collection."""

    def __init__(
        self,
        base_url: str,
        collection: str,
        user: str | None = None,
        password: str | None = None,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection if collection.startswith("/") else "/" + collection
        if not self.collection.endswith("/"):
            self.collection += "/"
        self._opener = opener or urllib.request.build_opener()
        self._auth = None
        if user and password:
            token = base64.b64encode(f"{user}:{password}".encode()).decode()
            self._auth = f"Basic {token}"

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(extra or {})
        if self._auth:
            headers["Authorization"] = self._auth
        return headers

    def _open(self, request: urllib.request.Request, timeout: int = 30):
        try:
            return self._opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            raise CaldavError(
                f"{exc.code} {exc.reason} for {request.full_url}"
            ) from exc
        except urllib.error.URLError as exc:
            raise CaldavError(f"Cannot reach Radicale: {exc.reason}") from exc

    def report(self) -> str:
        """Return the raw calendar-query REPORT body."""
        url = f"{self.base_url}{self.collection}"
        request = urllib.request.Request(
            url,
            data=REPORT_BODY.encode(),
            method="REPORT",
            headers=self._headers(
                {"Content-Type": "application/xml; charset=utf-8", "Depth": "1"}
            ),
        )
        with self._open(request) as response:
            return response.read().decode()

    def get(self, href: str) -> tuple[str, str]:
        """Return (etag, ical text) for one resource."""
        if not is_safe_href(href, self.collection):
            raise CaldavError("Refusing href outside the tasks collection.")
        request = urllib.request.Request(
            f"{self.base_url}{href}",
            method="GET",
            headers=self._headers(),
        )
        with self._open(request) as response:
            etag = response.headers.get("ETag", "").strip()
            return etag, response.read().decode()

    def put(self, href: str, etag: str, ical_text: str) -> None:
        """Overwrite one resource. Send If-Match when etag is present."""
        if not is_safe_href(href, self.collection):
            raise CaldavError("Refusing href outside the tasks collection.")
        headers = {"Content-Type": "text/calendar; charset=utf-8"}
        if etag:
            headers["If-Match"] = etag
        request = urllib.request.Request(
            f"{self.base_url}{href}",
            data=ical_text.encode(),
            method="PUT",
            headers=self._headers(headers),
        )
        with self._open(request):
            return None

    def list_tasks(self) -> list[Task]:
        """Return every VTODO in the collection."""
        return parse_report_xml(self.report())

    def toggle(self, href: str, completed: bool, now) -> None:
        """Mark a task done or open and write it back."""
        from alientasks.ical import toggle_ical

        etag, ical_text = self.get(href)
        self.put(href, etag, toggle_ical(ical_text, completed=completed, now=now))

    def add(self, summary: str, category: str, now, uid: str) -> str:
        """Create one new VTODO in the collection and return its href."""
        from alientasks.ical import new_todo_ical

        href = f"{self.collection}{uid}.ics"
        if not is_safe_href(href, self.collection):
            raise CaldavError("Refusing href outside the tasks collection.")
        self.put(href, "", new_todo_ical(summary, category, now, uid))
        return href


def parse_report_xml(xml_text: str) -> list[Task]:
    """Parse a CalDAV multistatus REPORT into Task values."""
    root = ET.fromstring(xml_text)
    tasks: list[Task] = []
    for response in root.findall("d:response", NS):
        href = (response.findtext("d:href", default="", namespaces=NS) or "").strip()
        prop = response.find("d:propstat/d:prop", NS)
        if prop is None:
            continue
        etag = (prop.findtext("d:getetag", default="", namespaces=NS) or "").strip()
        data = prop.findtext("c:calendar-data", default="", namespaces=NS) or ""
        if not data.strip():
            continue
        task = parse_vtodo(href, etag, data)
        if task is not None:
            tasks.append(task)
    return tasks
