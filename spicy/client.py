# spicy/client.py
# Author: SSL-ACTX (Seuriin)
# Code Reviewer / QA: Gemini 2.5 Flash

import asyncio
import logging
import json
import mimetypes
import hashlib
from typing import Optional, List, Callable, Awaitable, Dict, Any

from ._auth import AuthManager
from ._http import HttpManager
from ._models import *
from ._constants import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def default_otp_callback() -> str:
    otp = await asyncio.to_thread(input, "Please enter the OTP you received: ")
    return otp.strip()


class SpicyClient:
    """The main asynchronous client for interacting with the SpicyChat API."""

    def __init__(self, guest_id: Optional[str] = None):
        self.guest_id = guest_id or DEFAULT_GUEST_ID
        self._auth_manager = AuthManager()
        self._http = HttpManager(self._auth_manager, self.guest_id)

        self.user: Optional[User] = None
        self.settings: Optional[UserSettings] = None
        self.personas: Optional[List[Persona]] = None
        self.app_settings: Optional[ApplicationSettings] = None
        self.typesense_api_key: Optional[str] = None

        # Recombee has a different base URL
        self.recombee_url = "https://client-rapi-ca-east.recombee.com/spicychat-prod"


    async def login(self, email: str, otp_callback: Callable[[], Awaitable[str]] = default_otp_callback):
        token_valid = await self._auth_manager.get_token()
        if token_valid:
            logger.info("Found valid session token. Logging in...")
        else:
            await self._auth_manager.login(email, otp_callback)

        logger.info("Login successful. Fetching user data...")
        await self._post_login_setup()
        logger.info(f"Welcome, {self.user.name if self.user else 'User'}!")

    async def _post_login_setup(self):
        tasks = [
            self.get_user_profile(),
            self.get_user_settings(),
            self.get_personas(),
            self.get_application_settings(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error during post-login setup: {result}")

    async def get_user_profile(self) -> User:
        """Fetches the current user's profile information."""
        response = await self._http.get(f"{BASE_URL}/v2/users", authenticated=True)
        self.user = User(**response.json()["user"])
        return self.user

    async def get_user_settings(self) -> UserSettings:
        """Fetches the current user's settings."""
        response = await self._http.get(f"{BASE_URL}/users/settings", authenticated=True)
        self.settings = UserSettings(**response.json())
        return self.settings

    async def get_personas(self) -> List[Persona]:
        """Fetches the list of user personas."""
        response = await self._http.get(f"{BASE_URL}/personas", authenticated=True)
        self.personas = [Persona(**p) for p in response.json()]
        return self.personas

    async def get_application_settings(self) -> ApplicationSettings:
        """Fetches global application settings, including available models."""
        response = await self._http.get(f"{BASE_URL}/v2/applications/spicychat", authenticated=True)
        data = response.json()
        self.app_settings = ApplicationSettings(**data)
        if "typesenseConfig" in data and "apiKeyPublicCharacter" in data["typesenseConfig"]:
            self.typesense_api_key = data["typesenseConfig"]["apiKeyPublicCharacter"]
        return self.app_settings

    async def search(self, query: str, per_page: int = 24) -> SearchResult:
        """Searches for characters on SpicyChat."""
        if not self.typesense_api_key:
            await self.get_application_settings()
            if not self.typesense_api_key:
                 raise APIError(500, "Could not retrieve Typesense API key.")
        search_payload = {"searches": [{"query_by": "name,title,tags,creator_username,character_id","exclude_fields":"application_ids,greeting,moderation_flags,moderation_keywords,moderation_status,reportsType","sort_by": "num_messages_24h:desc","highlight_full_fields":"name,title,tags,creator_username,character_id","collection": "public_characters_alias","q": query,"per_page": per_page}]}
        headers = {"x-typesense-api-key": self.typesense_api_key, "content-type": "text/plain"}
        response = await self._http.post(f"{TYPESENSE_URL}/multi_search", data=json.dumps(search_payload), headers=headers)
        return SearchResult(**response.json()["results"][0])

    async def get_home_feed(self, count: int = 12) -> SearchResult:
        """Fetches the home feed characters (approximated via search)."""
        return await self.search(query="*", per_page=count)

    async def get_conversations(self, limit: int = 25) -> List[Conversation]:
        """Retrieves a list of recent conversations."""
        params = {"limit": limit}
        response = await self._http.get(f"{BASE_URL}/v2/conversations", authenticated=True, params=params)
        return [Conversation(**c) for c in response.json()]

    async def get_conversation_history(self, character_id: str, limit: int = 50) -> List[Message]:
        """Retrieves message history for a specific character."""
        params = {"limit": limit}
        response = await self._http.get(f"{BASE_URL}/characters/{character_id}/messages", authenticated=True, params=params)
        messages_data = response.json().get("messages", [])
        return [Message(**m) for m in messages_data]

    async def send_message(self, character_id: str, message: str, model: ChatModel = ChatModel.SPICEDQ3_A3B, persona_id: Optional[str] = None, conversation_id: Optional[str] = None) -> Message:
        """Sends a message to a character."""
        if not self.user: raise AuthenticationError("User not logged in. Please call login() first.")
        payload = {"message": message,"character_id": character_id,"inference_model": model.value,"user_persona_id": persona_id or (self.user.default_persona_id if self.user else None),"inference_settings": {"max_new_tokens": 180, "temperature": 0.7, "top_k": 90, "top_p": 0.7}}
        if conversation_id: payload["conversation_id"] = conversation_id
        response = await self._http.post(f"{CHAT_API_URL}/chat", authenticated=True, json=payload)
        return Message(**response.json()["message"])

    async def regenerate_response(self, conversation_id: str, character_id: str, last_user_message_id: str, model: ChatModel = ChatModel.SPICEDQ3_A3B) -> Message:
        """Regenerates the last bot response in a conversation."""
        payload = {"character_id": character_id,"inference_model": model.value,"inference_settings": {"max_new_tokens": 180, "temperature": 0.7, "top_k": 90, "top_p": 0.7},"continue_chat": True,"conversation_id": conversation_id,"prev_id": last_user_message_id}
        response = await self._http.post(f"{CHAT_API_URL}/chat", authenticated=True, json=payload)
        return Message(**response.json()["message"])

    async def generate_image(self, prompt: str, model: ImageModel = ImageModel.ANIME_V2, negative_prompt: str = "") -> GeneratedImage:
        """Generates an image based on a prompt."""
        payload = {"prompt": prompt, "negative_prompt": negative_prompt, "model_style": model.value, "seed": None, "image": None}
        response = await self._http.post(f"{BASE_URL}/generate-image", authenticated=True, json=payload)
        return GeneratedImage(**response.json())

    async def edit_message(self, message_id: str, new_content: str) -> Message:
        """
        Edits the content of a previously sent message.
        :param message_id: The ID of the message to edit.
        :param new_content: The new text content for the message.
        :return: The updated message object.
        """
        payload = {"content": new_content}
        response = await self._http.patch(f"{BASE_URL}/messages/{message_id}", authenticated=True, json=payload)
        return Message(**response.json())

    async def delete_messages(self, conversation_id: str, message_ids: List[str]) -> List[DeletedMessage]:
        """
        Deletes one or more messages from a conversation.
        :param conversation_id: The ID of the conversation.
        :param message_ids: A list of message IDs to delete.
        :return: A list of the deleted message objects with deletion metadata.
        """
        payload = {"ids": message_ids}
        url = f"{BASE_URL}/conversations/{conversation_id}/messages"
        response = await self._http.delete(url, authenticated=True, json=payload)
        return [DeletedMessage(**m) for m in response.json()]

    async def get_suggested_reply(self, conversation_id: str, character_id: str, bot_message_id: str, model: ChatModel = ChatModel.SPICEDQ3_A3B) -> Message:
        """
        Generates a suggested reply for the user (Autopilot feature).
        :param conversation_id: The ID of the conversation.
        :param character_id: The ID of the character.
        :param bot_message_id: The ID of the bot's message to reply to.
        :param model: The AI model to use.
        :return: A message object with the suggested user reply.
        """
        if not self.user: raise AuthenticationError("User not logged in.")
        payload = {
            "character_id": character_id,
            "conversation_id": conversation_id,
            "inference_model": model.value,
            "inference_settings": {"max_new_tokens": 180, "temperature": 0.7, "top_k": 90, "top_p": 0.7},
            "autopilot": True,
            "user_persona_id": self.user.default_persona_id,
            "alt_message_id": bot_message_id
        }
        response = await self._http.post(f"{CHAT_API_URL}/chat", authenticated=True, json=payload)
        return Message(**response.json()["message"])

    async def switch_persona_for_chat(self, conversation_id: str, persona_id: str) -> bool:
        """
        Switches the active user persona for a specific conversation.
        :param conversation_id: The ID of the conversation to modify.
        :param persona_id: The ID of the persona to switch to.
        """
        payload = {"user_persona_id": persona_id}
        url = f"{BASE_URL}/conversations/{conversation_id}/user_persona"
        response = await self._http.patch(url, authenticated=True, json=payload)
        return response.status_code == 200

    async def update_profile(self, name: Optional[str] = None, username: Optional[str] = None, highlights: Optional[str] = None) -> User:
        """
        Updates the user's profile.
        :param name: New display name.
        :param username: New unique username.
        :param highlights: New profile description/highlights.
        :return: The updated User object.
        """
        if not self.user: raise AuthenticationError("Cannot update profile, not logged in.")

        payload = {}
        if name is not None: payload["name"] = name
        if username is not None: payload["username"] = username
        if highlights is not None: payload["highlights"] = highlights

        if not payload:
            logger.warning("Update profile called with no changes.")
            return self.user

        await self._http.patch(f"{BASE_URL}/users", authenticated=True, json=payload)
        return await self.get_user_profile() # Re-fetch to confirm changes

    async def _get_upload_url(self, image_bytes: bytes, mime_type: str) -> Dict[str, str]:
        """Internal: Gets a signed URL to upload an avatar."""
        image_hash = hashlib.md5(image_bytes).hexdigest()
        payload = {"image_type": mime_type, "hash": image_hash}
        response = await self._http.post(f"{BASE_URL}/save-image", authenticated=True, json=payload)
        return response.json()

    async def _upload_to_s3(self, upload_url: str, image_bytes: bytes, mime_type: str):
        """Internal: Uploads image data to the provided S3 URL."""
        headers = {'Content-Type': mime_type}
        async with httpx.AsyncClient() as s3_client:
            response = await s3_client.put(upload_url, content=image_bytes, headers=headers)
            response.raise_for_status()

    async def create_persona(self, name: str, highlights: str, avatar_path: str, is_default: bool = False) -> Persona:
        """
        Creates a new user persona with an avatar.
        :param name: Name of the persona.
        :param highlights: Description of the persona.
        :param avatar_path: Local file path to the avatar image (PNG or JPG).
        :param is_default: Whether to set this as the default persona.
        :return: The newly created Persona object.
        """
        try:
            with open(avatar_path, "rb") as f:
                image_bytes = f.read()
        except FileNotFoundError:
            raise ValueError(f"Avatar file not found at: {avatar_path}")

        mime_type, _ = mimetypes.guess_type(avatar_path)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError("Could not determine image type for avatar. Use PNG or JPG.")

        upload_data = await self._get_upload_url(image_bytes, mime_type)
        await self._upload_to_s3(upload_data['signed_url'], image_bytes, mime_type)

        persona_payload = {
            "name": name,
            "highlights": highlights,
            "avatar_url": upload_data['key'],
            "is_default": is_default
        }

        response = await self._http.post(f"{BASE_URL}/personas", authenticated=True, json=persona_payload)
        new_persona = Persona(**response.json())

        # Refresh local persona list
        await self.get_personas()

        return new_persona

    async def delete_persona(self, persona_id: str) -> bool:
        """
        Deletes a user persona.
        :param persona_id: The ID of the persona to delete.
        """
        response = await self._http.delete(f"{BASE_URL}/personas/{persona_id}", authenticated=True)
        # Refresh local persona list
        if response.is_success:
            await self.get_personas()
        return response.is_success

    async def rate_bot(self, character_id: str, action: RatingAction) -> bool:
        """
        Rates a character (like, love, dislike).
        :param character_id: The ID of the character to rate.
        :param action: The rating action (RatingAction.LIKE, etc.).
        """
        if not self.user: raise AuthenticationError("User not logged in.")
        payload = {
            "userId": self.user.id,
            "itemId": character_id,
            "rating": action.value,
            "cascadeCreate": True
        }
        url = f"{self.recombee_url}/ratings/"
        response = await self._http.post(url, json=payload) # This endpoint might not need auth bearer
        return response.text.strip() == '"ok"'

    async def favorite_bot(self, character_id: str) -> bool:
        """
        Adds a character to your favorites.
        :param character_id: The ID of the character to favorite.
        """
        if not self.user: raise AuthenticationError("User not logged in.")
        # Main API call
        settings_payload = {"likedBot": character_id}
        await self._http.patch(f"{BASE_URL}/users/settings", authenticated=True, json=settings_payload)

        # Recombee API call for bookmarks
        recombee_payload = {"userId": self.user.id, "itemId": character_id, "cascadeCreate": True}
        await self._http.post(f"{self.recombee_url}/bookmarks/", json=recombee_payload)

        # Refresh local settings
        await self.get_user_settings()
        return True

    async def unfavorite_bot(self, character_id: str) -> bool:
        """
        Removes a character from your favorites.
        :param character_id: The ID of the character to unfavorite.
        """
        if not self.user: raise AuthenticationError("User not logged in.")

        # Get current favorites
        if not self.settings: await self.get_user_settings()
        if not self.settings: return False

        current_faves = self.settings.liked_bots
        if character_id in current_faves:
            current_faves.remove(character_id)
            # Patch the entire list back
            payload = {"liked_bots": current_faves}
            await self._http.patch(f"{BASE_URL}/users/settings", authenticated=True, json=payload)

        # Also delete from recombee
        url = f"{self.recombee_url}/bookmarks/?userId={self.user.id}&itemId={character_id}"
        await self._http.delete(url)

        await self.get_user_settings()
        return True

    async def close(self):
        """Closes all underlying HTTP client sessions."""
        await self._http.close()
        await self._auth_manager.close()
