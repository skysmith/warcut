from pathlib import Path

import yaml

from scw_builder.cli import _cmd_build


def test_build_writes_outputs(tmp_path, monkeypatch):
    root = tmp_path / "warcut"
    episodes = root / "episodes"
    episodes.mkdir(parents=True)
    episode_data = yaml.safe_load(Path("episodes/ep01.yaml").read_text(encoding="utf-8"))
    episode_data["beats"] = [episode_data["beats"][0]]
    (episodes / "ep01.yaml").write_text(yaml.safe_dump(episode_data), encoding="utf-8")
    monkeypatch.setattr("scw_builder.cli.build_animatic", lambda *args, **kwargs: None)
    fixtures = Path("tests/fixtures")
    search_payload = (fixtures / "commons_search_barcelona-1936-militia_2.json").read_text(
        encoding="utf-8"
    )
    metadata_payload = (
        fixtures / "commons_metadata_file-valid-commons-photo-jpg.json"
    ).read_text(encoding="utf-8")
    monkeypatch.setattr(
        "scw_builder.sources.commons.search_commons",
        lambda *args, **kwargs: yaml.safe_load(search_payload)["query"]["search"],
    )
    monkeypatch.setattr(
        "scw_builder.sources.commons.get_file_metadata",
        lambda *args, **kwargs: yaml.safe_load(metadata_payload),
    )
    monkeypatch.chdir(root)
    _cmd_build(episodes / "ep01.yaml", offline=True, no_download=True)

    assert (root / "build" / "ep01" / "manifest.json").exists()
    assert (root / "build" / "ep01" / "credits.md").exists()
    assert (root / "build" / "ep01" / "slides" / "0001.png").exists()
    assert (root / "build" / "ep01" / "timeline" / "ep01.otio").exists()
    assert (root / "build" / "ep01" / "coverage.json").exists()
