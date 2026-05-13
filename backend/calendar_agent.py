"""Google Calendar helpers for meeting-time parsing and availability checks."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo


WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


TIME_PATTERN = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
ISO_DATE_PATTERN = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
SLASH_DATE_PATTERN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
DURATION_PATTERN = re.compile(r"\b(\d+)\s*(minute|minutes|min|hour|hours|hr|hrs)\b", re.IGNORECASE)


def _parse_time_components(text: str) -> Tuple[int, int] | None:
    """Parse time like `10`, `10:30`, `10 AM`, `2:15pm`."""
    match = TIME_PATTERN.search(text or "")
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = (match.group(3) or "").lower()

    if minute < 0 or minute > 59:
        return None

    if ampm in {"am", "pm"}:
        if hour < 1 or hour > 12:
            return None
        if ampm == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
    else:
        if hour > 23:
            return None

    return hour, minute


def _next_weekday(base_date, target_weekday: int):
    days_ahead = (target_weekday - base_date.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base_date + timedelta(days=days_ahead)


def _extract_duration_minutes(text: str) -> int:
    """Extract meeting duration; default 30 minutes."""
    default_minutes = int(os.getenv("MEETING_DURATION_MINUTES", "30"))

    match = DURATION_PATTERN.search(text or "")
    if not match:
        return max(15, default_minutes)

    value = int(match.group(1))
    unit = match.group(2).lower()

    if unit.startswith("hour") or unit in {"hr", "hrs"}:
        value *= 60

    return max(15, min(value, 240))


def parse_meeting_window(email_text: str, timezone_name: str | None = None) -> Dict:
    """Parse proposed meeting date/time from natural language.

    Supported examples:
    - "tomorrow at 10 AM"
    - "next monday 2:30 pm"
    - "2026-04-05 at 11:00"
    - "05/04/2026 at 11 am"
    """
    text = (email_text or "").strip()
    text_lower = text.lower()

    tz_name = timezone_name or os.getenv("APP_TIMEZONE", "Asia/Kolkata")
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)

    time_parts = _parse_time_components(text)
    if not time_parts:
        return {
            "status": "unparsed",
            "reason": "No clear meeting time found in email text.",
            "timezone": tz_name,
        }

    target_date = None

    # Explicit YYYY-MM-DD
    iso_match = ISO_DATE_PATTERN.search(text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        target_date = datetime(year, month, day, tzinfo=tz).date()

    # Explicit DD/MM/YYYY
    if target_date is None:
        slash_match = SLASH_DATE_PATTERN.search(text)
        if slash_match:
            day, month, year = map(int, slash_match.groups())
            target_date = datetime(year, month, day, tzinfo=tz).date()

    # Relative dates
    if target_date is None:
        if "tomorrow" in text_lower:
            target_date = (now + timedelta(days=1)).date()
        elif "today" in text_lower:
            target_date = now.date()
        else:
            for weekday_name, weekday_idx in WEEKDAY_MAP.items():
                if f"next {weekday_name}" in text_lower:
                    target_date = _next_weekday(now.date(), weekday_idx)
                    break
                if weekday_name in text_lower:
                    days_ahead = (weekday_idx - now.weekday() + 7) % 7
                    target_date = (now + timedelta(days=days_ahead)).date()
                    break

    if target_date is None:
        return {
            "status": "unparsed",
            "reason": "No clear meeting date found in email text.",
            "timezone": tz_name,
        }

    start_hour, start_minute = time_parts
    start_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        start_hour,
        start_minute,
        tzinfo=tz,
    )

    if start_dt < now:
        # If parsed time is in the past (e.g., today 9 AM but now 4 PM), move to next day.
        start_dt = start_dt + timedelta(days=1)

    duration_minutes = _extract_duration_minutes(text)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    return {
        "status": "parsed",
        "timezone": tz_name,
        "start_iso": start_dt.isoformat(),
        "end_iso": end_dt.isoformat(),
        "duration_minutes": duration_minutes,
        "display": start_dt.strftime("%A, %d %b %Y %I:%M %p"),
    }


def check_calendar_availability(calendar_service, start_iso: str, end_iso: str) -> Tuple[bool, List[dict]]:
    """Check if primary calendar is free in the requested slot."""
    query_body = {
        "timeMin": start_iso,
        "timeMax": end_iso,
        "items": [{"id": "primary"}],
    }

    response = calendar_service.freebusy().query(body=query_body).execute()
    busy_slots = response.get("calendars", {}).get("primary", {}).get("busy", [])
    return len(busy_slots) == 0, busy_slots


def create_calendar_event(
    calendar_service,
    summary: str,
    description: str,
    start_iso: str,
    end_iso: str,
    attendee_emails: List[str] | None = None,
) -> Dict:
    """Create a Google Calendar event on primary calendar."""
    attendees = [{"email": email} for email in (attendee_emails or []) if email]

    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
        "attendees": attendees,
    }

    event = (
        calendar_service.events()
        .insert(calendarId="primary", body=event_body, sendUpdates="all")
        .execute()
    )

    return {
        "event_id": event.get("id"),
        "html_link": event.get("htmlLink"),
    }


def list_upcoming_events(calendar_service, max_results: int = 20) -> List[Dict]:
    """List upcoming events from primary Google Calendar."""
    tz_name = os.getenv("APP_TIMEZONE", "Asia/Kolkata")
    tz = ZoneInfo(tz_name)
    now_iso = datetime.now(tz).isoformat()

    response = (
        calendar_service.events()
        .list(
            calendarId="primary",
            timeMin=now_iso,
            maxResults=max(1, min(int(max_results), 100)),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    items = response.get("items", [])
    events: List[Dict] = []

    for event in items:
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
        attendees = [att.get("email") for att in event.get("attendees", []) if att.get("email")]

        events.append(
            {
                "event_id": event.get("id"),
                "summary": event.get("summary", "(No title)"),
                "start": start,
                "end": end,
                "html_link": event.get("htmlLink"),
                "status": event.get("status"),
                "creator": (event.get("creator") or {}).get("email"),
                "attendees": attendees,
            }
        )

    return events
