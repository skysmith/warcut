from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class VoiceConfig(BaseModel):
    mode: Literal["voice_only", "narration_sync"] = "voice_only"
    narration_wav: str | None = None


class StyleConfig(BaseModel):
    theme: str = "noir_doc"
    aspect: Literal["16:9", "9:16", "1:1"] = "16:9"
    fps: int = Field(default=30, ge=1, le=120)
    font_family: str = "Inter"
    safe_margin_px: int = Field(default=80, ge=0)
    accent_color: Literal["burnt_red", "brassy_gold", "cold_blue"] = "burnt_red"


class BeatConfig(BaseModel):
    id: str
    type: str
    duration_sec: int = Field(ge=1)
    keywords: list[str] = Field(default_factory=list)
    search: dict[str, list[str]] = Field(default_factory=dict)
    pinned: dict[str, list[str]] = Field(default_factory=dict)
    must_include: list[str] = Field(default_factory=list)
    on_screen_text: list[str] = Field(default_factory=list)
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


class CommonsSourceConfig(BaseModel):
    max_assets_per_beat: int = Field(default=6, ge=1)
    min_resolution_px: int = Field(default=1400, ge=1)
    min_width_px: int | None = Field(default=None, ge=1)
    min_height_px: int | None = Field(default=None, ge=1)

    @property
    def effective_min_width_px(self) -> int:
        return self.min_width_px or self.min_resolution_px

    @property
    def effective_min_height_px(self) -> int:
        return self.min_height_px or self.min_resolution_px


class InternetArchiveSourceConfig(BaseModel):
    max_assets_per_beat: int = Field(default=2, ge=1)
    max_clip_sec: int = Field(default=12, ge=1)


class SourcesConfig(BaseModel):
    enable_commons: bool = True
    enable_internet_archive: bool = True
    commons: CommonsSourceConfig = Field(default_factory=CommonsSourceConfig)
    internet_archive: InternetArchiveSourceConfig = Field(
        default_factory=InternetArchiveSourceConfig
    )


class GuardrailsConfig(BaseModel):
    require_license_metadata: bool = True
    block_ai_generated_archival: bool = True
    require_source_urls_in_credits: bool = True


class EpisodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    duration_target_sec: int = Field(ge=1)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    style: StyleConfig = Field(default_factory=StyleConfig)
    beats: list[BeatConfig]
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)


def load_episode(path: str | Path) -> EpisodeConfig:
    episode_path = Path(path)
    data = yaml.safe_load(episode_path.read_text(encoding="utf-8"))
    return EpisodeConfig.model_validate(data)
