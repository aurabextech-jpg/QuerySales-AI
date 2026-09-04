"""Google Calendar OAuth endpoints for Android & iOS.

Handles:
  POST /calendar/sync       — Exchange auth code for refresh token (platform-aware)
  GET  /calendar/status      — Check connection status
  POST /calendar/disconnect  — Disconnect and revoke access
  GET  /calendar/config      — Return platform-specific OAuth client IDs + scopes

The mobile app (Android/iOS) uses `@react-native-google-signin/google-signin`
to get a `serverAuthCode` via the native Google Sign-In flow, then sends it
here for backend token exchange.

Key platform differences:
  - Android: Uses the *web* client ID for `serverAuthCode`, redirect_uri is ignored
             or set to empty string (Google handles it internally)
  - iOS:     Uses the *iOS* native client ID for the Sign-In flow, but the
             `serverAuthCode` is exchanged with the *web* client_secret on the backend

In both cases, the backend always uses `GOOGLE_CALENDAR_CLIENT_ID` (web) +
`GOOGLE_CALENDAR_CLIENT_SECRET` for the token exchange.
"""

import logging
from enum import Enum
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import get_current_user, encrypt_token
from db.models import User
from db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Calendar scopes required for full agent functionality ─────────────────
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class Platform(str, Enum):
    """Supported mobile platforms."""
    ANDROID = "android"
    IOS = "ios"


class SyncCalendarRequest(BaseModel):
    """Request body for the /sync endpoint."""
    auth_code: str = Field(..., description="Server auth code from Google Sign-In")
    platform: Platform = Field(
        Platform.ANDROID,
        description="Client platform: 'android' or 'ios'",
    )
    redirect_uri: Optional[str] = Field(
        None,
        description=(
            "Override redirect_uri for token exchange. "
            "If omitted, defaults to empty string for Android "
            "and the iOS reversed client ID URL scheme for iOS."
        ),
    )


def _get_redirect_uri(platform: Platform, override: Optional[str] = None) -> str:
    """Resolve the correct redirect_uri for the Google token exchange.

    Android: When using `@react-native-google-signin` with offlineAccess,
             the serverAuthCode is exchanged using an empty redirect_uri
             (Google handles it internally via the web client configuration).

    iOS:     Same as Android — the react-native-google-signin library
             handles the redirect internally. Empty string works.
    """
    if override:
        return override
    # For both platforms when using react-native-google-signin,
    # an empty redirect_uri works for server-side code exchange
    return ""


@router.post("/sync")
async def sync_google_calendar(
    request: SyncCalendarRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exchange a mobile OAuth authorization code for a Google refresh token.

    This endpoint is called by the mobile app after the user completes
    the Google Sign-In consent flow. The `serverAuthCode` obtained from
    the native SDK is exchanged server-side for access + refresh tokens.

    Supports both Android and iOS platforms.
    """
    if not all([settings.GOOGLE_CALENDAR_CLIENT_ID, settings.GOOGLE_CALENDAR_CLIENT_SECRET]):
        raise HTTPException(
            status_code=500,
            detail="Google Calendar integration is not configured on the server.",
        )

    redirect_uri = _get_redirect_uri(request.platform, request.redirect_uri)

    logger.info(
        "Calendar sync: user=%s platform=%s redirect_uri=%r",
        current_user.id,
        request.platform.value,
        redirect_uri,
    )

    # Always use the web client ID + secret for the server-side exchange
    token_payload = {
        "code": request.auth_code,
        "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
        "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data=token_payload,
            )

            if response.status_code != 200:
                error_body = response.text
                logger.error(
                    "Google token exchange failed: status=%d platform=%s body=%s",
                    response.status_code,
                    request.platform.value,
                    error_body,
                )
                # Parse Google's error response for better user feedback
                try:
                    error_json = response.json()
                    error_desc = error_json.get("error_description", "")
                    if "redirect_uri_mismatch" in error_desc.lower():
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Redirect URI mismatch. Ensure the OAuth client "
                                "is configured correctly in Google Cloud Console "
                                f"for {request.platform.value}."
                            ),
                        )
                except (ValueError, KeyError):
                    pass

                raise HTTPException(
                    status_code=400,
                    detail="Google Calendar authorization failed. Please try connecting again.",
                )

            data = response.json()
            refresh_token = data.get("refresh_token")
            access_token = data.get("access_token")

            # OAuth V2 only returns refresh_token on the first authorization.
            # If the user re-authorizes without revoking access first,
            # refresh_token will be None.
            if not refresh_token:
                logger.warning(
                    "No refresh_token returned for user=%s platform=%s. "
                    "Google may have already issued one previously.",
                    current_user.id,
                    request.platform.value,
                )
                if not current_user.google_refresh_token:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Failed to obtain refresh token. Please revoke SalesOps "
                            "access from your Google Account settings "
                            "(myaccount.google.com/permissions) and try again."
                        ),
                    )
            else:
                # Encrypt and persist the new refresh token
                current_user.google_refresh_token = encrypt_token(refresh_token)

            current_user.google_calendar_connected = True
            db.add(current_user)
            await db.commit()

            # Optionally fetch the user's calendar email for confirmation
            calendar_email = await _fetch_calendar_email(access_token) if access_token else None

            return {
                "status": "success",
                "message": "Google Calendar successfully connected.",
                "details": {
                    "email": calendar_email or current_user.email,
                    "calendar_connected": True,
                    "platform": request.platform.value,
                },
            }

    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("Timeout exchanging auth code for user=%s", current_user.id)
        raise HTTPException(
            status_code=504,
            detail="Google authentication timed out. Please try again.",
        )
    except Exception as exc:
        logger.error(
            "Error connecting calendar for user=%s: %s",
            current_user.id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to connect Google Calendar. Please try again later.",
        )


@router.get("/status")
async def get_calendar_status(
    current_user: User = Depends(get_current_user),
):
    """Check if the current user has connected their Google Calendar."""
    return {
        "is_connected": current_user.google_calendar_connected,
        "email": current_user.email if current_user.google_calendar_connected else None,
    }


@router.post("/disconnect")
async def disconnect_calendar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect Google Calendar and revoke the refresh token server-side."""
    # Attempt to revoke the token at Google to ensure clean disconnect
    if current_user.google_refresh_token:
        try:
            from core.security import decrypt_token as _decrypt
            plain_token = _decrypt(current_user.google_refresh_token)
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": plain_token},
                )
            logger.info("Revoked Google token for user=%s", current_user.id)
        except Exception as exc:
            # Non-critical: if revocation fails, still disconnect locally
            logger.warning("Token revocation failed for user=%s: %s", current_user.id, exc)

    current_user.google_refresh_token = None
    current_user.google_calendar_connected = False
    db.add(current_user)
    await db.commit()

    return {
        "status": "success",
        "message": "Google Calendar successfully disconnected.",
    }


@router.get("/config")
async def get_calendar_config():
    """Return platform-specific OAuth client IDs and scopes.

    The mobile app calls this on startup to configure Google Sign-In
    with the correct client ID for its platform (Android vs iOS).
    """
    return {
        "android": {
            "web_client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
            "scopes": CALENDAR_SCOPES,
        },
        "ios": {
            "web_client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
            "ios_client_id": settings.GOOGLE_CALENDAR_IOS_CLIENT_ID or None,
            "scopes": CALENDAR_SCOPES,
        },
        "scopes": CALENDAR_SCOPES,
    }


# ── Helper ────────────────────────────────────────────────────────────────

async def _fetch_calendar_email(access_token: str) -> Optional[str]:
    """Fetch the primary calendar's owner email for display purposes."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return resp.json().get("id")  # primary calendar ID is the email
    except Exception:
        pass
    return None
