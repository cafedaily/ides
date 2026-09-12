#!/usr/bin/env bash
set -euo pipefail
# Run as root on the authorized host. Archive contains tracked source only.
revision=${1:?release revision required}
archive=${2:?source archive required}
[[ "$revision" =~ ^[0-9a-f]{7,40}$ ]] || { echo 'Invalid revision' >&2; exit 2; }
root=/opt/ides
release="$root/releases/$revision"
[[ "$release" == /opt/ides/releases/* ]] || exit 2
test ! -e "$release"
id ides >/dev/null 2>&1 || useradd --system --home /var/lib/ides --shell /usr/sbin/nologin ides
install -d -m 755 "$root/releases" "$release"
install -d -o ides -g ides -m 700 /var/lib/ides
install -d -m 700 /etc/ides
tar -xzf "$archive" -C "$release"
cd "$release"
/usr/bin/python3 web/build.py --output "$release/dist/index.html"
if test -L "$root/current"; then
  readlink -f "$root/current" > "$root/previous-release"
fi
ln -sfn "$release" "$root/current"
install -m 644 deploy/ides.service /etc/systemd/system/ides.service
systemctl daemon-reload
systemctl enable ides.service
systemctl restart ides.service
for attempt in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8731/ >/dev/null; then exit 0; fi
  sleep 1
done
echo 'Health check failed; use deploy/rollback.sh' >&2
exit 1
