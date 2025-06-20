from __future__ import annotations

"""Utilities for interacting with Google Sheets.

This module centralises the authentication and client creation logic for the
Google Sheets-/Drive-API that is used across the bot (e.g. scheduled sync
processes or slash-commands).

It purposely keeps the public surface very small so that the *actual* business
logic (like what data gets written to a sheet) can live elsewhere without
having to duplicate boiler-plate authorisation code.
"""

from pathlib import Path
# Standard library
from typing import Any
import logging

from pydrive2.auth import GoogleAuth
import gspread_asyncio
from sentinel.config import get_settings

__all__ = [
    "get_async_gspread_client_manager",
]

_log = logging.getLogger(__name__)


def _login_with_service_account(json_credentials_path: str | Path) -> GoogleAuth:
    """Authenticate **once** using the given service-account key.

    Parameters
    ----------
    json_credentials_path:
        Path to the service-account *JSON* credentials file that you have
        downloaded from Google Cloud Console. The service-account *must* have
        been granted access to the spreadsheet(s) you want to access – you can
        simply share the document with the service-account's e-mail address.
    """

    json_path = Path(json_credentials_path)
    if not json_path.is_file():
        raise FileNotFoundError(f"Google service-account JSON not found: {json_path}")

    settings: dict[str, Any] = {
        "client_config_backend": "service",
        "service_config": {
            "client_json_file_path": str(json_path),
        },
    }

    gauth = GoogleAuth(settings=settings)

    # This performs the JWT flow and stores the resulting access token in
    # `gauth.credentials` which we will later hand over to *gspread_asyncio*.
    gauth.ServiceAuth()
    _log.debug("Authenticated Google service-account")
    return gauth


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_async_gspread_client_manager(json_credentials_path: str | Path | None = None) -> gspread_asyncio.AsyncioGspreadClientManager:
    """Return a *gspread-asyncio* client manager for the given credentials.

    The returned manager can be used like this::

        manager = get_async_gspread_client_manager("/path/to/creds.json")
        agc = await manager.authorize()  # expires automatically after some time
        ss = await agc.open_by_key(sheet_id)
        ws = await ss.worksheet("Sheet1")
        await ws.append_row(["foo", "bar"])

    Internally the manager takes care of auto-refreshing tokens when they
    expire, so you can safely cache and reuse the *manager* instance for the
    lifetime of the process.
    """

    if json_credentials_path is None:
        json_credentials_path = get_settings().google_credentials_path

    if json_credentials_path is None:
        raise ValueError("No Google service-account JSON path configured. Set GOOGLE_CREDENTIALS_PATH env var.")

    gauth = _login_with_service_account(json_credentials_path)

    def _get_creds() -> Any:  # noqa: D401 – gspread-asyncio expects *Any*
        """Return *current* oauth2 credentials.

        gspread-asyncio will call this every time before issuing a request so
        that expired tokens are automatically refreshed.
        """

        return gauth.credentials

    return gspread_asyncio.AsyncioGspreadClientManager(_get_creds) 
