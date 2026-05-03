from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from scw_builder.config import BuildPaths, repo_root_from_episode
from scw_builder.episode_schema import load_episode
from scw_builder.manifest import read_manifest
from scw_builder.utils.files import ensure_dir
from scw_builder.voice_cues import load_script_sections, script_path_for_episode


OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "nova"
DEFAULT_TTS_FORMAT = "mp3"
DEFAULT_TTS_INSTRUCTIONS = (
    "Perform a clear, restrained documentary narration. Keep it intimate and serious, "
    "with natural pauses and no added sound effects."
)


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def episode_narration_text(episode_path: Path) -> str:
    episode = load_episode(episode_path)
    sections = load_script_sections(script_path_for_episode(episode_path))
    parts = [sections.get(beat.id, "").strip() for beat in episode.beats]
    return "\n\n".join(part for part in parts if part)


def synthesize_episode_narration(
    episode_path: Path,
    *,
    model: str = DEFAULT_TTS_MODEL,
    voice: str = DEFAULT_TTS_VOICE,
    audio_format: str = DEFAULT_TTS_FORMAT,
    instructions: str = DEFAULT_TTS_INSTRUCTIONS,
    env_file: Path | None = None,
    output_path: Path | None = None,
    dry_run: bool = False,
) -> Path:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)
    if env_file:
        load_env_file(env_file.expanduser())

    text = episode_narration_text(episode_path)
    if not text:
        raise ValueError(f"no script text found for {episode_path}")

    narration_dir = paths.build_dir / "narration"
    if output_path is None:
        output_path = narration_dir / f"{episode.id}-openai-tts.{audio_format}"
    if output_path.suffix.lstrip(".") != audio_format:
        output_path = output_path.with_suffix(f".{audio_format}")

    sidecar_path = output_path.with_suffix(".json")
    metadata = {
        "created": datetime.now(UTC).isoformat(),
        "episode_id": episode.id,
        "model": model,
        "voice": voice,
        "format": audio_format,
        "instructions": instructions,
        "audio_path": str(output_path.resolve()),
        "script_path": str(script_path_for_episode(episode_path).resolve()),
        "text_chars": len(text),
        "text_preview": text[:240],
    }

    if dry_run:
        ensure_dir(output_path.parent)
        sidecar_path.write_text(
            json.dumps({**metadata, "dry_run": True}, indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Set it in the shell or pass --env-file "
            "pointing at a local env file that contains OPENAI_API_KEY."
        )

    payload = json.dumps(
        {
            "model": model,
            "voice": voice,
            "input": text,
            "instructions": instructions,
            "response_format": audio_format,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_SPEECH_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            audio = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI speech request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI speech request failed: {exc}") from exc

    ensure_dir(output_path.parent)
    output_path.write_bytes(audio)
    sidecar_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return output_path


def update_manifest_narration(episode_path: Path, narration_path: Path) -> Path:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)
    manifest = read_manifest(paths.manifest_path)
    manifest.narration_wav = str(narration_path.resolve())
    paths.manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return paths.manifest_path
