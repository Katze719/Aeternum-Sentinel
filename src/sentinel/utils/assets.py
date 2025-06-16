from pathlib import Path

import sass


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
            print(f"[scss] source not found: {src_path}")
            return

        if tgt_path.exists() and tgt_path.stat().st_mtime >= src_path.stat().st_mtime:
            # Up-to-date
            return

        css = sass.compile(filename=str(src_path), output_style="compressed")
        tgt_path.write_text(css, encoding="utf-8")
        print(f"[scss] compiled {src_path.name} -> {tgt_path.name}")
    except Exception as exc:  # pragma: no cover
        print(f"[scss] failed to compile {src_path}: {exc}") 
