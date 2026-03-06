from __future__ import annotations

from dataclasses import dataclass

from scw_builder.episode_schema import BeatConfig


@dataclass(frozen=True)
class BeatTiming:
    beat: BeatConfig
    start_sec: float
    end_sec: float


def build_timings(beats: list[BeatConfig]) -> list[BeatTiming]:
    timings: list[BeatTiming] = []
    cursor = 0.0
    for beat in beats:
        start = cursor
        end = start + float(beat.duration_sec)
        timings.append(BeatTiming(beat=beat, start_sec=start, end_sec=end))
        cursor = end
    return timings
