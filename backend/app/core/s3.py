"""
S3 / MinIO client utilities for pre-signed URL generation and object
management.

File bytes never transit through the API server. Instead:
1. The client requests a pre-signed upload URL.
2. The client uploads directly to S3 / MinIO.
3. The client notifies the API with the resulting S3 key.
4. The API generates pre-signed download URLs on demand.

The ``AWS_ENDPOINT_URL`` setting allows pointing to a local MinIO instance
in development while using real S3 in production.
"""

from __future__ import annotations

import uuid

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings

# ── Client factory ──────────────────────────────────────────────────────

_client = None


def _get_s3_client():
    """Lazily create and cache the boto3 S3 client."""
    global _client  # noqa: WPS420
    if _client is not None:
        return _client

    kwargs: dict = {
        "service_name": "s3",
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "config": BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    }
    if settings.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL

    _client = boto3.client(**kwargs)
    return _client


# ── Pre-signed URLs ────────────────────────────────────────────────────

def generate_presigned_upload_url(
    filename: str,
    content_type: str,
    org_id: str,
    prefix: str = "attachments",
) -> dict[str, str]:
    """Generate a pre-signed PUT URL for direct upload.

    Returns a dict with ``url``, ``s3_key``, and ``fields`` (empty for PUT).
    The S3 key includes the org_id to namespace uploads per tenant.
    """
    s3 = _get_s3_client()
    # Build a unique key: <prefix>/<org_id>/<uuid>/<original_filename>
    unique_id = str(uuid.uuid4())
    s3_key = f"{prefix}/{org_id}/{unique_id}/{filename}"

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.S3_PRESIGN_TTL,
    )
    return {
        "url": url,
        "s3_key": s3_key,
        "s3_bucket": settings.S3_BUCKET,
    }


def generate_presigned_download_url(
    s3_key: str,
    filename: str | None = None,
) -> str:
    """Generate a pre-signed GET URL for downloading an object.

    Optionally sets a ``Content-Disposition`` header so the browser suggests
    *filename* when saving the file.
    """
    s3 = _get_s3_client()
    params: dict = {
        "Bucket": settings.S3_BUCKET,
        "Key": s3_key,
    }
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params=params,
        ExpiresIn=settings.S3_PRESIGN_TTL,
    )


def delete_object(s3_key: str) -> None:
    """Delete an object from S3 by key.

    Silently succeeds if the key does not exist (S3 DELETE is idempotent).
    """
    s3 = _get_s3_client()
    s3.delete_object(
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
    )
