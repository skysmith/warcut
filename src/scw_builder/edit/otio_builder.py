from __future__ import annotations

import json
from pathlib import Path

from scw_builder.manifest import Manifest


def write_otio_json(manifest: Manifest, output_path: Path) -> Path:
    children = []
    slides_dir = Path(manifest.build_dir) / "slides"
    for index, beat in enumerate(manifest.beats, start=1):
        video_assets = [asset for asset in beat.assets if asset.media_type == "video"]
        if video_assets:
            clip_asset = video_assets[0]
            clip_duration = clip_asset.clip_duration_sec or beat.duration_sec
            children.append(
                _otio_clip(
                    name=f"{beat.beat_id}_ia",
                    target_url=clip_asset.local_filepath,
                    fps=manifest.fps,
                    duration_sec=min(beat.duration_sec, clip_duration),
                )
            )
            remaining = beat.duration_sec - min(beat.duration_sec, clip_duration)
            if remaining > 0:
                still_asset = next(
                    (asset for asset in beat.assets if asset.media_type == "image"),
                    None,
                )
                children.append(
                    _otio_clip(
                        name=f"{beat.beat_id}_{'still_fill' if still_asset else 'ia_loop'}",
                        target_url=(still_asset or clip_asset).local_filepath,
                        fps=manifest.fps,
                        duration_sec=remaining,
                    )
                )
        else:
            slide_path = slides_dir / f"{index:04d}.png"
            children.append(
                _otio_clip(
                    name=beat.beat_id,
                    target_url=str(slide_path.resolve()),
                    fps=manifest.fps,
                    duration_sec=beat.duration_sec,
                )
            )
    timeline = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": manifest.title,
        "global_start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": 0, "rate": manifest.fps},
        "tracks": [
            {
                "OTIO_SCHEMA": "Track.1",
                "name": "Video 1",
                "kind": "Video",
                "children": children,
            }
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    return output_path


def _otio_clip(*, name: str, target_url: str, fps: int, duration_sec: float) -> dict:
    duration_frames = int(round(duration_sec * fps))
    return {
        "OTIO_SCHEMA": "Clip.2",
        "name": name,
        "media_reference": {
            "OTIO_SCHEMA": "ExternalReference.1",
            "target_url": target_url,
            "available_range": {
                "OTIO_SCHEMA": "TimeRange.1",
                "start_time": {
                    "OTIO_SCHEMA": "RationalTime.1",
                    "value": 0,
                    "rate": fps,
                },
                "duration": {
                    "OTIO_SCHEMA": "RationalTime.1",
                    "value": duration_frames,
                    "rate": fps,
                },
            },
        },
        "source_range": {
            "OTIO_SCHEMA": "TimeRange.1",
            "start_time": {
                "OTIO_SCHEMA": "RationalTime.1",
                "value": 0,
                "rate": fps,
            },
            "duration": {
                "OTIO_SCHEMA": "RationalTime.1",
                "value": duration_frames,
                "rate": fps,
            },
        },
    }
