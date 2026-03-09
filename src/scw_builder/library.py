from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from scw_builder.manifest import Attribution, BeatManifest, Manifest, ManifestAsset
from scw_builder.utils.files import ensure_dir, slugify, unique_preserving_order


REGION_KEYWORDS = {
    "catalonia": {"catalonia", "catalan", "barcelona", "cnt", "fai"},
    "basque_country": {"basque", "bilbao", "euzkadi", "ikurrina"},
    "andalusia": {"andalusia", "andalusia", "seville", "granada", "jornaleros", "peasants", "laborers"},
    "madrid": {"madrid"},
    "galicia": {"galicia"},
    "castile": {"castile"},
}
THEME_KEYWORDS = {
    "militia": {"militia", "millicians", "milicianas", "barricades", "uprising"},
    "autonomy": {"autonomy", "autonomous", "regional", "regions", "nation"},
    "industry": {"factory", "factories", "industry", "industrial", "unions"},
    "land": {"land", "peasants", "laborers", "rural", "estates", "wages", "hunger"},
    "elections": {"elections", "electoral", "vote", "parliament"},
    "propaganda": {"poster", "propaganda", "cartel"},
    "map": {"map", "districts", "regions", "fronts"},
    "newsreel": {"newsreel", "footage", "archive", "reel"},
}
MOOD_KEYWORDS = {
    "crowd": {"crowds", "crowd", "rally", "manifestation"},
    "violence": {"barricades", "militia", "uprising", "war", "coup"},
    "institutional": {"constitution", "elections", "districts", "government"},
    "poverty": {"peasants", "laborers", "hunger", "rural", "land"},
}


class CuratedAssetRecord(BaseModel):
    asset_key: str
    title: str
    provider: str
    media_type: str
    mime_type: str | None = None
    source_url: str | None = None
    source_local_filepath: str | None = None
    curated_filepath: str | None = None
    page_title: str | None = None
    identifier: str | None = None
    raw_metadata_path: str | None = None
    episode_ids: list[str] = Field(default_factory=list)
    beat_ids: list[str] = Field(default_factory=list)
    captions: list[str] = Field(default_factory=list)
    tags: dict[str, list[str] | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    attribution: Attribution


def ingest_manifest(manifest: Manifest, curated_root: Path) -> list[CuratedAssetRecord]:
    files_dir = ensure_dir(curated_root / "files")
    items_dir = ensure_dir(curated_root / "items")
    library_path = curated_root / "library.json"
    existing = _load_library(items_dir)
    results: dict[str, CuratedAssetRecord] = dict(existing)

    for beat in manifest.beats:
        for asset in beat.assets:
            record = _record_from_asset(manifest, beat, asset, curated_root, files_dir)
            existing_record = results.get(record.asset_key)
            if existing_record:
                record = _merge_records(existing_record, record)
            results[record.asset_key] = record

    ordered = sorted(results.values(), key=lambda record: record.asset_key)
    for record in ordered:
        (items_dir / f"{record.asset_key}.json").write_text(
            json.dumps(record.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
    library_summary = [
        {
            "asset_key": record.asset_key,
            "title": record.title,
            "provider": record.provider,
            "media_type": record.media_type,
            "episode_ids": record.episode_ids,
            "beat_ids": record.beat_ids,
            "tags": record.tags,
            "item_path": f"items/{record.asset_key}.json",
            "curated_filepath": record.curated_filepath,
            "source_url": record.source_url,
        }
        for record in ordered
    ]
    library_path.write_text(json.dumps(library_summary, indent=2), encoding="utf-8")
    return ordered


def write_gallery(curated_root: Path) -> Path:
    library_path = curated_root / "library.json"
    entries = json.loads(library_path.read_text(encoding="utf-8")) if library_path.exists() else []
    cards = []
    for entry in entries:
        preview = _preview_markup(entry)
        tags = entry.get("tags", {})
        tag_lines = []
        for key in ["region", "theme", "asset_type", "period", "mood"]:
            values = tags.get(key, [])
            if values:
                joined = ", ".join(values)
                tag_lines.append(f"<div><strong>{key}</strong>: {joined}</div>")
        quality = tags.get("quality")
        if quality:
            tag_lines.append(f"<div><strong>quality</strong>: {quality}</div>")
        source_url = entry.get("source_url")
        source_link = f'<a href="{source_url}">source</a>' if source_url else ""
        item_link = f'<a href="{entry["item_path"]}">metadata</a>'
        cards.append(
            f"""
            <article class="card">
              <div class="preview">{preview}</div>
              <div class="body">
                <h3>{entry['title']}</h3>
                <div class="meta">{entry['provider']} · {entry['media_type']}</div>
                <div class="tags">{''.join(tag_lines)}</div>
                <div class="beats"><strong>beats</strong>: {', '.join(entry.get('beat_ids', []))}</div>
                <div class="links">{item_link} {source_link}</div>
              </div>
            </article>
            """
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>warcut asset library</title>
  <style>
    :root {{
      --bg: #0b0d10;
      --panel: #15181d;
      --text: #f2f2f2;
      --muted: #a7adb5;
      --accent: #d14a3a;
      --line: #2a2f36;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background: radial-gradient(circle at top, #15181d 0%, #0b0d10 45%);
      color: var(--text);
    }}
    header {{
      padding: 32px;
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      background: rgba(11, 13, 16, 0.9);
      backdrop-filter: blur(8px);
    }}
    header h1 {{ margin: 0 0 6px; font-size: 28px; }}
    header p {{ margin: 0; color: var(--muted); }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 18px;
      padding: 24px;
    }}
    .card {{
      border: 1px solid var(--line);
      background: var(--panel);
      min-height: 420px;
    }}
    .preview {{
      height: 220px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-bottom: 1px solid var(--line);
      background: #0d1014;
    }}
    .preview img, .preview video {{
      max-width: 100%;
      max-height: 100%;
      display: block;
    }}
    .placeholder {{
      color: var(--muted);
      font-size: 13px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .body {{ padding: 16px; }}
    h3 {{ margin: 0 0 8px; font-size: 18px; }}
    .meta, .beats, .tags, .links {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .links a {{
      color: var(--accent);
      text-decoration: none;
      margin-right: 12px;
    }}
    .tags div {{ margin-bottom: 2px; }}
  </style>
</head>
<body>
  <header>
    <h1>warcut asset library</h1>
    <p>{len(entries)} curated assets. Edit <code>assets_curated/items/*.json</code> to retag or add notes.</p>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    output = curated_root / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


def _load_library(items_dir: Path) -> dict[str, CuratedAssetRecord]:
    records: dict[str, CuratedAssetRecord] = {}
    if not items_dir.exists():
        return records
    for item_path in items_dir.glob("*.json"):
        record = CuratedAssetRecord.model_validate_json(item_path.read_text(encoding="utf-8"))
        records[record.asset_key] = record
    return records


def _record_from_asset(
    manifest: Manifest,
    beat: BeatManifest,
    asset: ManifestAsset,
    curated_root: Path,
    files_dir: Path,
) -> CuratedAssetRecord:
    identity = asset.identifier or asset.page_title or Path(asset.local_filepath).name
    asset_key = f"{asset.provider}-{slugify(identity)}"
    curated_filepath = _copy_asset_file(asset, files_dir, asset_key, curated_root)
    tags = _infer_tags(beat, asset)
    return CuratedAssetRecord(
        asset_key=asset_key,
        title=asset.attribution.title or identity,
        provider=asset.provider,
        media_type=asset.media_type,
        mime_type=asset.mime_type,
        source_url=asset.source_url,
        source_local_filepath=_relativize(asset.local_filepath, curated_root.parent),
        curated_filepath=curated_filepath,
        page_title=asset.page_title,
        identifier=asset.identifier,
        raw_metadata_path=_relativize(asset.raw_metadata_path, curated_root.parent),
        episode_ids=[manifest.episode_id],
        beat_ids=[beat.beat_id],
        captions=[beat.caption] if beat.caption else [],
        tags=tags,
        notes=[],
        attribution=asset.attribution,
    )


def _copy_asset_file(asset: ManifestAsset, files_dir: Path, asset_key: str, curated_root: Path) -> str | None:
    source = Path(asset.local_filepath)
    if not source.exists():
        return None
    suffix = source.suffix.lower()
    target = files_dir / f"{asset_key}{suffix}"
    if not target.exists():
        shutil.copy2(source, target)
    return str(target.relative_to(curated_root))


def _relativize(value: str | None, root: Path) -> str | None:
    if not value:
        return None
    path = Path(value)
    try:
        return os.path.relpath(str(path), str(root))
    except Exception:
        return str(path)


def _infer_tags(beat: BeatManifest, asset: ManifestAsset) -> dict[str, list[str] | str]:
    haystack = " ".join(
        [
            beat.beat_id,
            beat.caption or "",
            " ".join(beat.keywords),
            " ".join(beat.overlays),
            asset.page_title or "",
            asset.attribution.title or "",
            asset.query_used or "",
        ]
    ).lower()
    regions = _matched_labels(haystack, REGION_KEYWORDS)
    themes = _matched_labels(haystack, THEME_KEYWORDS)
    moods = _matched_labels(haystack, MOOD_KEYWORDS)
    periods = unique_preserving_order(re.findall(r"\b(19\d{2}|20\d{2})\b", haystack))
    asset_types = [beat.beat_type]
    if asset.media_type == "video":
        asset_types.append("clip")
    elif "poster" in haystack:
        asset_types.append("poster")
    elif "map" in haystack:
        asset_types.append("map")
    elif "election" in haystack or "constitution" in haystack or "newspaper" in haystack:
        asset_types.append("document")
    else:
        asset_types.append("photo")
    quality = "strong" if _is_pinned(beat, asset) else "usable"
    return {
        "region": regions,
        "theme": themes,
        "asset_type": unique_preserving_order(asset_types),
        "period": periods,
        "mood": moods,
        "quality": quality,
    }


def _is_pinned(beat: BeatManifest, asset: ManifestAsset) -> bool:
    pinned = beat.pinned or {}
    page_title = asset.page_title or ""
    identifier = asset.identifier or ""
    local_filepath = asset.local_filepath or ""
    return (
        page_title in pinned.get("commons_titles", [])
        or identifier in pinned.get("ia_identifiers", [])
        or local_filepath in pinned.get("local_files", [])
    )


def _matched_labels(haystack: str, mapping: dict[str, set[str]]) -> list[str]:
    matches: list[str] = []
    for label, words in mapping.items():
        if any(word in haystack for word in words):
            matches.append(label)
    return unique_preserving_order(matches)


def _merge_records(existing: CuratedAssetRecord, new: CuratedAssetRecord) -> CuratedAssetRecord:
    existing.tags = _merge_tags(existing.tags, new.tags)
    existing.episode_ids = unique_preserving_order(existing.episode_ids + new.episode_ids)
    existing.beat_ids = unique_preserving_order(existing.beat_ids + new.beat_ids)
    existing.captions = unique_preserving_order(existing.captions + new.captions)
    existing.notes = unique_preserving_order(existing.notes + new.notes)
    if new.curated_filepath:
        existing.curated_filepath = new.curated_filepath
    if new.source_local_filepath:
        existing.source_local_filepath = new.source_local_filepath
    if new.raw_metadata_path:
        existing.raw_metadata_path = new.raw_metadata_path
    return existing


def _merge_tags(left: dict[str, list[str] | str], right: dict[str, list[str] | str]) -> dict[str, list[str] | str]:
    merged: dict[str, list[str] | str] = dict(left)
    for key, value in right.items():
        if isinstance(value, list):
            current = merged.get(key, [])
            if not isinstance(current, list):
                current = [str(current)]
            merged[key] = unique_preserving_order(current + value)
        elif key == "quality":
            current_quality = str(merged.get(key, "usable"))
            merged[key] = "strong" if "strong" in {current_quality, value} else value
        else:
            merged[key] = value
    return merged


def _preview_markup(entry: dict[str, object]) -> str:
    media_type = entry.get("media_type")
    preview_path = entry.get("curated_filepath") or entry.get("source_local_filepath")
    if preview_path:
        if media_type == "video":
            return f'<video controls preload="metadata" src="{preview_path}"></video>'
        return f'<img src="{preview_path}" alt="{entry["title"]}">'
    return '<div class="placeholder">No Local Preview</div>'
