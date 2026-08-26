#!/usr/bin/env bash
# Install Radicale + alientasks on a Raspberry Pi as systemd user units.
# Run on the Pi, from the alientasks repo: deploy/install-pi.sh [RADICALE_PASSWORD]
# Details: docs/pi-and-phone.md
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TAILSCALE_IP="$(tailscale ip -4)"
ENV_FILE="$HOME/.config/alientasks/env"

if [ ! -x /usr/bin/socat ] || ! python3 -m venv --help >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq socat python3-venv
fi

# Radicale, same version as the reference machine.
mkdir -p "$HOME/repos/radicale"
python3 -m venv "$HOME/repos/radicale/.venv"
"$HOME/repos/radicale/.venv/bin/pip" install --quiet --disable-pip-version-check \
    "Radicale==3.7.8" "bcrypt==5.0.0"

mkdir -p "$HOME/.config/radicale" "$HOME/.config/alientasks" \
    "$HOME/.config/systemd/user" "$HOME/.local/share/radicale/collections"
if [ ! -f "$HOME/.config/radicale/users" ]; then
    echo "NOTE: no Radicale users file. Copy it from the old machine before login." >&2
fi

render() {
    sed -e "s|__HOME__|$HOME|g" -e "s|__TAILSCALE_IP__|$TAILSCALE_IP|g" "$1" > "$2"
}
render "$REPO_DIR/deploy/radicale.conf" "$HOME/.config/radicale/config"
render "$REPO_DIR/deploy/radicale.service" \
    "$HOME/.config/systemd/user/radicale.service"
render "$REPO_DIR/deploy/alientasks.service" \
    "$HOME/.config/systemd/user/alientasks.service"
render "$REPO_DIR/deploy/alientasks-tailscale.service" \
    "$HOME/.config/systemd/user/alientasks-tailscale.service"

if [ ! -f "$ENV_FILE" ]; then
    if [ -n "${1:-}" ]; then
        password="$1"
    else
        read -rsp "Radicale password for eve: " password
        echo >&2
    fi
    {
        echo "RADICALE_URL=http://127.0.0.1:5232"
        echo "RADICALE_COLLECTION=/eve/tasks/"
        echo "RADICALE_PASSWORD=$password"
    } > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

systemctl --user daemon-reload
systemctl --user enable --now radicale.service
systemctl --user enable --now alientasks.service
systemctl --user enable --now alientasks-tailscale.service
loginctl enable-linger "$USER" 2>/dev/null || sudo loginctl enable-linger "$USER"

# HTTPS front for the UI, best effort.
tailscale serve --bg 5233 >/dev/null 2>&1 || \
    echo "NOTE: 'tailscale serve --bg 5233' failed. Set it up manually." >&2

echo "Radicale (phone, CalDAV): http://$TAILSCALE_IP:5232/ user: eve"
echo "Alientasks (browsers):    http://$TAILSCALE_IP:5233/"
