"""Meeting slot generation from availability rules + exceptions + existing meetings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.availability_exception import AvailabilityException
from app.models.availability_rule import AvailabilityRule
from app.models.meeting import Meeting
from app.models.meeting_type import MeetingType


@dataclass
class TimeSlot:
    start_at: datetime
    end_at: datetime
    timezone: str


def _tz(name: str):
    n = (name or "UTC").strip() or "UTC"
    if n.upper() in {"UTC", "ETC/UTC", "GMT"}:
        return timezone.utc
    try:
        return ZoneInfo(n)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _combine(d: date, t: time, tz) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, tzinfo=tz)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    a_start, a_end = _as_utc(a_start), _as_utc(a_end)
    b_start, b_end = _as_utc(b_start), _as_utc(b_end)
    return a_start < b_end and b_start < a_end


class MeetingAvailabilityService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def generate_slots(
        self,
        meeting_type: MeetingType,
        *,
        range_start: date,
        range_end: date,
        timezone_name: str | None = None,
    ) -> list[TimeSlot]:
        tz_name = timezone_name or self.settings.meeting_default_timezone
        tz = _tz(tz_name)
        duration = timedelta(minutes=int(meeting_type.duration_minutes))
        buf_before = timedelta(minutes=int(meeting_type.buffer_before_minutes))
        buf_after = timedelta(minutes=int(meeting_type.buffer_after_minutes))
        interval = timedelta(minutes=int(self.settings.meeting_slot_interval_minutes))

        rules = (
            self.db.query(AvailabilityRule)
            .filter(AvailabilityRule.active.is_(True))
            .all()
        )
        exceptions = (
            self.db.query(AvailabilityException)
            .filter(
                AvailabilityException.date >= range_start,
                AvailabilityException.date <= range_end,
            )
            .all()
        )
        blocked_by_date: dict[date, list[AvailabilityException]] = {}
        available_override: dict[date, list[AvailabilityException]] = {}
        for ex in exceptions:
            if ex.type == "blocked":
                blocked_by_date.setdefault(ex.date, []).append(ex)
            elif ex.type == "available":
                available_override.setdefault(ex.date, []).append(ex)

        # Busy windows from existing meetings (with buffers)
        existing = (
            self.db.query(Meeting)
            .filter(
                Meeting.status.in_(["scheduled", "confirmed", "requested", "rescheduled"]),
                Meeting.start_at <= datetime.combine(range_end, time(23, 59), tzinfo=tz).astimezone(timezone.utc)
                + timedelta(days=1),
                Meeting.end_at >= datetime.combine(range_start, time(0, 0), tzinfo=tz).astimezone(timezone.utc)
                - timedelta(days=1),
            )
            .all()
        )
        busy: list[tuple[datetime, datetime]] = []
        for m in existing:
            busy.append((_as_utc(m.start_at) - buf_before, _as_utc(m.end_at) + buf_after))

        slots: list[TimeSlot] = []
        day = range_start
        now = datetime.now(timezone.utc)
        while day <= range_end:
            windows: list[tuple[time, time]] = []
            if day in available_override:
                for ex in available_override[day]:
                    if ex.start_time and ex.end_time:
                        windows.append((ex.start_time, ex.end_time))
            else:
                weekday = day.weekday()
                for rule in rules:
                    if rule.day_of_week == weekday:
                        windows.append((rule.start_time, rule.end_time))

            # Apply full-day blocks
            day_blocks = blocked_by_date.get(day, [])
            full_block = any(b.start_time is None and b.end_time is None for b in day_blocks)

            if not full_block:
                for start_t, end_t in windows:
                    cursor = _combine(day, start_t, tz)
                    window_end = _combine(day, end_t, tz)
                    while cursor + duration <= window_end:
                        slot_end = cursor + duration
                        # partial blocks
                        blocked = False
                        for b in day_blocks:
                            if b.start_time and b.end_time:
                                b_start = _combine(day, b.start_time, tz)
                                b_end = _combine(day, b.end_time, tz)
                                if _overlaps(cursor, slot_end, b_start, b_end):
                                    blocked = True
                                    break
                        if not blocked:
                            utc_start = cursor.astimezone(timezone.utc)
                            utc_end = slot_end.astimezone(timezone.utc)
                            if utc_start > now:
                                conflict = any(_overlaps(utc_start - buf_before, utc_end + buf_after, bs, be) for bs, be in busy)
                                if not conflict:
                                    slots.append(
                                        TimeSlot(start_at=utc_start, end_at=utc_end, timezone=tz_name)
                                    )
                        cursor += interval
            day += timedelta(days=1)
        return slots

    def is_slot_available(
        self,
        meeting_type: MeetingType,
        start_at: datetime,
        *,
        timezone_name: str | None = None,
        exclude_meeting_id=None,
    ) -> bool:
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
        local_date = start_at.astimezone(_tz(timezone_name or self.settings.meeting_default_timezone)).date()
        slots = self.generate_slots(
            meeting_type,
            range_start=local_date,
            range_end=local_date,
            timezone_name=timezone_name,
        )
        for s in slots:
            if abs((s.start_at - start_at).total_seconds()) < 1:
                return True
        # Also check overlap directly if regenerate filtered it out due to exclude
        if exclude_meeting_id:
            duration = timedelta(minutes=meeting_type.duration_minutes)
            end_at = start_at + duration
            conflict = (
                self.db.query(Meeting)
                .filter(
                    Meeting.id != exclude_meeting_id,
                    Meeting.status.in_(["scheduled", "confirmed", "requested", "rescheduled"]),
                    Meeting.start_at < end_at,
                    Meeting.end_at > start_at,
                )
                .first()
            )
            return conflict is None and any(
                abs((s.start_at - start_at).total_seconds()) < 60 for s in slots
            ) or conflict is None
        return False
