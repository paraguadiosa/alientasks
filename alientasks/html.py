"""Render the task list page."""

from __future__ import annotations

from html import escape
from urllib.parse import quote, urlencode

from alientasks.ical import Task, group_by_category

ALL_LIST = ""

STYLE = """
:root {
  --color-surface: #f4f1ea;
  --color-panel: #fffdf8;
  --color-text: #1c1917;
  --color-muted: #57534e;
  --color-line: #d6d3d1;
  --color-accent: #0f766e;
  --color-accent-text: #f0fdfa;
  --color-done: #78716c;
  --color-focus: #0f766e;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.5rem;
  --radius: 0.75rem;
  --font: "Source Sans 3", "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: var(--font);
  color: var(--color-text);
  background: var(--color-surface);
  line-height: 1.4;
  min-height: 100vh;
}
.app {
  max-width: 44rem;
  margin: 0 auto;
  padding: var(--space-4);
}
.app__header { margin-bottom: var(--space-4); }
.app__title {
  font-size: clamp(1.4rem, 1.2rem + 1vw, 1.8rem);
  margin: 0 0 var(--space-1);
}
.app__meta {
  margin: 0;
  color: var(--color-muted);
  font-size: 0.95rem;
}
.list-nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
}
.list-nav__item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-line);
  border-radius: 999px;
  background: var(--color-panel);
  color: var(--color-text);
  text-decoration: none;
  font-size: 0.95rem;
}
.list-nav__item--current {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: var(--color-accent-text);
}
.list-nav__count { font-variant-numeric: tabular-nums; }
.task-group { margin: 0 0 var(--space-5); }
.task-group__title {
  font-size: 1.1rem;
  margin: 0 0 var(--space-3);
}
.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--color-panel);
  border: 1px solid var(--color-line);
  border-radius: var(--radius);
}
.task {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-line);
}
.task:last-child { border-bottom: 0; }
.task__check {
  width: 1.15rem;
  height: 1.15rem;
  margin-top: 0.2rem;
  flex: 0 0 auto;
  accent-color: var(--color-accent);
}
.task__label {
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
}
.task--done .task__label {
  color: var(--color-done);
  text-decoration: line-through;
}
.task__save {
  font: inherit;
  border: 1px solid var(--color-line);
  background: var(--color-surface);
  border-radius: 0.4rem;
  padding: var(--space-1) var(--space-2);
}
html:not(.no-js) .task__save { display: none; }
.done-block { margin-top: var(--space-3); }
.done-block__summary {
  cursor: pointer;
  color: var(--color-muted);
}
.empty, .alert {
  background: var(--color-panel);
  border: 1px solid var(--color-line);
  border-radius: var(--radius);
  padding: var(--space-4);
}
.alert { border-color: #b45309; }
:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
"""

SCRIPT = """
document.documentElement.classList.remove("no-js");
document.querySelectorAll(".task").forEach(function (form) {
  var box = form.querySelector(".task__check");
  if (!box) return;
  box.addEventListener("change", function () { form.submit(); });
});
"""


def list_href(name: str) -> str:
    """Build the query URL for a list filter."""
    if not name:
        return "/"
    return "/?" + urlencode({"list": name})


def open_count(tasks: list[Task]) -> int:
    """Count tasks that are not completed."""
    return sum(1 for task in tasks if not task.completed)


def render_nav(grouped: dict[str, list[Task]], current: str) -> str:
    """Render the list filter navigation."""
    items = [("", "Todas", sum(open_count(items) for items in grouped.values()))]
    for name, tasks in grouped.items():
        items.append((name, name, open_count(tasks)))
    parts = ['<nav class="list-nav" aria-label="Listas">']
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
    done_label = "Desmarcar" if task.completed else "Completar"
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
        parts.append('<p class="empty">No hay tareas abiertas.</p>')
    if done_tasks:
        parts.append('<details class="done-block">')
        parts.append(
            f'<summary class="done-block__summary">'
            f"Completadas ({len(done_tasks)})</summary>"
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
        sections = '<p class="empty">No hay tareas en Radicale.</p>'
    error_html = f'<p class="alert" role="alert">{escape(error)}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="es" class="no-js">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alientasks</title>
  <style>{STYLE}</style>
</head>
<body>
  <div class="app">
    <header class="app__header">
      <h1 class="app__title">Alientasks</h1>
      <p class="app__meta">{total_open} abiertas</p>
    </header>
    {render_nav(grouped, current_list)}
    <main>
      {error_html}
      {sections}
    </main>
  </div>
  <script>{SCRIPT}</script>
</body>
</html>
"""


def redirect_location(list_name: str) -> str:
    """Return the Location header target after a toggle."""
    if not list_name:
        return "/"
    return "/?list=" + quote(list_name)
