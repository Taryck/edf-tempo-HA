"""Automatic frontend resource registration for EDF Tempo Rev TBE cards."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import MODE_STORAGE
from homeassistant.core import HomeAssistant

from .const import (
    CARD_FILENAME,
    CARD_URL_PATH,
    DOMAIN,
    INTEGRATION_VERSION,
    LEGACY_CARD_URL_PATH,
)

_LOGGER = logging.getLogger(__name__)

LOVELACE_DATA = "lovelace"
FRONTEND_DATA = f"{DOMAIN}_frontend"
FRONTEND_STATIC_REGISTERED = "_frontend_static_registered"
CARD_RESOURCE_URL = f"{CARD_URL_PATH}?v={INTEGRATION_VERSION}"


def _get_storage_resources(hass: HomeAssistant):
    """Return Lovelace storage resources across supported HA versions."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        return None

    if isinstance(lovelace_data, dict):
        if lovelace_data.get("mode") != MODE_STORAGE:
            return None
        return lovelace_data.get("resources")

    if lovelace_data.resource_mode != MODE_STORAGE:
        return None
    return lovelace_data.resources


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Expose the card bundle and register it as a Lovelace resource."""
    frontend_data = hass.data.setdefault(FRONTEND_DATA, {})
    if not frontend_data.get(FRONTEND_STATIC_REGISTERED):
        card_path = Path(__file__).parent / CARD_FILENAME
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_PATH, str(card_path), False)]
        )
        frontend_data[FRONTEND_STATIC_REGISTERED] = True

    resources = _get_storage_resources(hass)
    if resources is None:
        _LOGGER.warning(
            "Lovelace resources are unavailable; EDF Tempo Rev TBE card registration will be retried"
        )
        return
    await resources.async_get_info()

    for resource in resources.async_items():
        resource_url = resource.get("url", "")
        resource_path = resource_url.split("?", 1)[0]
        if resource_path not in (CARD_URL_PATH, LEGACY_CARD_URL_PATH):
            continue

        if resource_url != CARD_RESOURCE_URL or resource.get("type") != "module":
            await resources.async_update_item(
                resource["id"],
                {"res_type": "module", "url": CARD_RESOURCE_URL},
            )
        return

    await resources.async_create_item(
        {"res_type": "module", "url": CARD_RESOURCE_URL}
    )


async def async_remove_frontend_resource(hass: HomeAssistant) -> None:
    """Remove EDF Tempo Rev TBE Lovelace resources after final entry removal."""
    resources = _get_storage_resources(hass)
    if resources is None:
        return

    await resources.async_get_info()
    resource_ids = [
        resource["id"]
        for resource in resources.async_items()
        if resource.get("url", "").split("?", 1)[0]
        in (CARD_URL_PATH, LEGACY_CARD_URL_PATH)
    ]
    for resource_id in resource_ids:
        await resources.async_delete_item(resource_id)

    if resource_ids:
        _LOGGER.debug(
            "Removed %s EDF Tempo Rev TBE Lovelace resources",
            len(resource_ids),
        )
