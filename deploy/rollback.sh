#!/usr/bin/env bash
set -euo pipefail
previous=$(cat /opt/ides/previous-release)
[[ "$previous" =~ ^/opt/ides/releases/[0-9a-f]{7,40}$ ]] || exit 2
test -d "$previous"
ln -sfn "$previous" /opt/ides/current
install -m 644 "$previous/deploy/ides.service" /etc/systemd/system/ides.service
systemctl daemon-reload
systemctl restart ides.service
curl -o /dev/null --retry 5 --retry-delay 1 --retry-connrefused -fsS http://127.0.0.1:8731/
# Data remains in /var/lib/ides. Database restoration is a separate explicit action.
