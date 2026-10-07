"""Calendar provider abstraction — never fabricates live events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.config import Settings


@dataclass
class CalendarEventResult:
    provider: str
    external_event_id: str | None
    meeting_url: str | None
    live: bool
    status: str  # created | updated | cancelled | unconfigured | error
    error: str | None = None


class CalendarProvider(Protocol):
    name: str

    def create_event(
        self,
        *,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
        attendee_email: str | None,
    ) -> CalendarEventResult: ...

    def cancel_event(self, external_event_id: str) -> CalendarEventResult: ...

    def update_event(
        self,
        *,
        external_event_id: str,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
    ) -> CalendarEventResult: ...


class UnconfiguredCalendarProvider:
    name = "none"

    def create_event(self, **kwargs) -> CalendarEventResult:
        return CalendarEventResult(
            provider=self.name,
            external_event_id=None,
            meeting_url=None,
            live=False,
            status="unconfigured",
        )

    def cancel_event(self, external_event_id: str) -> CalendarEventResult:
        return CalendarEventResult(
            provider=self.name,
            external_event_id=external_event_id,
            meeting_url=None,
            live=False,
            status="unconfigured",
        )

    def update_event(self, **kwargs) -> CalendarEventResult:
        return CalendarEventResult(
            provider=self.name,
            external_event_id=kwargs.get("external_event_id"),
            meeting_url=None,
            live=False,
            status="unconfigured",
        )


class MockCalendarProvider:
    """Offline/QA calendar — IDs clearly marked mock_*, never live."""

    name = "mock"

    def create_event(
        self,
        *,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
        attendee_email: str | None,
    ) -> CalendarEventResult:
        eid = f"mock_{uuid.uuid4().hex[:16]}"
        return CalendarEventResult(
            provider=self.name,
            external_event_id=eid,
            meeting_url=f"https://meet.mock.local/{eid}",
            live=False,
            status="created",
        )

    def cancel_event(self, external_event_id: str) -> CalendarEventResult:
        return CalendarEventResult(
            provider=self.name,
            external_event_id=external_event_id,
            meeting_url=None,
            live=False,
            status="cancelled",
        )

    def update_event(
        self,
        *,
        external_event_id: str,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
    ) -> CalendarEventResult:
        return CalendarEventResult(
            provider=self.name,
            external_event_id=external_event_id,
            meeting_url=f"https://meet.mock.local/{external_event_id}",
            live=False,
            status="updated",
        )


def get_calendar_provider(settings: Settings | None = None) -> CalendarProvider:
    settings = settings or Settings()
    name = (settings.calendar_provider or "").strip().lower()
    if name in {"", "none", "unconfigured"}:
        return UnconfiguredCalendarProvider()
    if name == "mock":
        return MockCalendarProvider()
    # Future: google, outlook — remain unconfigured until implemented
    return UnconfiguredCalendarProvider()
