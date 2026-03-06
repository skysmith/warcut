from pathlib import Path

from scw_builder.episode_schema import load_episode
from scw_builder.plan.planner import plan_episode
from scw_builder.voice_cues import build_voice_cues, load_script_sections


def test_voice_cues_include_script_sections(tmp_path):
    episode = load_episode("episodes/ep01.yaml")
    episode.beats = episode.beats[:2]
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=True,
        allow_partial=True,
    )
    sections = load_script_sections(Path("episodes/ep01.script.md"))
    cues = build_voice_cues(manifest, sections)

    assert cues[0]["beat_id"] == "cold_open_montage"
    assert "you’re watching a country come apart." in cues[0]["script"]
    assert cues[1]["beat_id"] == "thesis"
    assert "this isn’t just left versus right." in cues[1]["script"]
