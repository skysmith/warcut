import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scw_builder.edit.otio_builder import write_otio_json
from scw_builder.episode_schema import load_episode
from scw_builder.manifest import Attribution, ManifestAsset
from scw_builder.plan.planner import plan_episode
from scw_builder.sources.internet_archive import (
    IASelectionOptions,
    _build_ia_query,
    get_item_metadata,
    search_ia,
    select_clip_by_identifier,
    select_clips_for_beat,
)


FIXTURES = Path("tests/fixtures")


def test_ia_search_and_metadata_from_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "search_barcelona-1936-militia_2.json").write_text(
        (FIXTURES / "ia_search_barcelona-1936-militia_2.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (cache_dir / "metadata_prelinger-test-reel.json").write_text(
        (FIXTURES / "ia_metadata_prelinger-test-reel.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    results = search_ia("Barcelona 1936 militia", limit=2, cache_dir=cache_dir, offline=True)
    metadata = get_item_metadata("prelinger-test-reel", cache_dir=cache_dir, offline=True)
    assert results[0]["identifier"] == "prelinger-test-reel"
    assert metadata["metadata"]["rights"] == "Public domain"


def test_build_ia_query_targets_movie_collections():
    query = _build_ia_query("Spanish Civil War newsreel Barcelona 1936")
    assert "mediatype:(movies)" in query
    assert "collection:prelinger" in query
    assert 'title:("Spanish Civil War newsreel Barcelona 1936")' in query


def test_ia_selects_trimmed_clip_without_network(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    for fixture in FIXTURES.glob("ia_*.json"):
        target_name = fixture.name.replace("ia_", "", 1)
        (cache_dir / target_name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    source_video = tmp_path / "cache_video.mp4"
    source_video.write_bytes(b"video")

    def fake_download(*args, **kwargs):
        return source_video, {"name": "prelinger_test_reel_h264.mp4", "format": "h.264 IA"}

    def fake_trim(input_path, start_sec, duration_sec, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"trimmed")
        return output_path

    monkeypatch.setattr(
        "scw_builder.sources.internet_archive.download_best_derivative",
        fake_download,
    )
    monkeypatch.setattr("scw_builder.sources.internet_archive.trim_clip", fake_trim)

    options = IASelectionOptions(
        assets_dir=tmp_path / "assets",
        cache_dir=cache_dir,
        limit=2,
        max_clip_sec=12,
        offline=True,
        no_download=False,
    )
    assets = select_clips_for_beat("cold_open", "Barcelona 1936 militia", options, fps=30)
    assert len(assets) == 1
    assert assets[0].provider == "internet_archive"
    assert assets[0].clip_duration_sec == 12
    assert Path(assets[0].local_filepath).exists()
    metadata = json.loads(Path(assets[0].raw_metadata_path).read_text(encoding="utf-8"))
    assert metadata["metadata"]["identifier"] == "prelinger-test-reel"


def test_select_clip_by_identifier_without_network(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "metadata_prelinger-test-reel.json").write_text(
        (FIXTURES / "ia_metadata_prelinger-test-reel.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    source_video = tmp_path / "cache_video.mp4"
    source_video.write_bytes(b"video")
    monkeypatch.setattr(
        "scw_builder.sources.internet_archive.download_best_derivative",
        lambda *args, **kwargs: (source_video, {"name": "prelinger_test_reel_h264.mp4"}),
    )
    monkeypatch.setattr(
        "scw_builder.sources.internet_archive.trim_clip",
        lambda input_path, start_sec, duration_sec, output_path, **kwargs: output_path.parent.mkdir(parents=True, exist_ok=True) or output_path.write_bytes(b"trimmed") or output_path,
    )
    options = IASelectionOptions(
        assets_dir=tmp_path / "assets",
        cache_dir=cache_dir,
        limit=1,
        max_clip_sec=8,
        offline=True,
        no_download=False,
    )
    asset = select_clip_by_identifier("beat1", "prelinger-test-reel", options, fps=30)
    assert asset is not None
    assert asset.identifier == "prelinger-test-reel"


def test_plan_and_timeline_use_ia_clips(tmp_path, monkeypatch):
    clip_path = tmp_path / "build" / "ep01" / "assets" / "ia_clips" / "cold_open_clip.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"trimmed")
    monkeypatch.setattr(
        "scw_builder.plan.planner._collect_commons_assets",
        lambda *args, **kwargs: ([], []),
    )
    monkeypatch.setattr(
        "scw_builder.plan.planner._collect_ia_assets",
        lambda *args, **kwargs: (
            [
                ManifestAsset(
                    asset_id="cold_open-prelinger-test-reel",
                    provider="internet_archive",
                    local_filepath=str(clip_path.resolve()),
                    source_url="https://archive.org/details/prelinger-test-reel",
                    query_used="Barcelona 1936 militia",
                    media_type="video",
                    mime_type="video/mp4",
                    identifier="prelinger-test-reel",
                    clip_start_sec=0.0,
                    clip_duration_sec=12.0,
                    raw_metadata_path=str((clip_path.parent / "cold_open_clip.mp4.json").resolve()),
                    attribution=Attribution(
                        title="Prelinger Test Reel",
                        author="Archive Tester",
                        creator="Archive Tester",
                        date="1936",
                        identifier="prelinger-test-reel",
                        license_name="Public domain",
                        license_url="https://creativecommons.org/publicdomain/mark/1.0/",
                        rights_statement="Public domain",
                        source_url="https://archive.org/details/prelinger-test-reel",
                    ),
                )
            ],
            [],
        ),
    )

    episode = load_episode("episodes/ep01.yaml")
    episode.beats = episode.beats[:1]
    episode.sources.internet_archive.max_assets_per_beat = 1
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=False,
    )
    otio_path = write_otio_json(manifest, tmp_path / "build" / "ep01" / "timeline" / "ep01.otio")
    otio = json.loads(otio_path.read_text(encoding="utf-8"))
    first_clip = otio["tracks"][0]["children"][0]
    assert manifest.beats[0].assets[0].provider == "internet_archive"
    assert first_clip["name"].endswith("_ia")


@pytest.mark.skipif(os.environ.get("SCW_LIVE_TESTS") != "1", reason="live IA test disabled")
def test_live_ia_search():
    results = search_ia("Barcelona 1936 militia", limit=1, offline=False)
    assert results


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_trim_clip_integration(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    source_video = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=2",
            str(source_video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    from scw_builder.utils.video import trim_clip

    output = trim_clip(source_video, 0.0, 1.0, tmp_path / "trimmed.mp4", fps=30)
    assert output.exists()
