from __future__ import annotations

import json
import re
from pathlib import Path

from scw_builder.manifest import Manifest


HEADING_RE = re.compile(r"^##\s+([A-Za-z0-9_]+)\s*$")


def script_path_for_episode(episode_path: Path) -> Path:
    return episode_path.with_suffix(".script.md")


def load_script_sections(script_path: Path) -> dict[str, str]:
    if not script_path.exists():
        return {}
    sections: dict[str, list[str]] = {}
    current_id: str | None = None
    for raw_line in script_path.read_text(encoding="utf-8").splitlines():
        heading = HEADING_RE.match(raw_line.strip())
        if heading:
            current_id = heading.group(1)
            sections.setdefault(current_id, [])
            continue
        if current_id is None:
            continue
        sections[current_id].append(raw_line.rstrip())
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def build_voice_cues(manifest: Manifest, script_sections: dict[str, str]) -> list[dict[str, object]]:
    cues: list[dict[str, object]] = []
    for beat in manifest.beats:
        cues.append(
            {
                "beat_id": beat.beat_id,
                "beat_type": beat.beat_type,
                "start_sec": beat.start_sec,
                "end_sec": beat.end_sec,
                "duration_sec": beat.duration_sec,
                "caption": beat.caption,
                "on_screen_text": beat.overlays,
                "script": script_sections.get(beat.beat_id, ""),
            }
        )
    return cues


def write_voice_cues_markdown(cues: list[dict[str, object]], path: Path) -> None:
    lines = ["# Voice Cues", ""]
    for cue in cues:
        lines.append(f"## {cue['beat_id']}")
        lines.append(f"- Start: {_fmt_time(float(cue['start_sec']))}")
        lines.append(f"- End: {_fmt_time(float(cue['end_sec']))}")
        lines.append(f"- Duration: {float(cue['duration_sec']):.1f}s")
        if cue.get("caption"):
            lines.append(f"- Caption: {cue['caption']}")
        if cue.get("on_screen_text"):
            lines.append("- On-screen:")
            for line in cue["on_screen_text"]:
                lines.append(f"  - {line}")
        script = str(cue.get("script", "")).strip()
        if script:
            lines.append("- Script:")
            lines.append("")
            lines.append(script)
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_voice_cues_json(cues: list[dict[str, object]], path: Path) -> None:
    path.write_text(json.dumps(cues, indent=2), encoding="utf-8")


def _fmt_time(total_seconds: float) -> str:
    total = int(round(total_seconds))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
