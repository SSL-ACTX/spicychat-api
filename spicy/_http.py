# spicy/_http.py

import httpx
from typing import Optional, Dict, Any, TYPE_CHECKING
import logging

from ._exceptions import APIError, AuthenticationError, RateLimitError, NotFoundError
from ._constants import BASE_HEADERS, DEFAULT_GUEST_ID

if TYPE_CHECKING:
    from ._auth import AuthManager

logger = logging.getLogger(__name__)

class HttpManager:
    def __init__(self, auth_manager: "AuthManager", guest_id: Optional[str] = None):
        self._auth_manager = auth_manager
        self._guest_id = guest_id or DEFAULT_GUEST_ID
        self._client = httpx.AsyncClient(
            headers=BASE_HEADERS,
            timeout=30.0,
            follow_redirects=True
        )
        self._client.headers["x-guest-userid"] = self._guest_id

    async def _request(
        self,
        method: str,
        url: str,
        authenticated: bool = False,
        **kwargs
    ) -> httpx.Response:
        headers = kwargs.get("headers", {})
        if authenticated:
            token = await self._auth_manager.get_token()
            if not token:
                raise AuthenticationError("Not logged in or token expired.")
            headers["authorization"] = f"Bearer {token.access_token}"

        kwargs["headers"] = headers
        logger.debug(f"Request: {method} {url} Headers: {headers} Body: {kwargs.get('json') or kwargs.get('data')}")

        response = await self._client.request(method, url, **kwargs)

        logger.debug(f"Response: {response.status_code} Body: {response.text[:200]}")

        if not response.is_success:
            self.handle_error(response)

        return response

    def handle_error(self, response: httpx.Response):
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
        except Exception:
            message = response.text

        if response.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {message}")
        elif response.status_code == 404:
            raise NotFoundError(response.status_code, message)
        elif response.status_code == 429:
            raise RateLimitError(response.status_code, message)
        else:
            raise APIError(response.status_code, message)

    async def get(self, url: str, authenticated: bool = False, **kwargs) -> httpx.Response:
        return await self._request("GET", url, authenticated=authenticated, **kwargs)

    async def post(self, url: str, authenticated: bool = False, **kwargs) -> httpx.Response:
        return await self._request("POST", url, authenticated=authenticated, **kwargs)

    async def patch(self, url: str, authenticated: bool = False, **kwargs) -> httpx.Response:
        return await self._request("PATCH", url, authenticated=authenticated, **kwargs)

    async def delete(self, url: str, authenticated: bool = False, **kwargs) -> httpx.Response:
        return await self._request("DELETE", url, authenticated=authenticated, **kwargs)

    async def close(self):
        await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client
