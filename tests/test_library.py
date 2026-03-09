import json
from pathlib import Path

from scw_builder.library import ingest_manifest
from scw_builder.manifest import Attribution, BeatManifest, Manifest, ManifestAsset, RenderInstruction


def test_ingest_manifest_creates_curated_library(tmp_path):
    source_file = tmp_path / "source.jpg"
    source_file.write_bytes(b"fake-image")

    manifest = Manifest(
        episode_id="ep01",
        title="many spains",
        duration_target_sec=100,
        theme="noir_doc",
        font_family="Inter",
        safe_margin_px=80,
        accent_color="burnt_red",
        fps=30,
        aspect="16:9",
        voice_mode="voice_only",
        build_dir=str((tmp_path / "build" / "ep01").resolve()),
        beats=[
            BeatManifest(
                beat_id="vignette_catalonia",
                beat_type="still",
                duration_sec=10,
                start_sec=0,
                end_sec=10,
                keywords=["Barcelona 1936 militia", "CNT poster"],
                caption="CATALONIA",
                pinned={"local_files": [str(source_file)]},
                assets=[
                    ManifestAsset(
                        asset_id="a1",
                        provider="local",
                        local_filepath=str(source_file.resolve()),
                        media_type="image",
                        mime_type="image/jpeg",
                        attribution=Attribution(
                            title="source.jpg",
                            author="Local asset",
                            license_name="User supplied",
                        ),
                    )
                ],
                render=[RenderInstruction(start_sec=0, duration_sec=10)],
            )
        ],
    )

    curated_root = tmp_path / "assets_curated"
    records = ingest_manifest(manifest, curated_root)

    assert len(records) == 1
    record = records[0]
    assert record.tags["region"] == ["catalonia"]
    assert "militia" in record.tags["theme"]
    assert record.tags["quality"] == "strong"
    assert (curated_root / "library.json").exists()
    assert (curated_root / "items" / f"{record.asset_key}.json").exists()
    copied = curated_root / record.curated_filepath
    assert copied.exists()

    summary = json.loads((curated_root / "library.json").read_text(encoding="utf-8"))
    assert summary[0]["asset_key"] == record.asset_key
