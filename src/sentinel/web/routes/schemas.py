from pydantic import BaseModel

__all__ = [
    "ConfigResponse",
    "RoleIconEntry",
    "NameFormatPayload",
    "TogglePayload",
    "VoiceAutoConfigPayload",
    "ReviewMessagePayload",
]


class ConfigResponse(BaseModel):
    prefix: str


class RoleIconEntry(BaseModel):
    role_id: str
    emoji: str
    priority: int | None = 0


class NameFormatPayload(BaseModel):
    name_format: str


class TogglePayload(BaseModel):
    enabled: bool


class VoiceAutoConfigPayload(BaseModel):
    generator_channel_id: str
    target_category_id: str
    name_pattern: str | None = "{username}" 


class ReviewMessagePayload(BaseModel):
    message: str 
