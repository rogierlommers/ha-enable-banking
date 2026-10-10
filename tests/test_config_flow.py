"""Tests for the Enable Banking config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enable_banking.const import (
    CONF_APPLICATION_ID,
    CONF_ASPSP_NAME,
    CONF_CONSENT_DAYS,
    CONF_COUNTRY,
    CONF_PRIVATE_KEY,
    CONF_PSU_TYPE,
    CONF_REFRESH_INTERVAL,
    CONF_SESSION_ID,
    CONF_TRANSACTION_COUNT,
    CONF_TRANSACTION_LOOKBACK_DAYS,
    DATA_PENDING_FLOWS,
    DATA_REAUTH_REASONS,
    DOMAIN,
    REAUTH_REASON_APPLICATION,
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
    assert hass.data[DOMAIN][DATA_PENDING_FLOWS] == {}


async def test_bank_rejects_unsupported_customer_type(hass: HomeAssistant) -> None:
    """ASPSP customer-type metadata prevents invalid authorization requests."""
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
        patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_validate_application",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_get_aspsps",
            new=AsyncMock(
                return_value=[{"name": "Business Bank", "psu_types": ["business"]}]
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_APPLICATION_ID: "application-id",
                CONF_PRIVATE_KEY: "private-key",
                CONF_COUNTRY: "NL",
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ASPSP_NAME: "Business Bank",
                CONF_PSU_TYPE: "personal",
                CONF_CONSENT_DAYS: 90,
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bank"
    assert result["errors"] == {CONF_PSU_TYPE: "unsupported_psu_type"}


async def test_options_flow_updates_polling_and_transaction_count(
    hass: HomeAssistant,
) -> None:
    """Options are persisted with bounded values for coordinator reload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_REFRESH_INTERVAL: 60,
            CONF_TRANSACTION_COUNT: 0,
            CONF_TRANSACTION_LOOKBACK_DAYS: 7,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    untouched_defaults = result["data_schema"]({})
    assert untouched_defaults[CONF_TRANSACTION_LOOKBACK_DAYS] == 7

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REFRESH_INTERVAL: 30,
            CONF_TRANSACTION_COUNT: 5,
            CONF_TRANSACTION_LOOKBACK_DAYS: "90",
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_REFRESH_INTERVAL: 30,
        CONF_TRANSACTION_COUNT: 5,
        CONF_TRANSACTION_LOOKBACK_DAYS: 90,
    }


async def test_options_flow_defaults_to_ten_transactions(
    hass: HomeAssistant,
) -> None:
    """New entries expose ten recent transaction summaries by default."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    defaults = result["data_schema"]({})

    assert defaults[CONF_TRANSACTION_COUNT] == 10


async def test_reconfigure_starts_consent_renewal(hass: HomeAssistant) -> None:
    """Reconfigure replaces the session and reloads the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="application-id:NL:Example Bank:personal",
        data={
            CONF_APPLICATION_ID: "application-id",
            CONF_PRIVATE_KEY: "private-key",
            CONF_COUNTRY: "NL",
            CONF_ASPSP_NAME: "Example Bank",
            CONF_PSU_TYPE: "personal",
            CONF_CONSENT_DAYS: 90,
            CONF_SESSION_ID: "old-session-id",
        },
    )
    entry.add_to_hass(hass)

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
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        with patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_start_authorization",
            new=AsyncMock(return_value="https://bank.example/authorize"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )

        assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP
        state = next(iter(hass.data[DOMAIN][DATA_PENDING_FLOWS]))
        with patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_create_session",
            new=AsyncMock(return_value={"session_id": "new-session-id"}),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={"state": state, "code": "authorization-code"},
            )
        assert result["type"] is data_entry_flow.FlowResultType.EXTERNAL_STEP_DONE

        with patch.object(hass.config_entries, "async_schedule_reload") as reload_entry:
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SESSION_ID] == "new-session-id"
    reload_entry.assert_called_once_with(entry.entry_id)


async def test_session_reauth_replaces_session(hass: HomeAssistant) -> None:
    """Expired consent completes reauthentication on the original entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="application-id:NL:Example Bank:personal",
        data={
            CONF_APPLICATION_ID: "application-id",
            CONF_PRIVATE_KEY: "private-key",
            CONF_COUNTRY: "NL",
            CONF_ASPSP_NAME: "Example Bank",
            CONF_PSU_TYPE: "personal",
            CONF_CONSENT_DAYS: 90,
            CONF_SESSION_ID: "old-session-id",
        },
    )
    entry.add_to_hass(hass)

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
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=dict(entry.data),
        )
        assert result["step_id"] == "reauth_confirm"
        with patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_start_authorization",
            new=AsyncMock(return_value="https://bank.example/authorize"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )
        state = next(iter(hass.data[DOMAIN][DATA_PENDING_FLOWS]))
        with patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_create_session",
            new=AsyncMock(return_value={"session_id": "renewed-session-id"}),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={"state": state, "code": "authorization-code"},
            )
        with patch.object(hass.config_entries, "async_schedule_reload"):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_SESSION_ID] == "renewed-session-id"


async def test_application_reauth_replaces_credentials(hass: HomeAssistant) -> None:
    """Rejected application credentials can be replaced before consent renewal."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="old-app:NL:Example Bank:personal",
        data={
            CONF_APPLICATION_ID: "old-app",
            CONF_PRIVATE_KEY: "old-private-key",
            CONF_COUNTRY: "NL",
            CONF_ASPSP_NAME: "Example Bank",
            CONF_PSU_TYPE: "personal",
            CONF_CONSENT_DAYS: 90,
            CONF_SESSION_ID: "old-session-id",
        },
    )
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {}).setdefault(DATA_REAUTH_REASONS, {})[
        entry.entry_id
    ] = REAUTH_REASON_APPLICATION

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
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=dict(entry.data),
        )
        assert result["step_id"] == "reauth_credentials"
        with (
            patch(
                "custom_components.enable_banking.config_flow.EnableBankingApi."
                "async_validate_application",
                new=AsyncMock(),
            ),
            patch(
                "custom_components.enable_banking.config_flow.EnableBankingApi."
                "async_start_authorization",
                new=AsyncMock(return_value="https://bank.example/authorize"),
            ),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_APPLICATION_ID: "new-app",
                    CONF_PRIVATE_KEY: "new-private-key",
                },
            )
        state = next(iter(hass.data[DOMAIN][DATA_PENDING_FLOWS]))
        with patch(
            "custom_components.enable_banking.config_flow.EnableBankingApi."
            "async_create_session",
            new=AsyncMock(return_value={"session_id": "new-session-id"}),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={"state": state, "code": "authorization-code"},
            )
        with patch.object(hass.config_entries, "async_schedule_reload"):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_APPLICATION_ID] == "new-app"
    assert entry.data[CONF_PRIVATE_KEY] == "new-private-key"
    assert entry.data[CONF_SESSION_ID] == "new-session-id"
    assert entry.unique_id == "new-app:NL:Example Bank:personal"
