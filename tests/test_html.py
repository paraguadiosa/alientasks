from alientasks.html import list_href, open_count, redirect_location, render_page
from alientasks.ical import COMPLETED, NEEDS_ACTION, Task


def make_task(uid, summary, category, status=NEEDS_ACTION):
    return Task(
        href=f"/eve/tasks/{uid}.ics",
        etag='"e"',
        uid=uid,
        summary=summary,
        category=category,
        status=status,
        raw_ical="",
    )


def test_list_href_and_redirect():
    assert list_href("") == "/"
    assert list_href("Proyectitos") == "/?list=Proyectitos"
    assert redirect_location("") == "/"
    assert redirect_location("Someday 2").startswith("/?list=")


def test_open_count_ignores_completed():
    tasks = [
        make_task("1", "A", "Default"),
        make_task("2", "B", "Default", COMPLETED),
    ]
    assert open_count(tasks) == 1


def test_render_page_all_lists_and_escapes():
    tasks = [
        make_task("1", "<script>", "Default"),
        make_task("2", "Done item", "Default", COMPLETED),
        make_task("3", "Other", "Reading List"),
    ]
    page = render_page(tasks, "")
    assert '<h1 class="app__title">Alientasks</h1>' in page
    assert "&lt;script&gt;" in page
    assert "<script>" not in page.split("<script>")[0]
    assert "Reading List" in page
    assert "Completadas (1)" in page
    assert 'aria-current="page"' in page
    assert "2 abiertas" in page


def test_render_page_filters_one_list_and_unknown_falls_back():
    tasks = [
        make_task("1", "Keep", "Default"),
        make_task("2", "Hide me", "Reading List"),
    ]
    page = render_page(tasks, "Default")
    assert "Keep" in page
    assert "Hide me" not in page
    fallback = render_page(tasks, "Missing")
    assert "Keep" in fallback
    assert "Hide me" in fallback


def test_render_page_includes_light_theme_support():
    page = render_page([], "")
    assert '[data-theme="light"]' in page
    assert 'class="theme-toggle"' in page
    assert 'name="color-scheme"' in page
    assert "alientasks-theme" in page
    assert 'aria-pressed="false"' in page


def test_render_page_empty_and_error():
    empty = render_page([], "")
    assert "No hay tareas en Radicale." in empty
    only_done = render_page([make_task("1", "Old", "Default", COMPLETED)], "Default")
    assert "No hay tareas abiertas." in only_done
    errored = render_page([], "", error="fallo <x>")
    assert 'role="alert"' in errored
    assert "fallo &lt;x&gt;" in errored
