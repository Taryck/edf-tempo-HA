"""Config flow for the EDF Tempo Rev TBE integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import EdfTempoAccessError, EdfTempoApiError, EdfTempoAuthError, EdfTempoClient
from .const import (
    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LIXEE_ENTITIES,
    CONF_LIXEE_LOCK_HOURS, CONF_TEMPO_SWITCH_TIME,
    DEFAULT_LIXEE_LOCK_HOURS, DEFAULT_TEMPO_SWITCH_TIME, DEFAULT_NAME, DOMAIN,
)


CLIENT_SECRET_SELECTOR = TextSelector(
    TextSelectorConfig(
        type=TextSelectorType.PASSWORD,
        autocomplete="current-password",
    )
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): CLIENT_SECRET_SELECTOR,
    }
)


def _reconfigure_schema(client_id: str) -> vol.Schema:
    """Return a reconfiguration schema that never exposes the stored secret."""
    return vol.Schema(
        {
            vol.Required(CONF_CLIENT_ID, default=client_id): str,
            vol.Optional(CONF_CLIENT_SECRET, default=""): CLIENT_SECRET_SELECTOR,
        }
    )


class EdfTempoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EDF Tempo Rev TBE."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> EdfTempoOptionsFlow:
        """Configurer la bascule RTE et les entités Lixee de secours."""
        return EdfTempoOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors = await self._async_validate_input(user_input)
        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""
        await self.async_set_unique_id(DOMAIN)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauthentication confirmation step."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = await self._async_validate_input(user_input)
        if errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates=user_input,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the existing entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_reconfigure_schema(
                    reconfigure_entry.data[CONF_CLIENT_ID]
                ),
            )

        updated_data = dict(user_input)
        if updated_data.get(CONF_CLIENT_SECRET, "") == "":
            updated_data[CONF_CLIENT_SECRET] = reconfigure_entry.data[
                CONF_CLIENT_SECRET
            ]

        errors = await self._async_validate_input(updated_data)
        if errors:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_reconfigure_schema(user_input[CONF_CLIENT_ID]),
                errors=errors,
            )

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_mismatch()

        return self.async_update_reload_and_abort(
            reconfigure_entry,
            data_updates=updated_data,
        )

    async def _async_validate_input(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate user input against the EDF Tempo Rev TBE API."""
        client = EdfTempoClient(
            session=async_get_clientsession(self.hass),
            client_id=data[CONF_CLIENT_ID],
            client_secret=data[CONF_CLIENT_SECRET],
        )

        try:
            await client.async_validate_access()
        except EdfTempoAccessError:
            return {"base": "access_denied"}
        except EdfTempoAuthError:
            return {"base": "invalid_auth"}
        except EdfTempoApiError:
            return {"base": "cannot_connect"}
        except Exception:
            return {"base": "unknown"}

        return {}


class EdfTempoOptionsFlow(config_entries.OptionsFlow):
    """1) Heure RTE ; 2) liste LTARF/NTARF ; 3) verrouillage du secours."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Afficher les options sans modifier les identifiants RTE."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema({
            vol.Required(CONF_TEMPO_SWITCH_TIME, default=options.get(CONF_TEMPO_SWITCH_TIME, DEFAULT_TEMPO_SWITCH_TIME)): str,
            vol.Optional(CONF_LIXEE_ENTITIES, default=options.get(CONF_LIXEE_ENTITIES, [])): EntitySelector(EntitySelectorConfig(domain="sensor", multiple=True)),
            vol.Required(CONF_LIXEE_LOCK_HOURS, default=options.get(CONF_LIXEE_LOCK_HOURS, DEFAULT_LIXEE_LOCK_HOURS)): vol.All(vol.Coerce(int), vol.Range(min=1, max=48)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
