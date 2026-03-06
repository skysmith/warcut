from pathlib import Path

from scw_builder.episode_schema import load_episode
from scw_builder.plan.planner import plan_episode
from scw_builder.sources.local import build_local_asset


def test_build_local_asset_image(tmp_path):
    image_path = tmp_path / "poster.png"
    image_path.write_bytes(b"fake")
    asset = build_local_asset("beat1", image_path)
    assert asset is not None
    assert asset.provider == "local"
    assert asset.media_type == "image"


def test_plan_episode_uses_local_pinned_file(tmp_path):
    image_path = tmp_path / "poster.png"
    image_path.write_bytes(b"fake")
    episode = load_episode("episodes/ep01_smoke.yaml")
    episode.beats = episode.beats[-1:]
    episode.beats[0].pinned = {"local_files": [str(image_path)]}
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=True,
        allow_partial=True,
    )
    assert manifest.beats[0].assets[0].provider == "local"
    assert manifest.beats[0].assets[0].local_filepath == str(image_path.resolve())
