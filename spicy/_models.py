# spicy/_models.py

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
import datetime

# --- Auth Models ---
class TokenData(BaseModel):
    access_token: str
    expires_in: int
    id_token: str
    refresh_token: str
    scope: str
    token_type: str
    created_at: float = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).timestamp())

# --- User Models ---
class UserSubscription(BaseModel):
    pass # Empty; this one seems useless tbh

class User(BaseModel):
    id: str
    name: str
    username: str
    email: str
    avatar_url: Optional[str] = None
    highlights: Optional[str] = ""
    default_persona_id: Optional[str] = None
    token: str
    subscription: UserSubscription

class Persona(BaseModel):
    id: str
    name: str
    avatar_url: Optional[str] = None
    highlights: Optional[str] = ""

class UserSettings(BaseModel):
    userId: str
    blur_nsfw: bool
    show_nsfw: bool
    liked_bots: List[str]
    blocked_users: List[str]
    tts_include_narration: bool
    chat_language: str

# --- Character and Chat Models ---
class Character(BaseModel):
    id: str
    name: str
    title: Optional[str] = None
    visibility: str
    creator_username: Optional[str] = None
    creator_user_id: Optional[str] = None
    greeting: Optional[str] = None
    avatar_url: Optional[str] = None
    num_messages: int
    is_nsfw: bool
    avatar_is_nsfw: bool
    definition_visible: bool
    tags: List[str]
    language: str
    token_count: int
    createdAt: datetime.datetime
    updatedAt: datetime.datetime

class Message(BaseModel):
    conversation_id: str
    role: str
    id: str
    content: str
    prev_id: Optional[str] = None
    createdAt: Optional[float] = None

# --- Model for the response from deleting messages ---
class DeletedMessage(Message):
    deletedAt: int
    deleteReason: str
    is_deleted: bool

class Conversation(BaseModel):
    id: str
    character_id: str
    last_message: Optional[Dict[str, Any]]
    character: Dict[str, Any]
    label: str
    user_persona_id: Optional[str] = None

class SearchHit(BaseModel):
    document: Character

class SearchResult(BaseModel):
    found: int
    hits: List[SearchHit]

class GeneratedImage(BaseModel):
    key: str
    signed_url: HttpUrl

# --- Application Models ---
class InferenceModel(BaseModel):
    id: str
    tag: Optional[str] = None
    name: str
    size: str
    tokens: Optional[str] = None
    description: str
    hide_unauthorized: Optional[bool] = None
    level: Optional[str] = None
    permission: Optional[str] = None

class TypesenseConfig(BaseModel):
    collectionNamePublicCharacter: str
    apiKeyPublicCharacter: str
    collectionNameLeaderboard: str
    apiKeyLeaderboard: str

class ApplicationSettings(BaseModel):
    name: str
    id: str
    typesenseConfig: TypesenseConfig
    inferenceModels: List[InferenceModel]
    isNsfwEnabled: bool
