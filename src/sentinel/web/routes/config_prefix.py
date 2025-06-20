from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["config"])


@router.post("/config/prefix")
async def update_prefix(new_prefix: str, request: Request):
    if not new_prefix:
        raise HTTPException(status_code=400, detail="Prefix cannot be empty.")

    bot = request.app.state.bot
    bot.command_prefix = new_prefix  # type: ignore[assignment]
    return {"prefix": new_prefix} 
