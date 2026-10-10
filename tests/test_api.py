"""Tests for the Enable Banking API client."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.enable_banking.api import (
    EnableBankingApi,
    EnableBankingApplicationAuthError,
    EnableBankingAuthError,
    EnableBankingConnectionError,
    EnableBankingError,
)


async def test_invalid_private_key_is_auth_error() -> None:
    """Invalid PEM data is classified without making a network request."""
    session = AsyncMock()
    api = EnableBankingApi(session, "app-id", "not-a-private-key")

    with pytest.raises(EnableBankingAuthError):
        await api.async_validate_application()

    session.request.assert_not_called()


async def test_transactions_are_paginated_until_limit() -> None:
    """Transaction retrieval stops once the configured number is available."""
    api = EnableBankingApi(MagicMock(), "app-id", "private-key")
    request = AsyncMock(
        side_effect=[
            {
                "transactions": [
                    {"transaction_id": "one"},
                    {"transaction_id": "two"},
                ],
                "continuation_key": "next-page",
            },
            {
                "transactions": [
                    {"transaction_id": "three"},
                    {"transaction_id": "four"},
                ]
            },
        ]
    )
    with patch.object(api, "_request", new=request):
        transactions = await api.async_get_transactions(
            "account-id", 3, date_from=date(2026, 7, 13)
        )

    assert [item["transaction_id"] for item in transactions] == [
        "one",
        "two",
        "three",
        "four",
    ]
    assert request.await_count == 2
    assert request.await_args_list[0].kwargs["params"] == {
        "date_from": "2026-07-13",
        "strategy": "longest",
    }
    assert request.await_args_list[1].kwargs["params"] == {
        "date_from": "2026-07-13",
        "strategy": "longest",
        "continuation_key": "next-page",
    }


async def test_authorization_explicitly_requests_balance_and_transaction_access() -> (
    None
):
    """Consent remains suitable when transactions are enabled after setup."""
    api = EnableBankingApi(MagicMock(), "app-id", "private-key")
    request = AsyncMock(return_value={"url": "https://bank.example/authorize"})

    with patch.object(api, "_request", new=request):
        await api.async_start_authorization(
            country="NL",
            aspsp_name="Example Bank",
            psu_type="personal",
            valid_until=datetime(2027, 1, 1, tzinfo=UTC),
            state="state",
            redirect_url="https://ha.example/api/enable_banking/callback",
        )

    access = request.await_args.kwargs["json"]["access"]
    assert access["balances"] is True
    assert access["transactions"] is True


async def test_zero_transaction_limit_makes_no_request() -> None:
    """Disabled transaction retrieval never calls the provider endpoint."""
    api = EnableBankingApi(MagicMock(), "app-id", "private-key")
    request = AsyncMock()
    with patch.object(api, "_request", new=request):
        transactions = await api.async_get_transactions(
            "account-id", 0, date_from=date(2026, 7, 13)
        )

    assert transactions == []
    request.assert_not_awaited()


async def test_transaction_pagination_stops_after_five_pages() -> None:
    """A provider continuation loop cannot create unbounded API calls."""
    api = EnableBankingApi(MagicMock(), "app-id", "private-key")
    request = AsyncMock(
        side_effect=[
            {
                "transactions": [{"transaction_id": str(page)}],
                "continuation_key": f"page-{page + 1}",
            }
            for page in range(5)
        ]
    )

    with patch.object(api, "_request", new=request):
        transactions = await api.async_get_transactions(
            "account-id", 20, date_from=date(2025, 10, 10)
        )

    assert len(transactions) == 5
    assert request.await_count == 5


async def test_raw_limit_does_not_hide_later_transaction_pages() -> None:
    """Normalization can still find valid rows behind a full malformed page."""
    api = EnableBankingApi(MagicMock(), "app-id", "private-key")
    request = AsyncMock(
        side_effect=[
            {
                "transactions": [{"invalid": index} for index in range(3)],
                "continuation_key": "valid-page",
            },
            {"transactions": [{"transaction_id": "valid"}]},
        ]
    )

    with patch.object(api, "_request", new=request):
        transactions = await api.async_get_transactions(
            "account-id", 2, date_from=date(2026, 7, 13)
        )

    assert transactions[-1] == {"transaction_id": "valid"}
    assert request.await_count == 2


def _api_with_response_status(
    status: int,
) -> tuple[EnableBankingApi, MagicMock]:
    """Create an API client whose shared session returns one HTTP status."""
    response = MagicMock(status=status)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    response.json = AsyncMock(return_value={})
    session = MagicMock()
    session.request.return_value = response
    return EnableBankingApi(session, "app-id", "private-key"), response


async def test_missing_session_is_auth_error() -> None:
    """A missing stored session asks Home Assistant to start reauthentication."""
    api, _response = _api_with_response_status(404)

    with (
        patch.object(api, "_create_token", return_value="signed-token"),
        pytest.raises(EnableBankingAuthError),
    ):
        await api.async_get_session("missing-session")


async def test_account_404_remains_generic_api_error() -> None:
    """A missing account resource does not misclassify app credentials."""
    api, _response = _api_with_response_status(404)

    with (
        patch.object(api, "_create_token", return_value="signed-token"),
        pytest.raises(EnableBankingError, match=r"failed \(404\)"),
    ):
        await api.async_get_account_details("missing-account")


async def test_http_401_is_application_credential_error() -> None:
    """Provider JWT rejection starts credential replacement, not consent renewal."""
    api, _response = _api_with_response_status(401)

    with (
        patch.object(api, "_create_token", return_value="signed-token"),
        pytest.raises(EnableBankingApplicationAuthError),
    ):
        await api.async_get_session("session-id")


async def test_malformed_json_is_generic_api_error() -> None:
    """Invalid provider JSON stays inside the integration error boundary."""
    api, response = _api_with_response_status(200)
    response.json.side_effect = ValueError("Malformed JSON")

    with (
        patch.object(api, "_create_token", return_value="signed-token"),
        pytest.raises(EnableBankingError, match="invalid data"),
    ):
        await api.async_validate_application()


async def test_non_object_json_is_generic_api_error() -> None:
    """Provider responses must remain JSON objects."""
    api, response = _api_with_response_status(200)
    response.json.return_value = []

    with (
        patch.object(api, "_create_token", return_value="signed-token"),
        pytest.raises(EnableBankingError, match="invalid data"),
    ):
        await api.async_validate_application()


async def test_server_error_is_generic_api_error() -> None:
    """Provider outages do not incorrectly trigger authentication repair."""
    api, _response = _api_with_response_status(500)

    with (
        patch.object(api, "_create_token", return_value="signed-token"),
        pytest.raises(EnableBankingError, match=r"failed \(500\)"),
    ):
        await api.async_validate_application()


async def test_timeout_is_connection_error() -> None:
    """HTTP timeouts use the coordinator's recoverable connection path."""
    session = MagicMock()
    session.request.side_effect = TimeoutError
    api = EnableBankingApi(session, "app-id", "private-key")

    with (
        patch.object(api, "_create_token", return_value="signed-token"),
        pytest.raises(EnableBankingConnectionError, match="timed out"),
    ):
        await api.async_validate_application()
