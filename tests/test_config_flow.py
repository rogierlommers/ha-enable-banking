"""Tests for the Enable Banking config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.enable_banking.const import (
    CONF_APPLICATION_ID,
    CONF_ASPSP_NAME,
    CONF_CONSENT_DAYS,
    CONF_COUNTRY,
    CONF_PRIVATE_KEY,
    CONF_PSU_TYPE,
    DATA_PENDING_FLOWS,
    DOMAIN,
)


async def _start_authorization(hass: HomeAssistant) -> tuple[str, str]:
    """Advance a flow to the external bank authorization step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    with (
        patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_validate_application",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_get_aspsps",
            new=AsyncMock(return_value=[{"name": "Example Bank"}]),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_APPLICATION_ID: "application-id",
                CONF_PRIVATE_KEY: "private-key",
                CONF_COUNTRY: "NL",
            },
        )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bank"

    with patch(
        "custom_components.enable_banking.config_flow.EnableBankingApi."
        "async_start_authorization",
        new=AsyncMock(return_value="https://bank.example/authorize"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ASPSP_NAME: "Example Bank",
                CONF_PSU_TYPE: "personal",
                CONF_CONSENT_DAYS: 90,
            },
        )
    assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
    state = next(iter(hass.data[DOMAIN][DATA_PENDING_FLOWS]))
    return result["flow_id"], state


async def test_complete_config_flow(hass: HomeAssistant) -> None:
    """A valid callback creates a config entry with the supplied credentials."""
    with (
        patch(
            "custom_components.enable_banking.config_flow.get_url",
            return_value="https://ha.example",
        ),
        patch(
            "custom_components.enable_banking.config_flow.aiohttp_client."
            "async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        flow_id, state = await _start_authorization(hass)

        with patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_create_session",
            new=AsyncMock(return_value={"session_id": "session-id"}),
        ):
            result = await hass.config_entries.flow.async_configure(
                flow_id,
                user_input={"state": state, "code": "authorization-code"},
            )
        assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP_DONE

        with patch(
            "custom_components.enable_banking.async_setup_entry",
            new=AsyncMock(return_value=True),
        ):
            result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Example Bank (NL)"
    assert result["data"][CONF_PRIVATE_KEY] == "private-key"


async def test_rejects_callback_with_wrong_state(hass: HomeAssistant) -> None:
    """A callback cannot complete a different or forged flow."""
    with (
        patch(
            "custom_components.enable_banking.config_flow.get_url",
            return_value="https://ha.example",
        ),
        patch(
            "custom_components.enable_banking.config_flow.aiohttp_client."
            "async_get_clientsession",
            return_value=MagicMock(),
        ),
    ):
        flow_id, _state = await _start_authorization(hass)
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"state": "wrong-state", "code": "authorization-code"},
        )
        assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP_DONE
        result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "invalid_state"
