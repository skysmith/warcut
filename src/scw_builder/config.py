from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildPaths:
    root: Path
    episode_id: str

    @property
    def build_dir(self) -> Path:
        return self.root / "build" / self.episode_id

    @property
    def assets_dir(self) -> Path:
        return self.build_dir / "assets"

    @property
    def slides_dir(self) -> Path:
        return self.build_dir / "slides"

    @property
    def timeline_dir(self) -> Path:
        return self.build_dir / "timeline"

    @property
    def manifest_path(self) -> Path:
        return self.build_dir / "manifest.json"

    @property
    def credits_path(self) -> Path:
        return self.build_dir / "credits.md"

    @property
    def animatic_path(self) -> Path:
        return self.build_dir / "animatic.mp4"

    @property
    def coverage_path(self) -> Path:
        return self.build_dir / "coverage.json"

    @property
    def voice_cues_md_path(self) -> Path:
        return self.build_dir / "voice_cues.md"

    @property
    def voice_cues_json_path(self) -> Path:
        return self.build_dir / "voice_cues.json"


def repo_root_from_episode(episode_path: Path) -> Path:
    return episode_path.resolve().parent.parent


def curated_assets_root(root: Path) -> Path:
    return root / "assets_curated"
