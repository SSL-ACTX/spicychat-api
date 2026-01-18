# spicy/_auth.py
# Author: SSL-ACTX (Seuriin)
# Code Reviewer / QA: Gemini 2.5 Flash

import json
import os
import secrets
import hashlib
import base64
import asyncio
import datetime
from pathlib import Path
from typing import Optional, Callable, Awaitable, Tuple
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from ._models import TokenData
from ._exceptions import AuthenticationError
from ._constants import (
    CLIENT_ID, REDIRECT_URI, AUTH_ENDPOINT, TOKEN_ENDPOINT, OTP_SUBMIT_ENDPOINT
)

CONFIG_DIR = Path.home() / ".config" / "spicychat-api"
TOKEN_FILE = CONFIG_DIR / "tokens.json"

class AuthManager:
    def __init__(self):
        self._auth_client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        self._token_data: Optional[TokenData] = None
        self._lock = asyncio.Lock()

    async def close(self):
        await self._auth_client.aclose()

    def _generate_pkce(self) -> Tuple[str, str]:
        code_verifier = secrets.token_urlsafe(64)
        hashed = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(hashed).decode('utf-8').replace('=', '')
        return code_verifier, code_challenge

    async def _request_otp(self, email: str, code_challenge: str) -> Tuple[str, str]:
        state = secrets.token_hex(30)
        params = {
            "connection_id": "conn_018f086c2c8b8d0865256c986b6ad99f",
            "login_hint": email,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "response_type": "code",
            "scope": "openid profile email offline",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "prompt": "create",
            "org_code": "org_7d8efc10ab9"
        }

        response = await self._auth_client.get(AUTH_ENDPOINT, params=params)

        if response.status_code != 200:
            raise AuthenticationError(f"Failed to get OTP page: {response.status_code} {response.text}")

        print("OTP page received. Parsing for credentials...")
        soup = BeautifulSoup(response.text, 'html.parser')

        csrf_token_tag = soup.find('meta', {'name': 'csrf-token'})
        psid_tag = soup.find('input', {'name': 'p_psid'})

        if not csrf_token_tag or not psid_tag:
            raise AuthenticationError("Could not find CSRF token or PSID on the page.")

        csrf = csrf_token_tag['content']
        psid = psid_tag['value']

        if 'kbtc' not in self._auth_client.cookies:
            raise AuthenticationError("Failed to get kbtc cookie.")

        print("Credentials parsed. Please check your email for the OTP.")
        return csrf, psid

    async def _submit_otp(self, otp: str, csrf: str, psid: str) -> str:
        files_payload = {
            'x_csrf_token': (None, csrf),
            'p_psid': (None, psid),
            'p_confirmation_code': (None, otp)
        }

        headers = {
            "accept": "roast/mixed",
            "x-csrf-token": csrf,
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://gamma.kinde.com",
            "referer": f"https://gamma.kinde.com/auth/cx/_:nav&m:verify_email&psid:{psid}"
        }

        # POST the OTP.
        # Note: Kinde often returns 200 OK even if the OTP is wrong, passing back HTML instead of JSON logic.
        post_response = await self._auth_client.post(
            OTP_SUBMIT_ENDPOINT,
            files=files_payload,
            headers=headers
        )

        if post_response.status_code != 200:
            raise AuthenticationError(f"OTP submission failed with unexpected status: {post_response.status_code} - {post_response.text}")

        try:
            response_data = post_response.json()
            nested_json_str = response_data.get('json', '')
            html_content = response_data.get('html', '')

            # Case: OTP Failed (Server returns 200, empty 'json', and error message in 'html')
            if not nested_json_str and html_content:
                if "Please enter a valid confirmation code" in html_content:
                    raise AuthenticationError("OTP submission failed. The code was likely incorrect or expired. Please try again.")
                else:
                    # Try to parse the HTML to see if there is another error message
                    soup = BeautifulSoup(html_content, 'html.parser')
                    error_msg = soup.find(class_='kinde-control-associated-text-variant-invalid-message')
                    if error_msg:
                        raise AuthenticationError(f"OTP submission failed: {error_msg.get_text(strip=True)}")

                    raise AuthenticationError("OTP submission returned an HTML response indicating failure, but no specific error message was found.")

            # Case: OTP Success
            redirect_info = json.loads(nested_json_str)

            if redirect_info.get('action') != 'redirect' or 'location' not in redirect_info:
                raise AuthenticationError(f"OTP submission response was not a valid redirect object: {response_data}")

            redirect_location = redirect_info['location']
        except (json.JSONDecodeError, KeyError) as e:
            # If the specific error logic above didn't catch it, fail here
            raise AuthenticationError(f"Failed to parse redirect information from OTP response: {e} - Response was: {post_response.text}")

        print("OTP accepted. Following server-instructed redirect...")

        # The _auth_client, with follow_redirects=True, will handle any subsequent 302s.
        final_response = await self._auth_client.get(redirect_location)

        # The final URL after all redirects will contain the authorization code.
        final_url = str(final_response.url)
        parsed_url = urlparse(final_url)
        query_params = parse_qs(parsed_url.query)

        if 'error' in query_params:
            error = query_params.get('error', ['Unknown error'])[0]
            raise AuthenticationError(
                f"Authentication failed after redirect. Server returned error: '{error}'."
            )

        code = query_params.get("code", [None])[0]
        if not code:
            raise AuthenticationError(f"Could not extract authorization code from final redirect URL. Full URL: {final_url}")

        return code

    async def _exchange_code_for_token(self, code: str, verifier: str) -> TokenData:
        data = {
            "client_id": CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI
        }
        headers = {"kinde-sdk": "React/4.0.5", "origin": "https://spicychat.ai"}

        response = await self._auth_client.post(TOKEN_ENDPOINT, data=data, headers=headers)

        if not response.is_success:
             raise AuthenticationError(f"Token exchange failed: {response.status_code} - {response.text}")

        return TokenData(**response.json())

    def _save_token(self, token_data: TokenData):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(token_data.model_dump_json())

    def _load_token(self) -> Optional[TokenData]:
        if not TOKEN_FILE.exists():
            return None
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                return TokenData(**data)
        except (json.JSONDecodeError, TypeError, FileNotFoundError):
            if TOKEN_FILE.exists():
                os.remove(TOKEN_FILE)
            return None

    async def get_token(self) -> Optional[TokenData]:
        async with self._lock:
            if not self._token_data:
                self._token_data = self._load_token()

            if not self._token_data:
                return None

            if (datetime.datetime.now().timestamp() - self._token_data.created_at) > (self._token_data.expires_in - 300):
                self._token_data = None
                if TOKEN_FILE.exists():
                    os.remove(TOKEN_FILE)
                return None

            return self._token_data

    async def login(
        self,
        email: str,
        otp_callback: Callable[[], Awaitable[str]]
    ):
        async with self._lock:
            if self._token_data or self._load_token():
                return

            print("Starting new login process...")
            verifier, challenge = self._generate_pkce()

            print(f"Requesting OTP page for {email}...")
            csrf, psid = await self._request_otp(email, challenge)

            otp = await otp_callback()

            print("Submitting OTP...")
            auth_code = await self._submit_otp(otp, csrf, psid)

            print("Exchanging authorization code for token...")
            self._token_data = await self._exchange_code_for_token(auth_code, verifier)

            self._save_token(self._token_data)
            print("Login successful. Tokens saved.")
