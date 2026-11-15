"""Asynchronous client for the Enable Banking API."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from typing import Any

import aiohttp
import jwt

from .const import API_BASE_URL, MAX_TRANSACTION_PAGES

_APPLICATION_AUTH_ERROR_STATUSES = frozenset({401, 403})
_SESSION_AUTH_ERROR_STATUSES = frozenset({404})
_MAX_PROVIDER_ERROR_LENGTH = 500


class EnableBankingError(Exception):
    """Base error raised by the Enable Banking client."""


class EnableBankingAuthError(EnableBankingError):
    """Raised when application or bank authorization is invalid."""


class EnableBankingApplicationAuthError(EnableBankingAuthError):
    """Raised when Enable Banking application credentials are invalid."""


class EnableBankingSessionAuthError(EnableBankingAuthError):
    """Raised when a stored bank session is missing or invalid."""


class EnableBankingConnectionError(EnableBankingError):
    """Raised when the API cannot be reached."""


def _provider_error_detail(payload: Any) -> str | None:
    """Extract bounded human-readable diagnostics from an API error response."""
    if not isinstance(payload, Mapping):
        return None

    messages: list[str] = []

    def collect(value: Any, depth: int = 0) -> None:
        if len(messages) >= 3 or depth > 3:
            return
        if isinstance(value, str):
            normalized = " ".join(value.split())
            if normalized and normalized not in messages:
                messages.append(normalized)
            return
        if isinstance(value, Mapping):
            for key in ("message", "msg", "detail"):
                collect(value.get(key), depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                collect(item, depth + 1)

    collect(payload.get("message"))
    collect(payload.get("detail"))
    if not messages:
        collect(payload.get("error"))
    if not messages:
        return None

    detail = "; ".join(messages)
    if len(detail) <= _MAX_PROVIDER_ERROR_LENGTH:
        return detail
    return f"{detail[: _MAX_PROVIDER_ERROR_LENGTH - 1].rstrip()}…"


async def _response_error_detail(
    response: aiohttp.ClientResponse, *, include: bool
) -> str | None:
    """Read a provider diagnostic when the caller can safely display it."""
    if not include or response.status < 400:
        return None
    with suppress(aiohttp.ContentTypeError, ValueError):
        return _provider_error_detail(await response.json())
    return None


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
        session_error_statuses: frozenset[int] = frozenset(),
        include_error_detail: bool = False,
    ) -> dict[str, Any]:
        try:
            token = await asyncio.to_thread(self._create_token)
        except (ValueError, TypeError, jwt.PyJWTError) as err:
            raise EnableBankingApplicationAuthError(
                "Invalid application private key"
            ) from err

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
                error_detail = await _response_error_detail(
                    response, include=include_error_detail
                )
                if response.status in _APPLICATION_AUTH_ERROR_STATUSES:
                    message = (
                        f"Enable Banking rejected authorization ({response.status})"
                    )
                    if error_detail:
                        message = f"{message}: {error_detail}"
                    raise EnableBankingApplicationAuthError(message)
                if response.status in session_error_statuses:
                    message = (
                        f"Enable Banking session is unavailable ({response.status})"
                    )
                    if error_detail:
                        message = f"{message}: {error_detail}"
                    raise EnableBankingSessionAuthError(message)
                if response.status >= 400:
                    message = f"Enable Banking request failed ({response.status})"
                    if error_detail:
                        message = f"{message}: {error_detail}"
                    raise EnableBankingError(message)
                try:
                    payload = await response.json()
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise EnableBankingError(
                        "Enable Banking returned invalid data"
                    ) from err
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
                "access": {
                    "balances": True,
                    "transactions": True,
                    "valid_until": valid_until.isoformat(),
                },
                "aspsp": {"name": aspsp_name, "country": country.upper()},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": psu_type,
            },
            include_error_detail=True,
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
        return await self._request(
            "GET",
            f"/sessions/{session_id}",
            session_error_statuses=_SESSION_AUTH_ERROR_STATUSES,
        )

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

    async def async_get_transactions(
        self,
        account_id: str,
        limit: int,
        *,
        date_from: date,
    ) -> list[dict[str, Any]]:
        """Fetch bounded transaction pages for later normalization and truncation."""
        if limit <= 0:
            return []

        transactions: list[dict[str, Any]] = []
        continuation_key: str | None = None
        for _page in range(MAX_TRANSACTION_PAGES):
            params = {"date_from": date_from.isoformat(), "strategy": "longest"}
            if continuation_key:
                params["continuation_key"] = continuation_key
            payload = await self._request(
                "GET",
                f"/accounts/{account_id}/transactions",
                params=params,
            )
            page = payload.get("transactions")
            if not isinstance(page, list):
                raise EnableBankingError(
                    "Enable Banking returned invalid transaction data"
                )
            transactions.extend(item for item in page if isinstance(item, dict))
            continuation_key = payload.get("continuation_key")
            if not isinstance(continuation_key, str) or not continuation_key:
                break

        return transactions
