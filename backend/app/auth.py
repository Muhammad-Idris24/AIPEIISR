"""Authentication and role resolution scaffold for AIPEIISR.

Phase 6 delivery: production auth scaffold layered on top of the existing
``x-role`` development header. Priority order for role resolution is:

1. ``Authorization: Bearer <JWT>`` header (production) — when Auth0 is
   configured, only Auth0 RS256 access tokens with the configured issuer and
   audience are accepted. Auth0 public signing keys are retrieved from its
   JWKS endpoint; no Auth0 secret is stored by this API.
2. ``Authorization: Bearer <JWT>`` header (legacy local scaffold) — an
   HS256 token is accepted only when Auth0 is *not* configured and
   ``JWT_SECRET`` is present.
3. ``x-role`` header (development-only fallback). This allows the existing
   Next.js ``x-role=ADMIN/ANALYST`` development headers to keep working for
   docker-compose local and pytest loops. ``X_ROLE_ENABLED=false`` env var
   disables this fallback if you want to enforce JWT-only mode on a
   pre-production staging box.
3. Default ``CITIZEN`` — chosen when neither auth method produced a role.

The public endpoints (``/public/*``, ``GET /citizen/*``) do not require
any role and will never hit a 403 purely because of missing auth: their
role argument defaults to CITIZEN anyway.

Production hardening TODO (see KNOWN_ISSUES.md):
- Issue real tokens via a login endpoint (user DB table + bcrypt or
  external IdP like Google OAuth/OpenID Connect/Azure AD).
- Replace JWT_HARDCODED_USER_TOKENS below with a proper token issuance
  flow — currently they are EXAMPLE tokens that only work when JWT_SECRET
  is set, and they are the only scaffolded identity for this phase.
- Add refresh tokens / rotation / logout.
- Add rate limiting / audit logs around login failures.
"""
from __future__ import annotations
import os
import base64
import hashlib
import hmac
import json
from enum import Enum
from typing import Any, Dict, Optional


class Role(str, Enum):
    CITIZEN = "CITIZEN"
    ANALYST = "ANALYST"
    REVIEWER = "REVIEWER"
    MANAGER = "MANAGER"
    PUBLISHER = "PUBLISHER"
    ADMIN = "ADMIN"
    PARTNER = "PARTNER"
    AI_WORKER = "AI_WORKER"


# ----------------------------- JWT helpers ---------------------------------
# We intentionally avoid requiring pyjwt as a hard dependency: if the package
# is missing (dev/test loops with the default mock providers + x-role headers)
# the application still boots and works correctly. When JWT_SECRET is set and
# pyjwt is available, the Bearer path activates automatically.
try:  # pragma: no cover - import depends on optional install
    import jwt  # type: ignore

    _HAS_JWT = True
except Exception:  # pragma: no cover
    jwt = None  # type: ignore
    _HAS_JWT = False


JWT_SECRET: Optional[str] = os.environ.get("JWT_SECRET") or None
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
X_ROLE_ENABLED = (os.environ.get("X_ROLE_ENABLED") or "true").lower() not in {"0", "false", "no", "off"}
JWT_ROLE_CLAIM = os.environ.get("JWT_ROLE_CLAIM", "role")
JWT_USER_CLAIM = os.environ.get("JWT_USER_CLAIM", "sub")
AUTH0_DOMAIN = (os.environ.get("AUTH0_DOMAIN") or "").strip().rstrip("/")
AUTH0_AUDIENCE = (os.environ.get("AUTH0_AUDIENCE") or "").strip()
AUTH0_ROLES_CLAIM = (os.environ.get("AUTH0_ROLES_CLAIM") or "https://api.aipeiisr.local/roles").strip()
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/" if AUTH0_DOMAIN else ""
AUTH0_ENABLED = bool(AUTH0_DOMAIN and AUTH0_AUDIENCE)
_AUTH0_JWK_CLIENT: Any = None
_LAST_AUTH0_VALIDATION_ERROR: Optional[str] = None


def _auth0_jwk_client() -> Any:
    """Return a cached Auth0 JWKS client, without embedding any private key."""
    global _AUTH0_JWK_CLIENT
    if not AUTH0_ENABLED or not _HAS_JWT:
        return None
    if _AUTH0_JWK_CLIENT is None:
        _AUTH0_JWK_CLIENT = jwt.PyJWKClient(
            f"{AUTH0_ISSUER}.well-known/jwks.json", cache_keys=True, lifespan=300, timeout=5
        )
    return _AUTH0_JWK_CLIENT


def _decode_auth0_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify an Auth0 RS256 access token, including issuer and audience.

    Any failure is deliberately indistinguishable to callers: an invalid
    token never produces an authenticated role or actor.
    """
    global _LAST_AUTH0_VALIDATION_ERROR
    if not AUTH0_ENABLED or not _HAS_JWT:
        return None
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            return None
        key = _auth0_jwk_client().get_signing_key_from_jwt(token).key
        decoded = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=AUTH0_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
        _LAST_AUTH0_VALIDATION_ERROR = None
        return decoded
    except Exception as exc:
        # Development diagnostics deliberately record only the exception class.
        # Do not log tokens, headers, claims, keys, or exception text.
        _LAST_AUTH0_VALIDATION_ERROR = type(exc).__name__
        return None


def auth0_validation_diagnostic() -> Optional[str]:
    """Return an error category for local troubleshooting, never token data."""
    return _LAST_AUTH0_VALIDATION_ERROR


def _legacy_hs256_decode(token: str, secret: str) -> Optional[Dict]:
    """Minimal fallback HS256 verifier used when ``pyjwt`` is not installed.

    Supports the EXAMPLE hardcoded tokens below and tokens issued in the same
    way.  If a verifiable signature cannot be confirmed we return ``None``
    (so the caller falls through to x-role / CITIZEN instead of trusting a
    tampered token). Supports ``exp`` claim when present (integer unix
    seconds). Ignores ``nbf``/``iat`` for simplicity — those are optional
    in the scaffold.
    """
    import time
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        def b64url_decode(s: str) -> bytes:
            pad = "=" * (-len(s) % 4)
            return base64.urlsafe_b64decode(s + pad)
        header = json.loads(b64url_decode(header_b64).decode())
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return None
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected = base64.urlsafe_b64encode(
            hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        ).decode().rstrip("=")
        if not hmac.compare_digest(expected, sig_b64):
            return None
        payload = json.loads(b64url_decode(payload_b64).decode())
        if isinstance(payload.get("exp"), int) and int(time.time()) > payload["exp"]:
            return None
        return payload
    except Exception:
        return None


def decode_bearer_token(bearer: str) -> Optional[Dict]:
    """Decode and verify the content of an ``Authorization: Bearer …`` value.

    Returns the decoded payload dict on success, or ``None`` on any failure
    (missing secret, missing pyjwt, bad signature, expired, malformed).
    On failure the caller must NOT treat this as a 401/403 by itself — it
    should fall back to the dev x-role header (if enabled) then CITIZEN.
    """
    token = bearer.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return None
    if AUTH0_ENABLED:
        return _decode_auth0_token(token)
    if not JWT_SECRET:
        return None
    if _HAS_JWT:  # pragma: no cover - requires optional pyjwt install
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except Exception:
            return None
    return _legacy_hs256_decode(token, JWT_SECRET)


# ------------------------ Example hardcoded tokens -------------------------
# These are HERE as a SCAFFOLD ONLY. In production, replace with a real
# token-issuing login endpoint + proper user directory.
# They are computed deterministically so the scaffold is self-documenting:
#   header = b64urlencode({"alg":"HS256","typ":"JWT"})
#   payload = b64urlencode({"sub":"admin@aipieisr.local","role":"ADMIN","iss":"aipieisr","iat":0,"exp":1<<62})
#   signature = HMAC-SHA256(JWT_SECRET, header.payload)
# The tokens are never valid unless the operator explicitly sets JWT_SECRET
# to the same value in their env. JWT_SECRET unset → Bearer path fully off.
def example_issue_token(sub: str, role: Role, secret: str) -> str:
    """Return a HS256 signed example JWT for the given user/role.

    Used by ``GET /auth/examples`` to print example tokens for local dev.
    Requires a JWT_SECRET (same as will be used for verify). Tokens issued
    by this helper intentionally expire ``1<<62`` seconds after 1970 so
    they will be "valid" for billions of years — fine for a dev scaffold,
    NEVER keep this expiry window in production.
    """
    header_b64 = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(
            {"sub": sub, "role": role.value, "iss": "aipieisr", "iat": 0, "exp": 1 << 62},
            separators=(",", ":"),
        ).encode()
    ).decode().rstrip("=")
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig_b64 = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def examples_for_current_secret() -> Dict[str, str]:
    """Return a mapping of Role -> example JWT if JWT_SECRET is set, else {}."""
    if AUTH0_ENABLED or not JWT_SECRET:
        return {}
    roles = [Role.ADMIN, Role.ANALYST, Role.REVIEWER, Role.PUBLISHER, Role.CITIZEN]
    out: Dict[str, str] = {}
    for r in roles:
        sub = f"{r.value.lower()}@aipieisr.local"
        out[r.value] = example_issue_token(sub, r, JWT_SECRET)
    return out


# --------------------------- Role resolution --------------------------------
def resolve_role(authorization: Optional[str], x_role: Optional[str]) -> Role:
    """Resolve the caller's Role using the JWT > x-role > CITIZEN priority.

    Parameters
    ----------
    authorization:
        Content of the HTTP ``Authorization`` header (raw, including the
        ``Bearer `` prefix when provided). ``None`` or ``''`` if omitted.
    x_role:
        Content of the dev-only ``x-role`` header. ``None`` when omitted.

    Returns
    -------
    Role
        A valid AIPEIISR role. Unknown values fall through to CITIZEN.
    """
    # 1) Production JWT path (Auth0 RS256 when configured; local HS256 only
    # when Auth0 is absent). A valid Auth0 role claim is an array.
    if authorization:
        payload = decode_bearer_token(authorization)
        if payload:
            claim = payload.get(AUTH0_ROLES_CLAIM if AUTH0_ENABLED else JWT_ROLE_CLAIM)
            values = claim if isinstance(claim, list) else [claim]
            resolved = {str(value).upper() for value in values if isinstance(value, str)}
            for candidate in (Role.ADMIN, Role.PUBLISHER, Role.REVIEWER, Role.ANALYST, Role.MANAGER, Role.PARTNER, Role.CITIZEN):
                if candidate.value in resolved:
                    return candidate
            # Bad/missing role claim in an otherwise valid token is always
            # least privilege, never an implicit analyst/admin grant.
            return Role.CITIZEN
    # 2) Dev x-role fallback. Disable in preprod via X_ROLE_ENABLED=false.
    if X_ROLE_ENABLED and x_role:
        try:
            return Role(str(x_role).upper())
        except ValueError:
            return Role.CITIZEN
    # 3) Default.
    return Role.CITIZEN


def resolve_actor(authorization: Optional[str], x_role: Optional[str]) -> str:
    """Resolve an actor name/identifier for audit logs.

    Returns:
        - ``jwt:{sub}`` when a valid JWT with ``sub`` claim is present.
        - ``x-role:{role}`` when the role came from the x-role fallback.
        - ``citizen`` otherwise.
    """
    if authorization:
        payload = decode_bearer_token(authorization)
        if payload:
            sub = payload.get(JWT_USER_CLAIM)
            if isinstance(sub, str) and sub:
                return f"{'auth0' if AUTH0_ENABLED else 'jwt'}:{sub}"
            role = payload.get(JWT_ROLE_CLAIM) or "token"
            return f"jwt:{role}"
    if X_ROLE_ENABLED and x_role:
        return f"x-role:{str(x_role).upper()}"
    return "citizen"
