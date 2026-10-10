"""Config flow for Enable Banking."""

from __future__ import annotations

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, selector
from homeassistant.helpers.network import NoURLAvailableError, get_url

from . import async_ensure_callback_registered
from .api import (
    EnableBankingApi,
    EnableBankingAuthError,
    EnableBankingConnectionError,
    EnableBankingError,
)
from .const import (
    CALLBACK_PATH,
    CONF_APPLICATION_ID,
    CONF_ASPSP_NAME,
    CONF_CONSENT_DAYS,
    CONF_COUNTRY,
    CONF_PRIVATE_KEY,
    CONF_PSU_TYPE,
    CONF_REFRESH_INTERVAL,
    CONF_SESSION_ID,
    CONF_TRANSACTION_COUNT,
    DATA_PENDING_FLOWS,
    DEFAULT_CONSENT_DAYS,
    DEFAULT_PSU_TYPE,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_TRANSACTION_COUNT,
    DOMAIN,
    MAX_REFRESH_INTERVAL,
    MAX_TRANSACTION_COUNT,
    MIN_REFRESH_INTERVAL,
)


class EnableBankingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Enable Banking config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._data: dict[str, Any] = {}
        self._api: EnableBankingApi | None = None
        self._banks: list[str] = []
        self._state: str | None = None
        self._session: dict[str, Any] | None = None
        self._authorization_error: str | None = None
        self._reauth_entry: ConfigEntry | None = None

    def _callback_url(self) -> str:
        base_url = get_url(
            self.hass,
            allow_internal=False,
            prefer_external=True,
            require_ssl=True,
        )
        return f"{base_url.rstrip('/')}{CALLBACK_PATH}"

    def _new_api(self) -> EnableBankingApi:
        return EnableBankingApi(
            aiohttp_client.async_get_clientsession(self.hass),
            self._data[CONF_APPLICATION_ID],
            self._data[CONF_PRIVATE_KEY],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect and validate Enable Banking application credentials."""
        async_ensure_callback_registered(self.hass)
        errors: dict[str, str] = {}
        try:
            callback_url = self._callback_url()
        except NoURLAvailableError:
            return self.async_abort(reason="external_url_missing")

        if user_input is not None:
            self._data.update(user_input)
            self._data[CONF_COUNTRY] = self._data[CONF_COUNTRY].upper()
            self._api = self._new_api()
            try:
                await self._api.async_validate_application()
                aspsps = await self._api.async_get_aspsps(self._data[CONF_COUNTRY])
            except EnableBankingAuthError:
                errors["base"] = "invalid_auth"
            except EnableBankingConnectionError:
                errors["base"] = "cannot_connect"
            except EnableBankingError:
                errors["base"] = "unknown"
            else:
                self._banks = sorted(
                    {
                        str(item["name"])
                        for item in aspsps
                        if isinstance(item.get("name"), str)
                    }
                )
                if not self._banks:
                    errors["base"] = "no_banks"
                else:
                    return await self.async_step_bank()

        schema = vol.Schema(
            {
                vol.Required(CONF_APPLICATION_ID): str,
                vol.Required(CONF_PRIVATE_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                        multiline=True,
                    )
                ),
                vol.Required(CONF_COUNTRY, default="NL"): selector.CountrySelector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"callback_url": callback_url},
        )

    async def async_step_bank(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a bank and consent settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_authorize()

        return self.async_show_form(
            step_id="bank",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ASPSP_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=self._banks,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_PSU_TYPE, default=DEFAULT_PSU_TYPE
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["personal", "business"],
                            translation_key="psu_type",
                        )
                    ),
                    vol.Required(
                        CONF_CONSENT_DAYS, default=DEFAULT_CONSENT_DAYS
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=365,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start authorization or process its callback."""
        if user_input is not None:
            state = str(user_input.get("state", ""))
            if self._state is None or not hmac.compare_digest(self._state, state):
                return self._async_external_error("invalid_state")
            if user_input.get("error"):
                return self._async_external_error("access_denied")
            code = user_input.get("code")
            if not isinstance(code, str) or not code:
                return self._async_external_error("missing_code")
            try:
                self._session = await self._new_api().async_create_session(code)
            except EnableBankingAuthError:
                return self._async_external_error("invalid_auth")
            except EnableBankingConnectionError:
                return self._async_external_error("cannot_connect")
            except EnableBankingError:
                return self._async_external_error("unknown")
            return self.async_external_step_done(next_step_id="finish")

        self._state = secrets.token_urlsafe(32)
        self.hass.data[DOMAIN][DATA_PENDING_FLOWS][self._state] = self.flow_id
        valid_until = datetime.now(tz=UTC) + timedelta(
            days=int(self._data[CONF_CONSENT_DAYS])
        )
        try:
            authorization_url = await self._new_api().async_start_authorization(
                country=self._data[CONF_COUNTRY],
                aspsp_name=self._data[CONF_ASPSP_NAME],
                psu_type=self._data[CONF_PSU_TYPE],
                valid_until=valid_until,
                state=self._state,
                redirect_url=self._callback_url(),
            )
        except (EnableBankingError, NoURLAvailableError):
            self.hass.data[DOMAIN][DATA_PENDING_FLOWS].pop(self._state, None)
            return self.async_abort(reason="cannot_connect")
        return self.async_external_step(step_id="authorize", url=authorization_url)

    def _async_external_error(self, reason: str) -> ConfigFlowResult:
        """Finish the external step before aborting with an authorization error."""
        self._authorization_error = reason
        return self.async_external_step_done(next_step_id="authorization_error")

    async def async_step_authorization_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after an external authorization error."""
        return self.async_abort(reason=self._authorization_error or "unknown")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update the config entry after authorization."""
        if self._session is None or not isinstance(
            self._session.get("session_id"), str
        ):
            return self.async_abort(reason="invalid_session")
        self._data[CONF_SESSION_ID] = self._session["session_id"]
        unique_id = ":".join(
            (
                self._data[CONF_APPLICATION_ID],
                self._data[CONF_COUNTRY],
                self._data[CONF_ASPSP_NAME],
                self._data[CONF_PSU_TYPE],
            )
        )
        await self.async_set_unique_id(unique_id)
        title = f"{self._data[CONF_ASPSP_NAME]} ({self._data[CONF_COUNTRY]})"

        if self._reauth_entry is not None:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data_updates=self._data,
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=self._data)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start bank consent renewal."""
        self._reauth_entry = self._get_reauth_entry()
        self._data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bank consent renewal."""
        if user_input is not None:
            return await self.async_step_authorize()
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return EnableBankingOptionsFlow(config_entry)


class EnableBankingOptionsFlow(config_entries.OptionsFlow):
    """Configure polling and recent transaction options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options with the current config entry."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Enable Banking options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REFRESH_INTERVAL,
                        default=self._config_entry.options.get(
                            CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL
                        ),
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=MIN_REFRESH_INTERVAL,
                                max=MAX_REFRESH_INTERVAL,
                                step=5,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    ),
                    vol.Required(
                        CONF_TRANSACTION_COUNT,
                        default=self._config_entry.options.get(
                            CONF_TRANSACTION_COUNT, DEFAULT_TRANSACTION_COUNT
                        ),
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=MAX_TRANSACTION_COUNT,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
        )
