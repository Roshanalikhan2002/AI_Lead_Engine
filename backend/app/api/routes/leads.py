from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant import TenantDep, require_permission
from app.models.ai_qualification import AIQualification
from app.models.contact_discovery import ContactDiscovery
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.lead_opportunity import LeadOpportunity
from app.models.email_message import EmailMessage
from app.models.outreach_draft import OutreachDraft
from app.models.website_analysis import WebsiteAnalysis
from app.schemas.contacts import LeadContactRead
from app.schemas.lead import LeadListResponse, LeadRead
from app.schemas.outreach import OutreachDraftRead
from app.schemas.qualification import AIQualificationRead
from app.schemas.sending import EmailMessageRead
from app.schemas.verification import EmailVerificationRead
from app.schemas.website import LeadOpportunityRead, WebsiteAnalysisRead

router = APIRouter(tags=["leads"])


@router.get("/api/leads", response_model=LeadListResponse)
def list_leads(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("leads.view")),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: str | None = None,
    country: str | None = None,
    state: str | None = None,
    city: str | None = None,
    industry: str | None = None,
    website_filter: str | None = Query(default=None, pattern="^(any|yes|no)$"),
    website_analysis_status: str | None = Query(
        default=None,
        pattern="^(not_analyzed|pending|running|completed|failed|not_available|blocked)$",
    ),
    contact_discovery_status: str | None = Query(
        default=None,
        pattern="^(not_discovered|pending|running|completed|failed|not_available|no_public_email)$",
    ),
    verification_status: str | None = Query(
        default=None,
        pattern="^(valid|invalid|risky|unknown|not_verified|error|blocked)$",
    ),
    discovery_confidence: str | None = Query(default=None, pattern="^(high|medium|low)$"),
    qualification_status: str | None = Query(
        default=None,
        pattern="^(qualified|not_qualified|insufficient_data|error|unconfigured|not_analyzed)$",
    ),
    priority: str | None = Query(default=None, pattern="^(hot|warm|cold|unknown)$"),
    outreach_draft_status: str | None = Query(
        default=None,
        pattern="^(not_generated|draft|approved|rejected|edited)$",
    ),
    sending_status: str | None = Query(
        default=None,
        pattern="^(not_sent|simulated|sent|delivered|failed|bounced|blocked|approved)$",
    ),
    min_lead_score: int | None = Query(default=None, ge=0, le=100),
    min_website_score: int | None = Query(default=None, ge=0, le=100),
    opportunity_service: str | None = None,
    source: str | None = None,
    sort: str = Query(
        default="newest",
        pattern="^(newest|oldest|rating_desc|rating_asc|name|website_score_desc|lead_score_desc|lead_score_asc)$",
    ),
) -> LeadListResponse:
    query = db.query(Lead).filter(Lead.organization_id == tenant.organization_id)

    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Lead.company_name.ilike(like),
                Lead.city.ilike(like),
                Lead.industry.ilike(like),
                Lead.address.ilike(like),
            )
        )
    if country:
        query = query.filter(Lead.country == country)
    if state:
        query = query.filter(Lead.state == state)
    if city:
        query = query.filter(Lead.city == city)
    if industry:
        query = query.filter(Lead.industry == industry)
    if source:
        query = query.filter(Lead.source == source)
    if website_filter == "yes":
        query = query.filter(Lead.website.isnot(None), Lead.website != "")
    elif website_filter == "no":
        query = query.filter(or_(Lead.website.is_(None), Lead.website == ""))

    if website_analysis_status == "not_analyzed":
        query = query.outerjoin(WebsiteAnalysis).filter(WebsiteAnalysis.id.is_(None))
    elif website_analysis_status:
        query = query.join(WebsiteAnalysis).filter(WebsiteAnalysis.analysis_status == website_analysis_status)

    if contact_discovery_status == "not_discovered":
        query = query.outerjoin(ContactDiscovery).filter(ContactDiscovery.id.is_(None))
    elif contact_discovery_status:
        query = query.join(ContactDiscovery).filter(ContactDiscovery.status == contact_discovery_status)

    if discovery_confidence:
        query = query.join(LeadContact).filter(LeadContact.confidence == discovery_confidence)

    if verification_status == "not_verified":
        query = query.join(LeadContact).outerjoin(
            EmailVerification, EmailVerification.lead_contact_id == LeadContact.id
        ).filter(EmailVerification.id.is_(None))
    elif verification_status:
        query = (
            query.join(LeadContact)
            .join(EmailVerification, EmailVerification.lead_contact_id == LeadContact.id)
            .filter(EmailVerification.status == verification_status)
        )

    if min_website_score is not None:
        query = query.join(WebsiteAnalysis).filter(WebsiteAnalysis.website_score >= min_website_score)

    if opportunity_service:
        query = query.join(LeadOpportunity).filter(LeadOpportunity.service == opportunity_service)

    if qualification_status == "not_analyzed":
        query = query.outerjoin(AIQualification).filter(AIQualification.id.is_(None))
    elif qualification_status:
        query = query.join(AIQualification).filter(AIQualification.status == qualification_status)

    if priority:
        query = query.join(AIQualification).filter(AIQualification.priority == priority)

    if min_lead_score is not None:
        query = query.join(AIQualification).filter(AIQualification.lead_score >= min_lead_score)

    if outreach_draft_status == "not_generated":
        query = query.outerjoin(OutreachDraft).filter(OutreachDraft.id.is_(None))
    elif outreach_draft_status:
        query = query.join(OutreachDraft).filter(OutreachDraft.status == outreach_draft_status)

    if sending_status == "not_sent":
        query = query.outerjoin(EmailMessage).filter(EmailMessage.id.is_(None))
    elif sending_status == "approved":
        query = query.join(OutreachDraft).filter(OutreachDraft.status == "approved").outerjoin(
            EmailMessage, EmailMessage.outreach_draft_id == OutreachDraft.id
        ).filter(EmailMessage.id.is_(None))
    elif sending_status:
        query = query.join(EmailMessage).filter(EmailMessage.status == sending_status)

    query = query.distinct()

    if sort == "oldest":
        query = query.order_by(Lead.created_at.asc())
    elif sort == "rating_desc":
        query = query.order_by(Lead.rating.desc().nullslast(), Lead.created_at.desc())
    elif sort == "rating_asc":
        query = query.order_by(Lead.rating.asc().nullslast(), Lead.created_at.desc())
    elif sort == "name":
        query = query.order_by(Lead.company_name.asc())
    elif sort == "website_score_desc":
        query = query.outerjoin(WebsiteAnalysis).order_by(
            WebsiteAnalysis.website_score.desc().nullslast(),
            Lead.created_at.desc(),
        )
    elif sort == "lead_score_desc":
        query = query.outerjoin(AIQualification).order_by(
            AIQualification.lead_score.desc().nullslast(),
            Lead.created_at.desc(),
        )
    elif sort == "lead_score_asc":
        query = query.outerjoin(AIQualification).order_by(
            AIQualification.lead_score.asc().nullslast(),
            Lead.created_at.desc(),
        )
    else:
        query = query.order_by(Lead.created_at.desc())

    total = query.count()
    pages = max(1, math.ceil(total / limit)) if total else 0
    items = query.offset((page - 1) * limit).limit(limit).all()

    analysis_by_lead = {}
    discovery_by_lead = {}
    qualification_by_lead = {}
    outreach_by_lead: dict[uuid.UUID, OutreachDraft] = {}
    message_by_lead: dict[uuid.UUID, EmailMessage] = {}
    counts: dict[uuid.UUID, int] = {}
    verification_stats: dict[uuid.UUID, dict[str, int]] = {}
    if items:
        ids = [lead.id for lead in items]
        for row in db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id.in_(ids)).all():
            analysis_by_lead[row.lead_id] = row
        for row in db.query(ContactDiscovery).filter(ContactDiscovery.lead_id.in_(ids)).all():
            discovery_by_lead[row.lead_id] = row
        for row in db.query(AIQualification).filter(AIQualification.lead_id.in_(ids)).all():
            qualification_by_lead[row.lead_id] = row
        for row in (
            db.query(OutreachDraft)
            .filter(OutreachDraft.lead_id.in_(ids))
            .order_by(OutreachDraft.updated_at.desc())
            .all()
        ):
            outreach_by_lead.setdefault(row.lead_id, row)
        for row in (
            db.query(EmailMessage)
            .filter(EmailMessage.lead_id.in_(ids))
            .order_by(EmailMessage.created_at.desc())
            .all()
        ):
            message_by_lead.setdefault(row.lead_id, row)
        contacts = db.query(LeadContact).filter(LeadContact.lead_id.in_(ids)).all()
        for c in contacts:
            counts[c.lead_id] = counts.get(c.lead_id, 0) + 1
        contact_ids = [c.id for c in contacts]
        ver_by_contact = {
            v.lead_contact_id: v
            for v in db.query(EmailVerification).filter(EmailVerification.lead_contact_id.in_(contact_ids or [uuid.uuid4()])).all()
        }
        for c in contacts:
            stats = verification_stats.setdefault(
                c.lead_id,
                {"valid": 0, "invalid": 0, "risky": 0, "unknown": 0, "unverified": 0},
            )
            v = ver_by_contact.get(c.id)
            if not v:
                stats["unverified"] += 1
            elif v.status == "valid":
                stats["valid"] += 1
            elif v.status == "invalid":
                stats["invalid"] += 1
            elif v.status == "risky":
                stats["risky"] += 1
            else:
                stats["unknown"] += 1

    serialized = [
        _serialize_lead(
            lead,
            analysis_by_lead.get(lead.id),
            discovery=discovery_by_lead.get(lead.id),
            qualification=qualification_by_lead.get(lead.id),
            outreach=outreach_by_lead.get(lead.id),
            latest_message=message_by_lead.get(lead.id),
            email_count=counts.get(lead.id, 0),
            verification_stats=verification_stats.get(lead.id),
            include_details=False,
        )
        for lead in items
    ]
    return LeadListResponse(items=serialized, total=total, page=page, limit=limit, pages=pages)


@router.get("/api/leads/{lead_id}", response_model=LeadRead)
def get_lead(
    lead_id: uuid.UUID,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("leads.view")),
) -> LeadRead:
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.organization_id == tenant.organization_id)
        .one_or_none()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    analysis = db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead_id).one_or_none()
    discovery = db.query(ContactDiscovery).filter(ContactDiscovery.lead_id == lead_id).one_or_none()
    qualification = db.query(AIQualification).filter(AIQualification.lead_id == lead_id).one_or_none()
    outreach = (
        db.query(OutreachDraft)
        .filter(OutreachDraft.lead_id == lead_id)
        .order_by(OutreachDraft.updated_at.desc())
        .first()
    )
    latest_message = (
        db.query(EmailMessage)
        .filter(EmailMessage.lead_id == lead_id)
        .order_by(EmailMessage.created_at.desc())
        .first()
    )
    opportunities = (
        db.query(LeadOpportunity)
        .filter(LeadOpportunity.lead_id == lead_id)
        .order_by(LeadOpportunity.created_at.desc())
        .all()
    )
    contacts = (
        db.query(LeadContact)
        .filter(LeadContact.lead_id == lead_id)
        .order_by(LeadContact.is_primary.desc(), LeadContact.created_at.asc())
        .all()
    )
    verifications = {
        row.lead_contact_id: row
        for row in db.query(EmailVerification)
        .filter(EmailVerification.lead_contact_id.in_([c.id for c in contacts] or [uuid.uuid4()]))
        .all()
    }
    return _serialize_lead(
        lead,
        analysis,
        discovery=discovery,
        qualification=qualification,
        outreach=outreach,
        latest_message=latest_message,
        opportunities=opportunities,
        contacts=contacts,
        verifications=verifications,
        email_count=len(contacts),
        include_details=True,
    )


def _serialize_lead(
    lead: Lead,
    analysis: WebsiteAnalysis | None,
    *,
    discovery: ContactDiscovery | None = None,
    qualification: AIQualification | None = None,
    outreach: OutreachDraft | None = None,
    latest_message: EmailMessage | None = None,
    opportunities: list[LeadOpportunity] | None = None,
    contacts: list[LeadContact] | None = None,
    verifications: dict[uuid.UUID, EmailVerification] | None = None,
    email_count: int = 0,
    verification_stats: dict[str, int] | None = None,
    include_details: bool,
) -> LeadRead:
    payload = LeadRead.model_validate(lead)
    if analysis:
        payload.website_analysis_status = analysis.analysis_status
        payload.website_score = analysis.website_score
        if include_details:
            payload.website_analysis = WebsiteAnalysisRead.model_validate(analysis)
    else:
        payload.website_analysis_status = "not_analyzed"
        payload.website_score = None

    if discovery:
        payload.contact_discovery_status = discovery.status
        payload.contact_email_count = discovery.emails_found if discovery.emails_found else email_count
    else:
        payload.contact_discovery_status = "not_discovered"
        payload.contact_email_count = email_count

    if qualification:
        payload.qualification_status = qualification.status
        payload.lead_score = qualification.lead_score
        payload.priority = qualification.priority
        payload.primary_service = qualification.primary_service
        if include_details:
            payload.qualification = AIQualificationRead.model_validate(qualification)
    else:
        payload.qualification_status = "not_analyzed"
        payload.lead_score = None
        payload.priority = None
        payload.primary_service = None

    if verification_stats:
        payload.contacts_verified_count = verification_stats.get("valid", 0)
        payload.contacts_invalid_count = verification_stats.get("invalid", 0)
        payload.contacts_risky_count = verification_stats.get("risky", 0)
        payload.contacts_unknown_count = verification_stats.get("unknown", 0)
        payload.contacts_unverified_count = verification_stats.get("unverified", 0)

    if include_details and opportunities is not None:
        payload.opportunities = [LeadOpportunityRead.model_validate(o) for o in opportunities]
    if include_details and contacts is not None:
        verifications = verifications or {}
        serialized_contacts = []
        stats = {"valid": 0, "invalid": 0, "risky": 0, "unknown": 0, "unverified": 0}
        for c in contacts:
            item = LeadContactRead.model_validate(c)
            v = verifications.get(c.id)
            if v:
                item.verification = EmailVerificationRead.model_validate(v)
                item.verification_status = v.status
                if v.status == "valid":
                    stats["valid"] += 1
                elif v.status == "invalid":
                    stats["invalid"] += 1
                elif v.status == "risky":
                    stats["risky"] += 1
                else:
                    stats["unknown"] += 1
            else:
                item.verification_status = "not_verified"
                stats["unverified"] += 1
            serialized_contacts.append(item)
        payload.contacts = serialized_contacts
        payload.contact_email_count = len(contacts)
        payload.contacts_verified_count = stats["valid"]
        payload.contacts_invalid_count = stats["invalid"]
        payload.contacts_risky_count = stats["risky"]
        payload.contacts_unknown_count = stats["unknown"]
        payload.contacts_unverified_count = stats["unverified"]

    verified_count = payload.contacts_verified_count
    payload.outreach_ready = bool(
        qualification
        and qualification.status == "qualified"
        and qualification.primary_service
        and qualification.primary_service != "unknown"
        and verified_count > 0
    )
    if outreach:
        payload.outreach_draft_status = outreach.status
        if include_details:
            od = OutreachDraftRead.model_validate(outreach)
            payload.outreach_draft = od
    else:
        payload.outreach_draft_status = "not_generated"

    if latest_message:
        payload.sending_status = latest_message.status
        if include_details:
            payload.latest_email_message = EmailMessageRead.model_validate(latest_message)
    elif outreach and outreach.status == "approved":
        payload.sending_status = "approved"
    else:
        payload.sending_status = "not_sent"

    return payload
