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
