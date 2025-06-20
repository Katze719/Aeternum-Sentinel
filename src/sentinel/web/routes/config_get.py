from fastapi import APIRouter

from sentinel.config import get_settings

from .schemas import ConfigResponse

router = APIRouter(tags=["config"])


@router.get("/config", response_model=ConfigResponse)
async def read_config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(prefix=settings.command_prefix) 
