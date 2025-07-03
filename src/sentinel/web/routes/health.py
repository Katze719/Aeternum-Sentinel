from fastapi import APIRouter

router = APIRouter(tags=["misc"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Light-weight health probe used by deployment environments."""
    return {"status": "ok"} 
