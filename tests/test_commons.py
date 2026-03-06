import json
from pathlib import Path

from scw_builder.episode_schema import load_episode
from scw_builder.plan.planner import _expand_queries, plan_episode
from scw_builder.sources.commons import (
    CommonsSelectionOptions,
    get_file_metadata,
    search_commons,
    select_assets_by_title,
    select_assets_for_beat,
)
from scw_builder.sources.licenses import normalize_commons_attribution


FIXTURES = Path("tests/fixtures")


def test_search_and_metadata_load_from_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "search_barcelona-1936-militia_2.json").write_text(
        (FIXTURES / "commons_search_barcelona-1936-militia_2.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (cache_dir / "metadata_file-valid-commons-photo-jpg.json").write_text(
        (FIXTURES / "commons_metadata_file-valid-commons-photo-jpg.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    results = search_commons(
        "Barcelona 1936 militia",
        limit=2,
        cache_dir=cache_dir,
        offline=True,
    )
    metadata = get_file_metadata(
        "File:Valid Commons Photo.jpg",
        cache_dir=cache_dir,
        offline=True,
    )

    assert results[0]["title"] == "File:Valid Commons Photo.jpg"
    assert metadata["query"]["pages"]["101"]["imageinfo"][0]["mime"] == "image/jpeg"


def test_filtering_and_attribution_extraction(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    for fixture in FIXTURES.glob("commons_*.json"):
        target_name = fixture.name.replace("commons_", "", 1)
        (cache_dir / target_name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    options = CommonsSelectionOptions(
        assets_dir=tmp_path / "assets",
        cache_dir=cache_dir,
        limit=2,
        min_width=1400,
        min_height=1400,
        require_attribution=True,
        offline=True,
        no_download=True,
    )
    assets = select_assets_for_beat("cold_open", "Barcelona 1936 militia", options)

    assert len(assets) == 1
    asset = assets[0]
    assert asset.page_title == "File:Valid Commons Photo.jpg"
    assert asset.mime_type == "image/jpeg"
    assert asset.width == 1800
    assert asset.height == 1500
    assert asset.raw_metadata_path is not None

    metadata = json.loads(Path(asset.raw_metadata_path).read_text(encoding="utf-8"))
    attribution = normalize_commons_attribution(
        asset.page_title,
        metadata,
        asset.source_url,
    )
    assert attribution.author == "Jane Example"
    assert attribution.license_name == "CC BY-SA 4.0"
    assert attribution.license_url == "https://creativecommons.org/licenses/by-sa/4.0/"


def test_plan_episode_prefers_pinned_commons_without_fallback_spillover(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    for fixture in FIXTURES.glob("commons_*.json"):
        target_name = fixture.name.replace("commons_", "", 1)
        (cache_dir / target_name).write_text(
            fixture.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    # Inject an unrelated metadata record under the cached title we know exists
    unrelated_metadata = json.loads(
        (FIXTURES / "commons_metadata_file-valid-commons-photo-jpg.json").read_text(
            encoding="utf-8"
        )
    )
    page = unrelated_metadata["query"]["pages"]["101"]
    page["title"] = "File:Totally Unrelated Orwell Portrait.jpg"
    (cache_dir / "metadata_file-totally-unrelated-orwell-portrait-jpg.json").write_text(
        json.dumps(unrelated_metadata),
        encoding="utf-8",
    )

    search_data = json.loads(
        (FIXTURES / "commons_search_barcelona-1936-militia_2.json").read_text(
            encoding="utf-8"
        )
    )
    search_data["query"]["search"].append(
        {
            "title": "File:Totally Unrelated Orwell Portrait.jpg",
            "pageid": 202,
        }
    )
    (cache_dir / "search_barcelona-1936-militia_3.json").write_text(
        json.dumps(search_data),
        encoding="utf-8",
    )

    build_cache_dir = tmp_path / "build" / "ep01" / "assets" / "_cache" / "commons"
    build_cache_dir.mkdir(parents=True)
    for cached in cache_dir.iterdir():
        (build_cache_dir / cached.name).write_text(cached.read_text(encoding="utf-8"), encoding="utf-8")

    episode = load_episode("episodes/ep01_smoke.yaml")
    episode.beats = episode.beats[:1]
    episode.sources.commons.max_assets_per_beat = 3
    episode.beats[0].pinned = {"commons_titles": ["File:Valid Commons Photo.jpg"]}
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=True,
        allow_partial=True,
    )
    assert [asset.page_title for asset in manifest.beats[0].assets] == ["File:Valid Commons Photo.jpg"]


def test_select_assets_by_title_from_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "metadata_file-valid-commons-photo-jpg.json").write_text(
        (FIXTURES / "commons_metadata_file-valid-commons-photo-jpg.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    options = CommonsSelectionOptions(
        assets_dir=tmp_path / "assets",
        cache_dir=cache_dir,
        limit=1,
        min_width=1400,
        min_height=1400,
        require_attribution=True,
        offline=True,
        no_download=True,
    )
    asset = select_assets_by_title("beat1", "File:Valid Commons Photo.jpg", options)
    assert asset is not None
    assert asset.page_title == "File:Valid Commons Photo.jpg"


def test_plan_episode_populates_manifest_with_commons_assets(tmp_path):
    cache_dir = tmp_path / "build" / "ep01" / "assets" / "_cache" / "commons"
    cache_dir.mkdir(parents=True)
    for fixture in FIXTURES.glob("commons_*.json"):
        target_name = fixture.name.replace("commons_", "", 1)
        (cache_dir / target_name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    episode = load_episode("episodes/ep01.yaml")
    episode.beats = episode.beats[:1]
    episode.sources.commons.max_assets_per_beat = 2
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=True,
    )

    asset = manifest.beats[0].assets[0]
    assert asset.provider == "commons"
    assert asset.local_filepath.endswith(".jpg")
    assert asset.source_url == "https://commons.wikimedia.org/wiki/File:Valid_Commons_Photo.jpg"
    assert asset.attribution.author == "Jane Example"
    assert asset.attribution.license_name == "CC BY-SA 4.0"


def test_expand_queries_adds_fallbacks():
    queries = _expand_queries(
        ["Barcelona 1936 militia"],
        beat_type="montage",
        provider="commons",
        warm_cache=True,
    )
    assert "Barcelona 1936 militia" in queries
    assert "Barcelona militia" in queries
    assert "Catalonia 1936 militia" in queries
    assert "Barcelona 1936 militia poster" in queries
    assert "Barcelona 1936 militia republican" in queries


def test_plan_episode_records_suggested_queries(tmp_path):
    cache_dir = tmp_path / "build" / "ep01" / "assets" / "_cache" / "commons"
    cache_dir.mkdir(parents=True)
    episode = load_episode("episodes/ep01_smoke.yaml")
    episode.beats = episode.beats[-1:]
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=True,
        allow_partial=True,
    )
    assert manifest.beats[0].suggested_queries


def test_plan_episode_prefers_pinned_commons_titles(tmp_path):
    cache_dir = tmp_path / "build" / "ep01" / "assets" / "_cache" / "commons"
    cache_dir.mkdir(parents=True)
    (cache_dir / "metadata_file-valid-commons-photo-jpg.json").write_text(
        (FIXTURES / "commons_metadata_file-valid-commons-photo-jpg.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    episode = load_episode("episodes/ep01_smoke.yaml")
    episode.beats = episode.beats[:1]
    episode.beats[0].pinned = {"commons_titles": ["File:Valid Commons Photo.jpg"]}
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=True,
        allow_partial=True,
    )
    assert manifest.beats[0].assets[0].page_title == "File:Valid Commons Photo.jpg"


def test_archival_clip_prefers_ia_suggested_queries(tmp_path):
    episode = load_episode("episodes/ep01_smoke.yaml")
    episode.beats = [beat for beat in episode.beats if beat.id == "archival_reel"]
    manifest = plan_episode(
        episode,
        tmp_path / "build" / "ep01",
        offline=True,
        no_download=True,
        allow_partial=True,
    )
    assert any("prelinger" in query or "newsreel" in query for query in manifest.beats[0].suggested_queries)
