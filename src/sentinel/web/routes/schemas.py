from pydantic import BaseModel

__all__ = [
    "ConfigResponse",
    "RoleIconEntry",
    "NameFormatPayload",
    "TogglePayload",
    "VoiceAutoConfigPayload",
    "ReviewMessagePayload",
    "VodLinkPayload",
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


class VodLinkPayload(BaseModel):
    link: str 


class ReactionRoleItem(BaseModel):
    emoji_id: str | None = None
    emoji_name: str | None = None
    emoji_unicode: str | None = None
    role_id: str
    description: str | None = None

class ReactionRolesPayload(BaseModel):
    channel_id: str
    title: str | None = None
    description: str | None = None
    items: list[ReactionRoleItem] = [] 
