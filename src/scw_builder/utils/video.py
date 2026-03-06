from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


def trim_clip(
    input_path: Path,
    start_sec: float,
    duration_sec: float,
    output_path: Path,
    *,
    fps: int | None = None,
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to trim Internet Archive clips")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    copy_cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{duration_sec:.3f}",
        "-c",
        "copy",
        str(output_path),
    ]
    try:
        subprocess.run(
            copy_cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return output_path
    except subprocess.CalledProcessError:
        filter_parts = ["format=yuv420p"]
        if fps:
            filter_parts.insert(0, f"fps={fps}")
        reencode_cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            str(input_path),
            "-t",
            f"{duration_sec:.3f}",
            "-vf",
            ",".join(filter_parts),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            str(output_path),
        ]
        subprocess.run(
            reencode_cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return output_path


def clip_hash(identifier: str, start_sec: float, duration_sec: float) -> str:
    payload = f"{identifier}:{start_sec:.3f}:{duration_sec:.3f}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
