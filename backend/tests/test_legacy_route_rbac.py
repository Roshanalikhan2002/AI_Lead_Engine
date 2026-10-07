"""Phase 14 — legacy route RBAC / public exception matrix."""

from __future__ import annotations

from app.core.tenant import PUBLIC_EXACT, PUBLIC_PATH_PREFIXES, is_public_path
from app.services.system.route_matrix import PRIVATE_ORG_SCOPED_ROUTES, PUBLIC_ROUTE_EXCEPTIONS, route_matrix


def test_route_matrix_non_empty():
    matrix = route_matrix()
    assert len(matrix) >= 10
    assert any(r["public_exception"] for r in matrix)
    assert any(r["organization_scope"] for r in matrix)


def test_public_exceptions_match_tenant_allowlist():
    # Spot-check critical public paths
    assert is_public_path("/api/health", "GET")
    assert is_public_path("/api/auth/login", "POST")
    assert is_public_path("/api/webhooks/billing/mock", "POST")
    assert is_public_path("/api/webhooks/email/resend", "POST")
    assert is_public_path("/api/meetings/book", "POST")
    assert not is_public_path("/api/leads", "GET")
    assert not is_public_path("/api/system/providers/ai/test", "POST")


def test_private_routes_require_auth_and_org_scope():
    for row in PRIVATE_ORG_SCOPED_ROUTES:
        assert row["auth_required"] is True
        assert row["public_exception"] is False


def test_public_route_exceptions_documented():
    for row in PUBLIC_ROUTE_EXCEPTIONS:
        assert row["auth_required"] is False
        assert row["public_exception"] is True


def test_public_prefixes_include_webhooks_and_health():
    assert any(p.startswith("/api/health") or p == "/api/health" for p in (*PUBLIC_PATH_PREFIXES, *PUBLIC_EXACT))
    assert any("webhook" in p for p in PUBLIC_PATH_PREFIXES)
