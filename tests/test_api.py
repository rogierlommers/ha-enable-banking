"""Tests for the Enable Banking API client."""

from unittest.mock import AsyncMock

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
