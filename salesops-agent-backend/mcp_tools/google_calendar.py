"""Google Calendar API MCP tool adapter.

Provides tools to check availability and create calendar events
for the SalesOps agent when meeting intent is detected.
"""

import httpx
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, List
from pydantic import BaseModel, Field
from core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth Helper
# ---------------------------------------------------------------------------

async def get_access_token(refresh_token: Optional[str] = None) -> str:
    """Fetch a fresh access token using the refresh token."""
    # Fallback to settings if no token provided (backward compatibility)
    rt = refresh_token or settings.GOOGLE_CALENDAR_REFRESH_TOKEN
    
    if not all([settings.GOOGLE_CALENDAR_CLIENT_ID, settings.GOOGLE_CALENDAR_CLIENT_SECRET, rt]):
        raise ValueError("Google Calendar credentials are not fully configured. User must connect their calendar.")
        
    url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
        "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        "refresh_token": rt,
        "grant_type": "refresh_token",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        return data["access_token"]


# ---------------------------------------------------------------------------
# Input / Output schemas
# ---------------------------------------------------------------------------

class CheckAvailabilityInput(BaseModel):
    """Input schema for checking calendar availability."""
    date: str = Field(..., description="Date to check in YYYY-MM-DD format")
    timezone: str = Field("Asia/Karachi", description="IANA timezone")
    refresh_token: Optional[str] = Field(None, description="Internal use: User's refresh token")


class CreateEventInput(BaseModel):
    """Input schema for creating a Google Calendar event."""
    summary: str = Field(..., description="Event title, e.g. 'Meeting with Al-Shifa Clinic'")
    description: Optional[str] = Field("", description="Event description / notes")
    start_datetime: str = Field(..., description="ISO-8601 start, e.g. '2026-05-20T10:00:00'")
    end_datetime: Optional[str] = Field(None, description="ISO-8601 end, e.g. '2026-05-20T11:00:00'. If omitted, defaults to 1 hour after start.")
    timezone: str = Field("Asia/Karachi", description="IANA timezone")
    attendee_emails: Optional[List[str]] = Field(default_factory=list, description="Email addresses of attendees")
    refresh_token: Optional[str] = Field(None, description="Internal use: User's refresh token")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def check_availability(input_data: CheckAvailabilityInput) -> dict[str, Any]:
    """Check calendar availability for a given date using Google FreeBusy API."""
    try:
        access_token = await get_access_token(input_data.refresh_token)
    except Exception as e:
        logger.error("Failed to get access token: %s", e)
        return {"status": "error", "message": str(e)}

    # Build timezone-aware RFC3339 timestamps for the requested local date
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(input_data.timezone)
        day_start = datetime(
            *map(int, input_data.date.split("-")),  # year, month, day
            0, 0, 0, tzinfo=tz,
        )
        day_end = day_start + timedelta(days=1) - timedelta(seconds=1)
        time_min = day_start.isoformat()
        time_max = day_end.isoformat()
    except Exception:
        # Fallback: let Google interpret via timeZone field
        time_min = f"{input_data.date}T00:00:00"
        time_max = f"{input_data.date}T23:59:59"

    url = "https://www.googleapis.com/calendar/v3/freeBusy"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "timeMin": time_min,
        "timeMax": time_max,
        "timeZone": input_data.timezone,
        "items": [{"id": "primary"}],
    }

    logger.info("FreeBusy request: date=%s tz=%s timeMin=%s timeMax=%s",
                input_data.date, input_data.timezone, time_min, time_max)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            busy_slots = data.get("calendars", {}).get("primary", {}).get("busy", [])

            return {
                "status": "success",
                "message": f"Availability for {input_data.date}",
                "date": input_data.date,
                "timezone": input_data.timezone,
                "busy_slots": busy_slots,
                "total_busy": len(busy_slots),
                "is_free_all_day": len(busy_slots) == 0,
            }
        except httpx.HTTPStatusError as e:
            logger.error("FreeBusy API error: %s — %s", e.response.status_code, e.response.text)
            return {"status": "error", "message": f"Calendar API error: {e.response.status_code}"}
        except Exception as e:
            logger.error("Failed to check availability: %s", e)
            return {"status": "error", "message": f"Failed to check availability: {str(e)}"}


async def create_event(input_data: CreateEventInput) -> dict[str, Any]:
    """Create a real Google Calendar event via the Calendar Events API."""
    try:
        access_token = await get_access_token(input_data.refresh_token)
    except Exception as e:
        logger.error("Failed to get access token: %s", e)
        return {"status": "error", "message": str(e)}

    end_time = input_data.end_datetime
    if not end_time:
        try:
            start_dt = datetime.fromisoformat(input_data.start_datetime.replace('Z', '+00:00'))
            end_dt = start_dt + timedelta(hours=1)
            end_time = end_dt.isoformat()
        except Exception:
            end_time = input_data.start_datetime

    attendees = [{"email": email} for email in (input_data.attendee_emails or [])]

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "summary": input_data.summary,
        "description": input_data.description,
        "start": {
            "dateTime": input_data.start_datetime,
            "timeZone": input_data.timezone,
        },
        "end": {
            "dateTime": end_time,
            "timeZone": input_data.timezone,
        },
        "attendees": attendees,
    }

    logger.info(
        "Creating calendar event: summary=%s start=%s end=%s tz=%s attendees=%s",
        input_data.summary, input_data.start_datetime, end_time,
        input_data.timezone, [e["email"] for e in attendees],
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            event_data = response.json()

            logger.info("Event created: id=%s link=%s",
                        event_data.get("id"), event_data.get("htmlLink"))

            return {
                "status": "success",
                "message": "Event created successfully.",
                "data": {
                    "event_id": event_data.get("id"),
                    "summary": event_data.get("summary"),
                    "start": event_data.get("start", {}).get("dateTime"),
                    "end": event_data.get("end", {}).get("dateTime"),
                    "html_link": event_data.get("htmlLink"),
                },
            }
        except httpx.HTTPStatusError as e:
            logger.error("Calendar Events API error: %s — %s", e.response.status_code, e.response.text)
            return {"status": "error", "message": f"Calendar API error: {e.response.status_code} — {e.response.text}"}
        except Exception as e:
            logger.error("Failed to create event: %s", e)
            return {"status": "error", "message": f"Failed to create event: {str(e)}"}
