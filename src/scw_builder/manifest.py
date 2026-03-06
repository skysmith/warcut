from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Attribution(BaseModel):
    title: str
    author: str | None = None
    creator: str | None = None
    date: str | None = None
    identifier: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    rights_statement: str | None = None
    source_url: str | None = None
    attribution_text: str | None = None
    attribution_html: str | None = None


class RenderInstruction(BaseModel):
    start_sec: float
    duration_sec: float
    transform: dict[str, Any] = Field(default_factory=dict)
    overlay_text: list[str] = Field(default_factory=list)


class ManifestAsset(BaseModel):
    asset_id: str
    provider: str
    local_filepath: str
    source_url: str | None = None
    query_used: str | None = None
    media_type: str = "image"
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    page_title: str | None = None
    identifier: str | None = None
    clip_start_sec: float | None = None
    clip_duration_sec: float | None = None
    raw_metadata_path: str | None = None
    attribution: Attribution


class BeatManifest(BaseModel):
    beat_id: str
    beat_type: str
    duration_sec: float
    start_sec: float
    end_sec: float
    keywords: list[str] = Field(default_factory=list)
    search: dict[str, list[str]] = Field(default_factory=dict)
    pinned: dict[str, list[str]] = Field(default_factory=dict)
    overlays: list[str] = Field(default_factory=list)
    caption: str | None = None
    motion: dict[str, Any] = Field(default_factory=dict)
    noir: dict[str, Any] = Field(default_factory=dict)
    lower_third: dict[str, Any] | None = None
    quote: str | None = None
    source: str | None = None
    layout: str | None = None
    accent_word: str | None = None
    map: dict[str, Any] | None = None
    highlights: list[str] = Field(default_factory=list)
    arrows: list[dict[str, Any]] = Field(default_factory=list)
    labels: list[dict[str, Any]] = Field(default_factory=list)
    montage: dict[str, Any] | None = None
    sourcing_notes: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    assets: list[ManifestAsset] = Field(default_factory=list)
    render: list[RenderInstruction] = Field(default_factory=list)


class Manifest(BaseModel):
    episode_id: str
    title: str
    duration_target_sec: int
    theme: str
    font_family: str
    safe_margin_px: int
    accent_color: str
    fps: int
    aspect: str
    voice_mode: str
    narration_wav: str | None = None
    build_dir: str
    beats: list[BeatManifest]


def write_manifest(manifest: Manifest, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )


def read_manifest(path: str | Path) -> Manifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Manifest.model_validate(data)
