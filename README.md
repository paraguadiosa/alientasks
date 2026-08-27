# Alientasks

A self-hosted task list for a CalDAV VTODO collection.

The page groups tasks by `CATEGORIES`, writes `STATUS` back when you
tick a checkbox, and adds new tasks with the New task form. Every
change is a CalDAV request straight to Radicale, so the phone (DAVx5)
sees the same tasks.

Tasks are created with a fresh `UID` and PUT into the collection, so
any CalDAV client picks them up on the next sync.

## Run

```bash
cd ~/repos/alientasks
./.venv/bin/python -m alientasks
```

Open http://127.0.0.1:5233/

Systemd user unit: `alientasks.service` (localhost only).

## Raspberry Pi and phone sync

Alientasks runs on a Raspberry Pi next to Radicale. The phone syncs
tasks through CalDAV (DAVx5) against Radicale, not against this UI.
See [docs/pi-and-phone.md](docs/pi-and-phone.md) for install, data
migration and phone setup. The installer is
`deploy/install-pi.sh`.

## Themes

Dark phosphor (default) and a Solarized-style light theme. Both use the same
terminal look: square corners, `[ ]` / `[x]` task markers drawn in CSS,
prompt-style `>` group headings, a blinking cursor in the title, and an
inverse-video active list tab. The palettes are unchanged. The header button
toggles the theme and stores the choice in `localStorage`. Without a stored
choice, the page follows `prefers-color-scheme`. Each theme also sets the CSS
`color-scheme` property, so native scrollbars and form controls match. All
light-theme text colors meet WCAG 2.2 AA contrast (>= 4.5:1).

The styling stays cheap for a Raspberry Pi 3: no blur shadows on boxes, no
filters, no transitions, and one small opacity animation that
`prefers-reduced-motion` disables.

CSS and JS live in `alientasks/static/` and are served under `/static/` with
cache-busted URLs (`?v=` + package version) and immutable caching. A tiny
inline script applies the saved theme before first paint to avoid a flash.

## Flags

- `--host` / `TASKS_UI_HOST` (default `127.0.0.1`)
- `--port` / `TASKS_UI_PORT` (default `5233`)
- `--radicale` / `RADICALE_URL` (default `http://127.0.0.1:5232`)
- `--collection` / `RADICALE_COLLECTION` (default `/eve/tasks/`)
- Auth is optional. If `RADICALE_PASSWORD` is set, the client sends basic auth as `eve`.

## Test

```bash
./.venv/bin/pytest
./.venv/bin/ruff check alientasks tests
./.venv/bin/ruff format --check alientasks tests
```
