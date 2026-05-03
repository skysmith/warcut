from __future__ import annotations

import argparse
import json
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scw_builder.episode_schema import load_episode
from scw_builder.manifest import Manifest
from scw_builder.plan.planner import _beat_requires_sourced_assets, plan_episode


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_EPISODE_PATH = REPO_ROOT / "episodes" / "autoresearch_planner.yaml"


def _normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def _commons_metadata(
    *,
    page_id: int,
    title: str,
    width: int,
    height: int,
    author: str,
    license_name: str = "CC BY-SA 4.0",
    license_url: str = "https://creativecommons.org/licenses/by-sa/4.0/",
    missing_attribution: bool = False,
) -> dict[str, Any]:
    extmetadata = {
        "ObjectName": {"value": title},
        "Artist": {"value": author},
        "Credit": {"value": author},
        "LicenseShortName": {"value": license_name},
        "LicenseUrl": {"value": license_url},
        "Attribution": {"value": author},
    }
    if missing_attribution:
        extmetadata.pop("Artist", None)
        extmetadata.pop("Credit", None)
    stem = title.replace("File:", "").replace(" ", "_")
    return {
        "query": {
            "pages": {
                str(page_id): {
                    "pageid": page_id,
                    "title": title,
                    "imageinfo": [
                        {
                            "url": f"https://commons.wikimedia.org/wiki/Special:FilePath/{stem}",
                            "descriptionurl": f"https://commons.wikimedia.org/wiki/{stem}",
                            "mime": "image/jpeg",
                            "width": width,
                            "height": height,
                            "extmetadata": extmetadata,
                        }
                    ],
                }
            }
        }
    }


def _ia_metadata(
    *,
    identifier: str,
    title: str,
    creator: str,
    rights: str,
    license_url: str,
) -> dict[str, Any]:
    return {
        "metadata": {
            "identifier": identifier,
            "title": title,
            "creator": creator,
            "date": "1936",
            "rights": rights,
            "licenseurl": license_url,
        },
        "files": [
            {
                "name": f"{identifier}_512kb.mp4",
                "format": "h.264",
                "source": "derivative",
                "size": "1048576",
            }
        ],
    }


COMMONS_SEARCH_RESULTS = {
    _normalize_query("Barcelona 1936 militia"): [
        {"title": "File:Crowd Street Scene Blurry.jpg", "pageid": 101},
        {"title": "File:Lowres Poster.png", "pageid": 102},
    ],
    _normalize_query("Barcelona militia"): [
        {"title": "File:Barcelona Militia Street.jpg", "pageid": 103},
    ],
    _normalize_query("Catalonia 1936 militia"): [
        {"title": "File:Workers Barricade Poster.jpg", "pageid": 104},
    ],
    _normalize_query("Spain civil war 1936 street scene"): [
        {"title": "File:Workers Barricade Poster.jpg", "pageid": 104},
    ],
    _normalize_query("CNT Barcelona"): [
        {"title": "File:CNT Meeting Leaflet.jpg", "pageid": 105},
        {"title": "File:Lowres Poster.png", "pageid": 102},
    ],
    _normalize_query("Catalonia Barcelona"): [
        {"title": "File:LLEGIU Catalunya.jpg", "pageid": 106},
    ],
    _normalize_query("Confederacion Nacional del Trabajo Barcelona"): [
        {"title": "File:CNT-AIT-FAI.jpg", "pageid": 107},
    ],
    _normalize_query("CNT FAI UGT poster Spain"): [
        {"title": "File:LLEGIU Catalunya.jpg", "pageid": 106},
        {"title": "File:CNT-AIT-FAI.jpg", "pageid": 107},
    ],
    _normalize_query("Spanish Civil War poster Barcelona"): [
        {"title": "File:LLEGIU Catalunya.jpg", "pageid": 106},
    ],
    _normalize_query("Spanish election press Barcelona"): [],
    _normalize_query("Spanish Civil War newspaper Barcelona"): [
        {"title": "File:1936 elections, Barcelona.jpg", "pageid": 108},
    ],
    _normalize_query("Spanish election posters 1936"): [
        {"title": "File:1936 elections, Barcelona.jpg", "pageid": 108},
        {"title": "File:Spain, electoral districts 1933-1936.jpg", "pageid": 109},
    ],
    _normalize_query("Spanish Civil War poster"): [
        {"title": "File:Spain, electoral districts 1933-1936.jpg", "pageid": 109},
    ],
}


COMMONS_METADATA = {
    "File:Crowd Street Scene Blurry.jpg": _commons_metadata(
        page_id=101,
        title="File:Crowd Street Scene Blurry.jpg",
        width=1600,
        height=1200,
        author="Archive Photographer",
    ),
    "File:Lowres Poster.png": _commons_metadata(
        page_id=102,
        title="File:Lowres Poster.png",
        width=420,
        height=420,
        author="Unknown",
        missing_attribution=True,
    ),
    "File:Barcelona Militia Street.jpg": _commons_metadata(
        page_id=103,
        title="File:Barcelona Militia Street.jpg",
        width=2200,
        height=1600,
        author="Republican Press Office",
    ),
    "File:Workers Barricade Poster.jpg": _commons_metadata(
        page_id=104,
        title="File:Workers Barricade Poster.jpg",
        width=2000,
        height=1600,
        author="Workers Graphics Cooperative",
    ),
    "File:CNT Meeting Leaflet.jpg": _commons_metadata(
        page_id=105,
        title="File:CNT Meeting Leaflet.jpg",
        width=1400,
        height=1100,
        author="CNT Press",
    ),
    "File:LLEGIU Catalunya.jpg": _commons_metadata(
        page_id=106,
        title="File:LLEGIU Catalunya.jpg",
        width=1900,
        height=1500,
        author="Catalan Propaganda Service",
    ),
    "File:CNT-AIT-FAI.jpg": _commons_metadata(
        page_id=107,
        title="File:CNT-AIT-FAI.jpg",
        width=1800,
        height=1500,
        author="CNT Archive",
    ),
    "File:1936 elections, Barcelona.jpg": _commons_metadata(
        page_id=108,
        title="File:1936 elections, Barcelona.jpg",
        width=2100,
        height=1600,
        author="Barcelona Municipal Archive",
    ),
    "File:Spain, electoral districts 1933-1936.jpg": _commons_metadata(
        page_id=109,
        title="File:Spain, electoral districts 1933-1936.jpg",
        width=2000,
        height=1600,
        author="Election Atlas Office",
    ),
}


IA_SEARCH_RESULTS = {
    _normalize_query("Madrid 1936 crowds"): [
        {
            "identifier": "restricted-test-reel",
            "title": "Restricted Test Reel",
            "rights": "All rights reserved",
            "licenseurl": "",
        }
    ],
    _normalize_query("Spanish Republic crowds"): [
        {
            "identifier": "madrid-crowds-1936",
            "title": "Madrid Crowds 1936",
            "rights": "Public domain",
            "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
        }
    ],
    _normalize_query("Spanish Civil War newsreel"): [
        {
            "identifier": "spanish-civil-war-newsreel-1936",
            "title": "Spanish Civil War Newsreel 1936",
            "rights": "Public domain",
            "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
        }
    ],
    _normalize_query("Spanish Civil War archive footage"): [
        {
            "identifier": "spanish-civil-war-newsreel-1936",
            "title": "Spanish Civil War Newsreel 1936",
            "rights": "Public domain",
            "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
        }
    ],
    _normalize_query("Spanish Civil War documentary"): [
        {
            "identifier": "prelinger-test-reel",
            "title": "Prelinger Test Reel",
            "rights": "Public domain",
            "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
        }
    ],
    _normalize_query("Spain war newsreel"): [
        {
            "identifier": "prelinger-test-reel",
            "title": "Prelinger Test Reel",
            "rights": "Public domain",
            "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
        }
    ],
}


IA_METADATA = {
    "restricted-test-reel": _ia_metadata(
        identifier="restricted-test-reel",
        title="Restricted Test Reel",
        creator="Archive Tester",
        rights="All rights reserved",
        license_url="",
    ),
    "madrid-crowds-1936": _ia_metadata(
        identifier="madrid-crowds-1936",
        title="Madrid Crowds 1936",
        creator="Archive Tester",
        rights="Public domain",
        license_url="https://creativecommons.org/publicdomain/mark/1.0/",
    ),
    "spanish-civil-war-newsreel-1936": _ia_metadata(
        identifier="spanish-civil-war-newsreel-1936",
        title="Spanish Civil War Newsreel 1936",
        creator="Archive Tester",
        rights="Public domain",
        license_url="https://creativecommons.org/publicdomain/mark/1.0/",
    ),
    "prelinger-test-reel": _ia_metadata(
        identifier="prelinger-test-reel",
        title="Prelinger Test Reel",
        creator="Archive Tester",
        rights="Public domain",
        license_url="https://creativecommons.org/publicdomain/mark/1.0/",
    ),
}


QUALITY_BONUSES = {
    "cold_open": {
        "File:Crowd Street Scene Blurry.jpg": 1.0,
        "File:Barcelona Militia Street.jpg": 6.0,
        "File:Workers Barricade Poster.jpg": 4.0,
        "spanish-civil-war-newsreel-1936": 7.0,
        "prelinger-test-reel": 3.0,
    },
    "union_posters": {
        "File:CNT Meeting Leaflet.jpg": 1.0,
        "File:LLEGIU Catalunya.jpg": 7.0,
        "File:CNT-AIT-FAI.jpg": 6.0,
    },
    "election_press": {
        "File:1936 elections, Barcelona.jpg": 7.0,
        "File:Spain, electoral districts 1933-1936.jpg": 3.0,
    },
    "archival_reel": {
        "madrid-crowds-1936": 4.0,
        "spanish-civil-war-newsreel-1936": 6.0,
        "prelinger-test-reel": 2.0,
    },
}


@dataclass(slots=True)
class PlannerBenchmarkBeatResult:
    beat_id: str
    beat_type: str
    required: bool
    used_assets: int
    providers: dict[str, int]
    asset_identities: list[str]
    beat_score: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "beat_type": self.beat_type,
            "required": self.required,
            "used_assets": self.used_assets,
            "providers": self.providers,
            "asset_identities": self.asset_identities,
            "beat_score": self.beat_score,
            "notes": self.notes,
        }


@dataclass(slots=True)
class PlannerBenchmarkResult:
    planner_score: float
    covered_required_beats: int
    total_required_beats: int
    required_coverage_ratio: float
    duplicate_assets: int
    beat_results: list[PlannerBenchmarkBeatResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "planner_score": self.planner_score,
            "covered_required_beats": self.covered_required_beats,
            "total_required_beats": self.total_required_beats,
            "required_coverage_ratio": self.required_coverage_ratio,
            "duplicate_assets": self.duplicate_assets,
            "beats": [beat.to_dict() for beat in self.beat_results],
        }


def run_planner_benchmark(
    *,
    episode_path: Path | None = None,
) -> PlannerBenchmarkResult:
    benchmark_episode = episode_path or BENCHMARK_EPISODE_PATH
    episode = load_episode(benchmark_episode)
    with tempfile.TemporaryDirectory(prefix="warcut-planner-benchmark-") as temp_dir:
        build_dir = Path(temp_dir) / "build" / episode.id
        with ExitStack() as stack:
            stack.enter_context(
                patch("scw_builder.sources.commons.search_commons", _fake_search_commons)
            )
            stack.enter_context(
                patch("scw_builder.sources.commons.get_file_metadata", _fake_get_file_metadata)
            )
            stack.enter_context(patch("scw_builder.sources.internet_archive.search_ia", _fake_search_ia))
            stack.enter_context(
                patch("scw_builder.sources.internet_archive.get_item_metadata", _fake_get_item_metadata)
            )
            manifest = plan_episode(
                episode,
                build_dir,
                offline=True,
                no_download=True,
                allow_partial=True,
            )
    return _score_manifest(manifest)


def print_planner_benchmark(
    *,
    json_output: bool = False,
    episode_path: Path | None = None,
) -> None:
    result = run_planner_benchmark(episode_path=episode_path)
    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
        return
    print(f"planner_score:          {result.planner_score:.2f}")
    print(
        "required_coverage:      "
        f"{result.covered_required_beats}/{result.total_required_beats}"
    )
    print(f"required_coverage_pct:  {result.required_coverage_ratio:.3f}")
    print(f"duplicate_assets:       {result.duplicate_assets}")
    for beat in result.beat_results:
        identities = ", ".join(beat.asset_identities) if beat.asset_identities else "-"
        print(
            f"beat {beat.beat_id}: used={beat.used_assets} "
            f"score={beat.beat_score:.1f} assets={identities}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scw_builder.benchmark")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--episode", type=Path, default=BENCHMARK_EPISODE_PATH)
    args = parser.parse_args()
    print_planner_benchmark(json_output=args.json, episode_path=args.episode)


def _score_manifest(manifest: Manifest) -> PlannerBenchmarkResult:
    beat_results: list[PlannerBenchmarkBeatResult] = []
    covered_required = 0
    identity_counts: dict[str, int] = {}
    total_score = 0.0

    for beat in manifest.beats:
        required = _beat_requires_sourced_assets(beat.beat_type)
        identities = [_asset_identity(asset) for asset in beat.assets]
        for identity in identities:
            identity_counts[identity] = identity_counts.get(identity, 0) + 1

        providers: dict[str, int] = {}
        beat_score = 0.0
        for asset in beat.assets:
            providers[asset.provider] = providers.get(asset.provider, 0) + 1
            beat_score += QUALITY_BONUSES.get(beat.beat_id, {}).get(_asset_identity(asset), 0.5)

        if required and beat.assets:
            covered_required += 1
            beat_score += 18.0
        elif required:
            beat_score -= 12.0

        if beat.beat_type in {"archival_clip", "montage"} and providers.get("internet_archive", 0):
            beat_score += 4.0
        if beat.beat_type in {"still", "doc_scan"} and providers.get("commons", 0):
            beat_score += 3.0
        if beat.beat_type in {"montage", "still", "doc_scan"} and providers.get("commons", 0):
            beat_score += min(providers.get("commons", 0), 2) * 1.0

        note_penalty = sum(1 for note in beat.sourcing_notes if "no matching" in note.lower())
        beat_score -= note_penalty * 1.5
        total_score += beat_score

        beat_results.append(
            PlannerBenchmarkBeatResult(
                beat_id=beat.beat_id,
                beat_type=beat.beat_type,
                required=required,
                used_assets=len(beat.assets),
                providers=providers,
                asset_identities=identities,
                beat_score=beat_score,
                notes=beat.sourcing_notes,
            )
        )

    duplicate_assets = sum(count - 1 for count in identity_counts.values() if count > 1)
    total_score -= duplicate_assets * 4.0
    total_required_beats = sum(1 for beat in manifest.beats if _beat_requires_sourced_assets(beat.beat_type))
    coverage_ratio = covered_required / total_required_beats if total_required_beats else 1.0

    return PlannerBenchmarkResult(
        planner_score=round(total_score, 2),
        covered_required_beats=covered_required,
        total_required_beats=total_required_beats,
        required_coverage_ratio=round(coverage_ratio, 3),
        duplicate_assets=duplicate_assets,
        beat_results=beat_results,
    )


def _asset_identity(asset: Any) -> str:
    return asset.page_title or asset.identifier or asset.source_url or asset.asset_id


def _fake_search_commons(
    query: str,
    limit: int = 10,
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> list[dict[str, Any]]:
    del cache_dir, offline
    return COMMONS_SEARCH_RESULTS.get(_normalize_query(query), [])[:limit]


def _fake_get_file_metadata(
    title: str,
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    del cache_dir, offline
    return COMMONS_METADATA.get(title, {})


def _fake_search_ia(
    query: str,
    limit: int = 10,
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> list[dict[str, Any]]:
    del cache_dir, offline
    return IA_SEARCH_RESULTS.get(_normalize_query(query), [])[:limit]


def _fake_get_item_metadata(
    identifier: str,
    *,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    del cache_dir, offline
    return IA_METADATA.get(identifier, {})


if __name__ == "__main__":
    main()
