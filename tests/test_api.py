"""Tests for the Enable Banking API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.enable_banking.api import (
    EnableBankingApi,
    EnableBankingAuthError,
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
        transactions = await api.async_get_transactions("account-id", 3)

    assert [item["transaction_id"] for item in transactions] == [
        "one",
        "two",
        "three",
        "four",
    ]
    assert request.await_count == 2
    assert request.await_args_list[1].kwargs["params"] == {
        "continuation_key": "next-page"
    }
