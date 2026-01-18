# spicy/_models.py
# Author: SSL-ACTX (Seuriin)
# Code Reviewer / QA: Gemini 2.5 Flash

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
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
    pass

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

# --- Application & Generation Models ---
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

class GenerationSettings(BaseModel):
    """
    Settings to control the AI generation behavior.
    """
    max_new_tokens: int = Field(180, ge=1, le=300, description="Max tokens to generate (180 default, 300 for premium).")
    temperature: float = Field(0.7, ge=0.0, le=1.5, description="Creativity vs focus (0.7 default).")
    top_p: float = Field(0.7, ge=0.01, le=1.0, description="Nucleus sampling (0.7 default).")
    top_k: int = Field(90, ge=1, le=100, description="Vocabulary limit (90 default).")

    @field_validator('max_new_tokens')
    def check_token_limit(cls, v):
        # Warn or clamp if needed, but the API might just reject it.
        return v
