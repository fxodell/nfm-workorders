"""QR-code generation service: PNG creation and URL building."""

from __future__ import annotations

import io
import logging
import uuid

import qrcode
from qrcode.image.pil import PilImage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# QR PNG generation
# ---------------------------------------------------------------------------


def generate_qr_png(
    data_url: str,
    label: str | None = None,
) -> bytes:
    """Generate a QR code PNG image encoding ``data_url``.

    Parameters
    ----------
    data_url : str
        The URL or text content to encode in the QR code.
    label : str, optional
        A human-readable label printed below the QR code (if the imaging
        library supports text overlay).  Currently embedded as metadata only.

    Returns
    -------
    bytes
        Raw PNG image bytes ready to serve or store.
    """
    qr = qrcode.QRCode(
        version=None,  # auto-detect version
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data_url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    # If a label is provided and Pillow is available, draw it below the QR code
    if label:
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Convert to Pillow Image if not already
            if not isinstance(img, Image.Image):
                img = img.get_image()

            # Extend the canvas for the label
            original_width, original_height = img.size
            label_height = 40
            new_img = Image.new(
                "RGB",
                (original_width, original_height + label_height),
                "white",
            )
            new_img.paste(img, (0, 0))

            draw = ImageDraw.Draw(new_img)
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except (OSError, IOError):
                font = ImageFont.load_default()

            # Center the label text
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (original_width - text_width) // 2
            text_y = original_height + (label_height - (bbox[3] - bbox[1])) // 2
            draw.text((text_x, text_y), label, fill="black", font=font)
            img = new_img
        except ImportError:
            # Pillow not available for label rendering; return QR only
            logger.debug("Pillow not fully available for label rendering")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------


def get_qr_url(
    entity_type: str,
    qr_code_token: uuid.UUID | str,
    frontend_url: str,
) -> str:
    """Build the frontend scan URL for a QR code.

    The URL format follows the convention:
    ``{frontend_url}/scan/{entity_type}/{qr_code_token}``

    Parameters
    ----------
    entity_type : str
        One of ``"asset"``, ``"location"``, ``"site"``, ``"part"``.
    qr_code_token : UUID or str
        The unique token stored on the entity.
    frontend_url : str
        The base frontend URL (e.g. ``"https://app.example.com"``).

    Returns
    -------
    str
        The complete scan URL.
    """
    base = frontend_url.rstrip("/")
    token_str = str(qr_code_token)
    return f"{base}/scan/{entity_type}/{token_str}"
