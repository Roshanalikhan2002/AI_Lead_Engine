"""Legacy route RBAC / public exception matrix for audits and tests."""

from __future__ import annotations

# Explicit public exceptions (auth not required)
PUBLIC_ROUTE_EXCEPTIONS = [
    {"route": "GET /api/health", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "GET /api/health/live", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "GET /api/health/ready", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/auth/register", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/auth/login", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/auth/refresh", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/auth/forgot-password", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/auth/reset-password", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "GET /api/auth/invitations/{token}", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/auth/invitations/accept", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/meetings/book", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "GET /api/bookings/{token}", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/unsubscribe", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "GET /unsubscribe", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/webhooks/email/{provider}", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
    {"route": "POST /api/webhooks/billing/{provider}", "auth_required": False, "permission": None, "organization_scope": False, "public_exception": True},
]

# Representative private routes that MUST be org-scoped
PRIVATE_ORG_SCOPED_ROUTES = [
    {"route": "GET /api/leads", "auth_required": True, "permission": "leads.view", "organization_scope": True, "public_exception": False},
    {"route": "GET /api/leads/{id}", "auth_required": True, "permission": "leads.view", "organization_scope": True, "public_exception": False},
    {"route": "POST /api/generation", "auth_required": True, "permission": "leads.create", "organization_scope": True, "public_exception": False},
    {"route": "GET /api/campaigns", "auth_required": True, "permission": "campaigns.view", "organization_scope": True, "public_exception": False},
    {"route": "POST /api/billing/change-plan", "auth_required": True, "permission": "billing.manage", "organization_scope": True, "public_exception": False},
    {"route": "POST /api/system/providers/{provider}/test", "auth_required": True, "permission": "integrations.manage", "organization_scope": True, "public_exception": False},
    {"route": "GET /api/system/config/validate", "auth_required": True, "permission": "integrations.manage", "organization_scope": False, "public_exception": False},
    {"route": "GET /api/system/readiness", "auth_required": True, "permission": "integrations.manage", "organization_scope": False, "public_exception": False},
]


def route_matrix() -> list[dict]:
    return [*PUBLIC_ROUTE_EXCEPTIONS, *PRIVATE_ORG_SCOPED_ROUTES]
