# Phase 3 — R2 / S3 file storage

## Goal
Store client attachments, mirrored Techcombank PDFs, and client export ZIP
contents outside Postgres. Postgres keeps only object metadata and keys.

The implementation uses one S3-compatible code path:
- **Cloudflare R2:** provide the account endpoint and `region=auto`
- **AWS S3:** leave the endpoint empty and provide an AWS region
- **Local development:** filesystem backend under `./data/files`

## Cloudflare R2 setup
1. Create a private bucket, e.g. `banker-crm-files`.
2. Create an R2 API token with Object Read & Write on that bucket.
3. Configure:

```bash
export CRM_STORAGE_BACKEND=s3
export CRM_S3_ENDPOINT_URL='https://<account-id>.r2.cloudflarestorage.com'
export CRM_S3_REGION=auto
export CRM_S3_BUCKET=banker-crm-files
export CRM_S3_ACCESS_KEY_ID='...'
export CRM_S3_SECRET_ACCESS_KEY='...'
export CRM_S3_PREFIX=banker-crm
export CRM_S3_SIGNED_URL_TTL_SECONDS=3600
```

## AWS S3 setup
Use a private bucket and credentials restricted to that bucket:

```bash
export CRM_STORAGE_BACKEND=s3
unset CRM_S3_ENDPOINT_URL
export CRM_S3_REGION=us-east-1
export CRM_S3_BUCKET=banker-crm-files
export CRM_S3_ACCESS_KEY_ID='...'
export CRM_S3_SECRET_ACCESS_KEY='...'
```

Required IAM actions: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, and
`s3:ListBucket` on the configured bucket/prefix.

## Local development
```bash
export CRM_STORAGE_BACKEND=local
export CRM_LOCAL_STORAGE_PATH="$(pwd)/data/files"
uvicorn api.main:app --reload --port 8000
```

Do not use local storage for a horizontally scaled deployment.

## API
All routes require the Phase 2 Bearer token.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/clients/{id}/attachments` | Paginated attachment metadata |
| `POST` | `/clients/{id}/attachments` | Multipart upload (`file`, optional `label`) |
| `GET` | `/clients/{id}/attachments/{file_id}` | Metadata + download URL |
| `DELETE` | `/clients/{id}/attachments/{file_id}` | Delete object and metadata |
| `GET` | `/clients/{id}/export.zip` | JSON CRM export plus attachments |
| `GET` | `/files/{file_id}/download` | Authenticated local download or S3 redirect |
| `POST` | `/files/techcombank/sync` | Mirror current monthly reports |
| `GET` | `/files/techcombank/reports` | List mirrored reports |
| `GET` | `/files/techcombank/reports/{yyyymm}` | Report metadata + download URL |

R2/S3 metadata responses contain short-lived signed download URLs. Credentials
are never returned. Local responses point to the authenticated API download
route.

## Object keys
```text
banker-crm/clients/{client_id}/{file_id}-{safe_filename}
banker-crm/techcombank/{yyyymm}.pdf
```

The `stored_files` table records the backend, bucket, object key, MIME type,
size, SHA-256 checksum, owner/report period, and source URL.

## Limits and allowed file types
Default upload maximum: 20 MiB (`CRM_S3_MAX_UPLOAD_BYTES`).
Client export attachment total: 100 MiB (`CRM_MAX_EXPORT_BYTES`).

Default MIME allowlist:
- PDF
- JPEG / PNG
- XLSX
- plain text

Override with comma-separated `CRM_ALLOWED_UPLOAD_TYPES`.

## Sync Techcombank from a job
```bash
python -m scripts.sync_techcombank_pdfs --limit 8
```

The sync is idempotent: an unchanged report already present in storage is
skipped.

## Moving existing local objects to R2/S3
The Phase 1 SQLite→Postgres script copies `stored_files` metadata, but cannot
copy filesystem bytes. Before changing `CRM_STORAGE_BACKEND` from `local` to
`s3`, upload the objects under their recorded keys and verify SHA-256 values.
Do not migrate metadata alone to a host that cannot access the local storage
path.

## Exit criteria
- [x] Local storage backend
- [x] Cloudflare R2 / AWS S3 backend
- [x] Client attachment upload, download, list, and delete
- [x] Techcombank report mirroring
- [x] Client JSON + attachment ZIP export
- [x] File metadata in Postgres/SQLite
- [x] Signed private downloads
- [ ] Create production R2/S3 bucket and perform a live smoke test
- [ ] Add attachment controls to the Phase 4 web app

## Next
Phase 4 web UI can call these APIs without handling bucket credentials.
See `docs/PHASE4_WEB.md`.
