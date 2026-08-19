"""Render the task list page."""

from __future__ import annotations

from html import escape
from urllib.parse import quote, urlencode

from alientasks.ical import Task, group_by_category

ALL_LIST = ""

STYLE = """
:root {
  --color-surface: #040804;
  --color-panel: #0a100a;
  --color-text: #00ff41;
  --color-muted: #1f8a4c;
  --color-line: #123f1f;
  --color-accent: #00ff66;
  --color-accent-text: #040804;
  --color-done: #0a5c2a;
  --color-focus: #00ff41;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.5rem;
  --radius: 4px;
  --font: "JetBrains Mono", "Cascadia Code", "Fira Code", Consolas,
          "Courier New", monospace;
  --glow: 0 0 6px rgba(0, 255, 65, 0.35);
  --color-inset: #0a140a;
  --color-hover: #0d1a0d;
  --scanline: rgba(0, 255, 65, 0.03);
}
[data-theme="light"] {
  --color-surface: #f4f7ec;
  --color-panel: #e9efe0;
  --color-text: #1a3c22;
  --color-muted: #3f6b4d;
  --color-line: #c3d4b8;
  --color-accent: #0f6a35;
  --color-accent-text: #f4f7ec;
  --color-done: #4f7359;
  --color-focus: #0f6a35;
  --color-inset: #dde7cf;
  --color-hover: #dfe9d2;
  --scanline: rgba(15, 106, 53, 0.05);
  --glow: none;
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
body::after {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 99999;
  background: repeating-linear-gradient(
    to bottom,
    var(--scanline) 0px,
    var(--scanline) 1px,
    transparent 1px,
    transparent 3px
  );
}
::selection {
  background: var(--color-accent);
  color: var(--color-accent-text);
}
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--color-surface); }
::-webkit-scrollbar-thumb { background: var(--color-line); }
::-webkit-scrollbar-thumb:hover { background: var(--color-muted); }
html { scrollbar-color: var(--color-line) var(--color-surface); }
.app {
  max-width: 100%;
  margin: 0 auto;
  padding: var(--space-4);
}
.app__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.theme-toggle {
  font: inherit;
  font-size: 0.85rem;
  border: 1px solid var(--color-line);
  background: var(--color-panel);
  color: var(--color-muted);
  border-radius: 999px;
  padding: var(--space-1) var(--space-3);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.theme-toggle:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
html.no-js .theme-toggle { display: none; }
.app__title {
  font-size: clamp(1.4rem, 1.2rem + 1vw, 1.8rem);
  margin: 0 0 var(--space-1);
  color: var(--color-accent);
  text-shadow: var(--glow);
  text-transform: uppercase;
  letter-spacing: 0.1em;
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
  color: var(--color-muted);
  text-decoration: none;
  font-size: 0.95rem;
  transition: border-color 0.2s, color 0.2s;
}
.list-nav__item:hover {
  border-color: var(--color-accent);
  color: var(--color-text);
}
.list-nav__item--current {
  background: var(--color-inset);
  border-color: var(--color-accent);
  color: var(--color-accent);
  text-shadow: var(--glow);
}
.list-nav__count { font-variant-numeric: tabular-nums; }
main {
  display: flex;
  gap: var(--space-4);
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scroll-snap-type: x mandatory;
  height: calc(100vh - 10rem);
}
.task-group {
  flex: 0 0 min(85vw, 22rem);
  scroll-snap-align: start;
  margin: 0;
  overflow-y: auto;
  height: 100%;
}
.task-group__title {
  font-size: 1.1rem;
  margin: 0 0 var(--space-3);
  color: var(--color-accent);
  text-shadow: var(--glow);
  position: sticky;
  top: 0;
  background: var(--color-surface);
  padding: var(--space-2) 0;
  z-index: 1;
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
.task:hover { background: var(--color-hover); }
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
  background: var(--color-inset);
  color: var(--color-muted);
  border-radius: var(--radius);
  padding: var(--space-1) var(--space-2);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.task__save:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
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
.alert { border-color: var(--color-accent); color: var(--color-accent); }
:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
"""

SCRIPT = """
document.documentElement.classList.remove("no-js");
(function () {
  var toggle = document.querySelector(".theme-toggle");
  if (!toggle) return;
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    toggle.setAttribute("aria-pressed", String(theme === "light"));
    toggle.textContent = theme === "light" ? "Modo oscuro" : "Modo claro";
  }
  apply(document.documentElement.getAttribute("data-theme") || "dark");
  toggle.addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-theme");
    var next = current === "light" ? "dark" : "light";
    try { localStorage.setItem("alientasks-theme", next); } catch (e) {}
    apply(next);
  });
})();
document.querySelectorAll(".task").forEach(function (form) {
  var box = form.querySelector(".task__check");
  if (!box) return;
  box.addEventListener("change", function () { form.submit(); });
});
"""


HEAD_SCRIPT = """
(function () {
  var theme = "";
  try { theme = localStorage.getItem("alientasks-theme") || ""; } catch (e) {}
  if (!theme && window.matchMedia &&
      matchMedia("(prefers-color-scheme: light)").matches) theme = "light";
  document.documentElement.setAttribute("data-theme", theme || "dark");
})();
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
  <meta name="color-scheme" content="dark light">
  <style>{STYLE}</style>
  <script>{HEAD_SCRIPT}</script>
</head>
<body>
  <div class="app">
    <header class="app__header">
      <div>
        <h1 class="app__title">Alientasks</h1>
        <p class="app__meta">{total_open} abiertas</p>
      </div>
      <button type="button" class="theme-toggle" aria-pressed="false">
        Modo claro
      </button>
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
