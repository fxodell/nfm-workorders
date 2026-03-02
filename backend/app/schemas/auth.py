"""Authentication and authorization schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Credentials for email/password login."""

    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("password", mode="before")
    @classmethod
    def strip_password(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class LoginResponse(BaseModel):
    """Response after successful credential validation.

    If ``mfa_required`` is True the client must complete MFA verification
    using the ``mfa_session_token`` before gaining access.  The
    ``access_token`` and ``refresh_token`` will be empty strings in that case.
    """

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_session_token: Optional[str] = None


class RefreshRequest(BaseModel):
    """Request body to exchange a refresh token for a new token pair."""

    refresh_token: str = Field(..., min_length=1)

    @field_validator("refresh_token", mode="before")
    @classmethod
    def strip_refresh_token(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class TokenResponse(BaseModel):
    """Fresh token pair returned after a successful refresh."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MFASetupResponse(BaseModel):
    """Data the client needs to set up a TOTP authenticator app."""

    model_config = ConfigDict(from_attributes=True)

    secret: str
    provisioning_uri: str
    qr_code_data_url: str


class MFAVerifyRequest(BaseModel):
    """Submit a 6-digit TOTP code to enable MFA on the account."""

    code: str = Field(..., pattern=r"^\d{6}$", description="6-digit TOTP code")

    @field_validator("code", mode="before")
    @classmethod
    def strip_code(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class MFAConfirmRequest(BaseModel):
    """Complete MFA challenge during login.

    Sent after ``LoginResponse.mfa_required`` is True.
    """

    mfa_session_token: str = Field(..., min_length=1)
    code: str = Field(..., pattern=r"^\d{6}$", description="6-digit TOTP code")

    @field_validator("mfa_session_token", mode="before")
    @classmethod
    def strip_session_token(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("code", mode="before")
    @classmethod
    def strip_code(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class PasswordResetRequest(BaseModel):
    """Initiate a password-reset flow (sends email)."""

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class PasswordResetConfirm(BaseModel):
    """Complete a password-reset using the emailed token."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)

    @field_validator("token", mode="before")
    @classmethod
    def strip_token(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("new_password", mode="before")
    @classmethod
    def strip_new_password(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class WSTokenResponse(BaseModel):
    """Short-lived token for authenticating WebSocket connections."""

    model_config = ConfigDict(from_attributes=True)

    token: str
    expires_in: int = Field(
        ..., gt=0, description="Token lifetime in seconds"
    )


class FCMTokenRequest(BaseModel):
    """Register or update the device's FCM push-notification token."""

    fcm_token: str = Field(..., min_length=1)

    @field_validator("fcm_token", mode="before")
    @classmethod
    def strip_fcm_token(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v
