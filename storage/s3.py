"""Cloudflare R2 / AWS S3 storage backend."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class S3Storage:
    backend_name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
    ) -> None:
        if not bucket:
            raise ValueError("CRM_S3_BUCKET is required for the s3 backend")
        if bool(access_key_id) != bool(secret_access_key):
            raise ValueError(
                "CRM_S3_ACCESS_KEY_ID and CRM_S3_SECRET_ACCESS_KEY must be set together"
            )
        self.bucket = bucket
        kwargs: dict[str, Any] = {
            "region_name": region or "auto",
            "config": Config(signature_version="s3v4"),
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if access_key_id:
            kwargs["aws_access_key_id"] = access_key_id
        if secret_access_key:
            kwargs["aws_secret_access_key"] = secret_access_key
        self.client = boto3.client("s3", **kwargs)

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise

    def signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_name: str | None = None,
    ) -> str:
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        if download_name:
            safe_name = download_name.replace('"', "")
            params["ResponseContentDisposition"] = (
                f"attachment; filename*=UTF-8''{quote(safe_name)}"
            )
        return self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_seconds,
        )
