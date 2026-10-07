from fastapi import APIRouter, Depends

from app.api.deps import bind_tenant_context, enforce_auth_dependency
from app.api.routes import (
    auth,
    billing,
    campaigns,
    contacts,
    conversations,
    generation,
    leads,
    meetings,
    outreach,
    qualification,
    sending,
    system,
    verification,
    websites,
)

api_router = APIRouter(
    dependencies=[Depends(enforce_auth_dependency), Depends(bind_tenant_context)]
)
api_router.include_router(auth.router)
api_router.include_router(billing.router)
api_router.include_router(system.router)
api_router.include_router(generation.router)
api_router.include_router(leads.router)
api_router.include_router(websites.router)
api_router.include_router(contacts.router)
api_router.include_router(verification.router)
api_router.include_router(qualification.router)
api_router.include_router(outreach.router)
api_router.include_router(sending.router)
api_router.include_router(campaigns.router)
api_router.include_router(conversations.router)
api_router.include_router(meetings.router)
