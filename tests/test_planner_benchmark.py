import json

from scw_builder.benchmark import run_planner_benchmark
from scw_builder.cli import _cmd_benchmark_planner


def test_run_planner_benchmark_returns_stable_shape():
    result = run_planner_benchmark()

    assert result.total_required_beats == 4
    assert result.covered_required_beats >= 3
    assert result.planner_score > 40
    assert len(result.beat_results) == 5
    cold_open = next(beat for beat in result.beat_results if beat.beat_id == "cold_open")
    archival = next(beat for beat in result.beat_results if beat.beat_id == "archival_reel")
    assert cold_open.used_assets >= 1
    assert archival.used_assets >= 1


def test_benchmark_cli_json_output(capsys):
    _cmd_benchmark_planner(json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["planner_score"] > 40
    assert payload["total_required_beats"] == 4
    assert any(beat["beat_id"] == "union_posters" for beat in payload["beats"])
