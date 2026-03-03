"""Authentication routes: login, refresh, logout, MFA, password reset, WS token."""

import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.mfa import generate_qr_data_url, generate_totp_secret, verify_totp
from app.core.rate_limit import RATE_AUTH, limiter
from app.core.redis import (
    get_redis,
    is_refresh_token_revoked,
    revoke_all_user_tokens,
    revoke_refresh_token,
)
from app.core.security import (
    create_access_token,
    create_mfa_session_token,
    create_refresh_token,
    create_ws_token,
    decode_mfa_session_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    FCMTokenRequest,
    LoginRequest,
    LoginResponse,
    MFAConfirmRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
    WSTokenResponse,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Helpers ─────────────────────────────────────────────────────────────

_RESET_TOKEN_PREFIX = "password_reset:"
_RESET_TOKEN_TTL = 3600  # 1 hour


def _issue_tokens(user: User) -> dict:
    """Create access + refresh tokens and return them as a dict."""
    user_id = str(user.id)
    org_id = str(user.org_id)
    role = user.role.value

    access_token = create_access_token(user_id, org_id, role)
    refresh_token, _ = create_refresh_token(user_id, org_id, role)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ── POST /login ────────────────────────────────────────────────────────

_LOGIN_FAIL_PREFIX = "login_fail:"
_LOGIN_FAIL_TTL = 900  # 15 minutes
_LOGIN_FAIL_MAX = 5


@router.post("/login", response_model=LoginResponse)
@limiter.limit(RATE_AUTH)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Authenticate with email + password. Returns tokens or MFA challenge."""
    # Check account lockout
    lockout_key = f"{_LOGIN_FAIL_PREFIX}{body.email.lower()}"
    fail_count = await r.get(lockout_key)
    if fail_count and int(fail_count) >= _LOGIN_FAIL_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed login attempts. Try again later.",
        )

    result = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    user = result.scalars().first()

    if user is None or not verify_password(body.password, user.password_hash):
        # Increment failed login counter
        pipe = r.pipeline()
        pipe.incr(lockout_key)
        pipe.expire(lockout_key, _LOGIN_FAIL_TTL)
        await pipe.execute()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Check MFA requirement
    if user.mfa_enabled and user.totp_secret:
        mfa_session = create_mfa_session_token(
            str(user.id), str(user.org_id), user.role.value
        )
        return LoginResponse(
            access_token="",
            refresh_token="",
            mfa_required=True,
            mfa_session_token=mfa_session,
        )

    # Clear failed login counter on success
    await r.delete(lockout_key)

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    tokens = _issue_tokens(user)
    return LoginResponse(**tokens)


# ── POST /refresh ──────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(RATE_AUTH)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Exchange a valid refresh token for a new access + refresh pair."""
    try:
        payload = decode_refresh_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    jti = payload.get("jti")
    user_id = payload.get("sub")

    if not jti or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    # Check revocation
    if await is_refresh_token_revoked(r, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Revoke the old refresh token (rotation)
    await revoke_refresh_token(r, jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    # Load user to get current role
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access = create_access_token(str(user.id), str(user.org_id), user.role.value)
    new_refresh, _ = create_refresh_token(str(user.id), str(user.org_id), user.role.value)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


# ── POST /logout ───────────────────────────────────────────────────────

@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: RefreshRequest,
    r: aioredis.Redis = Depends(get_redis),
):
    """Revoke the provided refresh token."""
    try:
        payload = decode_refresh_token(body.refresh_token)
    except JWTError:
        # Silently accept invalid tokens on logout
        return MessageResponse(message="Logged out")

    jti = payload.get("jti")
    if jti:
        await revoke_refresh_token(r, jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    return MessageResponse(message="Logged out")


# ── GET /ws-token ──────────────────────────────────────────────────────

@router.get("/ws-token", response_model=WSTokenResponse)
async def get_ws_token(
    current_user: User = Depends(get_current_active_user),
):
    """Generate a short-lived WebSocket handshake token (60s TTL)."""
    token = create_ws_token(
        str(current_user.id), str(current_user.org_id), current_user.role.value
    )
    return WSTokenResponse(token=token, expires_in=60)


# ── POST /mfa/setup ───────────────────────────────────────────────────

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    r: aioredis.Redis = Depends(get_redis),
):
    """Generate a TOTP secret and QR code for MFA enrollment."""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    secret = generate_totp_secret()

    # Store secret in Redis temporarily (5-minute TTL) instead of DB
    await r.set(f"mfa_setup:{current_user.id}", secret, ex=300)

    provisioning_uri = f"otpauth://totp/OFMaint%20CMMS:{current_user.email}?secret={secret}&issuer=OFMaint%20CMMS"
    qr_data_url = generate_qr_data_url(secret, current_user.email)

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_data_url=qr_data_url,
    )


# ── POST /mfa/verify ──────────────────────────────────────────────────

@router.post("/mfa/verify", response_model=MessageResponse)
@limiter.limit(RATE_AUTH)
async def mfa_verify(
    request: Request,
    body: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    r: aioredis.Redis = Depends(get_redis),
):
    """Verify a TOTP code and enable MFA on the account."""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    # Read the pending secret from Redis (set during /mfa/setup)
    redis_key = f"mfa_setup:{current_user.id}"
    secret = await r.get(redis_key)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Call /mfa/setup first to generate a TOTP secret",
        )
    if isinstance(secret, bytes):
        secret = secret.decode()

    if not verify_totp(secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    # Only persist the secret after successful verification
    current_user.totp_secret = secret
    current_user.mfa_enabled = True
    await db.flush()

    # Clean up the temporary Redis key
    await r.delete(redis_key)

    return MessageResponse(message="MFA enabled successfully")


# ── POST /mfa/confirm ─────────────────────────────────────────────────

@router.post("/mfa/confirm", response_model=TokenResponse)
@limiter.limit(RATE_AUTH)
async def mfa_confirm(
    request: Request,
    body: MFAConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete MFA challenge during login by submitting the TOTP code."""
    try:
        payload = decode_mfa_session_token(body.mfa_session_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA session token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA session",
        )

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    if not user.totp_secret or not verify_totp(user.totp_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    access = create_access_token(str(user.id), str(user.org_id), user.role.value)
    refresh, _ = create_refresh_token(str(user.id), str(user.org_id), user.role.value)
    return TokenResponse(access_token=access, refresh_token=refresh)


# ── POST /mfa/disable ─────────────────────────────────────────────────

@router.post("/mfa/disable", response_model=MessageResponse)
@limiter.limit(RATE_AUTH)
async def mfa_disable(
    request: Request,
    body: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Disable MFA on the account. Requires a valid TOTP code."""
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled",
        )

    if not current_user.totp_secret or not verify_totp(current_user.totp_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    current_user.mfa_enabled = False
    current_user.totp_secret = None
    await db.flush()
    return MessageResponse(message="MFA disabled successfully")


# ── POST /password-reset-request ───────────────────────────────────────

@router.post("/password-reset-request", response_model=MessageResponse)
@limiter.limit(RATE_AUTH)
async def password_reset_request(
    request: Request,
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Initiate a password reset. Generates a token and (in production) sends an email."""
    # Always return success to avoid user enumeration
    result = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    user = result.scalars().first()

    if user and user.is_active:
        reset_token = str(uuid.uuid4())
        key = f"{_RESET_TOKEN_PREFIX}{reset_token}"
        await r.set(key, str(user.id), ex=_RESET_TOKEN_TTL)

        # In production, send email with reset link containing the token.
        # For now the token is stored in Redis and consumed via /password-reset.
        import logging
        logging.getLogger(__name__).info(
            "Password reset token generated for user %s: %s",
            user.email,
            reset_token,
        )

    return MessageResponse(message="If an account with that email exists, a reset link has been sent")


# ── POST /password-reset ──────────────────────────────────────────────

@router.post("/password-reset", response_model=MessageResponse)
@limiter.limit(RATE_AUTH)
async def password_reset(
    request: Request,
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Consume a password-reset token and set a new password."""
    key = f"{_RESET_TOKEN_PREFIX}{body.token}"
    user_id_str = await r.get(key)

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id_str))
    )
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_password(body.new_password)
    await db.flush()

    # Delete the token so it cannot be reused
    await r.delete(key)

    # Revoke all existing sessions for this user
    await revoke_all_user_tokens(r, str(user.id), settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    return MessageResponse(message="Password has been reset successfully")
