"""Timezone-aware send window helpers for campaigns."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.campaign import Campaign


def _tz(campaign: Campaign):
    name = (campaign.timezone or "UTC").strip() or "UTC"
    if name.upper() in {"UTC", "ETC/UTC", "GMT"}:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def compute_next_send_at(
    campaign: Campaign,
    earliest: datetime,
    *,
    max_days_ahead: int = 60,
) -> datetime:
    """
    Return the soonest UTC datetime >= earliest that falls inside the campaign
    send window (and weekend rules) in the campaign timezone.
    """
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=timezone.utc)

    tz = _tz(campaign)
    local = earliest.astimezone(tz)
    start_h = int(campaign.send_start_hour)
    end_h = int(campaign.send_end_hour)
    if start_h < 0 or start_h > 23 or end_h < 1 or end_h > 24 or start_h >= end_h:
        start_h, end_h = 9, 17

    for _ in range(max_days_ahead * 24 + 2):
        weekday = local.weekday()  # Mon=0 … Sun=6
        if not campaign.send_on_weekends and weekday >= 5:
            days_ahead = 7 - weekday
            local = (local + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            continue

        window_start = local.replace(hour=start_h, minute=0, second=0, microsecond=0)
        if end_h >= 24:
            window_end = (local + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            window_end = local.replace(hour=end_h, minute=0, second=0, microsecond=0)

        if local < window_start:
            local = window_start
            continue
        if local >= window_end:
            local = (local + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            continue

        return local.astimezone(timezone.utc)

    return earliest.astimezone(timezone.utc)


def is_within_send_window(campaign: Campaign, when: datetime | None = None) -> bool:
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    tz = _tz(campaign)
    local = when.astimezone(tz)
    if not campaign.send_on_weekends and local.weekday() >= 5:
        return False
    end_h = campaign.send_end_hour
    if end_h >= 24:
        return campaign.send_start_hour <= local.hour <= 23
    return campaign.send_start_hour <= local.hour < end_h
