# spicy/__init__.py
from .client import SpicyClient, ChatSession # Added ChatSession
from ._exceptions import SpicychatError, AuthenticationError, APIError, RateLimitError, NotFoundError
from ._models import (
    User, Persona, Character, Message, Conversation, GeneratedImage, TokenData, UserSettings, GenerationSettings
)
from ._constants import ImageModel, ChatModel, RatingAction

__all__ = [
    "SpicyClient", "ChatSession",
    "SpicychatError", "AuthenticationError", "APIError",
    "User", "Persona", "Character", "Message", "GenerationSettings",
    "ChatModel"
]
