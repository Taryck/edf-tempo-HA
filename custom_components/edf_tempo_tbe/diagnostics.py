"""Diagnostics support for the EDF Tempo Rev TBE integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN

REDACTED = "REDACTED"
TO_REDACT = {"client_id", "client_secret", "access_token", "authorization"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return sanitized diagnostics for a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    diagnostics: dict[str, Any] = {
        "entry": _redact(entry.data),
        "coordinator_loaded": coordinator is not None,
    }

    if coordinator is None:
        return diagnostics

    diagnostics.update(
        {
            "current_season_start_year": coordinator.current_season_start_year,
            "update_interval_seconds": (
                int(coordinator.update_interval.total_seconds())
                if coordinator.update_interval is not None
                else None
            ),
            "last_update_success": coordinator.last_update_success,
            "data": _serialize_coordinator_data(coordinator.data),
            "season_cache_keys": sorted(getattr(coordinator._season_cache, "_data", {}).keys()),
            "client": _redact(
                {
                    "client_id": getattr(coordinator.client, "_client_id", None),
                    "client_secret": getattr(coordinator.client, "_client_secret", None),
                    "access_token": getattr(coordinator.client, "_access_token", None),
                    "token_expires_at": (
                        coordinator.client._token_expires_at.isoformat()
                        if getattr(coordinator.client, "_token_expires_at", None) is not None
                        else None
                    ),
                }
            ),
        }
    )
    return diagnostics


def _serialize_coordinator_data(data: Any) -> Any:
    """Serialize coordinator data into diagnostics-safe primitives."""
    if data is None:
        return None

    return {
        "today": {
            "date": data.today.date,
            "color_code": data.today.color_code,
            "display_color": data.today.display_color,
            "fallback": data.today.fallback,
            "updated_date": data.today.updated_date,
        },
        "tomorrow": {
            "date": data.tomorrow.date,
            "color_code": data.tomorrow.color_code,
            "display_color": data.tomorrow.display_color,
            "fallback": data.tomorrow.fallback,
            "updated_date": data.tomorrow.updated_date,
        },
        "season_summary": (
            {
                "season_start": data.season_summary.season_start,
                "season_end": data.season_summary.season_end,
                "total_placed": data.season_summary.total_placed,
                "blue_days": data.season_summary.blue_days,
                "white_days": data.season_summary.white_days,
                "red_days": data.season_summary.red_days,
                "blue_total": data.season_summary.blue_total,
                "white_total": data.season_summary.white_total,
                "red_total": data.season_summary.red_total,
            }
            if data.season_summary is not None
            else None
        ),
        "fetched_at": data.fetched_at,
        "summary_updated_at": data.summary_updated_at,
    }


def _redact(value: Any) -> Any:
    """Recursively redact sensitive values."""
    if isinstance(value, dict):
        return {
            key: REDACTED if key.lower() in TO_REDACT and item is not None else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
