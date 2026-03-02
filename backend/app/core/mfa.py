"""
TOTP-based Multi-Factor Authentication helpers.

Uses ``pyotp`` for TOTP generation / verification and the ``qrcode``
library to produce a data-URL PNG that the frontend can render directly
in an ``<img>`` tag during MFA enrollment.
"""

from __future__ import annotations

import base64
import io

import pyotp
import qrcode
import qrcode.constants


def generate_totp_secret() -> str:
    """Generate a new random base-32 TOTP secret (160-bit)."""
    return pyotp.random_base32()


def generate_provisioning_uri(
    secret: str,
    email: str,
    issuer: str = "OFMaint CMMS",
) -> str:
    """Return the ``otpauth://`` URI for importing into an authenticator app."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP *code* against the stored *secret*.

    Allows a 30-second window on either side of the current interval to
    account for minor clock drift between client and server.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_qr_data_url(
    secret: str,
    email: str,
    issuer: str = "OFMaint CMMS",
) -> str:
    """Generate a ``data:image/png;base64,...`` URL encoding the provisioning
    URI as a QR code.

    The resulting string can be used as the ``src`` attribute of an HTML
    ``<img>`` element with no additional server round-trip.
    """
    uri = generate_provisioning_uri(secret, email, issuer)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
