"""CRM pipeline stage transitions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.lead_pipeline_event import LeadPipelineEvent

PIPELINE_STAGES = (
    "new",
    "qualified",
    "contacted",
    "replied",
    "meeting_requested",
    "meeting_scheduled",
    "meeting_completed",
    "proposal",
    "won",
    "lost",
)

# Safe automatic transitions (from -> allowed tos for system)
SYSTEM_TRANSITIONS: dict[str, set[str]] = {
    "new": {"qualified", "contacted"},
    "qualified": {"contacted", "replied", "meeting_requested"},
    "contacted": {"replied", "meeting_requested", "qualified"},
    "replied": {"meeting_requested", "meeting_scheduled", "contacted"},
    "meeting_requested": {"meeting_scheduled", "replied"},
    "meeting_scheduled": {"meeting_completed", "meeting_requested"},
    "meeting_completed": {"proposal", "meeting_scheduled"},
    "proposal": {"won", "lost", "meeting_completed"},
    "won": set(),
    "lost": set(),
}

# Manual can move more freely except inventing won/lost only via user
MANUAL_ALLOWED = set(PIPELINE_STAGES)


class PipelineError(ValueError):
    def __init__(self, message: str, *, code: str = "pipeline_error"):
        super().__init__(message)
        self.code = code


def set_pipeline_stage(
    db: Session,
    lead_id: uuid.UUID,
    to_stage: str,
    *,
    reason: str | None = None,
    source: str = "system",
    created_by: str | None = None,
    force: bool = False,
) -> Lead:
    if to_stage not in PIPELINE_STAGES:
        raise PipelineError(f"Invalid stage: {to_stage}", code="invalid_stage")

    lead = db.get(Lead, lead_id)
    if not lead:
        raise PipelineError("Lead not found", code="lead_not_found")

    current = lead.pipeline_stage or "new"
    if current == to_stage:
        return lead

    # Never auto-mark won/lost
    if source != "user" and to_stage in {"won", "lost"}:
        raise PipelineError("won/lost require manual user action", code="manual_only")

    if source != "user" and not force:
        allowed = SYSTEM_TRANSITIONS.get(current, set())
        # Allow skip-forward for common flows (e.g. new -> meeting_requested via reply)
        order = {s: i for i, s in enumerate(PIPELINE_STAGES)}
        if to_stage not in allowed:
            # Permit forward-only progression within pre-proposal stages
            if order.get(to_stage, 99) < order.get(current, 0):
                # don't regress automatically
                return lead
            if order.get(to_stage, 99) > order.get("proposal", 99):
                raise PipelineError("Invalid automatic transition", code="invalid_transition")

    event = LeadPipelineEvent(
        lead_id=lead.id,
        from_stage=current,
        to_stage=to_stage,
        reason=reason,
        source=source,
        created_by=created_by,
    )
    db.add(event)
    lead.pipeline_stage = to_stage
    lead.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    try:
        from app.services.system.audit import write_audit

        write_audit(
            db,
            action="lead_stage_changed",
            entity_type="lead",
            entity_id=str(lead.id),
            actor_type="user" if source == "user" else "system",
            metadata={"from": current, "to": to_stage, "source": source},
        )
    except Exception:  # noqa: BLE001
        pass
    return lead


def ensure_pipeline_at_least(
    db: Session,
    lead_id: uuid.UUID,
    stage: str,
    *,
    reason: str,
    source: str,
) -> None:
    """Move forward to stage if current is earlier; never regress."""
    lead = db.get(Lead, lead_id)
    if not lead:
        return
    order = {s: i for i, s in enumerate(PIPELINE_STAGES)}
    current = lead.pipeline_stage or "new"
    if order.get(stage, -1) > order.get(current, -1):
        set_pipeline_stage(db, lead_id, stage, reason=reason, source=source, force=True)
