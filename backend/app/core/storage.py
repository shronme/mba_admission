from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass
from typing import BinaryIO, Iterator, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StorageCredentials:
    bucket: str | None
    endpoint_url: str | None
    access_key_id: str | None
    secret_access_key: str | None
    region: str | None


def _read_creds() -> StorageCredentials:
    # Railway Storage Buckets env var names can differ slightly in the dashboard.
    # Support multiple common aliases.
    return StorageCredentials(
        bucket=os.getenv("BUCKET") or os.getenv("STORAGE_BUCKET"),
        endpoint_url=os.getenv("ENDPOINT") or os.getenv("STORAGE_ENDPOINT"),
        access_key_id=os.getenv("ACCESS_KEY_ID") or os.getenv("STORAGE_ACCESS_KEY_ID"),
        secret_access_key=os.getenv("SECRET_ACCESS_KEY")
        or os.getenv("STORAGE_SECRET_ACCESS_KEY"),
        region=os.getenv("REGION") or os.getenv("STORAGE_REGION"),
    )


class StorageBackend:
    def put_bytes(self, *, key: str, data: bytes, content_type: str | None) -> str:
        raise NotImplementedError

    def open_stream(self, *, storage_uri: str) -> Tuple[BinaryIO, str | None]:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def _path_for_key(self, key: str) -> str:
        # key is treated as a relative path under base_dir.
        return os.path.join(self.base_dir, key)

    def put_bytes(self, *, key: str, data: bytes, content_type: str | None) -> str:
        path = self._path_for_key(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        logger.debug("storage_put_local key=%s bytes=%s path=%s", key, len(data), path)
        return f"file://{os.path.abspath(path)}"

    def open_stream(self, *, storage_uri: str) -> Tuple[BinaryIO, str | None]:
        if not storage_uri.startswith("file://"):
            raise ValueError("LocalStorageBackend expects file:// storage_uri")
        path = storage_uri[len("file://") :]
        logger.debug("storage_open_local storage_uri=%s path=%s", storage_uri, path)
        return open(path, "rb"), None


class S3CompatibleStorageBackend(StorageBackend):
    def __init__(self, creds: StorageCredentials) -> None:
        import boto3  # local import so backend remains importable without boto3

        if not creds.bucket or not creds.endpoint_url:
            raise ValueError("S3 creds missing bucket or endpoint_url")
        if not creds.access_key_id or not creds.secret_access_key:
            raise ValueError("S3 creds missing access_key_id or secret_access_key")

        self.bucket = creds.bucket
        self.creds = creds

        logger.info(
            "storage_backend_s3 enabled bucket=%s endpoint_url=%s",
            creds.bucket,
            creds.endpoint_url,
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=creds.endpoint_url,
            region_name=creds.region or "us-east-1",
            aws_access_key_id=creds.access_key_id,
            aws_secret_access_key=creds.secret_access_key,
        )

    def put_bytes(self, *, key: str, data: bytes, content_type: str | None) -> str:
        kwargs = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        self._client.put_object(**kwargs)
        logger.debug(
            "storage_put_s3 key=%s bytes=%s content_type=%s", key, len(data), content_type
        )
        return f"s3://{self.bucket}/{key}"

    def open_stream(self, *, storage_uri: str) -> Tuple[BinaryIO, str | None]:
        # Expected format: s3://bucket/key
        m = re.match(r"^s3://([^/]+)/(.+)$", storage_uri)
        if not m:
            raise ValueError("Invalid s3 storage_uri; expected s3://bucket/key")
        bucket, key = m.group(1), m.group(2)
        obj = self._client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"]
        content_type = obj.get("ContentType")
        logger.debug("storage_open_s3 key=%s content_type=%s", key, content_type)
        return body, content_type


_BACKEND: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """
    Choose between Railway bucket (S3-compatible) and local filesystem fallback.

    In production/preview, configure `BUCKET`, `ENDPOINT`, `ACCESS_KEY_ID`,
    and `SECRET_ACCESS_KEY`. For local dev, it falls back to `.local_bucket/`.
    """

    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    creds = _read_creds()
    if creds.bucket and creds.endpoint_url and creds.access_key_id and creds.secret_access_key:
        _BACKEND = S3CompatibleStorageBackend(creds)
        return _BACKEND

    local_dir = os.getenv("LOCAL_STORAGE_DIR", "/app/.local_bucket")
    logger.info("storage_backend_local enabled base_dir=%s", local_dir)
    _BACKEND = LocalStorageBackend(local_dir)
    return _BACKEND


def storage_key_for_upload(*, candidate_id: str, file_id: str, filename: str) -> str:
    # Deterministic key so you can reproduce object locations later.
    # We do not rely on original filename uniqueness.
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename)[:200]
    return f"candidates/{candidate_id}/{file_id}/{safe}"

