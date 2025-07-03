from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"], include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Public landing/index page (Jinja2 template)."""
    templates = request.app.state.templates
    return templates.TemplateResponse("landing.html", {"request": request}) 
