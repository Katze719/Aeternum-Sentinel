import asyncio
import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Optional

import uvicorn
from discord import Intents
from discord.ext import commands

from .config import get_settings
from .web.server import get_app

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class SentinelBot(commands.Bot):
    """A subclass of `commands.Bot` that auto-discovers and loads cogs."""

    def __init__(self, *args, **kwargs):
        settings = get_settings()
        intents = Intents.all()
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix=settings.command_prefix, intents=intents, *args, **kwargs)

        # Placeholder for the uvicorn server instance.
        self._uvicorn: Optional[uvicorn.Server] = None

    async def setup_hook(self) -> None:  # noqa: D401
        """Called by discord.py to set up the bot before it connects."""

        await self._load_cogs()

        try:
            await self.tree.sync()
            _log.info("Synced %d application command(s).", len(self.tree.get_commands()))
        except Exception:  # pragma: no cover
            _log.exception("Failed to sync application commands")


    async def _load_cogs(self) -> None:
        """Auto-discover and load all cogs in the `sentinel.cogs` package."""

        _log.info("Loading cogs ...")
        for module_info in pkgutil.walk_packages(path=[str(Path(__file__).parent / "cogs")], prefix="sentinel.cogs."):
            if module_info.ispkg:
                continue
            try:
                module = importlib.import_module(module_info.name)
            except Exception as exc:  # pragma: no cover
                _log.exception("Failed to import cog %s: %s", module_info.name, exc)
                continue

            # The cog module should expose a `setup` coroutine following discord.py conventions
            if hasattr(module, "setup"):
                try:
                    await module.setup(self)
                    _log.debug("Loaded cog: %s", module_info.name)
                except Exception as exc:  # pragma: no cover
                    _log.exception("Failed to setup cog %s: %s", module_info.name, exc)

    async def start_web_server(self) -> None:
        """Start the FastAPI web server in a background task."""

        settings = get_settings()
        # Log the public URL where the web UI should be reachable. We derive it from the
        # configured OAuth redirect (everything before the last slash) so users can
        # override it easily via the OAUTH_REDIRECT_URI env var.
        ui_base_url = settings.oauth_redirect_uri.rsplit("/", 1)[0]
        _log.info("Web interface available at %s", ui_base_url)
        config = uvicorn.Config(get_app(self), host=settings.host, port=settings.port, log_level="info")
        self._uvicorn = uvicorn.Server(config=config)

        loop = asyncio.get_event_loop()
        loop.create_task(self._uvicorn.serve())

    async def close(self) -> None:  # noqa: D401
        """Shut down the bot and the web server cleanly."""

        if self._uvicorn and self._uvicorn.started:
            await self._uvicorn.shutdown()
        await super().close() 