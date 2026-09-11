# Deployment and rollback

The public domain is `ideas.cafedaily.top`. Anonymous visitors use an isolated local demo. Owner data and model requests require a bearer token or a signed HttpOnly, Secure, SameSite=Strict cookie.

Source releases live in `/opt/ides/releases/<git-revision>`, selected by `/opt/ides/current`. SQLite lives in `/var/lib/ides/yang.db` and belongs to the dedicated `ides` service account. The token and production configuration belong in root-only `/etc/ides/environment`:

```text
YANG_PRODUCTION=1
YANG_TRUST_PROXY=loopback
YANG_PUBLIC_ORIGIN=https://ideas.cafedaily.top
YANG_AUTH_TOKEN=<generate a strong random token outside Git>
```

Build an archive using `git archive --format=tar.gz HEAD`. Copy it over SSH and run `sudo bash deploy/install.sh <revision> <archive>`. Install the dedicated HTTP Nginx configuration, obtain a certificate with certbot webroot `/var/lib/ides-acme`, then install the HTTPS configuration and run `nginx -t` before reloading Nginx. Existing unrelated sites must remain unchanged.

The installer fails if a release directory already exists. Before every later release, back up SQLite with the SQLite backup API. Do not copy a live WAL database with an ordinary file copy. `deploy/rollback.sh` switches the code symlink to the recorded previous release and verifies health; it intentionally preserves current business data. The first deployment has no previous code release.

`GET /api/health` is public and redacted. Check `/api/state` returns 401 without credentials, login sends Secure/HttpOnly cookies over HTTPS, and authenticated state never includes model keys. Encrypted exports require `cryptography` and carry the password in a POST JSON body. Optional embedding calls send text to the selected provider only after the owner enables the feature and requests recall.

The signed browser session is stateless: logout clears the browser cookie; an already copied cookie remains valid until expiration or token rotation. The default session lifetime is bounded by the authentication policy. Rotate `YANG_AUTH_TOKEN` to invalidate all issued sessions.
