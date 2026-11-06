"""The EDF Tempo Rev TBE integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EdfTempoClient
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, DATA_COORDINATOR, DOMAIN, PARIS_TIME_ZONE
from .coordinator import EdfTempoDataUpdateCoordinator
from .frontend import async_register_frontend, async_remove_frontend_resource
from .season_cache import EdfTempoSeasonCache
from .websocket_api import async_register as async_register_websocket

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CLEAR_CACHE_SERVICE = "clear_cache"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the EDF Tempo Rev TBE integration."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_frontend(hass)
    if not hass.data[DOMAIN].get("_websocket_registered"):
        async_register_websocket(hass)
        hass.data[DOMAIN]["_websocket_registered"] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EDF Tempo Rev TBE from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    # Retry Lovelace registration here in case its resource collection was not
    # ready during the integration's global setup.
    await async_register_frontend(hass)

    session = async_get_clientsession(hass)
    season_cache = EdfTempoSeasonCache(hass)
    await season_cache.async_load()
    client = EdfTempoClient(
        session=session,
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
    )
    coordinator = EdfTempoDataUpdateCoordinator(hass, entry, client, season_cache)
    coordinator.data = season_cache.calendar_for(datetime.now(PARIS_TIME_ZONE).date())
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # The entities can still expose dated cached colors, or unknown when
        # no reliable color exists. Their listeners schedule the next retry.
        pass

    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN][DATA_COORDINATOR] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_clear_cache(call: ServiceCall) -> None:
        """Clear the season cache for this config entry."""
        await season_cache.async_clear()

    # Recharger les options de bascule et de sources Lixee après modification.
    entry.async_on_unload(entry.add_update_listener(lambda hass, entry: hass.config_entries.async_reload(entry.entry_id)))
    hass.services.async_register(DOMAIN, CLEAR_CACHE_SERVICE, async_clear_cache)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an EDF Tempo Rev TBE config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.async_unload()
        hass.services.async_remove(DOMAIN, CLEAR_CACHE_SERVICE)
        removed = hass.data[DOMAIN].pop(entry.entry_id, None)
        if hass.data[DOMAIN].get(DATA_COORDINATOR) is removed:
            hass.data[DOMAIN].pop(DATA_COORDINATOR, None)
        if list(hass.data[DOMAIN].keys()) == ["_websocket_registered"]:
            hass.data.pop(DOMAIN)
        elif not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up resources after permanent removal of a config entry."""
    await EdfTempoSeasonCache(hass).async_clear()
    await async_remove_frontend_resource(hass)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries."""
    return True
