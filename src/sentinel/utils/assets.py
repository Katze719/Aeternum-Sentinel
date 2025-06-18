from pathlib import Path
import logging

import sass

_log = logging.getLogger(__name__)


def compile_scss(source: str | Path, target: str | Path) -> None:
    """Compile `source` SCSS file into `target` CSS file if needed.

    If the target file does not exist or the source has been modified more
    recently, a fresh compilation is triggered. Errors are silenced but
    logged to console so that a missing Sass binary does not break the app
    in production.
    """
    src_path = Path(source)
    tgt_path = Path(target)

    try:
        if not src_path.exists():
            _log.warning("[scss] source not found: %s", src_path)
            return

        if tgt_path.exists() and tgt_path.stat().st_mtime >= src_path.stat().st_mtime:
            # Up-to-date
            return

        tgt_path.parent.mkdir(parents=True, exist_ok=True)

        css = sass.compile(filename=str(src_path), output_style="compressed")
        tgt_path.write_text(css, encoding="utf-8")
        _log.info("[scss] compiled %s -> %s", src_path.name, tgt_path.name)
    except Exception as exc:  # pragma: no cover
        _log.error("[scss] failed to compile %s: %s", src_path, exc)
