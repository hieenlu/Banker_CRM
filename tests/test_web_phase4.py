"""Phase 4 web desk smoke checks (structure + API contract helpers)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_phase4_docs_exist():
    assert (ROOT / "docs" / "PHASE4_WEB.md").is_file()
    text = (ROOT / "docs" / "PHASE4_WEB.md").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_API_URL" in text
    assert "/clients" in text
    assert "iPad" in text or "Safari" in text


def test_web_package_scripts():
    pkg = (WEB / "package.json").read_text(encoding="utf-8")
    assert '"dev"' in pkg
    assert '"build"' in pkg
    assert "next" in pkg


def test_web_routes_present():
    routes = [
        "src/app/login/page.tsx",
        "src/app/(app)/clients/page.tsx",
        "src/app/(app)/clients/[id]/page.tsx",
        "src/app/(app)/portfolio/page.tsx",
        "src/app/(app)/reminders/page.tsx",
        "src/app/(app)/news/page.tsx",
        "src/app/(app)/news/latest/page.tsx",
        "src/app/(app)/news/briefing/page.tsx",
        "src/app/(app)/news/archive/page.tsx",
        "src/lib/api.ts",
        "src/components/AttachmentPanel.tsx",
    ]
    missing = [r for r in routes if not (WEB / r).is_file()]
    assert not missing, missing


def test_api_client_covers_phase2_and_3():
    api = (WEB / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    for needle in (
        "/auth/login",
        "/clients",
        "/investments",
        "/news/articles",
        "/newspaper/today",
        "/attachments",
        "/files/techcombank/sync",
        "export.zip",
    ):
        assert needle in api, needle


def test_gcp_deploy_assets_exist():
    assert (ROOT / "docs" / "DEPLOY_GCP.md").is_file()
    assert (ROOT / "scripts" / "deploy_cloudrun.sh").is_file()
    assert (ROOT / "Dockerfile.api").is_file()
    assert (WEB / "Dockerfile").is_file()
    assert (ROOT / "cloudbuild.api.yaml").is_file()
