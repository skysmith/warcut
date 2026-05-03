from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def mux_narration(
    *,
    animatic_path: Path,
    narration_path: Path,
    output_path: Path,
    fit_narration: bool = False,
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    if not animatic_path.exists():
        raise FileNotFoundError(f"animatic not found: {animatic_path}")
    if not narration_path.exists():
        raise FileNotFoundError(f"narration not found: {narration_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_args: list[str]
    if fit_narration:
        video_duration = _media_duration(animatic_path)
        narration_duration = _media_duration(narration_path)
        if video_duration <= 0 or narration_duration <= 0:
            raise RuntimeError("could not determine media durations for fit-narration render")
        speed_ratio = narration_duration / video_duration
        video_args = [
            "-filter:v",
            f"setpts={speed_ratio:.8f}*PTS,fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "stillimage",
        ]
    else:
        video_args = ["-c:v", "copy"]

    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(animatic_path),
            "-i",
            str(narration_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            *video_args,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
    )
    return output_path


def _media_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return float(result.stdout.strip())
