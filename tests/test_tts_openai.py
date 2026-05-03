from pathlib import Path

from scw_builder.tts_openai import episode_narration_text, synthesize_episode_narration


def test_episode_narration_text_uses_episode_beat_order():
    text = episode_narration_text(Path("episodes/ep01.yaml"))

    assert text.index("you’re watching a country come apart.") < text.index(
        "to understand the spanish civil war"
    )
    assert "next episode:\nthe land question." in text


def test_tts_dry_run_writes_sidecar_without_api_key(tmp_path):
    output = tmp_path / "ep01-test.mp3"

    result = synthesize_episode_narration(
        Path("episodes/ep01.yaml"),
        output_path=output,
        dry_run=True,
    )

    assert result == output
    sidecar = output.with_suffix(".json")
    assert sidecar.exists()
    assert '"dry_run": true' in sidecar.read_text(encoding="utf-8")
