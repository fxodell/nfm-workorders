"""
QR Code Sheet Generator for Oilfield CMMS.

Generates a printable PDF with QR codes for sites, assets, and parts.
Each QR encodes a URL that routes to the scan handler in the frontend.

Usage:
    python scripts/generate_qr_sheet.py --org-id <uuid> --entity-type all
    python scripts/generate_qr_sheet.py --org-id <uuid> --entity-type site --output sites.pdf
    python scripts/generate_qr_sheet.py --org-id <uuid> --entity-type asset
    python scripts/generate_qr_sheet.py --org-id <uuid> --entity-type part

Requirements (already in requirements.txt):
    - reportlab
    - qrcode[pil]
    - Pillow
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

# Ensure the backend package is on sys.path when executed directly.
_backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import qrcode
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.asset import Asset
from app.models.org import Organization
from app.models.part import Part
from app.models.site import Site

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

PAGE_WIDTH, PAGE_HEIGHT = LETTER  # 8.5 x 11 inches
COLS = 3
ROWS = 4
MARGIN_X = 0.75 * inch
MARGIN_Y = 0.75 * inch
CELL_W = (PAGE_WIDTH - 2 * MARGIN_X) / COLS
CELL_H = (PAGE_HEIGHT - 2 * MARGIN_Y) / ROWS
QR_SIZE = min(CELL_W, CELL_H) * 0.65  # QR code occupies ~65% of cell
LABEL_FONT_SIZE = 8
SUBLABEL_FONT_SIZE = 6
HEADER_FONT_SIZE = 10


@dataclass
class QRItem:
    """A single item to render as a QR code on the sheet."""
    entity_type: str  # "site", "asset", or "part"
    qr_code_token: str
    label: str  # Primary label (name or part number)
    sublabel: str  # Secondary label (type, location, etc.)


def _make_qr_image(url: str) -> io.BytesIO:
    """Generate a QR code PNG image in memory."""
    qr = qrcode.QRCode(
        version=None,  # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _build_url(entity_type: str, qr_token: str) -> str:
    """Build the scan URL for a given entity."""
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/scan/{entity_type}/{qr_token}"


def generate_pdf(
    items: list[QRItem],
    output_path: str,
    org_name: str,
) -> None:
    """Render all QR items to a multi-page PDF."""
    if not items:
        print("No items to generate. PDF not created.")
        return

    c = canvas.Canvas(output_path, pagesize=LETTER)
    c.setTitle(f"QR Code Sheet - {org_name}")

    total_items = len(items)
    items_per_page = COLS * ROWS
    page_count = (total_items + items_per_page - 1) // items_per_page

    for page_idx in range(page_count):
        if page_idx > 0:
            c.showPage()

        # Page header
        c.setFont("Helvetica-Bold", 12)
        c.drawString(
            MARGIN_X,
            PAGE_HEIGHT - MARGIN_Y + 0.3 * inch,
            f"{org_name} - QR Code Sheet",
        )
        c.setFont("Helvetica", HEADER_FONT_SIZE)
        c.drawRightString(
            PAGE_WIDTH - MARGIN_X,
            PAGE_HEIGHT - MARGIN_Y + 0.3 * inch,
            f"Page {page_idx + 1} of {page_count}",
        )

        # Draw items in grid
        start = page_idx * items_per_page
        end = min(start + items_per_page, total_items)

        for i, item in enumerate(items[start:end]):
            row = i // COLS
            col = i % COLS

            # Cell origin (bottom-left)
            cell_x = MARGIN_X + col * CELL_W
            cell_y = PAGE_HEIGHT - MARGIN_Y - (row + 1) * CELL_H

            # Center QR in cell
            qr_x = cell_x + (CELL_W - QR_SIZE) / 2
            qr_y = cell_y + CELL_H - QR_SIZE - 5

            # Generate and draw QR
            url = _build_url(item.entity_type, item.qr_code_token)
            qr_buf = _make_qr_image(url)

            from reportlab.lib.utils import ImageReader
            qr_img = ImageReader(qr_buf)
            c.drawImage(qr_img, qr_x, qr_y, QR_SIZE, QR_SIZE)

            # Primary label
            c.setFont("Helvetica-Bold", LABEL_FONT_SIZE)
            label_text = item.label
            if len(label_text) > 32:
                label_text = label_text[:30] + "..."
            label_x = cell_x + CELL_W / 2
            label_y = qr_y - 12
            c.drawCentredString(label_x, label_y, label_text)

            # Sublabel (type or description)
            c.setFont("Helvetica", SUBLABEL_FONT_SIZE)
            sublabel_text = item.sublabel
            if len(sublabel_text) > 40:
                sublabel_text = sublabel_text[:38] + "..."
            c.drawCentredString(label_x, label_y - 10, sublabel_text)

            # Entity type badge
            c.setFont("Helvetica-Oblique", SUBLABEL_FONT_SIZE)
            c.drawCentredString(label_x, label_y - 20, item.entity_type.upper())

            # Cell border (light gray)
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.setLineWidth(0.5)
            c.rect(cell_x + 2, cell_y + 2, CELL_W - 4, CELL_H - 4)

    c.save()
    print(f"PDF generated: {output_path} ({total_items} QR codes, {page_count} pages)")


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------


async def _fetch_sites(org_id: uuid.UUID) -> list[QRItem]:
    async with async_session() as session:
        result = await session.execute(
            select(Site).where(Site.org_id == org_id, Site.is_active.is_(True))
        )
        sites = result.scalars().all()
        return [
            QRItem(
                entity_type="site",
                qr_code_token=str(s.qr_code_token),
                label=s.name,
                sublabel=s.type.value.replace("_", " ").title(),
            )
            for s in sites
        ]


async def _fetch_assets(org_id: uuid.UUID) -> list[QRItem]:
    async with async_session() as session:
        result = await session.execute(
            select(Asset).where(Asset.org_id == org_id, Asset.is_active.is_(True))
        )
        assets = result.scalars().all()
        return [
            QRItem(
                entity_type="asset",
                qr_code_token=str(a.qr_code_token),
                label=a.name,
                sublabel=f"{a.manufacturer or ''} {a.model or ''}".strip() or (a.asset_type or "Asset"),
            )
            for a in assets
        ]


async def _fetch_parts(org_id: uuid.UUID) -> list[QRItem]:
    async with async_session() as session:
        result = await session.execute(
            select(Part).where(Part.org_id == org_id, Part.is_active.is_(True))
        )
        parts = result.scalars().all()
        return [
            QRItem(
                entity_type="part",
                qr_code_token=str(p.qr_code_token),
                label=p.part_number,
                sublabel=p.description[:50] if p.description else "Part",
            )
            for p in parts
        ]


async def _fetch_org_name(org_id: uuid.UUID) -> str:
    async with async_session() as session:
        result = await session.execute(
            select(Organization.name).where(Organization.id == org_id)
        )
        name = result.scalar_one_or_none()
        if name is None:
            print(f"ERROR: Organization {org_id} not found.")
            sys.exit(1)
        return name


async def run(
    org_id: uuid.UUID,
    entity_type: str,
    output: str,
) -> None:
    """Fetch entities from database and generate the PDF."""
    org_name = await _fetch_org_name(org_id)
    print(f"Generating QR sheet for: {org_name}")

    items: list[QRItem] = []

    if entity_type in ("site", "all"):
        site_items = await _fetch_sites(org_id)
        items.extend(site_items)
        print(f"  Sites: {len(site_items)}")

    if entity_type in ("asset", "all"):
        asset_items = await _fetch_assets(org_id)
        items.extend(asset_items)
        print(f"  Assets: {len(asset_items)}")

    if entity_type in ("part", "all"):
        part_items = await _fetch_parts(org_id)
        items.extend(part_items)
        print(f"  Parts: {len(part_items)}")

    if not items:
        print("No items found for the given organization and entity type.")
        return

    generate_pdf(items, output, org_name)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a PDF sheet of QR codes for sites, assets, and parts.",
    )
    parser.add_argument(
        "--org-id",
        required=True,
        type=uuid.UUID,
        help="Organization UUID",
    )
    parser.add_argument(
        "--entity-type",
        choices=["site", "asset", "part", "all"],
        default="all",
        help="Type of entities to include (default: all)",
    )
    parser.add_argument(
        "--output",
        default="qr_sheet.pdf",
        help="Output PDF file path (default: qr_sheet.pdf)",
    )

    args = parser.parse_args()
    asyncio.run(run(args.org_id, args.entity_type, args.output))


if __name__ == "__main__":
    main()
