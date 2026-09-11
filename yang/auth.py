"""Small stdlib-only authentication helpers for the Yang HTTP server.

This module intentionally has no project-local dependencies so it can be used
from the server, API layer, CLI startup checks, and tests without creating
import cycles.  It provides:

* environment-driven token/session policy loading;
* production/weak-token detection for safe startup decisions;
* bearer-token validation using constant-time comparison;
* HMAC-signed, expiring session cookie creation and verification; and
* a bounded in-memory failure throttle suitable for login attempts.

The helpers do not decide which routes are private; callers should combine
``validate_bearer`` and ``verify_session_cookie`` according to their routing
policy.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from http import cookies
from typing import Callable, Dict, Mapping, Optional, Tuple


AUTH_TOKEN_ENV = "YANG_AUTH_TOKEN"
PRODUCTION_ENV = "YANG_PRODUCTION"
ENV_ENV = "YANG_ENV"
PUBLIC_ORIGIN_ENV = "YANG_PUBLIC_ORIGIN"
SESSION_COOKIE_NAME_ENV = "YANG_SESSION_COOKIE"
SESSION_TTL_ENV = "YANG_SESSION_TTL"
AUTH_SECURE_COOKIE_ENV = "YANG_AUTH_SECURE_COOKIE"

DEFAULT_SESSION_COOKIE_NAME = "yang_session"
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60
MIN_STRONG_TOKEN_LENGTH = 32
MAX_TOKEN_LENGTH = 4096

_TRUE_VALUES = {"1", "true", "yes", "y", "on", "prod", "production"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "dev", "development", "local"}
_PRODUCTION_ENV_VALUES = {"prod", "production", "release"}
_LOOPBACK_HOSTS = {"", "127.0.0.1", "localhost", "::1", "[::1]"}
_WEAK_TOKEN_WORDS = {
    "admin",
    "changeme",
    "default",
    "dev",
    "development",
    "letmein",
    "local",
    "login",
    "password",
    "please-change-me",
    "secret",
    "test",
    "token",
    "yang",
    "yang-auth-token",
}


class AuthError(Exception):
    """Base class for authentication helper errors."""


class AuthConfigError(AuthError):
    """Raised when authentication policy is unsafe or malformed."""


class SessionCookieError(AuthError):
    """Raised when a session cookie cannot be created."""


@dataclasses.dataclass(frozen=True)
class AuthPolicy:
    """Configuration used by bearer and session authentication.

    ``token`` is the shared secret expected from bearer clients and login
    requests.  In production it must be present and non-weak.  Development
    loopback deployments may leave it empty so existing local workflows can
    remain compatible until the server chooses to enforce private routes.
    """

    token: str = ""
    production: bool = False
    public_origin: str = ""
    session_cookie_name: str = DEFAULT_SESSION_COOKIE_NAME
    session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
    secure_cookie: bool = False

    @property
    def has_token(self) -> bool:
        return bool(self.token)

    @property
    def weak_token(self) -> bool:
        return is_weak_token(self.token)

    def require_safe_for_startup(self) -> None:
        """Raise ``AuthConfigError`` if this policy is unsafe to use.

        The check is deliberately strict only for production mode; callers that
        bind to a public interface in development can additionally call this
        after constructing a policy with ``production=True`` or perform their
        own host-based decision.
        """

        if self.production and self.weak_token:
            raise AuthConfigError(
                "%s must be set to a strong secret in production mode" % AUTH_TOKEN_ENV
            )

    def validate_token(self, supplied_token: Optional[str]) -> bool:
        return validate_token(supplied_token, self.token)

    def validate_bearer(self, authorization_header: Optional[str]) -> bool:
        return validate_bearer(authorization_header, self.token)

    def make_session_cookie(
        self,
        *,
        now: Optional[float] = None,
        max_age: Optional[int] = None,
        path: str = "/",
    ) -> str:
        return make_session_cookie(
            self.token,
            cookie_name=self.session_cookie_name,
            max_age=self.session_ttl_seconds if max_age is None else max_age,
            secure=self.secure_cookie,
            path=path,
            now=now,
        )

    def clear_session_cookie(self, *, path: str = "/") -> str:
        return clear_session_cookie(
            cookie_name=self.session_cookie_name,
            secure=self.secure_cookie,
            path=path,
        )

    def verify_session_cookie(
        self,
        cookie_header: Optional[str],
        *,
        now: Optional[float] = None,
    ) -> bool:
        return verify_session_cookie(
            cookie_header,
            self.token,
            cookie_name=self.session_cookie_name,
            now=now,
        )


def _truthy(value: object) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in _TRUE_VALUES


def _falsey(value: object) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in _FALSE_VALUES


def _clean(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def is_loopback_host(host: Optional[str]) -> bool:
    """Return True when ``host`` denotes a local-only bind address."""

    if host is None:
        return True
    h = str(host).strip().lower()
    if h in _LOOPBACK_HOSTS:
        return True
    if h.startswith("127."):
        return True
    return False


def is_production_mode(
    env: Optional[Mapping[str, str]] = None,
    *,
    host: Optional[str] = None,
    public_origin: Optional[str] = None,
) -> bool:
    """Detect production mode from environment and optional bind context.

    Production is enabled by ``YANG_PRODUCTION`` truthy values or by
    ``YANG_ENV=prod|production|release``.  A supplied non-loopback ``host`` also
    counts as production unless ``YANG_PRODUCTION`` is explicitly false.  An
    HTTPS ``public_origin`` is treated as production because cookies should be
    Secure for that deployment shape.
    """

    env = os.environ if env is None else env
    explicit = env.get(PRODUCTION_ENV)
    if _truthy(explicit):
        return True
    if _falsey(explicit):
        return False
    if _clean(env.get(ENV_ENV)).lower() in _PRODUCTION_ENV_VALUES:
        return True
    origin = public_origin if public_origin is not None else env.get(PUBLIC_ORIGIN_ENV, "")
    if _clean(origin).lower().startswith("https://"):
        return True
    if host is not None and not is_loopback_host(host):
        return True
    return False


def _parse_positive_int(value: object, default: int, *, minimum: int = 1, maximum: int = 30 * 24 * 60 * 60) -> int:
    try:
        n = int(str(value).strip())
    except Exception:
        return default
    if n < minimum:
        return minimum
    if n > maximum:
        return maximum
    return n


def _valid_cookie_name(name: str) -> bool:
    if not name:
        return False
    # RFC6265 token-ish subset; avoid separators and control chars.
    forbidden = set('()<>@,;:\\"/[]?={} \t')
    return all(32 < ord(ch) < 127 and ch not in forbidden for ch in name)


def load_policy_from_env(
    env: Optional[Mapping[str, str]] = None,
    *,
    host: Optional[str] = None,
) -> AuthPolicy:
    """Load authentication policy from environment variables.

    Recognized variables:

    * ``YANG_AUTH_TOKEN``: shared bearer/login token;
    * ``YANG_PRODUCTION`` or ``YANG_ENV``: production-mode switches;
    * ``YANG_PUBLIC_ORIGIN``: expected browser origin for server integration;
    * ``YANG_SESSION_COOKIE``: session cookie name; and
    * ``YANG_SESSION_TTL``: session lifetime in seconds.

    ``YANG_AUTH_SECURE_COOKIE`` can override cookie ``Secure`` behavior;
    otherwise production mode implies Secure cookies.
    """

    env = os.environ if env is None else env
    token = _clean(env.get(AUTH_TOKEN_ENV))
    if len(token) > MAX_TOKEN_LENGTH:
        raise AuthConfigError("%s is too long" % AUTH_TOKEN_ENV)
    public_origin = _clean(env.get(PUBLIC_ORIGIN_ENV))
    production = is_production_mode(env, host=host, public_origin=public_origin)
    cookie_name = _clean(env.get(SESSION_COOKIE_NAME_ENV), DEFAULT_SESSION_COOKIE_NAME)
    if not _valid_cookie_name(cookie_name):
        raise AuthConfigError("%s is not a valid cookie name" % SESSION_COOKIE_NAME_ENV)
    ttl = _parse_positive_int(env.get(SESSION_TTL_ENV), DEFAULT_SESSION_TTL_SECONDS)
    secure_override = env.get(AUTH_SECURE_COOKIE_ENV)
    secure_cookie = production if secure_override is None else _truthy(secure_override)
    policy = AuthPolicy(
        token=token,
        production=production,
        public_origin=public_origin,
        session_cookie_name=cookie_name,
        session_ttl_seconds=ttl,
        secure_cookie=secure_cookie,
    )
    policy.require_safe_for_startup()
    return policy


# Friendly aliases for callers/tests that prefer explicit names.
load_auth_policy_from_env = load_policy_from_env
load_token_policy_from_env = load_policy_from_env
TokenPolicy = AuthPolicy


def is_weak_token(token: Optional[str]) -> bool:
    """Return True if a token is absent, common, short, or low variety.

    The heuristic is intentionally simple and deterministic.  A strong
    production token should be generated with a CSPRNG, for example
    ``python -c "import secrets; print(secrets.token_urlsafe(32))"``.
    """

    if token is None:
        return True
    t = str(token).strip()
    if len(t) < MIN_STRONG_TOKEN_LENGTH:
        return True
    lowered = t.lower()
    compact = "".join(ch for ch in lowered if ch.isalnum())
    if lowered in _WEAK_TOKEN_WORDS or compact in _WEAK_TOKEN_WORDS:
        return True
    if any(word in lowered for word in ("changeme", "password", "secret", "default")):
        return True
    if len(set(t)) < 8:
        return True
    classes = 0
    classes += any(ch.islower() for ch in t)
    classes += any(ch.isupper() for ch in t)
    classes += any(ch.isdigit() for ch in t)
    classes += any(not ch.isalnum() for ch in t)
    # Long lowercase hex/base64-ish strings are acceptable, but short strings
    # need more variety than a single character class.
    if len(t) < 48 and classes < 2:
        return True
    return False


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _session_key(secret: str) -> bytes:
    return hashlib.sha256(("yang-session\0" + secret).encode("utf-8")).digest()


def _sign_payload(payload_b64: str, secret: str) -> str:
    return _b64encode(hmac.new(_session_key(secret), payload_b64.encode("ascii"), hashlib.sha256).digest())


def _cookie_date(timestamp: float) -> str:
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(timestamp))


def make_session_token(
    secret: str,
    *,
    max_age: int = DEFAULT_SESSION_TTL_SECONDS,
    now: Optional[float] = None,
) -> str:
    """Return an opaque HMAC-signed session token with an embedded expiry."""

    if not secret:
        raise SessionCookieError("cannot create a session without an auth token")
    now = time.time() if now is None else float(now)
    max_age = max(1, int(max_age))
    payload = {
        "v": 1,
        "iat": int(now),
        "exp": int(now) + max_age,
        "nonce": secrets.token_urlsafe(18),
    }
    payload_raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64encode(payload_raw)
    return payload_b64 + "." + _sign_payload(payload_b64, secret)


def verify_session_token(
    token: Optional[str],
    secret: str,
    *,
    now: Optional[float] = None,
) -> bool:
    """Return True when ``token`` has a valid signature and is unexpired."""

    if not token or not secret:
        return False
    try:
        payload_b64, sig = str(token).split(".", 1)
    except ValueError:
        return False
    if not payload_b64 or not sig:
        return False
    expected = _sign_payload(payload_b64, secret)
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return False
    if payload.get("v") != 1:
        return False
    try:
        exp = int(payload["exp"])
        iat = int(payload.get("iat", 0))
    except Exception:
        return False
    when = time.time() if now is None else float(now)
    if exp <= when:
        return False
    # Reject absurd future-issued tokens to limit usefulness of copied cookies
    # if a server clock is temporarily wrong.
    if iat > when + 300:
        return False
    return True


def make_session_cookie(
    secret: str,
    *,
    cookie_name: str = DEFAULT_SESSION_COOKIE_NAME,
    max_age: int = DEFAULT_SESSION_TTL_SECONDS,
    secure: bool = False,
    path: str = "/",
    now: Optional[float] = None,
) -> str:
    """Create a ``Set-Cookie`` value for an expiring signed session.

    The cookie is always ``HttpOnly`` and ``SameSite=Strict``.  ``Secure`` is
    controlled by the caller/policy so local HTTP development can remain usable
    while production deployments can require HTTPS-only cookies.
    """

    if not _valid_cookie_name(cookie_name):
        raise SessionCookieError("invalid cookie name")
    token = make_session_token(secret, max_age=max_age, now=now)
    morsel = cookies.SimpleCookie()
    morsel[cookie_name] = token
    c = morsel[cookie_name]
    c["path"] = path or "/"
    c["max-age"] = str(max(1, int(max_age)))
    c["expires"] = _cookie_date((time.time() if now is None else float(now)) + max(1, int(max_age)))
    c["httponly"] = True
    c["samesite"] = "Strict"
    if secure:
        c["secure"] = True
    return c.OutputString()


def clear_session_cookie(
    *,
    cookie_name: str = DEFAULT_SESSION_COOKIE_NAME,
    secure: bool = False,
    path: str = "/",
) -> str:
    """Create a ``Set-Cookie`` value that removes the session cookie."""

    if not _valid_cookie_name(cookie_name):
        raise SessionCookieError("invalid cookie name")
    morsel = cookies.SimpleCookie()
    morsel[cookie_name] = ""
    c = morsel[cookie_name]
    c["path"] = path or "/"
    c["max-age"] = "0"
    c["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
    c["httponly"] = True
    c["samesite"] = "Strict"
    if secure:
        c["secure"] = True
    return c.OutputString()


def parse_cookie_header(cookie_header: Optional[str]) -> Dict[str, str]:
    """Parse an HTTP Cookie header into a plain dict.

    Malformed cookies are treated as absent instead of raising; authentication
    callers should fail closed.
    """

    if not cookie_header:
        return {}
    try:
        jar = cookies.SimpleCookie()
        jar.load(cookie_header)
    except Exception:
        return {}
    return {name: morsel.value for name, morsel in jar.items()}


def verify_session_cookie(
    cookie_header: Optional[str],
    secret: str,
    *,
    cookie_name: str = DEFAULT_SESSION_COOKIE_NAME,
    now: Optional[float] = None,
) -> bool:
    """Return True if ``cookie_header`` contains a valid session cookie."""

    token = parse_cookie_header(cookie_header).get(cookie_name)
    return verify_session_token(token, secret, now=now)


def extract_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """Extract a bearer token from an Authorization header."""

    if not authorization_header:
        return None
    parts = str(authorization_header).strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _constant_time_text_equals(a: object, b: object) -> bool:
    return hmac.compare_digest(str(a).encode("utf-8"), str(b).encode("utf-8"))


def validate_token(supplied_token: Optional[str], expected_token: str) -> bool:
    """Constant-time validation for login/body tokens."""

    if not supplied_token or not expected_token:
        return False
    return _constant_time_text_equals(supplied_token, expected_token)


def validate_bearer(authorization_header: Optional[str], expected_token: str) -> bool:
    """Validate ``Authorization: Bearer ...`` against ``expected_token``."""

    return validate_token(extract_bearer_token(authorization_header), expected_token)


def authenticate_request(
    headers: Mapping[str, str],
    policy: AuthPolicy,
) -> bool:
    """Validate request headers using bearer auth or a signed session cookie."""

    # BaseHTTPRequestHandler's headers object is case-insensitive, but tests may
    # pass plain dicts.  Support both.
    auth_header = headers.get("Authorization") or headers.get("authorization")
    cookie_header = headers.get("Cookie") or headers.get("cookie")
    return policy.validate_bearer(auth_header) or policy.verify_session_cookie(cookie_header)


def origin_allowed(
    origin: Optional[str],
    public_origin: str,
) -> bool:
    """Return True when a browser mutation origin matches policy.

    Empty ``public_origin`` means no origin policy is configured.  Empty
    ``origin`` is accepted so same-origin forms/non-browser clients without an
    Origin header are not rejected by this helper; server integration can choose
    to be stricter for cookie-authenticated mutations.
    """

    expected = _clean(public_origin).rstrip("/")
    if not expected:
        return True
    got = _clean(origin).rstrip("/")
    if not got:
        return True
    return _constant_time_text_equals(got, expected)


class FailureThrottle:
    """Bounded in-memory failed-attempt throttle.

    The throttle tracks failures per key (typically client IP).  It keeps at
    most ``max_keys`` entries, evicting the oldest entry when the bound is
    exceeded.  After ``limit`` failures in ``window_seconds``, ``retry_after``
    returns a positive number until the window expires.  Successful login should
    call ``reset(key)``.
    """

    def __init__(
        self,
        *,
        limit: int = 5,
        window_seconds: int = 60,
        max_keys: int = 1024,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self.max_keys = max(1, int(max_keys))
        self._now = now
        self._lock = threading.Lock()
        self._items: Dict[str, Tuple[float, int, float]] = {}

    def _key(self, key: object) -> str:
        text = str(key or "").strip()
        return text[:200] or "unknown"

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        stale = [key for key, (first, _count, _last) in self._items.items() if first <= cutoff]
        for key in stale:
            self._items.pop(key, None)
        while len(self._items) > self.max_keys:
            oldest = min(self._items.items(), key=lambda item: item[1][2])[0]
            self._items.pop(oldest, None)

    def retry_after(self, key: object) -> int:
        """Seconds until ``key`` may try again, or 0 when allowed."""

        now = self._now()
        k = self._key(key)
        with self._lock:
            self._prune(now)
            item = self._items.get(k)
            if not item:
                return 0
            first, count, _last = item
            if count < self.limit:
                return 0
            wait = int((first + self.window_seconds) - now)
            return max(0, wait)

    def allowed(self, key: object) -> bool:
        return self.retry_after(key) <= 0

    def record_failure(self, key: object) -> int:
        """Record a failure and return current ``retry_after`` seconds."""

        now = self._now()
        k = self._key(key)
        with self._lock:
            self._prune(now)
            first, count, _last = self._items.get(k, (now, 0, now))
            self._items[k] = (first, count + 1, now)
            self._prune(now)
        return self.retry_after(k)

    def reset(self, key: object) -> None:
        """Clear failure history for ``key`` after successful authentication."""

        k = self._key(key)
        with self._lock:
            self._items.pop(k, None)

    def snapshot(self) -> Dict[str, Tuple[float, int, float]]:
        """Return a copy of internal state for tests/diagnostics."""

        with self._lock:
            return dict(self._items)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


__all__ = [
    "AUTH_TOKEN_ENV",
    "PRODUCTION_ENV",
    "ENV_ENV",
    "PUBLIC_ORIGIN_ENV",
    "SESSION_COOKIE_NAME_ENV",
    "SESSION_TTL_ENV",
    "AUTH_SECURE_COOKIE_ENV",
    "DEFAULT_SESSION_COOKIE_NAME",
    "DEFAULT_SESSION_TTL_SECONDS",
    "MIN_STRONG_TOKEN_LENGTH",
    "MAX_TOKEN_LENGTH",
    "AuthConfigError",
    "AuthError",
    "AuthPolicy",
    "TokenPolicy",
    "FailureThrottle",
    "SessionCookieError",
    "authenticate_request",
    "clear_session_cookie",
    "extract_bearer_token",
    "is_loopback_host",
    "is_production_mode",
    "is_weak_token",
    "load_auth_policy_from_env",
    "load_policy_from_env",
    "load_token_policy_from_env",
    "make_session_cookie",
    "make_session_token",
    "origin_allowed",
    "parse_cookie_header",
    "validate_bearer",
    "validate_token",
    "verify_session_cookie",
    "verify_session_token",
]
