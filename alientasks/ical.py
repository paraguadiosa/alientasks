"""Parse and update VTODO iCalendar text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

COMPLETED = "COMPLETED"
NEEDS_ACTION = "NEEDS-ACTION"
INBOX = "Inbox"


@dataclass(frozen=True)
class Task:
    """One VTODO item from a CalDAV collection."""

    href: str
    etag: str
    uid: str
    summary: str
    category: str
    status: str
    raw_ical: str

    @property
    def completed(self) -> bool:
        """Return True when the task is done."""
        return self.status.upper() == COMPLETED


def unfold_ical(text: str) -> str:
    """Join RFC 5545 folded lines."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in normalized.split("\n"):
        if lines and line[:1] in {" ", "\t"}:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return "\n".join(lines)


def unescape_ical(value: str) -> str:
    """Decode RFC 5545 TEXT escapes."""
    out: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt in {"\\", ";", ",", "N"}:
                out.append("\n" if nxt == "N" else nxt)
            else:
                out.append(nxt)
            index += 2
            continue
        out.append(value[index])
        index += 1
    return "".join(out)


def parse_properties(block: str) -> dict[str, str]:
    """Parse the first value of each property name in an unfolded block."""
    props: dict[str, str] = {}
    for line in unfold_ical(block).split("\n"):
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        key = name.split(";", 1)[0].upper()
        if key not in props:
            props[key] = value
    return props


def first_category(raw: str) -> str:
    """Return the first CATEGORIES value, or Inbox."""
    if not raw.strip():
        return INBOX
    return unescape_ical(raw.split(",", 1)[0]).strip() or INBOX


def parse_vtodo(href: str, etag: str, ical_text: str) -> Task | None:
    """Build a Task from one calendar resource. Return None if no VTODO."""
    unfolded = unfold_ical(ical_text)
    start = unfolded.find("BEGIN:VTODO")
    end = unfolded.find("END:VTODO")
    if start < 0 or end < 0:
        return None
    props = parse_properties(unfolded[start:end])
    uid = props.get("UID", "").strip()
    if not uid:
        return None
    return Task(
        href=href,
        etag=etag.strip(),
        uid=uid,
        summary=unescape_ical(props.get("SUMMARY", "")).strip() or uid,
        category=first_category(props.get("CATEGORIES", "")),
        status=props.get("STATUS", NEEDS_ACTION).strip() or NEEDS_ACTION,
        raw_ical=ical_text,
    )


def group_by_category(tasks: list[Task]) -> dict[str, list[Task]]:
    """Group tasks by category. Keep category name order stable."""
    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        grouped.setdefault(task.category, []).append(task)
    for items in grouped.values():
        items.sort(key=lambda item: (item.completed, item.summary.lower()))
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def utc_stamp(now: datetime) -> str:
    """Format a UTC datetime as iCalendar TIMESTAMP."""
    return now.strftime("%Y%m%dT%H%M%SZ")


def _replace_or_drop(lines: list[str], name: str, value: str | None) -> list[str]:
    """Remove NAME lines. Insert NAME:value before END:VTODO when value is set."""
    prefix = f"{name}:"
    prefix_param = f"{name};"
    kept = [
        line
        for line in lines
        if not line.upper().startswith(prefix)
        and not line.upper().startswith(prefix_param)
    ]
    if value is None:
        return kept
    out: list[str] = []
    inserted = False
    for line in kept:
        if line.upper() == "END:VTODO" and not inserted:
            out.append(f"{name}:{value}")
            inserted = True
        out.append(line)
    if not inserted:
        out.append(f"{name}:{value}")
    return out


def _bump_sequence(lines: list[str]) -> list[str]:
    """Increment SEQUENCE, or add SEQUENCE:1."""
    current = 0
    for line in lines:
        if line.upper().startswith("SEQUENCE:"):
            raw = line.split(":", 1)[1].strip()
            if raw.isdigit():
                current = int(raw)
    return _replace_or_drop(lines, "SEQUENCE", str(current + 1))


def toggle_ical(ical_text: str, *, completed: bool, now: datetime) -> str:
    """Return iCalendar text with the VTODO marked done or open."""
    unfolded = unfold_ical(ical_text)
    start = unfolded.find("BEGIN:VTODO")
    end = unfolded.find("END:VTODO")
    if start < 0 or end < 0:
        raise ValueError("No VTODO block in calendar text.")
    end += len("END:VTODO")
    head = unfolded[:start]
    body = unfolded[start:end]
    tail = unfolded[end:]
    lines = body.split("\n")
    stamp = utc_stamp(now)
    lines = _replace_or_drop(lines, "DTSTAMP", stamp)
    lines = _bump_sequence(lines)
    if completed:
        lines = _replace_or_drop(lines, "STATUS", COMPLETED)
        lines = _replace_or_drop(lines, "PERCENT-COMPLETE", "100")
        lines = _replace_or_drop(lines, "COMPLETED", stamp)
    else:
        lines = _replace_or_drop(lines, "STATUS", NEEDS_ACTION)
        lines = _replace_or_drop(lines, "PERCENT-COMPLETE", None)
        lines = _replace_or_drop(lines, "COMPLETED", None)
    updated = head + "\n".join(lines) + tail
    return updated.replace("\n", "\r\n")
