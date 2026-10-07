#!/bin/sh
# One-command Trap Garden bootstrap for a fresh Ubuntu VPS.
# Run as root:  sh bootstrap.sh yourdomain.example
# Idempotent-ish: safe to re-run; existing installs are left alone.
set -e
DOMAIN="${1:?usage: bootstrap.sh <domain>}"

echo "==> bootstrap: $DOMAIN"

# --- system basics -----------------------------------------------------
apt-get update -qq
# docker.io + compose: package name differs by Ubuntu release
apt-get install -y -qq ufw git curl \
    docker.io docker-compose-v2 2>/dev/null \
    || apt-get install -y -qq ufw git curl docker.io docker-compose

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # consider rate-limiting: ufw limit 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- caddy (TLS termination) — NOT in Ubuntu's repos; official source --
if ! command -v caddy >/dev/null 2>&1; then
  apt-get install -y -qq debian-keyring debian-archive-keyring \
      apt-transport-https gnupg 2>/dev/null || true
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --batch --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq
  apt-get install -y -qq caddy
fi

# --- garden ------------------------------------------------------------
mkdir -p /opt/swarmhunter
if [ -z "$(ls -A /opt/swarmhunter 2>/dev/null)" ]; then
  echo "ERROR: copy the swarmhunter repo to /opt/swarmhunter first:"
  echo "  rsync -av --exclude events.ndjson ./ root@THISBOX:/opt/swarmhunter/"
  exit 1
fi

cd /opt/swarmhunter/deploy
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose up -d --build
else
  docker-compose up -d --build
fi

# --- caddy site --------------------------------------------------------
mkdir -p /var/log/caddy && chown caddy:caddy /var/log/caddy || true
sed "s/DOMAIN/$DOMAIN/" Caddyfile > /etc/caddy/sites.garden
printf 'import /etc/caddy/sites.garden\n' > /etc/caddy/Caddyfile
systemctl enable --now caddy >/dev/null 2>&1 || true
systemctl restart caddy

echo
echo "==> done. garden on 127.0.0.1:8080 (container), caddy on :80/:443"
echo "    DNS: point $DOMAIN A record at this box, then"
echo "    verify: curl -sI https://$DOMAIN/robots.txt"
echo "    events: tail -f /opt/swarmhunter/garden/events.ndjson"
