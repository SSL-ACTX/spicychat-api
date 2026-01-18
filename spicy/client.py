# spicy/client.py
# Author: SSL-ACTX (Seuriin)
# Final Version: Adds 'reset()' and 'new_chat' capabilities.

import asyncio
import logging
import json
import mimetypes
import hashlib
from typing import Optional, List, Callable, Awaitable, Dict, Any, Union

from ._auth import AuthManager
from ._http import HttpManager
from ._models import *
from ._constants import *

# Suppress noisy technical logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def default_otp_callback() -> str:
    print("\n" + "="*40)
    print("AUTHENTICATION REQUIRED")
    print("="*40)
    otp = await asyncio.to_thread(input, ">> Please enter the OTP sent to your email: ")
    return otp.strip()

class ChatSession:
    """
    A high-level wrapper for a persistent conversation.
    """
    def __init__(self, client: "SpicyClient", character: Character, conversation_id: Optional[str] = None):
        self._client = client
        self.character = character
        self.conversation_id = conversation_id

        # We store the full message objects here
        self._history_objs: List[Message] = []

        # Internal state tracking
        self.last_user_message_id: Optional[str] = None
        self.last_bot_message_id: Optional[str] = None

        # Default settings
        self.model = ChatModel.SPICEDQ3_A3B
        self.settings = GenerationSettings()

        self.persona_id = client.user.default_persona_id if client.user else None

    async def load_history(self, limit: int = 50):
        """Fetches previous messages to restore context."""
        if not self.conversation_id:
            return

        logger.info(f"Loading history for conversation {self.conversation_id}...")
        msgs = await self._client.get_conversation_history(self.character.id, limit=limit)

        # Reverse to get chronological order (Oldest -> Newest)
        self._history_objs = msgs[::-1]

        if self._history_objs:
            self._update_ids()

        logger.info(f"Restored {len(self._history_objs)} messages.")

    def _update_ids(self):
        """Internal helper to refresh ID pointers based on current history."""
        if not self._history_objs:
            self.last_user_message_id = None
            self.last_bot_message_id = None
            return

        # Find last bot message
        for msg in reversed(self._history_objs):
            if msg.role != "user":
                self.last_bot_message_id = msg.id
                break

        # Find last user message
        for msg in reversed(self._history_objs):
            if msg.role == "user":
                self.last_user_message_id = msg.id
                break

    def history(self, limit: int = 10) -> List[str]:
        """Returns a human-readable list of the last N messages."""
        display_list = []
        msgs_to_show = self._history_objs[-limit:] if limit > 0 else self._history_objs

        for msg in msgs_to_show:
            name = "You" if msg.role == "user" else self.character.name
            display_list.append(f"{name}: {msg.content}")

        return display_list

    def reset(self):
        """
        Clears the local history and forgets the conversation ID.
        The next message sent will start a BRAND NEW conversation on the server.
        """
        self.conversation_id = None
        self._history_objs = []
        self.last_user_message_id = None
        self.last_bot_message_id = None
        logger.info("Chat session reset. Next message will start a new conversation.")

    async def send(self, message: str, **kwargs) -> Message:
        """Sends a message."""
        current_settings = self.settings.model_copy(update=kwargs)

        # 1. Send to API
        response = await self._client.send_message(
            character_id=self.character.id,
            message=message,
            model=self.model,
            persona_id=self.persona_id,
            conversation_id=self.conversation_id,
            generation_settings=current_settings
        )

        self.conversation_id = response.conversation_id

        # 2. Construct User Message for local history (Critical for Undo/Edit)
        user_msg = Message(
            id=response.prev_id,
            role="user",
            content=message,
            conversation_id=response.conversation_id
        )

        # 3. Update History
        self._history_objs.append(user_msg)
        self._history_objs.append(response)
        self._update_ids()

        return response

    async def regenerate(self, **kwargs) -> Message:
        """Regenerates the last bot response."""
        if not self.conversation_id or not self.last_user_message_id:
            raise ValueError("Cannot regenerate: No conversation history available.")

        current_settings = self.settings.model_copy(update=kwargs)
        response = await self._client.regenerate_response(
            conversation_id=self.conversation_id,
            character_id=self.character.id,
            last_user_message_id=self.last_user_message_id,
            model=self.model,
            generation_settings=current_settings
        )

        # Replace the last message
        if self._history_objs and self._history_objs[-1].role != "user":
            self._history_objs[-1] = response
            self.last_bot_message_id = response.id
        else:
            self._history_objs.append(response)
            self._update_ids()

        return response

    async def edit_last_user_message(self, new_text: str) -> Message:
        """Edits your last message."""
        if not self.last_user_message_id:
            raise ValueError("No user message found to edit.")

        updated_msg = await self._client.edit_message(self.last_user_message_id, new_text)

        for i, msg in enumerate(self._history_objs):
            if msg.id == self.last_user_message_id:
                self._history_objs[i].content = new_text
                break
        return updated_msg

    async def edit_last_bot_message(self, new_text: str) -> Message:
        """Edits the bot's last message."""
        if not self.last_bot_message_id:
            raise ValueError("No bot message found to edit.")

        updated_msg = await self._client.edit_message(self.last_bot_message_id, new_text)

        for i, msg in enumerate(self._history_objs):
            if msg.id == self.last_bot_message_id:
                self._history_objs[i].content = new_text
                break
        return updated_msg

    async def undo(self) -> bool:
        """Rewinds the chat by deleting the last interaction (User+Bot)."""
        if not self.conversation_id: return False

        ids_to_delete = []
        if self.last_bot_message_id: ids_to_delete.append(self.last_bot_message_id)
        if self.last_user_message_id: ids_to_delete.append(self.last_user_message_id)

        if not ids_to_delete: return False

        await self._client.delete_messages(self.conversation_id, ids_to_delete)

        self._history_objs = [m for m in self._history_objs if m.id not in ids_to_delete]
        self._update_ids()

        logger.info(f"Undid {len(ids_to_delete)} messages.")
        return True

    async def switch_persona(self, persona_name: str):
        if not self._client.personas: await self._client.get_personas()
        found = next((p for p in self._client.personas if p.name.lower() == persona_name.lower()), None)
        if not found: raise ValueError(f"Persona '{persona_name}' not found.")

        self.persona_id = found.id
        if self.conversation_id:
            await self._client.switch_persona_for_chat(self.conversation_id, found.id)
        logger.info(f"Switched chat persona to: {found.name}")

class SpicyClient:
    """The main high-level client."""

    def __init__(self, guest_id: Optional[str] = None):
        self.guest_id = guest_id or DEFAULT_GUEST_ID
        self._auth_manager = AuthManager()
        self._http = HttpManager(self._auth_manager, self.guest_id)

        self.user: Optional[User] = None
        self.settings: Optional[UserSettings] = None
        self.personas: Optional[List[Persona]] = None
        self.app_settings: Optional[ApplicationSettings] = None
        self.typesense_api_key: Optional[str] = None
        self.recombee_url = "https://client-rapi-ca-east.recombee.com/spicychat-prod"

    # --- High-Level Methods ---

    async def start_chat(self, character_query: str, new_chat: bool = False) -> ChatSession:
        """
        Searches for a character and starts a chat.
        :param new_chat: If True, ignores previous history and starts fresh.
        """
        if not self.user: raise AuthenticationError("Please login() first.")

        search = await self.search(character_query)
        if not search.hits: raise ValueError(f"Character '{character_query}' not found.")
        character = search.hits[0].document

        existing_conv_id = None
        if not new_chat:
            logger.info(f"Checking for existing conversations with {character.name}...")
            existing_conv_id = await self._find_existing_conversation_id(character.id)

        session = ChatSession(self, character, conversation_id=existing_conv_id)

        if existing_conv_id:
            logger.info("Resuming previous conversation...")
            await session.load_history()
        else:
            logger.info("Starting fresh conversation...")

        return session

    async def create_persona(self, name: str, description: str, avatar_path: str) -> Persona:
        if not self.user: raise AuthenticationError("Please login() first.")
        try:
            with open(avatar_path, "rb") as f:
                image_bytes = f.read()
        except FileNotFoundError:
            raise ValueError(f"Avatar file not found: {avatar_path}")

        mime_type, _ = mimetypes.guess_type(avatar_path)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError("Invalid image file.")

        upload_data = await self._get_upload_url(image_bytes, mime_type)
        await self._upload_to_s3(upload_data['signed_url'], image_bytes, mime_type)

        payload = {"name": name, "highlights": description, "avatar_url": upload_data['key'], "is_default": False}
        response = await self._http.post(f"{BASE_URL}/personas", authenticated=True, json=payload)
        new_persona = Persona(**response.json())
        await self.get_personas()
        return new_persona

    async def delete_persona(self, name: str) -> bool:
        if not self.personas: await self.get_personas()
        found = next((p for p in self.personas if p.name.lower() == name.lower()), None)
        if not found: return False

        response = await self._http.delete(f"{BASE_URL}/personas/{found.id}", authenticated=True)
        if response.is_success: await self.get_personas()
        return response.is_success

    async def rate_bot(self, character_query: str, action: RatingAction = RatingAction.LIKE):
        search = await self.search(character_query)
        if not search.hits: return False
        char_id = search.hits[0].document.id

        payload = {"userId": self.user.id, "itemId": char_id, "rating": action.value, "cascadeCreate": True}
        await self._http.post(f"{self.recombee_url}/ratings/", json=payload)
        return True

    # --- Internal Helpers ---

    async def _find_existing_conversation_id(self, character_id: str) -> Optional[str]:
        try:
            conversations = await self.get_conversations(limit=50)
            for conv in conversations:
                if conv.character_id == character_id: return conv.id
        except Exception: pass
        return None

    # --- Core API (Boilerplate) ---

    async def login(self, email: str, otp_callback: Callable[[], Awaitable[str]] = default_otp_callback):
        token_valid = await self._auth_manager.get_token()
        if token_valid: logger.info("Session restored.")
        else: await self._auth_manager.login(email, otp_callback)
        await self._post_login_setup()
        logger.info(f"Logged in as: {self.user.name if self.user else 'User'}")

    async def _post_login_setup(self):
        tasks = [self.get_user_profile(), self.get_user_settings(), self.get_personas(), self.get_application_settings()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def get_user_profile(self) -> User:
        response = await self._http.get(f"{BASE_URL}/v2/users", authenticated=True)
        self.user = User(**response.json()["user"])
        return self.user

    async def get_user_settings(self) -> UserSettings:
        response = await self._http.get(f"{BASE_URL}/users/settings", authenticated=True)
        self.settings = UserSettings(**response.json())
        return self.settings

    async def get_personas(self) -> List[Persona]:
        response = await self._http.get(f"{BASE_URL}/personas", authenticated=True)
        self.personas = [Persona(**p) for p in response.json()]
        return self.personas

    async def get_application_settings(self) -> ApplicationSettings:
        response = await self._http.get(f"{BASE_URL}/v2/applications/spicychat", authenticated=True)
        self.app_settings = ApplicationSettings(**response.json())
        if "typesenseConfig" in response.json(): self.typesense_api_key = response.json()["typesenseConfig"]["apiKeyPublicCharacter"]
        return self.app_settings

    async def search(self, query: str, per_page: int = 10) -> SearchResult:
        if not self.typesense_api_key: await self.get_application_settings()
        search_payload = {"searches": [{"query_by": "name,title,tags,creator_username,character_id","exclude_fields":"application_ids,greeting,moderation_flags,moderation_keywords,moderation_status,reportsType","sort_by": "num_messages_24h:desc","highlight_full_fields":"name,title,tags,creator_username,character_id","collection": "public_characters_alias","q": query,"per_page": per_page}]}
        headers = {"x-typesense-api-key": self.typesense_api_key, "content-type": "text/plain"}
        response = await self._http.post(f"{TYPESENSE_URL}/multi_search", data=json.dumps(search_payload), headers=headers)
        return SearchResult(**response.json()["results"][0])

    async def get_conversations(self, limit: int = 25) -> List[Conversation]:
        params = {"limit": limit}
        response = await self._http.get(f"{BASE_URL}/v2/conversations", authenticated=True, params=params)
        return [Conversation(**c) for c in response.json()]

    async def get_conversation_history(self, character_id: str, limit: int = 50) -> List[Message]:
        params = {"limit": limit}
        response = await self._http.get(f"{BASE_URL}/characters/{character_id}/messages", authenticated=True, params=params)
        return [Message(**m) for m in response.json().get("messages", [])]

    async def send_message(self, character_id: str, message: str, model: ChatModel = ChatModel.SPICEDQ3_A3B, persona_id: Optional[str] = None, conversation_id: Optional[str] = None, generation_settings: Optional[Union[GenerationSettings, Dict[str, Any]]] = None) -> Message:
        if not self.user: raise AuthenticationError("User not logged in.")
        gen_settings = generation_settings or GenerationSettings()
        if isinstance(gen_settings, dict): gen_settings = GenerationSettings(**gen_settings)
        payload = {"message": message, "character_id": character_id, "inference_model": model.value, "user_persona_id": persona_id or (self.user.default_persona_id if self.user else None), "inference_settings": gen_settings.model_dump()}
        if conversation_id: payload["conversation_id"] = conversation_id
        response = await self._http.post(f"{CHAT_API_URL}/chat", authenticated=True, json=payload)
        return Message(**response.json()["message"])

    async def regenerate_response(self, conversation_id: str, character_id: str, last_user_message_id: str, model: ChatModel = ChatModel.SPICEDQ3_A3B, generation_settings: Optional[Union[GenerationSettings, Dict[str, Any]]] = None) -> Message:
        gen_settings = generation_settings or GenerationSettings()
        if isinstance(gen_settings, dict): gen_settings = GenerationSettings(**gen_settings)
        payload = {"character_id": character_id, "inference_model": model.value, "inference_settings": gen_settings.model_dump(), "continue_chat": True, "conversation_id": conversation_id, "prev_id": last_user_message_id}
        response = await self._http.post(f"{CHAT_API_URL}/chat", authenticated=True, json=payload)
        return Message(**response.json()["message"])

    async def edit_message(self, message_id: str, new_content: str) -> Message:
        payload = {"content": new_content}
        response = await self._http.patch(f"{BASE_URL}/messages/{message_id}", authenticated=True, json=payload)
        return Message(**response.json())

    async def delete_messages(self, conversation_id: str, message_ids: List[str]) -> List[DeletedMessage]:
        payload = {"ids": message_ids}
        response = await self._http.delete(f"{BASE_URL}/conversations/{conversation_id}/messages", authenticated=True, json=payload)
        raw_list = response.json()
        if not isinstance(raw_list, list): raw_list = [raw_list] if raw_list else []
        return [DeletedMessage(**m) for m in raw_list if m]

    async def switch_persona_for_chat(self, conversation_id: str, persona_id: str) -> bool:
        payload = {"user_persona_id": persona_id}
        response = await self._http.patch(f"{BASE_URL}/conversations/{conversation_id}/user_persona", authenticated=True, json=payload)
        return response.status_code == 200

    async def _get_upload_url(self, image_bytes: bytes, mime_type: str) -> Dict[str, str]:
        image_hash = hashlib.md5(image_bytes).hexdigest()
        payload = {"image_type": mime_type, "hash": image_hash}
        response = await self._http.post(f"{BASE_URL}/save-image", authenticated=True, json=payload)
        return response.json()

    async def _upload_to_s3(self, upload_url: str, image_bytes: bytes, mime_type: str):
        headers = {'Content-Type': mime_type}
        async with httpx.AsyncClient() as s3_client:
            await s3_client.put(upload_url, content=image_bytes, headers=headers)

    async def close(self):
        await self._http.close()
        await self._auth_manager.close()
