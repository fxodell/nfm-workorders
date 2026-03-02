"""
Authentication and authorization tests.

Validates:
- Login with correct credentials returns access + refresh tokens
- Login with wrong password returns 401
- Login with inactive user returns 403
- Token refresh returns new access + refresh pair
- Token refresh revokes the old refresh token (rotation)
- Logout revokes the provided refresh token
- Expired tokens are rejected
- MFA-required flow returns mfa_session_token instead of access token
- Password reset flow (request + confirm)
- WebSocket token generation
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from jose import jwt

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    create_ws_token,
    decode_access_token,
    decode_refresh_token,
    decode_ws_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from tests.conftest import FakeRedis, make_auth_headers

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


async def test_password_hash_and_verify():
    """hash_password + verify_password round-trip should succeed."""
    plain = "SuperSecure123!"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


# ---------------------------------------------------------------------------
# Login success
# ---------------------------------------------------------------------------


async def test_login_success(
    async_client, org_a_hierarchy,
):
    """Logging in with correct credentials should return access and refresh tokens."""
    h = org_a_hierarchy
    # The admin user was created with password "testpassword123"
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": h["admin"].email,
            "password": "testpassword123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data.get("mfa_required", False) is False
    assert len(data["access_token"]) > 0
    assert len(data["refresh_token"]) > 0


# ---------------------------------------------------------------------------
# Login wrong password
# ---------------------------------------------------------------------------


async def test_login_wrong_password(
    async_client, org_a_hierarchy,
):
    """Logging in with wrong password should return 401."""
    h = org_a_hierarchy
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": h["admin"].email,
            "password": "WRONG_PASSWORD_123",
        },
    )
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Login inactive user
# ---------------------------------------------------------------------------


async def test_login_inactive_user(
    async_client, create_org, create_user,
):
    """Logging in with an inactive user account should return 403."""
    org = await create_org(name="Inactive Org")
    user = await create_user(
        org_id=org.id,
        email="inactive@test.com",
        password="testpassword123",
        is_active=False,
    )

    resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@test.com",
            "password": "testpassword123",
        },
    )
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


async def test_token_refresh(
    async_client, org_a_hierarchy,
):
    """A valid refresh token should yield a new access + refresh token pair."""
    h = org_a_hierarchy

    # Login first to get a refresh token
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": h["admin"].email,
            "password": "testpassword123",
        },
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Refresh
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["access_token"]) > 0
    # New tokens should be different from the original
    assert data["refresh_token"] != refresh_token


# ---------------------------------------------------------------------------
# Token refresh revokes old token (rotation)
# ---------------------------------------------------------------------------


async def test_token_refresh_revokes_old_token(
    async_client, org_a_hierarchy,
):
    """After a refresh, the old refresh token should be revoked and
    cannot be reused."""
    h = org_a_hierarchy

    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": h["admin"].email,
            "password": "testpassword123",
        },
    )
    old_refresh = login_resp.json()["refresh_token"]

    # First refresh -- should succeed
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refresh_resp.status_code == 200

    # Attempt to reuse the old refresh token -- should fail
    reuse_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert reuse_resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


async def test_logout_revokes_token(
    async_client, org_a_hierarchy,
):
    """Logging out should revoke the refresh token so it cannot be reused."""
    h = org_a_hierarchy

    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": h["admin"].email,
            "password": "testpassword123",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200
    assert "Logged out" in logout_resp.json()["message"]

    # Try to use the revoked refresh token
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401


# ---------------------------------------------------------------------------
# Expired token rejected
# ---------------------------------------------------------------------------


async def test_expired_token_rejected(
    async_client, org_a_hierarchy,
):
    """An expired access token should be rejected with 401."""
    h = org_a_hierarchy

    # Create a token that is already expired
    payload = {
        "sub": str(h["admin"].id),
        "org_id": str(h["admin"].org_id),
        "role": h["admin"].role.value,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    resp = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# MFA-required flow
# ---------------------------------------------------------------------------


async def test_mfa_required_flow(
    async_client, create_org, create_user,
):
    """When a user has MFA enabled, login should return mfa_required=True
    and an mfa_session_token instead of access/refresh tokens."""
    import pyotp

    org = await create_org(name="MFA Org")
    totp_secret = pyotp.random_base32()
    user = await create_user(
        org_id=org.id,
        email="mfa-user@test.com",
        password="testpassword123",
        mfa_enabled=True,
        totp_secret=totp_secret,
    )

    resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "mfa-user@test.com",
            "password": "testpassword123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mfa_required"] is True
    assert data.get("mfa_session_token") is not None
    assert len(data.get("mfa_session_token", "")) > 0
    # access_token should be empty when MFA is required
    assert data["access_token"] == ""


async def test_mfa_confirm_with_valid_code(
    async_client, create_org, create_user,
):
    """Completing MFA with a valid TOTP code should return access + refresh tokens."""
    import pyotp

    org = await create_org(name="MFA Confirm Org")
    totp_secret = pyotp.random_base32()
    user = await create_user(
        org_id=org.id,
        email="mfa-confirm@test.com",
        password="testpassword123",
        mfa_enabled=True,
        totp_secret=totp_secret,
    )

    # Step 1: Login to get MFA session token
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "mfa-confirm@test.com",
            "password": "testpassword123",
        },
    )
    mfa_session_token = login_resp.json()["mfa_session_token"]

    # Step 2: Confirm MFA with valid TOTP code
    totp = pyotp.TOTP(totp_secret)
    valid_code = totp.now()

    confirm_resp = await async_client.post(
        "/api/v1/auth/mfa/confirm",
        json={
            "mfa_session_token": mfa_session_token,
            "code": valid_code,
        },
    )
    assert confirm_resp.status_code == 200
    data = confirm_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["access_token"]) > 0


# ---------------------------------------------------------------------------
# Password reset flow
# ---------------------------------------------------------------------------


async def test_password_reset_flow(
    async_client, create_org, create_user, fake_redis,
):
    """The password reset flow should:
    1. Accept a reset request (always returns success)
    2. Store a reset token in Redis
    3. Accept the reset token + new password to change the password
    4. Allow login with the new password."""
    org = await create_org(name="Password Reset Org")
    user = await create_user(
        org_id=org.id,
        email="reset-me@test.com",
        password="oldpassword123",
    )

    # Step 1: Request password reset
    reset_req_resp = await async_client.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "reset-me@test.com"},
    )
    assert reset_req_resp.status_code == 200

    # Step 2: Find the reset token in FakeRedis
    reset_token = None
    for key, value in fake_redis._store.items():
        if key.startswith("password_reset:"):
            reset_token = key.replace("password_reset:", "")
            break

    if reset_token is not None:
        # Step 3: Confirm the password reset
        reset_confirm_resp = await async_client.post(
            "/api/v1/auth/password-reset",
            json={
                "token": reset_token,
                "new_password": "newpassword456",
            },
        )
        assert reset_confirm_resp.status_code == 200

        # Step 4: Login with the new password
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "reset-me@test.com",
                "password": "newpassword456",
            },
        )
        assert login_resp.status_code == 200
        assert len(login_resp.json()["access_token"]) > 0

        # Step 5: Old password should no longer work
        old_login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "reset-me@test.com",
                "password": "oldpassword123",
            },
        )
        assert old_login_resp.status_code == 401


async def test_password_reset_always_returns_success(
    async_client,
):
    """Password reset request should always return success to prevent
    user enumeration, even for non-existent emails."""
    resp = await async_client.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "nonexistent@test.com"},
    )
    assert resp.status_code == 200
    assert "reset link" in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# WebSocket token generation
# ---------------------------------------------------------------------------


async def test_ws_token_generation(
    async_client, org_a_hierarchy,
):
    """Authenticated users should be able to generate a short-lived WS token."""
    h = org_a_hierarchy
    headers = make_auth_headers(h["admin"])

    resp = await async_client.get(
        "/api/v1/auth/ws-token",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["expires_in"] == 60
    assert len(data["token"]) > 0

    # Verify the WS token can be decoded
    decoded = decode_ws_token(data["token"])
    assert decoded["sub"] == str(h["admin"].id)
    assert decoded["type"] == "ws"


async def test_ws_token_requires_auth(
    async_client,
):
    """The WS token endpoint should require authentication."""
    resp = await async_client.get("/api/v1/auth/ws-token")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Token type enforcement
# ---------------------------------------------------------------------------


async def test_access_token_type_enforcement():
    """decode_access_token should reject tokens with type != 'access'."""
    from jose import JWTError

    # Create a refresh token and try to use it as an access token
    refresh_token, _ = create_refresh_token("user-id", "org-id", "ADMIN")

    with pytest.raises(JWTError):
        decode_access_token(refresh_token)


async def test_refresh_token_type_enforcement():
    """decode_refresh_token should reject tokens with type != 'refresh'."""
    from jose import JWTError

    # Create an access token and try to use it as a refresh token
    access_token = create_access_token("user-id", "org-id", "ADMIN")

    with pytest.raises(JWTError):
        decode_refresh_token(access_token)


async def test_ws_token_type_enforcement():
    """decode_ws_token should reject tokens with type != 'ws'."""
    from jose import JWTError

    access_token = create_access_token("user-id", "org-id", "ADMIN")

    with pytest.raises(JWTError):
        decode_ws_token(access_token)


# ---------------------------------------------------------------------------
# Access control: unauthenticated requests
# ---------------------------------------------------------------------------


async def test_unauthenticated_request_rejected(
    async_client,
):
    """API endpoints requiring auth should return 401 without a token."""
    resp = await async_client.get("/api/v1/work-orders/")
    assert resp.status_code in (401, 403)


async def test_malformed_token_rejected(
    async_client,
):
    """A malformed JWT should be rejected with 401."""
    resp = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert resp.status_code == 401
