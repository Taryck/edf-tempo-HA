"""API client for EDF Tempo Rev TBE."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, PARIS_TIME_ZONE, TEMPO_CALENDARS_PATH, TOKEN_URL
from .const import TEMPO_BLUE_TOTAL, TEMPO_RED_TOTAL, TEMPO_WHITE_TOTAL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)
TOKEN_EXPIRY_SAFETY_MARGIN = timedelta(minutes=5)

COLOR_LABELS: dict[str, str] = {
    "BLUE": "Blue",
    "WHITE": "White",
    "RED": "Red",
}


class EdfTempoError(Exception):
    """Base exception for the EDF Tempo Rev TBE client."""


class EdfTempoAuthError(EdfTempoError):
    """Raised when authentication with the EDF Tempo Rev TBE API fails."""


class EdfTempoAccessError(EdfTempoAuthError):
    """Raised when the Tempo endpoint denies access (HTTP 403)."""


class EdfTempoApiError(EdfTempoError):
    """Raised when the EDF Tempo Rev TBE API returns an unexpected response."""


@dataclass(frozen=True, slots=True)
class TempoDayData:
    """Normalized day data from the EDF Tempo Rev TBE API."""

    date: str
    color_code: str | None
    display_color: str | None
    fallback: bool
    updated_date: str | None


@dataclass(frozen=True, slots=True)
class TempoCalendarData:
    """Normalized response exposed to the coordinator."""

    today: TempoDayData
    tomorrow: TempoDayData
    season_summary: "TempoSeasonSummaryData | None"
    fetched_at: str
    summary_updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class TempoSeasonSummaryData:
    """Normalized season summary data."""

    season_start: str
    season_end: str
    total_placed: int
    blue_days: int
    white_days: int
    red_days: int
    blue_total: int = TEMPO_BLUE_TOTAL
    white_total: int = TEMPO_WHITE_TOTAL
    red_total: int = TEMPO_RED_TOTAL


@dataclass(frozen=True, slots=True)
class TempoDayWindowData:
    """Normalized today/tomorrow payload."""

    today: TempoDayData
    tomorrow: TempoDayData


class EdfTempoClient:
    """Async client for the official EDF Tempo Rev TBE API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def async_validate_credentials(self) -> None:
        """Validate credentials by retrieving an access token."""
        await self._async_get_access_token(force_refresh=True)

    async def async_validate_access(self) -> None:
        """Validate credentials and Tempo access before saving configuration."""
        await self.async_validate_credentials()
        await self.async_get_tempo_days()

    async def async_get_tempo_days(self) -> TempoDayWindowData:
        """Fetch today and tomorrow Tempo colors."""
        _LOGGER.debug("Fetching EDF Tempo Rev TBE day window for today and tomorrow")
        token = await self._async_get_access_token()
        now_paris = datetime.now(PARIS_TIME_ZONE)
        today = now_paris.date()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)

        calendar_params = {
            "start_date": self._format_api_datetime(
                datetime.combine(today, datetime.min.time(), tzinfo=PARIS_TIME_ZONE)
            ),
            "end_date": self._format_api_datetime(
                datetime.combine(
                    day_after_tomorrow,
                    datetime.min.time(),
                    tzinfo=PARIS_TIME_ZONE,
                )
            ),
            "fallback_status": "true",
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        response_json = await self._async_request_json(
            "GET",
            f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}",
            headers=headers,
            params=calendar_params,
            retry_on_auth_error=True,
        )
        return self._parse_day_window_response(
            response_json,
            today.isoformat(),
            tomorrow.isoformat(),
        )

    async def async_get_season_day_colors(
        self,
        season_start: date,
        season_end: date,
    ) -> dict[str, str]:
        """Fetch and parse all known color days for a season."""
        _LOGGER.debug(
            "Fetching EDF Tempo Rev TBE season day colors for %s to %s",
            season_start.isoformat(),
            season_end.isoformat(),
        )
        today = datetime.now(PARIS_TIME_ZONE).date()
        effective_end = min(season_end, today)
        if effective_end < season_start:
            _LOGGER.debug(
                "Skipping season fetch because effective end %s is before start %s",
                effective_end.isoformat(),
                season_start.isoformat(),
            )
            return {}

        token = await self._async_get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        response_json = await self._async_request_json(
            "GET",
            f"{API_BASE_URL}{TEMPO_CALENDARS_PATH}",
            headers=headers,
            params={
                "start_date": self._format_api_datetime(
                    datetime.combine(season_start, datetime.min.time(), tzinfo=PARIS_TIME_ZONE)
                ),
                "end_date": self._format_api_datetime(
                    datetime.combine(
                        effective_end + timedelta(days=1),
                        datetime.min.time(),
                        tzinfo=PARIS_TIME_ZONE,
                    )
                ),
                "fallback_status": "true",
            },
            retry_on_auth_error=True,
        )
        parsed_by_date = self._parse_values_by_date(response_json)
        return {
            day.date: day.color_code
            for day in parsed_by_date.values()
            if day.color_code in {"BLUE", "WHITE", "RED"}
        }

    async def _async_get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid access token, refreshing it if needed."""
        now_utc = datetime.now().astimezone()
        if (
            not force_refresh
            and self._access_token is not None
            and self._token_expires_at is not None
            and now_utc + TOKEN_EXPIRY_SAFETY_MARGIN < self._token_expires_at
        ):
            return self._access_token

        headers = {"Accept": "application/json"}

        try:
            async with self._session.post(
                TOKEN_URL,
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    raise EdfTempoAuthError("Authentication failed")

                if response.status >= 400:
                    raise EdfTempoApiError(
                        f"Token request failed with status {response.status}"
                    )

                try:
                    payload = await response.json(content_type=None)
                except (ValueError, UnicodeDecodeError) as err:
                    raise EdfTempoApiError("Token response contained invalid JSON") from err
        except asyncio.TimeoutError as err:
            _LOGGER.warning("EDF Tempo Rev TBE token request timed out")
            raise EdfTempoApiError("Token request timed out") from err
        except aiohttp.ClientError as err:
            _LOGGER.warning("EDF Tempo Rev TBE token request failed: %s", err)
            raise EdfTempoApiError(f"Token request failed: {err}") from err

        if not isinstance(payload, dict):
            raise EdfTempoApiError("Token response was not a JSON object")

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in", 7200)
        if not isinstance(access_token, str):
            raise EdfTempoApiError("Token response did not include an access token")

        try:
            expires_in_int = int(expires_in)
        except (TypeError, ValueError) as err:
            raise EdfTempoApiError("Token response contained an invalid expires_in value") from err

        self._access_token = access_token
        self._token_expires_at = now_utc + timedelta(seconds=expires_in_int)
        return access_token

    async def _async_request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
        retry_on_auth_error: bool = False,
    ) -> dict[str, Any]:
        """Perform an HTTP request and return a JSON body."""
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    if retry_on_auth_error:
                        _LOGGER.debug("Access token rejected, forcing a token refresh")
                        self._access_token = None
                        self._token_expires_at = None
                        refreshed_token = await self._async_get_access_token(force_refresh=True)
                        retry_headers = dict(headers)
                        retry_headers["Authorization"] = f"Bearer {refreshed_token}"
                        return await self._async_request_json(
                            method,
                            url,
                            headers=retry_headers,
                            params=params,
                            retry_on_auth_error=False,
                        )
                    if response.status == 403:
                        raise EdfTempoAccessError("Tempo API access denied")
                    raise EdfTempoAuthError("Authentication failed")

                if response.status >= 400:
                    raise EdfTempoApiError(
                        f"API request failed with status {response.status}"
                    )

                try:
                    payload = await response.json(content_type=None)
                except (ValueError, UnicodeDecodeError) as err:
                    raise EdfTempoApiError("API response contained invalid JSON") from err

                if not isinstance(payload, dict):
                    raise EdfTempoApiError("API response was not a JSON object")

                return payload
        except asyncio.TimeoutError as err:
            _LOGGER.warning("EDF Tempo Rev TBE API request timed out for %s %s", method, url)
            raise EdfTempoApiError("API request timed out") from err
        except aiohttp.ClientError as err:
            _LOGGER.warning("EDF Tempo Rev TBE API request failed for %s %s: %s", method, url, err)
            raise EdfTempoApiError(f"API request failed: {err}") from err

    def _parse_day_window_response(
        self,
        payload: dict[str, Any],
        today_date: str,
        tomorrow_date: str,
    ) -> TempoDayWindowData:
        """Parse and normalize the today/tomorrow API response."""
        parsed_by_date = self._parse_values_by_date(payload)

        today = parsed_by_date.get(today_date) or TempoDayData(
            date=today_date,
            color_code=None,
            display_color=None,
            fallback=False,
            updated_date=None,
        )
        tomorrow = parsed_by_date.get(tomorrow_date) or TempoDayData(
            date=tomorrow_date,
            color_code=None,
            display_color=None,
            fallback=False,
            updated_date=None,
        )
        return TempoDayWindowData(
            today=today,
            tomorrow=tomorrow,
        )

    def _parse_values_by_date(self, payload: dict[str, Any]) -> dict[str, TempoDayData]:
        """Return parsed day values keyed by ISO date."""
        raw_calendars = payload.get("tempo_like_calendars")
        if raw_calendars is None:
            raise EdfTempoApiError("Response did not contain tempo_like_calendars")

        calendar_items: list[dict[str, Any]]
        if isinstance(raw_calendars, list):
            calendar_items = [item for item in raw_calendars if isinstance(item, dict)]
        elif isinstance(raw_calendars, dict):
            calendar_items = [raw_calendars]
        else:
            raise EdfTempoApiError("tempo_like_calendars has an unexpected type")

        values: list[dict[str, Any]] = []
        for calendar in calendar_items:
            raw_values = calendar.get("values", [])
            if isinstance(raw_values, list):
                values.extend(item for item in raw_values if isinstance(item, dict))

        parsed_by_date: dict[str, TempoDayData] = {}
        for item in values:
            day_data = self._parse_day_value(item)
            parsed_by_date[day_data.date] = day_data

        return parsed_by_date

    def _parse_day_value(self, item: dict[str, Any]) -> TempoDayData:
        """Parse an individual day value returned by the API."""
        start_date = item.get("start_date")
        if not isinstance(start_date, str):
            raise EdfTempoApiError("Calendar value missing start_date")

        try:
            parsed_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError as err:
            raise EdfTempoApiError(f"Invalid start_date in response: {start_date}") from err

        color_code_raw = item.get("value")
        color_code = color_code_raw.upper() if isinstance(color_code_raw, str) else None
        display_color = COLOR_LABELS.get(color_code) if color_code is not None else None

        updated_date = item.get("updated_date")
        if updated_date is not None and not isinstance(updated_date, str):
            updated_date = str(updated_date)

        fallback_raw = item.get("fallback", False)
        if isinstance(fallback_raw, bool):
            fallback = fallback_raw
        elif isinstance(fallback_raw, str):
            fallback = fallback_raw.strip().lower() == "true"
        else:
            fallback = False

        return TempoDayData(
            date=parsed_start.date().isoformat(),
            color_code=color_code,
            display_color=display_color,
            fallback=fallback,
            updated_date=updated_date,
        )

    @staticmethod
    def _format_api_datetime(value: datetime) -> str:
        """Format a timezone-aware datetime for the EDF Tempo Rev TBE API."""
        return value.isoformat(timespec="seconds")

    @staticmethod
    def _get_current_season_bounds(now: datetime) -> tuple[date, date]:
        """Return the active Tempo season bounds for the supplied datetime."""
        if now.month >= 9:
            start_year = now.year
        else:
            start_year = now.year - 1

        season_start = date(start_year, 9, 1)
        season_end = date(start_year + 1, 8, 31)
        return season_start, season_end
