"""Controlled isolated E2E provider pipeline — never auto-sends customer email."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.services.system.audit import write_audit
from app.services.system.provider_tests import run_provider_test
from app.services.system.test_org import (
    PROVIDER_TEST_LEAD_SOURCE,
    ensure_provider_test_organization,
)


def provider_status_matrix(db: Session, organization_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Honest provider matrix — never invents LIVE."""
    from app.services.system.registry import provider_registry

    settings = get_settings()
    registry = provider_registry(settings, db=db, organization_id=organization_id)
    rows = []
    for pid, info in registry["providers"].items():
        if pid == "reply_inbound":
            continue
        configured = bool(info.get("configured"))
        mode = str(info.get("mode") or "unavailable")
        live_tested = bool(info.get("live_tested") and mode == "live")
        rows.append(
            {
                "provider": pid,
                "configured": configured,
                "mode": mode,
                "live_tested": live_tested,
                "healthy": bool(info.get("healthy")),
                "last_checked": info.get("last_checked"),
                "last_success": info.get("last_success"),
                "last_error": info.get("last_error"),
                "result": _result_label(configured, mode, live_tested, info),
            }
        )
    return {
        "app_env": settings.app_env,
        "note": (
            "LIVE / LIVE-TESTED only after verified external success. "
            "Key presence alone is never LIVE. Stripe sandbox success is TEST, not LIVE."
        ),
        "providers": rows,
    }


def _result_label(configured: bool, mode: str, live_tested: bool, info: dict) -> str:
    if not configured or mode == "unavailable":
        return "NOT CONFIGURED"
    if mode == "mock":
        return "MOCK"
    if mode == "error" or info.get("degraded"):
        return "ERROR"
    if mode == "disabled":
        return "DISABLED"
    if live_tested and mode == "live":
        return "PASS"
    if mode == "test" and info.get("healthy"):
        return "TEST"
    if configured:
        return "CONFIGURED"
    return "NOT CONFIGURED"


def _stage(name: str, **kwargs: Any) -> dict[str, Any]:
    return {"stage": name, **kwargs}


def run_isolated_e2e_pipeline(
    db: Session,
    *,
    actor_user_id: uuid.UUID | None,
    request_id: str | None = None,
    send_email: bool = False,
) -> dict[str, Any]:
    """
    Create ONE isolated provider-test lead and run non-send stages.

    Never sends to discovered business emails.
    Optional send_email only to PROVIDER_TEST_EMAIL via provider test path.
    Usage counters for the provider-test org are never incremented.
    """
    settings = get_settings()
    org = ensure_provider_test_organization(db)

    write_audit(
        db,
        action="provider_e2e_started",
        entity_type="organization",
        entity_id=str(org.id),
        organization_id=org.id,
        actor_user_id=actor_user_id,
        metadata={"provider_test": True},
        commit=True,
    )

    stages: list[dict[str, Any]] = []

    for provider in (
        "google_places",
        "ai",
        "email_verification",
        "email_sending",
        "email_inbound",
        "calendar",
        "billing",
    ):
        try:
            result = run_provider_test(
                db,
                provider,
                organization_id=org.id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            stages.append(
                _stage(
                    f"probe:{provider}",
                    ok=result.get("ok"),
                    mode=result.get("mode"),
                    message=result.get("message"),
                    live_operation=result.get("live_operation"),
                    error_code=result.get("error_code"),
                    duration_ms=result.get("duration_ms"),
                )
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            err = detail.get("error") if isinstance(detail.get("error"), dict) else {}
            stages.append(
                _stage(
                    f"probe:{provider}",
                    ok=False,
                    message=err.get("message") or str(detail),
                    error_code=err.get("code"),
                )
            )

    lead = Lead(
        organization_id=org.id,
        company_name="LeadFlow Provider Test Business",
        industry="software",
        country="USA",
        state="TX",
        city="Austin",
        address="Provider Test Address",
        website="https://example.com",
        phone=None,
        google_place_id=f"provider_test_{uuid.uuid4().hex[:12]}",
        source=PROVIDER_TEST_LEAD_SOURCE,
        pipeline_stage="new",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    stages.append(
        _stage(
            "isolated_test_lead",
            ok=True,
            lead_id=str(lead.id),
            source=PROVIDER_TEST_LEAD_SOURCE,
            message="Isolated provider_test lead created (excluded from customer usage).",
        )
    )

    # Website analysis
    try:
        from app.services.website.analyzer import analyze_lead_website

        analysis = analyze_lead_website(db, lead.id)
        stages.append(
            _stage(
                "website_analysis",
                ok=True,
                status=getattr(analysis, "analysis_status", None) or getattr(analysis, "status", None),
                message="Website analysis ran for isolated test lead.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        stages.append(
            _stage(
                "website_analysis",
                ok=False,
                message=f"Website analysis failed/skipped: {type(exc).__name__}",
            )
        )

    # Public contact discovery (example.com — may find zero emails; still validates pipeline)
    try:
        from app.services.contacts.discovery import discover_lead_contacts

        discovery = discover_lead_contacts(db, lead.id)
        stages.append(
            _stage(
                "contact_discovery",
                ok=True,
                status=getattr(discovery, "status", None),
                emails_found=getattr(discovery, "emails_found", 0),
                message="Contact discovery completed for isolated test lead.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        stages.append(
            _stage(
                "contact_discovery",
                ok=False,
                message=f"Contact discovery failed/skipped: {type(exc).__name__}",
            )
        )

    # Seed PROVIDER_TEST_EMAIL as isolated contact for verification / AI / draft stages
    test_email = (settings.provider_test_email or "").strip().lower()
    contact: LeadContact | None = None
    if test_email:
        contact = (
            db.query(LeadContact)
            .filter(LeadContact.lead_id == lead.id, LeadContact.normalized_email == test_email)
            .one_or_none()
        )
        if contact is None:
            contact = LeadContact(
                lead_id=lead.id,
                email=test_email,
                normalized_email=test_email,
                contact_name="Provider Test Contact",
                role="test",
                contact_type="provider_test",
                source=PROVIDER_TEST_LEAD_SOURCE,
                confidence="high",
                domain_match=False,
                is_primary=True,
            )
            db.add(contact)
            db.commit()
            db.refresh(contact)
        stages.append(
            _stage(
                "seed_test_contact",
                ok=True,
                contact_id=str(contact.id),
                message="Seeded PROVIDER_TEST_EMAIL contact only (never discovered business email for send).",
            )
        )
    else:
        stages.append(
            _stage(
                "seed_test_contact",
                ok=False,
                error_code="TEST_RECIPIENT_NOT_CONFIGURED",
                message="PROVIDER_TEST_EMAIL not set — verification/AI/draft stages limited.",
            )
        )

    if contact is not None:
        try:
            from app.services.verification.service import verify_contact

            verification = verify_contact(db, contact.id)
            stages.append(
                _stage(
                    "email_verification",
                    ok=True,
                    status=getattr(verification, "status", None),
                    is_valid=getattr(verification, "is_valid", None),
                    message="Verified PROVIDER_TEST_EMAIL only.",
                )
            )
        except Exception as exc:  # noqa: BLE001
            stages.append(
                _stage(
                    "email_verification",
                    ok=False,
                    message=f"Verification stage failed/skipped: {type(exc).__name__}",
                )
            )

        try:
            from app.services.qualification.service import qualify_lead

            qual = qualify_lead(db, lead.id, force=True)
            stages.append(
                _stage(
                    "ai_qualification",
                    ok=True,
                    status=getattr(qual, "status", None),
                    message="AI qualification ran on isolated provider_test lead (usage isolated).",
                )
            )
        except Exception as exc:  # noqa: BLE001
            stages.append(
                _stage(
                    "ai_qualification",
                    ok=False,
                    message=f"AI qualification failed/skipped: {type(exc).__name__}",
                )
            )

        try:
            from app.services.outreach.service import generate_outreach_draft

            draft = generate_outreach_draft(db, lead.id, contact_id=contact.id, force=True)
            stages.append(
                _stage(
                    "personalized_email_generation",
                    ok=True,
                    draft_id=str(draft.id),
                    generation_status=getattr(draft, "generation_status", None),
                    draft_status=getattr(draft, "status", None),
                    message="Draft generated. Auto-send disabled for E2E.",
                )
            )
        except Exception as exc:  # noqa: BLE001
            stages.append(
                _stage(
                    "personalized_email_generation",
                    ok=False,
                    message=f"Outreach draft failed/skipped: {type(exc).__name__}",
                )
            )

    stages.append(
        _stage(
            "email_send_policy",
            ok=True,
            send_email_requested=send_email,
            message=(
                "Auto-send disabled. Controlled send only when send_email=true "
                "and PROVIDER_TEST_EMAIL is configured; never to discovered business email."
            ),
        )
    )

    if send_email:
        if not test_email:
            stages.append(
                _stage(
                    "controlled_email_send",
                    ok=False,
                    error_code="TEST_RECIPIENT_NOT_CONFIGURED",
                    message="PROVIDER_TEST_EMAIL required for controlled send.",
                )
            )
        else:
            result = run_provider_test(
                db,
                "email_sending",
                organization_id=org.id,
                actor_user_id=actor_user_id,
                request_id=request_id,
            )
            stages.append(
                _stage(
                    "controlled_email_send",
                    ok=result.get("ok"),
                    mode=result.get("mode"),
                    message=result.get("message"),
                    live_operation=result.get("live_operation"),
                    side_effects=result.get("side_effects"),
                    error_code=result.get("error_code"),
                )
            )

    write_audit(
        db,
        action="provider_e2e_completed",
        entity_type="organization",
        entity_id=str(org.id),
        organization_id=org.id,
        actor_user_id=actor_user_id,
        metadata={
            "provider_test": True,
            "lead_id": str(lead.id),
            "stages": [s.get("stage") for s in stages],
        },
        commit=True,
    )

    return {
        "provider_test": True,
        "organization_id": str(org.id),
        "organization_slug": org.slug,
        "lead_id": str(lead.id),
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "stages": stages,
        "matrix": provider_status_matrix(db, organization_id=org.id),
        "note": "No stage claims LIVE unless the corresponding probe recorded live_operation=true with success.",
    }
