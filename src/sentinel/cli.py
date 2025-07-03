import asyncio
import logging
import signal
import sys

from .bot import SentinelBot
from .config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


async def _run():
    settings = get_settings()

    bot = SentinelBot()

    await bot.start_web_server()

    loop = asyncio.get_running_loop()

    # Graceful shutdown on SIGTERM/SIGINT
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(bot.close()))

    await bot.start(settings.discord_token)


def main() -> None:  # noqa: D401
    """CLI entry point declared in pyproject.toml."""

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0) 
