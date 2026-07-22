"""Phase 3 local storage and file API tests."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("CRM_API_USER", "banker")
os.environ.setdefault("CRM_API_PASSWORD", "test-pass")
os.environ.setdefault("CRM_JWT_SECRET", "test-jwt-secret-at-least-32-bytes-long")

from api.config import clear_settings_cache  # noqa: E402
from api.deps import reset_db_state  # noqa: E402
from api.main import create_app  # noqa: E402
from storage.keys import client_attachment_key, safe_filename, techcombank_report_key  # noqa: E402
from storage.local import LocalStorage  # noqa: E402
from storage.s3 import S3Storage  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "phase3.sqlite3"
    storage_path = tmp_path / "objects"
    monkeypatch.setenv("CRM_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CRM_API_USER", "banker")
    monkeypatch.setenv("CRM_API_PASSWORD", "test-pass")
    monkeypatch.setenv("CRM_JWT_SECRET", "test-jwt-secret-at-least-32-bytes-long")
    monkeypatch.setenv("CRM_STORAGE_BACKEND", "local")
    monkeypatch.setenv("CRM_LOCAL_STORAGE_PATH", str(storage_path))
    clear_settings_cache()
    reset_db_state()
    with TestClient(create_app()) as test_client:
        yield test_client, storage_path
    clear_settings_cache()
    reset_db_state()


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"username": "banker", "password": "test-pass"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_key_builders_are_safe():
    assert safe_filename("../../Résumé 2026.PDF") == "resume-2026.pdf"
    assert (
        client_attachment_key("banker-crm", 7, 11, "../../Résumé 2026.PDF")
        == "banker-crm/clients/7/11-resume-2026.pdf"
    )
    assert techcombank_report_key("banker-crm", "202607") == (
        "banker-crm/techcombank/202607.pdf"
    )
    with pytest.raises(ValueError):
        techcombank_report_key("banker-crm", "../bad")


def test_local_storage_rejects_path_escape(tmp_path):
    storage = LocalStorage(tmp_path / "objects")
    storage.put_bytes("safe/file.txt", b"ok", "text/plain")
    assert storage.get_bytes("safe/file.txt") == b"ok"
    assert storage.exists("safe/file.txt")
    with pytest.raises(ValueError):
        storage.put_bytes("../../escape.txt", b"bad", "text/plain")
    storage.delete("safe/file.txt")
    assert not storage.exists("safe/file.txt")


def test_s3_backend_supports_r2_endpoint(monkeypatch):
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://signed.example/object"
    boto_factory = MagicMock(return_value=client)
    monkeypatch.setattr("storage.s3.boto3.client", boto_factory)

    storage = S3Storage(
        bucket="crm-files",
        region="auto",
        endpoint_url="https://account.r2.cloudflarestorage.com",
        access_key_id="key",
        secret_access_key="secret",
    )
    storage.put_bytes("prefix/file.pdf", b"%PDF", "application/pdf")
    client.put_object.assert_called_once_with(
        Bucket="crm-files",
        Key="prefix/file.pdf",
        Body=b"%PDF",
        ContentType="application/pdf",
    )
    url = storage.signed_get_url(
        "prefix/file.pdf",
        expires_seconds=900,
        download_name="report.pdf",
    )
    assert url == "https://signed.example/object"
    assert boto_factory.call_args.kwargs["endpoint_url"].endswith(
        ".r2.cloudflarestorage.com"
    )


def test_attachment_upload_download_export_delete(client):
    test_client, storage_path = client
    headers = _headers(test_client)
    created_client = test_client.post(
        "/clients",
        headers=headers,
        json={"name": "Files Client"},
    )
    assert created_client.status_code == 201
    client_id = created_client.json()["id"]

    uploaded = test_client.post(
        f"/clients/{client_id}/attachments",
        headers=headers,
        data={"label": "Signed agreement"},
        files={"file": ("Agreement 2026.pdf", b"%PDF-1.7 test", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_body = uploaded.json()
    file_id = file_body["id"]
    assert file_body["original_filename"] == "agreement-2026.pdf"
    assert file_body["label"] == "Signed agreement"
    assert file_body["backend"] == "local"
    assert file_body["download_url"].endswith(f"/files/{file_id}/download")
    assert list(storage_path.rglob("*.pdf"))

    listed = test_client.get(
        f"/clients/{client_id}/attachments",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    downloaded = test_client.get(
        f"/files/{file_id}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.7 test"

    exported = test_client.get(
        f"/clients/{client_id}/export.zip",
        headers=headers,
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    assert exported.content.startswith(b"PK")

    deleted = test_client.delete(
        f"/clients/{client_id}/attachments/{file_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert not list(storage_path.rglob("*.pdf"))


def test_upload_validation(client):
    test_client, _ = client
    headers = _headers(test_client)
    client_id = test_client.post(
        "/clients",
        headers=headers,
        json={"name": "Validation Client"},
    ).json()["id"]

    unsupported = test_client.post(
        f"/clients/{client_id}/attachments",
        headers=headers,
        files={"file": ("script.exe", b"MZ", "application/x-msdownload")},
    )
    assert unsupported.status_code == 415

    spoofed_pdf = test_client.post(
        f"/clients/{client_id}/attachments",
        headers=headers,
        files={"file": ("fake.pdf", b"not actually a pdf", "application/pdf")},
    )
    assert spoofed_pdf.status_code == 415

    empty = test_client.post(
        f"/clients/{client_id}/attachments",
        headers=headers,
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert empty.status_code == 400


def test_deleting_client_removes_objects(client):
    test_client, storage_path = client
    headers = _headers(test_client)
    client_id = test_client.post(
        "/clients",
        headers=headers,
        json={"name": "Delete Client"},
    ).json()["id"]
    response = test_client.post(
        f"/clients/{client_id}/attachments",
        headers=headers,
        files={"file": ("doc.txt", b"secret", "text/plain")},
    )
    assert response.status_code == 201
    assert list(storage_path.rglob("*.txt"))

    deleted = test_client.delete(f"/clients/{client_id}", headers=headers)
    assert deleted.status_code == 200
    assert not list(storage_path.rglob("*.txt"))


def test_techcombank_sync_and_download(client, monkeypatch):
    test_client, storage_path = client
    headers = _headers(test_client)

    monkeypatch.setattr(
        "storage.techcombank.scrape_techcombank_monthly_reports",
        lambda limit=8: [
            {
                "yyyymm": "202607",
                "period": "07/2026",
                "url": "https://techcombank.com/report.pdf",
            }
        ],
    )

    class FakeResponse:
        status_code = 200
        url = "https://techcombank.com/report.pdf"
        headers = {"content-type": "application/pdf"}

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def iter_content(chunk_size=64 * 1024):
            del chunk_size
            return iter([b"%PDF-1.7 mirrored report"])

        @staticmethod
        def close():
            return None

    monkeypatch.setattr("storage.techcombank.requests.get", lambda *args, **kwargs: FakeResponse())

    synced = test_client.post(
        "/files/techcombank/sync",
        headers=headers,
        params={"limit": 1},
    )
    assert synced.status_code == 200, synced.text
    assert synced.json() == {"found": 1, "synced": 1, "skipped": 0, "errors": []}
    assert list(storage_path.rglob("202607.pdf"))

    again = test_client.post(
        "/files/techcombank/sync",
        headers=headers,
        params={"limit": 1},
    )
    assert again.status_code == 200
    assert again.json()["skipped"] == 1

    report = test_client.get(
        "/files/techcombank/reports/202607",
        headers=headers,
    )
    assert report.status_code == 200
    assert report.json()["period_yyyymm"] == "202607"

    downloaded = test_client.get(
        report.json()["download_url"],
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.7 mirrored report"
