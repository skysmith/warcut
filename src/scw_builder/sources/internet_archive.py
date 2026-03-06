from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from scw_builder.manifest import ManifestAsset
from scw_builder.sources.licenses import ia_has_usable_rights, normalize_ia_attribution
from scw_builder.utils.files import ensure_dir, slugify
from scw_builder.utils.http import download_to_file, open_url
from scw_builder.utils.video import clip_hash, trim_clip


ADVANCEDSEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata"
ALLOWED_VIDEO_FORMAT_HINTS = ("h.264", "mpeg4", "mp4")
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024
PREFERRED_COLLECTIONS = (
    "prelinger",
    "newsandpublicaffairs",
    "opensource_movies",
    "classic_tv",
)


@dataclass(frozen=True)
class IASelectionOptions:
    assets_dir: Path
    cache_dir: Path
    limit: int
    max_clip_sec: int
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES
    offline: bool = False
    no_download: bool = False


def search_ia(
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
        "q": _build_ia_query(query),
        "fl[]": [
            "identifier",
            "title",
            "mediatype",
            "rights",
            "licenseurl",
            "collection",
            "subject",
            "description",
        ],
        "rows": limit,
        "output": "json",
    }
    data = _get_or_load_json(ADVANCEDSEARCH_URL, params, cache_path=cache_path, offline=offline)
    return data.get("response", {}).get("docs", [])


def _build_ia_query(query: str) -> str:
    escaped = query.replace('"', "")
    collection_clause = " OR ".join(f"collection:{collection}" for collection in PREFERRED_COLLECTIONS)
    rights_clause = (
        'rights:("public domain" OR "no known copyright restrictions") '
        'OR licenseurl:(creativecommons.org/*)'
    )
    text_clause = f'(title:("{escaped}") OR subject:("{escaped}") OR description:("{escaped}") OR "{escaped}")'
    return (
        f"({text_clause}) AND mediatype:(movies) AND ({collection_clause}) "
        f"AND ({rights_clause})"
    )


def get_item_metadata(
    identifier: str,
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    cache_path = None
    if cache_dir is not None:
        cache_path = ensure_dir(cache_dir) / f"metadata_{slugify(identifier)}.json"
    return _get_or_load_json(
        f"{METADATA_URL}/{identifier}",
        None,
        cache_path=cache_path,
        offline=offline,
    )


def download_best_derivative(
    identifier: str,
    dest_dir: Path,
    *,
    metadata: dict[str, Any],
    offline: bool = False,
    no_download: bool = False,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> tuple[Path | None, dict[str, Any] | None]:
    file_info = _select_best_derivative(metadata, max_file_size_bytes=max_file_size_bytes)
    if not file_info:
        return None, None
    filename = file_info["name"]
    dest_path = ensure_dir(dest_dir) / filename
    if dest_path.exists() or no_download:
        return dest_path, file_info
    if offline:
        return dest_path, file_info
    url = f"https://archive.org/download/{quote(identifier)}/{quote(filename)}"
    download_to_file(url, dest_path, timeout=120)
    return dest_path, file_info


def select_clips_for_beat(
    beat_id: str,
    query: str,
    options: IASelectionOptions,
    *,
    fps: int,
) -> list[ManifestAsset]:
    results = search_ia(query, options.limit, cache_dir=options.cache_dir, offline=options.offline)
    selections: list[ManifestAsset] = []
    cache_download_dir = ensure_dir(options.assets_dir / "_cache" / "ia")
    clip_dir = ensure_dir(options.assets_dir / "ia_clips")

    for result in results:
        identifier = result.get("identifier")
        if not identifier:
            continue
        metadata = get_item_metadata(identifier, cache_dir=options.cache_dir, offline=options.offline)
        if not metadata or not ia_has_usable_rights(metadata):
            continue
        source_path, file_info = download_best_derivative(
            identifier,
            cache_download_dir,
            metadata=metadata,
            offline=options.offline,
            no_download=options.no_download,
            max_file_size_bytes=options.max_file_size_bytes,
        )
        if not file_info:
            continue
        start_sec = 0.0
        duration_sec = float(options.max_clip_sec)
        trim_name = f"{beat_id}_{identifier}_{clip_hash(identifier, start_sec, duration_sec)}.mp4"
        trimmed_path = clip_dir / trim_name
        if source_path and source_path.exists():
            trim_clip(source_path, start_sec, duration_sec, trimmed_path, fps=fps)
        elif not trimmed_path.exists():
            if options.no_download:
                trimmed_path = clip_dir / trim_name
            else:
                continue
        metadata_path = clip_dir / f"{trim_name}.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        attribution = normalize_ia_attribution(identifier, metadata)
        selections.append(
            ManifestAsset(
                asset_id=f"{beat_id}-{identifier}",
                provider="internet_archive",
                local_filepath=str(trimmed_path.resolve()),
                source_url=attribution.source_url,
                query_used=query,
                media_type="video",
                mime_type="video/mp4",
                identifier=identifier,
                clip_start_sec=start_sec,
                clip_duration_sec=duration_sec,
                raw_metadata_path=str(metadata_path.resolve()),
                attribution=attribution,
            )
        )
        if len(selections) >= options.limit:
            break
    return selections


def select_clip_by_identifier(
    beat_id: str,
    identifier: str,
    options: IASelectionOptions,
    *,
    fps: int,
) -> ManifestAsset | None:
    cache_download_dir = ensure_dir(options.assets_dir / "_cache" / "ia")
    clip_dir = ensure_dir(options.assets_dir / "ia_clips")
    metadata = get_item_metadata(identifier, cache_dir=options.cache_dir, offline=options.offline)
    if not metadata or not ia_has_usable_rights(metadata):
        return None
    source_path, file_info = download_best_derivative(
        identifier,
        cache_download_dir,
        metadata=metadata,
        offline=options.offline,
        no_download=options.no_download,
        max_file_size_bytes=options.max_file_size_bytes,
    )
    if not file_info:
        return None
    start_sec = 0.0
    duration_sec = float(options.max_clip_sec)
    trim_name = f"{beat_id}_{identifier}_{clip_hash(identifier, start_sec, duration_sec)}.mp4"
    trimmed_path = clip_dir / trim_name
    if source_path and source_path.exists():
        trim_clip(source_path, start_sec, duration_sec, trimmed_path, fps=fps)
    elif not trimmed_path.exists():
        if options.no_download:
            trimmed_path = clip_dir / trim_name
        else:
            return None
    metadata_path = clip_dir / f"{trim_name}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    attribution = normalize_ia_attribution(identifier, metadata)
    return ManifestAsset(
        asset_id=f"{beat_id}-{identifier}",
        provider="internet_archive",
        local_filepath=str(trimmed_path.resolve()),
        source_url=attribution.source_url,
        query_used=identifier,
        media_type="video",
        mime_type="video/mp4",
        identifier=identifier,
        clip_start_sec=start_sec,
        clip_duration_sec=duration_sec,
        raw_metadata_path=str(metadata_path.resolve()),
        attribution=attribution,
    )


def _select_best_derivative(
    metadata: dict[str, Any],
    *,
    max_file_size_bytes: int,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = -1
    for file_info in metadata.get("files", []):
        name = str(file_info.get("name", ""))
        format_hint = str(file_info.get("format", "")).lower()
        source = str(file_info.get("source", "")).lower()
        if not name.lower().endswith(".mp4"):
            continue
        if source and source != "derivative":
            continue
        size = int(file_info.get("size", 0) or 0)
        if size and size > max_file_size_bytes:
            continue
        score = 0
        if any(marker in format_hint for marker in ALLOWED_VIDEO_FORMAT_HINTS):
            score += 10
        if "512kb" in name.lower() or "h264" in name.lower():
            score += 5
        if ia_has_usable_rights(metadata):
            score += 3
        if score > best_score:
            best_score = score
            best = file_info
    return best


def _get_or_load_json(
    base_url: str,
    params: dict[str, Any] | None,
    *,
    cache_path: Path | None,
    offline: bool,
) -> dict[str, Any]:
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    if offline:
        return {}
    url = base_url
    if params:
        normalized_params: list[tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, list):
                normalized_params.extend((key, str(item)) for item in value)
            else:
                normalized_params.append((key, str(value)))
        url = f"{base_url}?{urlencode(normalized_params)}"
    with open_url(url, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    if cache_path:
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
