from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from scw_builder.benchmark import print_planner_benchmark
from scw_builder.config import BuildPaths, repo_root_from_episode
from scw_builder.config import curated_assets_root
from scw_builder.edit.otio_builder import write_otio_json
from scw_builder.edit.resolve_bridge import write_resolve_script_stub
from scw_builder.episode_schema import load_episode
from scw_builder.library import ingest_manifest, write_gallery
from scw_builder.manifest import read_manifest, write_manifest
from scw_builder.plan.planner import _beat_requires_sourced_assets, plan_episode
from scw_builder.render.animatic import build_animatic
from scw_builder.render.final_video import mux_narration
from scw_builder.render.slides import render_slides
from scw_builder.sources.licenses import attribution_lines
from scw_builder.tts_openai import (
    DEFAULT_TTS_FORMAT,
    DEFAULT_TTS_INSTRUCTIONS,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    synthesize_episode_narration,
    update_manifest_narration,
)
from scw_builder.utils.files import ensure_dir
from scw_builder.utils.log import info
from scw_builder.voice_cues import (
    build_voice_cues,
    load_script_sections,
    script_path_for_episode,
    write_voice_cues_json,
    write_voice_cues_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="scw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("episode_path")
    build_parser.add_argument("--offline", action="store_true")
    build_parser.add_argument("--no-download", action="store_true")
    build_parser.add_argument("--warm-cache", action="store_true")

    cache_parser = subparsers.add_parser("cache")
    cache_parser.add_argument("episode_path")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("episode_path")

    voice_parser = subparsers.add_parser("voice")
    voice_parser.add_argument("episode_path")
    voice_parser.add_argument("voice_path")

    tts_parser = subparsers.add_parser("tts-openai")
    tts_parser.add_argument("episode_path")
    tts_parser.add_argument("--env-file", type=Path)
    tts_parser.add_argument("--model", default=DEFAULT_TTS_MODEL)
    tts_parser.add_argument("--voice", default=DEFAULT_TTS_VOICE)
    tts_parser.add_argument(
        "--format",
        default=DEFAULT_TTS_FORMAT,
        choices=["mp3", "opus", "aac", "flac", "wav", "pcm"],
    )
    tts_parser.add_argument("--instructions", default=DEFAULT_TTS_INSTRUCTIONS)
    tts_parser.add_argument("--output", type=Path)
    tts_parser.add_argument("--dry-run", action="store_true")
    tts_parser.add_argument("--no-manifest-update", action="store_true")

    final_parser = subparsers.add_parser("render-final")
    final_parser.add_argument("episode_path")
    final_parser.add_argument("--narration", type=Path)
    final_parser.add_argument("--output", type=Path)
    final_parser.add_argument("--fit-narration", action="store_true")

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("episode_path")

    benchmark_parser = subparsers.add_parser("benchmark-planner")
    benchmark_parser.add_argument("--json", action="store_true")
    benchmark_parser.add_argument("--episode", default=None)

    args = parser.parse_args()
    if args.command == "init":
        _cmd_init(Path.cwd())
    elif args.command == "build":
        _cmd_build(
            Path(args.episode_path),
            offline=args.offline,
            no_download=args.no_download,
            warm_cache=args.warm_cache,
        )
    elif args.command == "cache":
        _cmd_cache(Path(args.episode_path))
    elif args.command == "ingest":
        _cmd_ingest(Path(args.episode_path))
    elif args.command == "voice":
        _cmd_voice(Path(args.episode_path), Path(args.voice_path))
    elif args.command == "tts-openai":
        _cmd_tts_openai(
            Path(args.episode_path),
            env_file=args.env_file,
            model=args.model,
            voice=args.voice,
            audio_format=args.format,
            instructions=args.instructions,
            output=args.output,
            dry_run=args.dry_run,
            update_manifest=not args.no_manifest_update,
        )
    elif args.command == "render-final":
        _cmd_render_final(
            Path(args.episode_path),
            narration_path=args.narration,
            output_path=args.output,
            fit_narration=args.fit_narration,
        )
    elif args.command == "publish":
        _cmd_publish(Path(args.episode_path))
    elif args.command == "benchmark-planner":
        _cmd_benchmark_planner(json_output=args.json, episode_path=args.episode)


def _cmd_init(root: Path) -> None:
    directories = [
        root / "episodes",
        root / "src" / "scw_builder",
        root / "templates",
        root / "assets_static" / "brand" / "fonts",
        root / "assets_static" / "brand" / "icons",
        root / "tests",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    info(f"initialized warcut scaffolding at {root}")


def _cmd_build(
    episode_path: Path,
    *,
    offline: bool = False,
    no_download: bool = False,
    warm_cache: bool = False,
) -> None:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)

    preserved_cache_dir: Path | None = None
    existing_cache_dir = paths.assets_dir / "_cache"
    if existing_cache_dir.exists():
        preserved_cache_dir = Path(tempfile.mkdtemp(prefix="warcut-cache-")) / "_cache"
        shutil.copytree(existing_cache_dir, preserved_cache_dir, dirs_exist_ok=True)
    if paths.build_dir.exists():
        shutil.rmtree(paths.build_dir)
    ensure_dir(paths.build_dir)
    if preserved_cache_dir and preserved_cache_dir.exists():
        shutil.copytree(preserved_cache_dir, paths.assets_dir / "_cache", dirs_exist_ok=True)
    ensure_dir(paths.slides_dir)
    ensure_dir(paths.timeline_dir)

    manifest = plan_episode(
        episode,
        paths.build_dir,
        offline=offline,
        no_download=no_download,
        warm_cache=warm_cache,
        allow_partial=offline,
    )
    write_manifest(manifest, paths.manifest_path)
    _write_credits(manifest, paths.credits_path)
    _write_voice_cues(episode_path, manifest, paths)
    render_slides(manifest, paths.slides_dir)
    animatic_path = build_animatic(manifest, paths.slides_dir, paths.animatic_path)
    write_otio_json(manifest, paths.timeline_dir / f"{episode.id}.otio")
    write_resolve_script_stub(paths.timeline_dir / f"{episode.id}_resolve.py", episode.id)

    info(f"manifest: {paths.manifest_path}")
    info(f"credits: {paths.credits_path}")
    info(f"slides: {paths.slides_dir}")
    if animatic_path:
        info(f"animatic: {animatic_path}")
    else:
        info("animatic: skipped (ffmpeg not found)")
    info(f"voice cues: {paths.voice_cues_md_path}")
    _write_coverage_report(manifest, paths.coverage_path)
    _print_coverage_report(manifest)


def _cmd_cache(episode_path: Path) -> None:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)
    ensure_dir(paths.assets_dir / "_cache")
    manifest = plan_episode(
        episode,
        paths.build_dir,
        offline=False,
        no_download=False,
        warm_cache=True,
        allow_partial=True,
    )
    info(f"cache warmed for {episode.id}")
    _write_coverage_report(manifest, paths.coverage_path)
    _print_coverage_report(manifest)


def _cmd_ingest(episode_path: Path) -> None:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)
    if not paths.manifest_path.exists():
        raise FileNotFoundError(
            f"manifest not found for {episode.id}. Build the episode first: {paths.manifest_path}"
        )
    manifest = read_manifest(paths.manifest_path)
    curated_root = curated_assets_root(root)
    records = ingest_manifest(manifest, curated_root)
    gallery_path = write_gallery(curated_root)
    info(f"curated library: {curated_root / 'library.json'}")
    info(f"curated items: {curated_root / 'items'}")
    info(f"copied files: {curated_root / 'files'}")
    info(f"gallery: {gallery_path}")
    info(f"ingested {len(records)} unique assets")


def _cmd_voice(episode_path: Path, voice_path: Path) -> None:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)
    manifest = read_manifest(paths.manifest_path)
    manifest.narration_wav = str(voice_path.resolve())
    write_manifest(manifest, paths.manifest_path)
    info(f"updated narration path in {paths.manifest_path}")


def _cmd_tts_openai(
    episode_path: Path,
    *,
    env_file: Path | None,
    model: str,
    voice: str,
    audio_format: str,
    instructions: str,
    output: Path | None,
    dry_run: bool,
    update_manifest: bool,
) -> None:
    narration_path = synthesize_episode_narration(
        episode_path,
        model=model,
        voice=voice,
        audio_format=audio_format,
        instructions=instructions,
        env_file=env_file,
        output_path=output,
        dry_run=dry_run,
    )
    info(f"narration: {narration_path}")
    if update_manifest and not dry_run:
        manifest_path = update_manifest_narration(episode_path, narration_path)
        info(f"updated narration path in {manifest_path}")
    elif dry_run:
        info("manifest: unchanged (dry run)")


def _cmd_render_final(
    episode_path: Path,
    *,
    narration_path: Path | None,
    output_path: Path | None,
    fit_narration: bool,
) -> None:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)
    manifest = read_manifest(paths.manifest_path)
    resolved_narration = narration_path or (
        Path(manifest.narration_wav) if manifest.narration_wav else None
    )
    if resolved_narration is None:
        raise FileNotFoundError(
            "narration path not set. Run `scw tts-openai ...` or pass --narration."
        )
    resolved_output = output_path or (
        paths.build_dir / "publish" / f"{episode.id}-first-video.mp4"
    )
    final_path = mux_narration(
        animatic_path=paths.animatic_path,
        narration_path=resolved_narration,
        output_path=resolved_output,
        fit_narration=fit_narration,
    )
    info(f"final video: {final_path}")


def _cmd_publish(episode_path: Path) -> None:
    episode = load_episode(episode_path)
    root = repo_root_from_episode(episode_path)
    paths = BuildPaths(root=root, episode_id=episode.id)
    publish_dir = paths.build_dir / "publish"
    ensure_dir(publish_dir)
    for source in [paths.manifest_path, paths.credits_path]:
        shutil.copy2(source, publish_dir / source.name)
    notes_path = episode_path.with_suffix(".notes.md")
    if notes_path.exists():
        shutil.copy2(notes_path, publish_dir / notes_path.name)
    if paths.animatic_path.exists():
        shutil.copy2(paths.animatic_path, publish_dir / paths.animatic_path.name)
    info(f"publish package: {publish_dir}")


def _cmd_benchmark_planner(
    *,
    json_output: bool = False,
    episode_path: str | None = None,
) -> None:
    resolved_episode = Path(episode_path) if episode_path else None
    print_planner_benchmark(json_output=json_output, episode_path=resolved_episode)


def _write_credits(manifest, credits_path: Path) -> None:
    lines = [f"# Credits for {manifest.title}", ""]
    for beat in manifest.beats:
        lines.append(f"## {beat.beat_id}")
        for asset in beat.assets:
            lines.extend(attribution_lines(asset.attribution))
            lines.append("")
    credits_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_voice_cues(episode_path: Path, manifest, paths: BuildPaths) -> None:
    script_sections = load_script_sections(script_path_for_episode(episode_path))
    cues = build_voice_cues(manifest, script_sections)
    write_voice_cues_markdown(cues, paths.voice_cues_md_path)
    write_voice_cues_json(cues, paths.voice_cues_json_path)


def _print_coverage_report(manifest) -> None:
    info("coverage report:")
    missing = []
    for beat in manifest.beats:
        commons_count = sum(1 for asset in beat.assets if asset.provider == "commons")
        ia_count = sum(1 for asset in beat.assets if asset.provider == "internet_archive")
        used_count = len(beat.assets)
        info(
            f"  {beat.beat_id}: commons found {commons_count}, ia found {ia_count}, used {used_count}"
        )
        for note in beat.sourcing_notes[:3]:
            info(f"    note: {note}")
        if used_count == 0 and beat.suggested_queries:
            info(f"    try: {beat.suggested_queries[0]}")
            for suggestion in beat.suggested_queries[1:3]:
                info(f"    alt: {suggestion}")
        if used_count == 0 and _beat_requires_sourced_assets(beat.beat_type):
            missing.append(beat.beat_id)
    if missing:
        info(f"missing beats: {', '.join(missing)}")


def _write_coverage_report(manifest, path: Path) -> None:
    beats = []
    missing = []
    for beat in manifest.beats:
        commons_count = sum(1 for asset in beat.assets if asset.provider == "commons")
        ia_count = sum(1 for asset in beat.assets if asset.provider == "internet_archive")
        used_count = len(beat.assets)
        beats.append(
            {
                "beat_id": beat.beat_id,
                "beat_type": beat.beat_type,
                "requires_sourced_assets": _beat_requires_sourced_assets(beat.beat_type),
                "commons_found": commons_count,
                "ia_found": ia_count,
                "used": used_count,
                "notes": beat.sourcing_notes,
                "suggested_queries": beat.suggested_queries,
            }
        )
        if used_count == 0 and _beat_requires_sourced_assets(beat.beat_type):
            missing.append(beat.beat_id)
    path.write_text(
        json.dumps(
            {
                "episode_id": manifest.episode_id,
                "beats": beats,
                "missing_beats": missing,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
if __name__ == "__main__":
    main()
