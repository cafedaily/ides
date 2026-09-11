#!/usr/bin/env bash
set -euo pipefail
previous=$(cat /opt/ides/previous-release)
[[ "$previous" =~ ^/opt/ides/releases/[0-9a-f]{7,40}$ ]] || exit 2
test -d "$previous"
ln -sfn "$previous" /opt/ides/current
systemctl restart ides.service
curl --retry 5 --retry-delay 1 --retry-connrefused -fsS http://127.0.0.1:8731/api/health
# Data remains in /var/lib/ides. Database restoration is a separate explicit action.
