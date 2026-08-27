from datetime import UTC, datetime

from alientasks.ical import (
    COMPLETED,
    INBOX,
    NEEDS_ACTION,
    Task,
    escape_ical,
    first_category,
    group_by_category,
    new_todo_ical,
    parse_properties,
    parse_vtodo,
    toggle_ical,
    unescape_ical,
    unfold_ical,
    utc_stamp,
)

NOW = datetime(2026, 8, 18, 23, 40, 0, tzinfo=UTC)

FOLDED = (
    "BEGIN:VCALENDAR\n"
    "BEGIN:VTODO\n"
    "UID:abc\n"
    "SUMMARY:https://example.com/foo-\n"
    " bar\n"
    "CATEGORIES:Proyectitos\n"
    "STATUS:NEEDS-ACTION\n"
    "END:VTODO\n"
    "END:VCALENDAR\n"
)


def test_unfold_joins_continuation_lines():
    folded = unfold_ical("SUMMARY:hello\n world\r\n")
    assert "SUMMARY:helloworld" in folded
    spaced = unfold_ical("SUMMARY:hello \n world\r\n")
    assert "SUMMARY:hello world" in spaced


def test_unescape_ical_sequences():
    assert unescape_ical(r"a\;b\,c\\d\n e") == "a;b,c\\d\n e"
    assert unescape_ical(r"line\Nnext") == "line\nnext"
    assert unescape_ical(r"keep\x") == "keepx"


def test_parse_properties_keeps_first_and_strips_params():
    props = parse_properties("SUMMARY;LANGUAGE=es:Hola\nSUMMARY:Other\nNOCOLON\n")
    assert props["SUMMARY"] == "Hola"


def test_first_category_defaults_and_splits():
    assert first_category("") == INBOX
    assert first_category("  ") == INBOX
    assert first_category("Proyectitos,Other") == "Proyectitos"


def test_first_category_respects_escaped_comma():
    assert first_category(r"A\,B,C") == "A,B"
    # A doubled backslash is a literal backslash: the comma after it splits.
    assert first_category(r"A\\,B") == "A\\"


def test_parse_vtodo_reads_folded_summary():
    task = parse_vtodo("/eve/tasks/abc.ics", '"etag1"', FOLDED)
    assert task is not None
    assert task.uid == "abc"
    assert task.summary == "https://example.com/foo-bar"
    assert task.category == "Proyectitos"
    assert task.completed is False


def test_parse_vtodo_returns_none_without_block_or_uid():
    assert parse_vtodo("/x", "", "BEGIN:VCALENDAR\nEND:VCALENDAR\n") is None
    assert parse_vtodo("/x", "", "BEGIN:VTODO\nEND:VTODO\n") is None


def test_parse_vtodo_ignores_end_before_begin():
    text = "END:VTODO\nBEGIN:VTODO\nUID:one\nSUMMARY:First\nEND:VTODO\n"
    task = parse_vtodo("/x", "", text)
    assert task is not None
    assert task.uid == "one"
    assert task.summary == "First"


def test_parse_vtodo_takes_first_block():
    text = (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VTODO\nUID:one\nSUMMARY:First\nEND:VTODO\n"
        "BEGIN:VTODO\nUID:two\nSUMMARY:Second\nEND:VTODO\n"
        "END:VCALENDAR\n"
    )
    task = parse_vtodo("/eve/tasks/one.ics", "", text)
    assert task is not None
    assert task.uid == "one"


def test_parse_vtodo_uses_uid_when_summary_missing():
    text = "BEGIN:VTODO\nUID:only-id\nEND:VTODO\n"
    task = parse_vtodo("/eve/tasks/only-id.ics", "", text)
    assert task is not None
    assert task.summary == "only-id"
    assert task.category == INBOX


def test_group_by_category_sorts_lists_and_done_last():
    tasks = [
        Task("/a", "", "a", "Zebra", "B", NEEDS_ACTION, ""),
        Task("/b", "", "b", "Done", "A", COMPLETED, ""),
        Task("/c", "", "c", "Open", "A", NEEDS_ACTION, ""),
    ]
    grouped = group_by_category(tasks)
    assert list(grouped) == ["A", "B"]
    assert [item.summary for item in grouped["A"]] == ["Open", "Done"]


def test_utc_stamp_format():
    assert utc_stamp(NOW) == "20260818T234000Z"


def test_escape_ical_sequences():
    assert escape_ical("a;b,c\\d\ne") == r"a\;b\,c\\d\ne"
    assert escape_ical("plain") == "plain"
    assert escape_ical("") == ""


def test_new_todo_ical_builds_a_parsable_vtodo():
    text = new_todo_ical("Water plants", "Garden", NOW, "abc123")
    assert text.startswith("BEGIN:VCALENDAR")
    assert "\r\n" in text
    task = parse_vtodo("/eve/tasks/abc123.ics", '"e"', text)
    assert task is not None
    assert task.uid == "abc123"
    assert task.summary == "Water plants"
    assert task.category == "Garden"
    assert task.completed is False


def test_new_todo_ical_escapes_text_and_defaults_category():
    text = new_todo_ical("A; B, C\\D", "", NOW, "x")
    assert r"SUMMARY:A\; B\, C\\D" in text
    assert f"CATEGORIES:{INBOX}" in text
    assert "STATUS:NEEDS-ACTION" in text
    assert "SEQUENCE:0" in text
    assert "DTSTAMP:20260818T234000Z" in text


def test_toggle_ical_completes_and_reopens():
    done = toggle_ical(FOLDED, completed=True, now=NOW)
    assert "STATUS:COMPLETED" in done
    assert "PERCENT-COMPLETE:100" in done
    assert "COMPLETED:20260818T234000Z" in done
    assert "SEQUENCE:1" in done
    assert "\r\n" in done
    opened = toggle_ical(done, completed=False, now=NOW)
    assert "STATUS:NEEDS-ACTION" in opened
    assert "PERCENT-COMPLETE" not in opened
    assert "COMPLETED:" not in opened
    assert "SEQUENCE:2" in opened


def test_toggle_ical_increments_existing_sequence():
    text = "BEGIN:VTODO\nUID:x\nSEQUENCE:4\nSTATUS:NEEDS-ACTION\nEND:VTODO\n"
    updated = toggle_ical(text, completed=True, now=NOW)
    assert "SEQUENCE:5" in updated
    assert updated.count("SEQUENCE:") == 1


def test_toggle_ical_rejects_missing_vtodo():
    try:
        toggle_ical("BEGIN:VCALENDAR\nEND:VCALENDAR\n", completed=True, now=NOW)
    except ValueError as exc:
        assert "No VTODO" in str(exc)
    else:
        raise AssertionError("expected ValueError")
