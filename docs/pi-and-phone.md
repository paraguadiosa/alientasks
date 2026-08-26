# Alientasks on a Raspberry Pi with phone sync

## How the parts fit

The phone never talks to Alientasks. The phone talks to Radicale
through CalDAV. Alientasks is only a web UI on top of the same data.

```
                 Tailscale (only way in)
                 ------------------------
phone (eve-xl)                             mini (your desktop)
  |  CalDAV sync (DAVx5)                     |  browser
  v                                          v
Radicale :5232  <---- same files ---->  Alientasks :5233
        \                                /
         \_____ Raspberry Pi (jacinto) _/
```

Both services run on the Pi as systemd user units:

- Radicale binds `127.0.0.1:5232` and the Pi Tailscale IP `:5232`.
  The phone syncs against the Tailscale address.
- Alientasks binds `127.0.0.1:5233`.
  A socat unit forwards the Pi Tailscale IP `:5233` to it.
- `tailscale serve` also gives the UI HTTPS on
  `https://jacinto.tail66290a.ts.net/`.

Nothing listens on the plain LAN. Access needs Tailscale.

## What you need

- Raspberry Pi OS Trixie or newer (Python 3.12 or higher).
- Tailscale installed and up on the Pi.
- The Radicale `users` file and the task data from the old machine.

## Install on the Pi

Run this on the Pi, inside the alientasks repo:

```bash
./deploy/install-pi.sh
```

The script asks for the Radicale password once and stores it in
`~/.config/alientasks/env` with mode 600. It installs Radicale 3.7.8
in a venv, writes the three units and starts them.

The `users` file is not created by the script. Copy it from the old
machine, or no login will work:

```bash
scp oldmachine:.config/radicale/users ~/.config/radicale/users
```

## Move the data from the old machine

Stop the old services first. This gives a clean snapshot.
No data is deleted on the old machine.

On the old machine:

```bash
systemctl --user stop alientasks-tailscale.service alientasks.service radicale.service
rsync -a ~/.local/share/radicale/collections/ jacinto:.local/share/radicale/collections/
rsync -a ~/.config/radicale/users jacinto:.config/radicale/users
```

Then restart the Pi services if they were already running:

```bash
ssh jacinto 'systemctl --user restart radicale.service alientasks.service'
```

## Phone setup (Android)

1. Install DAVx5 (F-Droid or Play Store).
2. Install Tasks.org or OpenTasks. DAVx5 syncs VTODO data into it.
3. In DAVx5, add an account:
   - Address: `http://100.99.112.42:5232/`
   - User name: `eve`
   - Password: the same Radicale password as before.
4. Open the account and enable sync for the `tasks` collection.
5. Create and complete tasks in Tasks.org. DAVx5 pushes them to
   Radicale. Alientasks shows them after a page reload.

If the phone synced against the old machine before, only the account
address changes. The user name and password stay the same.

## Phone setup (iOS)

iOS Reminders does not sync with generic CalDAV VTODO servers in a
reliable way. Use a third-party app that speaks CalDAV tasks, for
example a CalDAV task client from the App Store. Point it at
`http://100.99.112.42:5232/eve/tasks/` with the same credentials.

## URLs after the move

| Use                          | Address                                    |
| ---------------------------- | ------------------------------------------ |
| Phone, CalDAV account        | `http://100.99.112.42:5232/`               |
| Browser, UI (Tailscale)      | `http://100.99.112.42:5233/`               |
| Browser, UI (HTTPS)          | `https://jacinto.tail66290a.ts.net/`       |
| Browser, UI on the Pi itself | `http://127.0.0.1:5233/`                   |

## Rollback

The old machine keeps its data. To go back:

```bash
# On the Pi:
systemctl --user disable --now alientasks-tailscale.service alientasks.service radicale.service
# On the old machine:
systemctl --user start radicale.service alientasks.service alientasks-tailscale.service
```

Then point DAVx5 back to the old machine address.
