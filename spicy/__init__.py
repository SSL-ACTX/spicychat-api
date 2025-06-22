# spicy/__init__.py

"""
An unofficial, asynchronous API wrapper for SpicyChat.ai.
"""

__version__ = "0.1.0"

from .client import SpicyClient
from ._exceptions import SpicychatError, AuthenticationError, APIError, RateLimitError, NotFoundError
from ._models import (
    User,
    Persona,
    Character,
    Message,
    Conversation,
    GeneratedImage,
    TokenData,
    UserSettings,
)
from ._constants import ImageModel, ChatModel, RatingAction

__all__ = [
    "SpicyClient",
    "SpicychatError",
    "AuthenticationError",
    "APIError",
    "RateLimitError",
    "NotFoundError",
    "User",
    "Persona",
    "Character",
    "Message",
    "Conversation",
    "GeneratedImage",
    "TokenData",
    "UserSettings",
    "ImageModel",
    "ChatModel",
    "RatingAction",
]
