# Alientasks

A self-hosted task list for a CalDAV VTODO collection.

The page groups tasks by `CATEGORIES` and writes `STATUS` back when you tick a checkbox.

This increment does not add, edit, or delete tasks.

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

Dark phosphor (default) and a Solarized-style light theme. The header button
toggles the theme and stores the choice in `localStorage`. Without a stored
choice, the page follows `prefers-color-scheme`. All light-theme text colors
meet WCAG 2.2 AA contrast (>= 4.5:1).

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
