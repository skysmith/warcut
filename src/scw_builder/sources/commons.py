from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from scw_builder.manifest import ManifestAsset
from scw_builder.sources.licenses import (
    commons_has_required_attribution,
    normalize_commons_attribution,
)
from scw_builder.utils.files import ensure_dir, slugify
from scw_builder.utils.http import download_to_file, open_url


MEDIAWIKI_API_URL = "https://commons.wikimedia.org/w/api.php"
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/svg+xml"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".svg"}


@dataclass(frozen=True)
class CommonsSelectionOptions:
    assets_dir: Path
    cache_dir: Path
    limit: int
    min_width: int
    min_height: int
    require_attribution: bool = True
    offline: bool = False
    no_download: bool = False


def search_commons(
    query: str,
    limit: int = 10,
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> list[dict[str, Any]]:
    cache_path = None
    if cache_dir is not None:
        cache_path = ensure_dir(cache_dir) / f"search_{slugify(query)}_{limit}.json"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srnamespace": "6",
        "srlimit": limit,
        "srsearch": query,
    }
    data = _get_or_load_json(params, cache_path=cache_path, offline=offline)
    return data.get("query", {}).get("search", [])


def get_file_metadata(
    title: str,
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    cache_path = None
    if cache_dir is not None:
        cache_path = ensure_dir(cache_dir) / f"metadata_{slugify(title)}.json"
    params = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": title,
        "iiprop": "url|size|mime|extmetadata",
    }
    return _get_or_load_json(params, cache_path=cache_path, offline=offline)


def download_file(url: str, dest: Path, *, offline: bool = False) -> Path:
    if dest.exists():
        return dest
    if offline:
        return dest
    return download_to_file(url, dest, timeout=60)


def select_assets_for_beat(
    beat_id: str,
    query: str,
    options: CommonsSelectionOptions,
) -> list[ManifestAsset]:
    candidates = search_commons(
        query,
        options.limit,
        cache_dir=options.cache_dir,
        offline=options.offline,
    )
    selected: list[ManifestAsset] = []
    provider_dir = ensure_dir(options.assets_dir / "commons")

    for candidate in candidates:
        title = candidate.get("title")
        if not title:
            continue
        metadata = get_file_metadata(
            title,
            cache_dir=options.cache_dir,
            offline=options.offline,
        )
        if not _passes_filters(
            metadata,
            min_width=options.min_width,
            min_height=options.min_height,
            require_attribution=options.require_attribution,
        ):
            continue
        asset = _materialize_asset(
            beat_id=beat_id,
            query=query,
            title=title,
            metadata=metadata,
            provider_dir=provider_dir,
            offline=options.offline,
            no_download=options.no_download,
        )
        selected.append(asset)
        if len(selected) >= options.limit:
            break
    return selected


def select_assets_by_title(
    beat_id: str,
    title: str,
    options: CommonsSelectionOptions,
) -> ManifestAsset | None:
    provider_dir = ensure_dir(options.assets_dir / "commons")
    metadata = get_file_metadata(
        title,
        cache_dir=options.cache_dir,
        offline=options.offline,
    )
    if not _passes_filters(
        metadata,
        min_width=options.min_width,
        min_height=options.min_height,
        require_attribution=options.require_attribution,
        ignore_resolution=True,
    ):
        return None
    return _materialize_asset(
        beat_id=beat_id,
        query=title,
        title=title,
        metadata=metadata,
        provider_dir=provider_dir,
        offline=options.offline,
        no_download=options.no_download,
    )


def _materialize_asset(
    *,
    beat_id: str,
    query: str,
    title: str,
    metadata: dict[str, Any],
    provider_dir: Path,
    offline: bool,
    no_download: bool,
) -> ManifestAsset:
    page = _first_page(metadata)
    imageinfo = _first_imageinfo(metadata)
    file_url = imageinfo["url"]
    description_url = imageinfo.get("descriptionurl") or file_url
    page_id = str(page.get("pageid", slugify(title)))
    extension = Path(title).suffix.lower()
    asset_stem = f"{page_id}_{slugify(Path(title).stem)}"
    asset_path = provider_dir / f"{asset_stem}{extension}"
    metadata_path = provider_dir / f"{asset_stem}.json"

    if not no_download:
        download_file(file_url, asset_path, offline=offline)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    attribution = normalize_commons_attribution(title, metadata, description_url)

    return ManifestAsset(
        asset_id=f"{beat_id}-{page_id}",
        provider="commons",
        local_filepath=str(asset_path.resolve()),
        source_url=description_url,
        query_used=query,
        media_type="image",
        mime_type=imageinfo.get("mime"),
        width=imageinfo.get("width"),
        height=imageinfo.get("height"),
        page_title=title,
        raw_metadata_path=str(metadata_path.resolve()),
        attribution=attribution,
    )


def _passes_filters(
    metadata: dict[str, Any],
    *,
    min_width: int,
    min_height: int,
    require_attribution: bool,
    ignore_resolution: bool = False,
) -> bool:
    page = _first_page(metadata)
    title = page.get("title", "")
    extension = Path(title).suffix.lower()
    imageinfo = _first_imageinfo(metadata)
    if extension not in ALLOWED_EXTENSIONS:
        return False
    if imageinfo.get("mime") not in ALLOWED_MIME_TYPES:
        return False
    width = int(imageinfo.get("width", 0) or 0)
    height = int(imageinfo.get("height", 0) or 0)
    if not ignore_resolution and (width < min_width or height < min_height):
        return False
    if require_attribution and not commons_has_required_attribution(metadata):
        return False
    return True


def _get_or_load_json(
    params: dict[str, Any],
    *,
    cache_path: Path | None,
    offline: bool,
) -> dict[str, Any]:
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    if offline:
        return {}
    url = f"{MEDIAWIKI_API_URL}?{urlencode(params)}"
    with open_url(url, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    if cache_path:
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _first_page(metadata: dict[str, Any]) -> dict[str, Any]:
    pages = metadata.get("query", {}).get("pages", {})
    if not pages:
        return {}
    return next(iter(pages.values()))


def _first_imageinfo(metadata: dict[str, Any]) -> dict[str, Any]:
    page = _first_page(metadata)
    imageinfo = page.get("imageinfo", [])
    return imageinfo[0] if imageinfo else {}
