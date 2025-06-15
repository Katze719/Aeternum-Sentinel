from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path.cwd() / "data"
_DATA_DIR.mkdir(exist_ok=True)


def _guild_file(guild_id: int) -> Path:
    return _DATA_DIR / f"guild_{guild_id}.json"


def load_guild_config(guild_id: int) -> dict[str, Any]:
    path = _guild_file(guild_id)
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)
        except json.JSONDecodeError:
            # Corrupted or partially written file → start fresh
            return {}
    return {}


def save_guild_config(guild_id: int, data: dict[str, Any]) -> None:
    path = _guild_file(guild_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8") 