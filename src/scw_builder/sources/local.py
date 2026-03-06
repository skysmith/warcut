from __future__ import annotations

from pathlib import Path


def static_assets_root(repo_root: Path) -> Path:
    return repo_root / "assets_static"
