from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from scw_builder.manifest import Manifest


def build_animatic(manifest: Manifest, slides_dir: Path, output_path: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None

    sequence_dir = slides_dir / "_animatic_seq"
    if sequence_dir.exists():
        shutil.rmtree(sequence_dir)
    sequence_dir.mkdir(parents=True, exist_ok=True)

    frame_number = 1
    for index, beat in enumerate(manifest.beats, start=1):
        slide_path = slides_dir / f"{index:04d}.png"
        duration_sec = max(int(round(beat.duration_sec)), 1)
        for _ in range(duration_sec):
            sequence_frame = sequence_dir / f"frame_{frame_number:06d}.png"
            _link_or_copy(slide_path, sequence_frame)
            frame_number += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            "1",
            "-i",
            str(sequence_dir / "frame_%06d.png"),
            "-vf",
            f"fps={manifest.fps},format=yuv420p",
            "-preset",
            "ultrafast",
            "-tune",
            "stillimage",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    shutil.rmtree(sequence_dir, ignore_errors=True)
    return output_path


def _link_or_copy(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
