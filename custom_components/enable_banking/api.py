"""Asynchronous client for the Enable Banking API."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
import jwt

from .const import API_BASE_URL


class EnableBankingError(Exception):
    """Base error raised by the Enable Banking client."""


class EnableBankingAuthError(EnableBankingError):
    """Raised when application or bank authorization is invalid."""


class EnableBankingConnectionError(EnableBankingError):
    """Raised when the API cannot be reached."""


class EnableBankingApi:
    """Small API client using Home Assistant's shared HTTP session."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        application_id: str,
        private_key: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._application_id = application_id
        self._private_key = private_key

    def _create_token(self) -> str:
        now = datetime.now(tz=UTC)
        return jwt.encode(
            {
                "iss": "enablebanking.com",
                "aud": "api.enablebanking.com",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=10)).timestamp()),
            },
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._application_id},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            token = await asyncio.to_thread(self._create_token)
        except (ValueError, TypeError, jwt.PyJWTError) as err:
            raise EnableBankingAuthError("Invalid application private key") from err

        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                params=params,
                json=json,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status in {401, 403}:
                    raise EnableBankingAuthError(
                        f"Enable Banking rejected authorization ({response.status})"
                    )
                if response.status >= 400:
                    raise EnableBankingError(
                        f"Enable Banking request failed ({response.status})"
                    )
                payload = await response.json()
                if not isinstance(payload, dict):
                    raise EnableBankingError("Enable Banking returned invalid data")
                return payload
        except TimeoutError as err:
            raise EnableBankingConnectionError(
                "Enable Banking request timed out"
            ) from err
        except aiohttp.ClientError as err:
            raise EnableBankingConnectionError(
                "Unable to connect to Enable Banking"
            ) from err

    async def async_validate_application(self) -> None:
        """Validate application credentials."""
        await self._request("GET", "/application")

    async def async_get_aspsps(self, country: str) -> list[dict[str, Any]]:
        """Return banks available in a country."""
        payload = await self._request(
            "GET", "/aspsps", params={"country": country.upper()}
        )
        aspsps = payload.get("aspsps")
        if not isinstance(aspsps, list):
            raise EnableBankingError("Enable Banking returned an invalid bank list")
        return [item for item in aspsps if isinstance(item, dict)]

    async def async_start_authorization(
        self,
        *,
        country: str,
        aspsp_name: str,
        psu_type: str,
        valid_until: datetime,
        state: str,
        redirect_url: str,
    ) -> str:
        """Start bank authorization and return its external URL."""
        payload = await self._request(
            "POST",
            "/auth",
            json={
                "access": {"valid_until": valid_until.isoformat()},
                "aspsp": {"name": aspsp_name, "country": country.upper()},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": psu_type,
            },
        )
        url = payload.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise EnableBankingError(
                "Enable Banking returned an invalid authorization URL"
            )
        return url

    async def async_create_session(self, code: str) -> dict[str, Any]:
        """Exchange an authorization code for a user session."""
        return await self._request("POST", "/sessions", json={"code": code})

    async def async_get_session(self, session_id: str) -> dict[str, Any]:
        """Return a user session."""
        return await self._request("GET", f"/sessions/{session_id}")

    async def async_get_account_details(self, account_id: str) -> dict[str, Any]:
        """Return account metadata."""
        return await self._request("GET", f"/accounts/{account_id}/details")

    async def async_get_balances(self, account_id: str) -> list[dict[str, Any]]:
        """Return balances for an account."""
        payload = await self._request("GET", f"/accounts/{account_id}/balances")
        balances = payload.get("balances")
        if not isinstance(balances, list):
            raise EnableBankingError("Enable Banking returned invalid balance data")
        return [item for item in balances if isinstance(item, dict)]
