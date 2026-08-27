"""Render the task list page."""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from alientasks import __version__
from alientasks.ical import Task, group_by_category

ALL_LIST = ""

MAX_SUMMARY_CHARS = 1000
MAX_CATEGORY_CHARS = 200

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect x="24" y="14" width="52" height="72" rx="8" fill="none"
        stroke="#00ff41" stroke-width="7"/>
  <rect x="38" y="6" width="24" height="14" rx="5" fill="none"
        stroke="#00ff41" stroke-width="7"/>
  <path d="M36 42 l7 7 l14 -14" fill="none" stroke="#00ff41"
        stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M36 62 l7 7 l14 -14" fill="none" stroke="#00ff41"
        stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

# Inline on purpose: it must run before first paint to apply the stored
# theme without a flash of the wrong colors. It also proves JS works by
# dropping the no-js class before the body renders.
THEME_BOOTSTRAP = """
(function () {
  document.documentElement.classList.remove("no-js");
  var theme = "";
  try { theme = localStorage.getItem("alientasks-theme") || ""; } catch (e) {}
  if (!theme && window.matchMedia &&
      matchMedia("(prefers-color-scheme: light)").matches) theme = "light";
  document.documentElement.setAttribute("data-theme", theme || "dark");
})();
"""


def asset_url(name: str) -> str:
    """Build a cache-busted URL for a static asset."""
    return f"/static/{name}?v={__version__}"


def list_href(name: str) -> str:
    """Build the query URL for a list filter."""
    if not name:
        return "/"
    return "/?" + urlencode({"list": name})


def open_count(tasks: list[Task]) -> int:
    """Count tasks that are not completed."""
    return sum(1 for task in tasks if not task.completed)


def render_add_form(current_list: str, categories: list[str]) -> str:
    """Render the add-task form."""
    options = "".join(
        f'<option value="{escape(name, quote=True)}"></option>' for name in categories
    )
    current = escape(current_list, quote=True)
    return (
        '<section class="add-task">'
        '<h2 class="add-task__title">New task</h2>'
        '<form class="add-task__form" method="post" action="/add">'
        '<label class="add-task__field add-task__field--summary">'
        '<span class="add-task__prompt">summary</span>'
        f'<input class="add-task__input" type="text" name="summary" '
        f'maxlength="{MAX_SUMMARY_CHARS}" autocomplete="off" required>'
        "</label>"
        '<label class="add-task__field">'
        '<span class="add-task__prompt">category</span>'
        f'<input class="add-task__input" type="text" name="category" '
        f'maxlength="{MAX_CATEGORY_CHARS}" list="category-options" value="{current}">'
        "</label>"
        f'<datalist id="category-options">{options}</datalist>'
        f'<input type="hidden" name="list" value="{current}">'
        '<button class="add-task__submit" type="submit">add</button>'
        "</form></section>"
    )


def render_nav(grouped: dict[str, list[Task]], current: str) -> str:
    """Render the list filter navigation."""
    items = [("", "All", sum(open_count(items) for items in grouped.values()))]
    for name, tasks in grouped.items():
        items.append((name, name, open_count(tasks)))
    parts = ['<nav class="list-nav" aria-label="Lists">']
    for value, label, count in items:
        current_cls = " list-nav__item--current" if value == current else ""
        aria = ' aria-current="page"' if value == current else ""
        parts.append(
            f'<a class="list-nav__item{current_cls}" '
            f'href="{escape(list_href(value))}"{aria}>'
            f'{escape(label)} <span class="list-nav__count">({count})</span></a>'
        )
    parts.append("</nav>")
    return "\n".join(parts)


def render_task(task: Task, current_list: str) -> str:
    """Render one task row as a form."""
    checked = " checked" if task.completed else ""
    state = " task--done" if task.completed else ""
    done_label = "Reopen" if task.completed else "Complete"
    return (
        f'<li><form class="task{state}" method="post" action="/toggle">'
        f'<input type="hidden" name="href" value="{escape(task.href, quote=True)}">'
        f'<input type="hidden" name="list" value="{escape(current_list, quote=True)}">'
        f'<input type="hidden" name="completed" value="0">'
        f'<input class="task__check" type="checkbox" name="completed" value="1"'
        f' id="t-{escape(task.uid, quote=True)}"{checked}>'
        f'<label class="task__label" for="t-{escape(task.uid, quote=True)}">'
        f"{escape(task.summary)}</label>"
        f'<button class="task__save" type="submit">{done_label}</button>'
        f"</form></li>"
    )


def render_group(title: str, tasks: list[Task], current_list: str) -> str:
    """Render one category section with open tasks and a completed disclosure."""
    open_tasks = [task for task in tasks if not task.completed]
    done_tasks = [task for task in tasks if task.completed]
    heading = f'<h2 class="task-group__title">{escape(title)}</h2>'
    parts = ['<section class="task-group">', heading]
    if open_tasks:
        parts.append('<ul class="task-list">')
        parts.extend(render_task(task, current_list) for task in open_tasks)
        parts.append("</ul>")
    else:
        parts.append('<p class="empty">No open tasks.</p>')
    if done_tasks:
        parts.append('<details class="done-block">')
        parts.append(
            f'<summary class="done-block__summary">'
            f"Completed ({len(done_tasks)})</summary>"
        )
        parts.append('<ul class="task-list">')
        parts.extend(render_task(task, current_list) for task in done_tasks)
        parts.append("</ul></details>")
    parts.append("</section>")
    return "\n".join(parts)


def render_page(
    tasks: list[Task],
    current_list: str = ALL_LIST,
    error: str | None = None,
) -> str:
    """Return the full HTML document."""
    grouped = group_by_category(tasks)
    if current_list and current_list not in grouped:
        current_list = ALL_LIST
    total_open = open_count(tasks)
    if current_list:
        sections = render_group(current_list, grouped[current_list], current_list)
    elif grouped:
        sections = "\n".join(
            render_group(name, items, current_list) for name, items in grouped.items()
        )
    else:
        sections = '<p class="empty">No tasks in Radicale.</p>'
    error_html = f'<p class="alert" role="alert">{escape(error)}</p>' if error else ""
    css_url = asset_url("style.css")
    js_url = asset_url("app.js")
    return f"""<!DOCTYPE html>
<html lang="en" class="no-js">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alientasks</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <meta name="color-scheme" content="dark light">
  <link rel="stylesheet" href="{css_url}">
  <script>{THEME_BOOTSTRAP}</script>
</head>
<body>
  <div class="app">
    <header class="app__header">
      <div>
        <h1 class="app__title">Alientasks</h1>
        <p class="app__meta">{total_open} open</p>
      </div>
      <button type="button" class="theme-toggle" aria-pressed="false">
        Light mode
      </button>
    </header>
    {render_nav(grouped, current_list)}
    {render_add_form(current_list, list(grouped))}
    <main>
      {error_html}
      {sections}
    </main>
  </div>
  <script src="{js_url}" defer></script>
</body>
</html>
"""


def redirect_location(list_name: str) -> str:
    """Return the Location header target after a toggle."""
    if not list_name:
        return "/"
    return "/?" + urlencode({"list": list_name})
