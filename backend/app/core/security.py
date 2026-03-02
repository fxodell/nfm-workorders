"""
JWT token management (access, refresh, WebSocket, MFA session) and password
hashing utilities.

Token types and their purposes:
- **Access token**: Short-lived (15 min default). Authorizes API requests.
- **Refresh token**: Longer-lived (7 days default). Used to obtain new access
  tokens. Rotated on every use; revoked JTI stored in Redis.
- **WS token**: Very short-lived (60 s). Exchanged during the WebSocket
  handshake to authenticate the connection.
- **MFA session token**: Short-lived (2 min). Issued after successful
  password verification when MFA is required. Presented alongside the TOTP
  code to complete login.

All tokens embed a ``jti`` (JWT ID) for revocation tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password hashing ───────────────────────────────────────────────────

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* with cost factor 12."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches the stored *hashed* value."""
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ─────────────────────────────────────────────────────────

ALGORITHM = "HS256"


def _build_payload(
    user_id: str,
    org_id: str,
    role: str,
    token_type: str,
    expires_delta: timedelta,
    jti: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "type": token_type,
        "jti": jti or str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }


# ── Access tokens ──────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    org_id: str,
    role: str,
) -> str:
    """Create a short-lived access JWT."""
    payload = _build_payload(
        user_id=user_id,
        org_id=org_id,
        role=role,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify an access JWT. Raises ``JWTError`` on failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type: expected access token")
    return payload


# ── Refresh tokens ─────────────────────────────────────────────────────

def create_refresh_token(
    user_id: str,
    org_id: str,
    role: str,
    jti: str | None = None,
) -> tuple[str, str]:
    """Create a refresh JWT.

    Returns ``(encoded_token, jti)`` so the caller can store the JTI for
    later revocation.
    """
    token_jti = jti or str(uuid.uuid4())
    payload = _build_payload(
        user_id=user_id,
        org_id=org_id,
        role=role,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        jti=token_jti,
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM), token_jti


def decode_refresh_token(token: str) -> dict:
    """Decode and verify a refresh JWT. Raises ``JWTError`` on failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "refresh":
        raise JWTError("Invalid token type: expected refresh token")
    return payload


# ── WebSocket tokens ───────────────────────────────────────────────────

WS_TOKEN_TTL = timedelta(seconds=60)


def create_ws_token(user_id: str, org_id: str, role: str) -> str:
    """Create a very short-lived token for the WebSocket handshake."""
    payload = _build_payload(
        user_id=user_id,
        org_id=org_id,
        role=role,
        token_type="ws",
        expires_delta=WS_TOKEN_TTL,
    )
    return jwt.encode(payload, settings.WS_SECRET_KEY, algorithm=ALGORITHM)


def decode_ws_token(token: str) -> dict:
    """Decode and verify a WebSocket handshake JWT."""
    payload = jwt.decode(token, settings.WS_SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "ws":
        raise JWTError("Invalid token type: expected ws token")
    return payload


# ── MFA session tokens ─────────────────────────────────────────────────

MFA_SESSION_TTL = timedelta(minutes=2)


def create_mfa_session_token(user_id: str, org_id: str, role: str) -> str:
    """Create a short-lived token issued after password verification.

    The client must present this token alongside the TOTP code to finish the
    MFA login flow.
    """
    payload = _build_payload(
        user_id=user_id,
        org_id=org_id,
        role=role,
        token_type="mfa_session",
        expires_delta=MFA_SESSION_TTL,
    )
    return jwt.encode(payload, settings.MFA_SECRET_KEY, algorithm=ALGORITHM)


def decode_mfa_session_token(token: str) -> dict:
    """Decode and verify an MFA session JWT."""
    payload = jwt.decode(token, settings.MFA_SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "mfa_session":
        raise JWTError("Invalid token type: expected mfa_session token")
    return payload
