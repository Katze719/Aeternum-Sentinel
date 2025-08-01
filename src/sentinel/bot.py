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
        # Detect whether to enable HTTPS. Both certificate and key files must be
        # configured *and* exist on disk; otherwise we fall back to HTTP.
        cert_path: Path | None = None
        key_path: Path | None = None

        if settings.ssl_certfile and settings.ssl_keyfile:
            cert_path = Path(settings.ssl_certfile)
            key_path = Path(settings.ssl_keyfile)

            if cert_path.is_file() and key_path.is_file():
                _log.info("Enabling HTTPS using cert '%s' and key '%s'", cert_path, key_path)
            else:
                _log.warning(
                    "SSL configuration detected but certificate or key file not found (cert=%s, key=%s). "
                    "Starting in HTTP mode.",
                    cert_path,
                    key_path,
                )
                cert_path = None
                key_path = None

        ui_base_url = settings.oauth_redirect_uri.rsplit("/", 1)[0]
        _log.info("Web interface available at %s", ui_base_url)

        if cert_path and key_path:
            config = uvicorn.Config(
                get_app(self),
                host=settings.host,
                port=settings.port,
                log_level="info",
                ssl_certfile=str(cert_path),
                ssl_keyfile=str(key_path),
            )
        else:
            config = uvicorn.Config(
                get_app(self),
                host=settings.host,
                port=settings.port,
                log_level="info",
            )
        self._uvicorn = uvicorn.Server(config=config)

        loop = asyncio.get_event_loop()
        loop.create_task(self._uvicorn.serve())

    async def close(self) -> None:  # noqa: D401
        """Shut down the bot and the web server cleanly."""

        if self._uvicorn and self._uvicorn.started:
            await self._uvicorn.shutdown()
        await super().close() 
