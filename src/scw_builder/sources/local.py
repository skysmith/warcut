from __future__ import annotations

from pathlib import Path

from scw_builder.manifest import Attribution, ManifestAsset
from scw_builder.utils.files import slugify


def static_assets_root(repo_root: Path) -> Path:
    return repo_root / "assets_static"


def build_local_asset(
    beat_id: str,
    local_path: Path,
    *,
    query_used: str | None = None,
) -> ManifestAsset | None:
    if not local_path.exists():
        return None
    suffix = local_path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".svg"}:
        media_type = "image"
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }[suffix]
    elif suffix in {".mp4", ".mov", ".m4v"}:
        media_type = "video"
        mime_type = "video/mp4" if suffix == ".mp4" else "video/quicktime"
    else:
        return None
    return ManifestAsset(
        asset_id=f"{beat_id}-local-{slugify(local_path.stem)}",
        provider="local",
        local_filepath=str(local_path.resolve()),
        source_url=None,
        query_used=query_used,
        media_type=media_type,
        mime_type=mime_type,
        page_title=local_path.name,
        attribution=Attribution(
            title=local_path.name,
            author="Local asset",
            license_name="User supplied",
            source_url=str(local_path.resolve()),
            attribution_text="User-supplied local asset.",
        ),
    )
