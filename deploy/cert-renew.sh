#!/usr/bin/env bash
set -euo pipefail
if [[ "${RENEWED_LINEAGE:-}" == /etc/letsencrypt/live/ideas.cafedaily.top ]]; then
    /usr/sbin/nginx -t
    /usr/bin/systemctl reload nginx
fi
