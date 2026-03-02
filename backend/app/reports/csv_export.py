"""CSV export utility for report endpoints."""

from __future__ import annotations

import csv
import io
from typing import Any

from starlette.responses import StreamingResponse


def generate_csv_response(
    data: list[dict[str, Any]],
    filename: str,
) -> StreamingResponse:
    """Generate a streaming CSV response from a list of dicts."""
    if not data:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["No data"])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
