"""WebSocket API for on-demand EDF Tempo Rev TBE season data."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .api import EdfTempoApiError, EdfTempoAuthError
from .const import DATA_COORDINATOR, DOMAIN, MIN_SEASON_START_YEAR
from .coordinator import EdfTempoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def async_register(hass: HomeAssistant) -> None:
    """Register websocket commands for the integration."""
    websocket_api.async_register_command(hass, ws_get_season_calendar)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "edf_tempo_tbe/get_season_calendar",
        vol.Required("season_start_year"): int,
    }
)
@websocket_api.async_response
async def ws_get_season_calendar(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return day colors for a selected Tempo season."""
    _LOGGER.debug(
        "Received EDF Tempo Rev TBE season calendar websocket request for season_start_year=%s",
        msg["season_start_year"],
    )
    domain_data = hass.data.get(DOMAIN)
    if not domain_data:
        _LOGGER.debug("EDF Tempo Rev TBE websocket request rejected because integration is not loaded")
        connection.send_error(msg["id"], "not_loaded", "EDF Tempo Rev TBE is not loaded")
        return

    coordinator = domain_data.get(DATA_COORDINATOR)
    if coordinator is None or not isinstance(coordinator, EdfTempoDataUpdateCoordinator):
        _LOGGER.debug("EDF Tempo Rev TBE websocket request rejected because coordinator was not found")
        connection.send_error(msg["id"], "not_loaded", "EDF Tempo Rev TBE coordinator not found")
        return

    season_start_year = msg["season_start_year"]
    current_season_start_year = coordinator.current_season_start_year
    if season_start_year < MIN_SEASON_START_YEAR or season_start_year > current_season_start_year:
        _LOGGER.debug(
            "EDF Tempo Rev TBE websocket request rejected for out-of-range season_start_year=%s",
            season_start_year,
        )
        connection.send_error(msg["id"], "invalid_season", "Season out of allowed range")
        return

    try:
        season_entry = await coordinator.async_get_season_entry(season_start_year)
    except EdfTempoAuthError:
        _LOGGER.warning(
            "EDF Tempo Rev TBE websocket season fetch failed due to authentication for season_start_year=%s",
            season_start_year,
        )
        connection.send_error(msg["id"], "auth_failed", "EDF Tempo Rev TBE authentication failed")
        return
    except EdfTempoApiError as err:
        _LOGGER.warning(
            "EDF Tempo Rev TBE websocket season fetch failed for season_start_year=%s: %s",
            season_start_year,
            err,
        )
        connection.send_error(msg["id"], "fetch_failed", str(err))
        return
    except Exception:
        _LOGGER.exception(
            "Unexpected EDF Tempo Rev TBE websocket error for season_start_year=%s",
            season_start_year,
        )
        connection.send_error(msg["id"], "unknown_error", "Unexpected EDF Tempo Rev TBE error")
        return

    _LOGGER.debug(
        "Serving EDF Tempo Rev TBE season calendar websocket response for season_start_year=%s with %s known days",
        season_start_year,
        len(season_entry.day_colors),
    )
    connection.send_result(
        msg["id"],
        {
            "season_start_year": season_start_year,
            "current_season_start_year": current_season_start_year,
            "min_season_start_year": MIN_SEASON_START_YEAR,
            "season_start": season_entry.summary.season_start,
            "season_end": season_entry.summary.season_end,
            "day_colors": season_entry.day_colors,
        },
    )
