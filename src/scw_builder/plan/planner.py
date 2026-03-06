from __future__ import annotations

import re
from pathlib import Path

from scw_builder.episode_schema import EpisodeConfig
from scw_builder.manifest import (
    BeatManifest,
    Manifest,
    RenderInstruction,
)
from scw_builder.plan.timing import build_timings
from scw_builder.sources.commons import (
    CommonsSelectionOptions,
    select_assets_by_title,
    select_assets_for_beat,
)
from scw_builder.sources.internet_archive import (
    IASelectionOptions,
    select_clip_by_identifier,
    select_clips_for_beat,
)
from scw_builder.sources.local import build_local_asset
from scw_builder.utils.files import unique_preserving_order
from scw_builder.utils.log import info


MAX_WARM_CACHE_QUERIES_PER_PROVIDER = 8


def plan_episode(
    episode: EpisodeConfig,
    build_dir: Path,
    *,
    offline: bool = False,
    no_download: bool = False,
    warm_cache: bool = False,
    allow_partial: bool = False,
) -> Manifest:
    beat_manifests: list[BeatManifest] = []
    assets_dir = build_dir / "assets"
    cache_dir = assets_dir / "_cache" / "commons"
    ia_cache_dir = assets_dir / "_cache" / "ia"
    commons_options = CommonsSelectionOptions(
        assets_dir=assets_dir,
        cache_dir=cache_dir,
        limit=episode.sources.commons.max_assets_per_beat,
        min_width=episode.sources.commons.effective_min_width_px,
        min_height=episode.sources.commons.effective_min_height_px,
        require_attribution=episode.guardrails.require_license_metadata,
        offline=offline,
        no_download=no_download,
    )
    ia_options = IASelectionOptions(
        assets_dir=assets_dir,
        cache_dir=ia_cache_dir,
        limit=episode.sources.internet_archive.max_assets_per_beat,
        max_clip_sec=episode.sources.internet_archive.max_clip_sec,
        offline=offline,
        no_download=no_download,
    )

    for timed in build_timings(episode.beats):
        beat = timed.beat
        suggested_queries = _suggest_queries(beat.keywords, beat.type)
        local_assets, local_notes = _collect_local_assets(
            beat.id,
            beat.pinned.get("local_files", []),
        )
        commons_assets, sourcing_notes = _collect_commons_assets(
            beat.id,
            _provider_queries(beat.keywords, beat.search, "commons"),
            commons_options,
            beat_type=beat.type,
            warm_cache=warm_cache,
            pinned_titles=beat.pinned.get("commons_titles", []),
        )
        sourcing_notes = local_notes + sourcing_notes
        ia_assets = []
        ia_notes: list[str] = []
        if beat.type in {"archival_clip", "montage"} and episode.sources.enable_internet_archive:
            ia_assets, ia_notes = _collect_ia_assets(
                beat.id,
                _provider_queries(beat.keywords, beat.search, "internet_archive"),
                ia_options,
                fps=episode.style.fps,
                beat_type=beat.type,
                warm_cache=warm_cache,
                pinned_identifiers=beat.pinned.get("ia_identifiers", []),
            )
        sourcing_notes.extend(ia_notes)
        assets = local_assets + ia_assets + commons_assets
        if not assets and _beat_requires_sourced_assets(beat.type) and not allow_partial:
            raise RuntimeError(
                f"No assets matched beat '{beat.id}'. "
                "Use different queries or warm the cache first."
            )
        render = RenderInstruction(
            start_sec=timed.start_sec,
            duration_sec=float(beat.duration_sec),
            transform={"style": "ken_burns", "preset": beat.type},
            overlay_text=beat.on_screen_text,
        )
        beat_manifests.append(
            BeatManifest(
                beat_id=beat.id,
                beat_type=beat.type,
                duration_sec=float(beat.duration_sec),
                start_sec=timed.start_sec,
                end_sec=timed.end_sec,
                keywords=beat.keywords,
                search=beat.search,
                pinned=beat.pinned,
                overlays=beat.on_screen_text,
                caption=beat.caption or _default_caption(beat.id),
                motion=beat.motion or _default_motion(beat.type),
                noir=beat.noir or _default_noir(beat.type),
                lower_third=beat.lower_third,
                quote=beat.quote,
                source=beat.source,
                layout=beat.layout,
                accent_word=beat.accent_word,
                map=beat.map,
                highlights=beat.highlights,
                arrows=beat.arrows,
                labels=beat.labels,
                montage=beat.montage or _default_montage(),
                sourcing_notes=sourcing_notes,
                suggested_queries=suggested_queries,
                assets=assets,
                render=[render],
            )
        )

    return Manifest(
        episode_id=episode.id,
        title=episode.title,
        duration_target_sec=episode.duration_target_sec,
        theme=episode.style.theme,
        font_family=episode.style.font_family,
        safe_margin_px=episode.style.safe_margin_px,
        accent_color=episode.style.accent_color,
        fps=episode.style.fps,
        aspect=episode.style.aspect,
        voice_mode=episode.voice.mode,
        narration_wav=episode.voice.narration_wav,
        build_dir=str(build_dir.resolve()),
        beats=beat_manifests,
    )


def _collect_commons_assets(
    beat_id: str,
    keywords: list[str],
    options: CommonsSelectionOptions,
    *,
    beat_type: str,
    warm_cache: bool,
    pinned_titles: list[str],
) -> list:
    assets = []
    notes: list[str] = []
    seen_titles: set[str] = set()
    for title in pinned_titles:
        try:
            asset = select_assets_by_title(beat_id, title, options)
        except Exception as exc:
            notes.append(f"commons pinned title failed '{title}': {exc}")
            continue
        if not asset:
            notes.append(f"commons pinned title not usable '{title}'")
            continue
        identity = asset.page_title or asset.source_url or asset.asset_id
        if identity in seen_titles:
            continue
        seen_titles.add(identity)
        assets.append(asset)
        if len(assets) >= options.limit:
            return assets, notes
    if assets:
        return assets, notes
    query_limit = options.limit * (3 if warm_cache else 1)
    queries = _expand_queries(
        keywords,
        beat_type=beat_type,
        provider="commons",
        warm_cache=warm_cache,
    )
    if warm_cache:
        queries = queries[:MAX_WARM_CACHE_QUERIES_PER_PROVIDER]
    expanded_options = CommonsSelectionOptions(
        assets_dir=options.assets_dir,
        cache_dir=options.cache_dir,
        limit=query_limit,
        min_width=options.min_width,
        min_height=options.min_height,
        require_attribution=options.require_attribution,
        offline=options.offline,
        no_download=options.no_download,
    )
    if warm_cache:
        info(f"[commons] {beat_id}: trying {len(queries)} queries")
    for keyword in queries:
        try:
            candidates = select_assets_for_beat(beat_id, keyword, expanded_options)
        except Exception as exc:
            notes.append(f"commons query failed '{keyword}': {exc}")
            continue
        for asset in candidates:
            identity = asset.page_title or asset.source_url or asset.asset_id
            if identity in seen_titles:
                continue
            seen_titles.add(identity)
            assets.append(asset)
            if len(assets) >= options.limit:
                break
        if len(assets) >= options.limit:
            break
    if not assets:
        notes.append("commons: no matching assets found")
    return assets, notes


def _collect_local_assets(
    beat_id: str,
    pinned_files: list[str],
) -> tuple[list, list[str]]:
    assets = []
    notes: list[str] = []
    for path_str in pinned_files:
        local_path = Path(path_str).expanduser()
        asset = build_local_asset(beat_id, local_path, query_used=path_str)
        if asset is None:
            notes.append(f"local pinned file not usable '{path_str}'")
            continue
        assets.append(asset)
    return assets, notes


def _default_caption(beat_id: str) -> str:
    return beat_id.replace("_", " ").upper()


def _default_motion(beat_type: str) -> dict:
    if beat_type == "quote_card":
        return {"style": "push_in", "zoom": [1.0, 1.03]}
    if beat_type == "map_move":
        return {"style": "map_hold", "sequence": ["hold", "highlight", "arrow", "hold"]}
    return {"style": "kenburns", "zoom": [1.02, 1.08], "pan": "slow_left"}


def _default_noir(beat_type: str) -> dict:
    if beat_type == "map_move":
        return {"grade": "clean_map", "grain": 0.02, "vignette": 0.04}
    return {"grade": "high_contrast", "grain": 0.05, "vignette": 0.08}


def _default_montage() -> dict:
    return {
        "cuts": 5,
        "min_cut_sec": 0.6,
        "max_cut_sec": 1.2,
        "prefer": ["archival_clip", "doc_scan", "poster"],
        "fallback": ["still"],
    }


def _beat_requires_sourced_assets(beat_type: str) -> bool:
    return beat_type not in {"map", "map_move", "quote_card"}


def _collect_ia_assets(
    beat_id: str,
    keywords: list[str],
    options: IASelectionOptions,
    *,
    fps: int,
    beat_type: str,
    warm_cache: bool,
    pinned_identifiers: list[str],
) -> list:
    assets = []
    notes: list[str] = []
    seen_identifiers: set[str] = set()
    for identifier in pinned_identifiers:
        try:
            asset = select_clip_by_identifier(beat_id, identifier, options, fps=fps)
        except Exception as exc:
            notes.append(f"internet_archive pinned identifier failed '{identifier}': {exc}")
            continue
        if not asset:
            notes.append(f"internet_archive pinned identifier not usable '{identifier}'")
            continue
        identity = asset.identifier or asset.asset_id
        if identity in seen_identifiers:
            continue
        seen_identifiers.add(identity)
        assets.append(asset)
        if len(assets) >= options.limit:
            return assets, notes
    query_limit = options.limit * (3 if warm_cache else 1)
    queries = _expand_queries(
        keywords,
        beat_type=beat_type,
        provider="internet_archive",
        warm_cache=warm_cache,
    )
    if warm_cache:
        queries = queries[:MAX_WARM_CACHE_QUERIES_PER_PROVIDER]
    expanded_options = IASelectionOptions(
        assets_dir=options.assets_dir,
        cache_dir=options.cache_dir,
        limit=query_limit,
        max_clip_sec=options.max_clip_sec,
        max_file_size_bytes=options.max_file_size_bytes,
        offline=options.offline,
        no_download=options.no_download,
    )
    if warm_cache:
        info(f"[internet_archive] {beat_id}: trying {len(queries)} queries")
    for keyword in queries:
        try:
            candidates = select_clips_for_beat(beat_id, keyword, expanded_options, fps=fps)
        except Exception as exc:
            notes.append(f"internet_archive query failed '{keyword}': {exc}")
            continue
        for asset in candidates:
            identity = asset.identifier or asset.asset_id
            if identity in seen_identifiers:
                continue
            seen_identifiers.add(identity)
            assets.append(asset)
            if len(assets) >= options.limit:
                break
        if len(assets) >= options.limit:
            break
    if not assets:
        notes.append("internet_archive: no matching clips found")
    return assets, notes


def _expand_queries(
    keywords: list[str],
    *,
    beat_type: str,
    provider: str,
    warm_cache: bool,
) -> list[str]:
    variants: list[str] = []
    for keyword in keywords:
        variants.append(keyword)
        cleaned = re.sub(r"\s+", " ", keyword).strip()
        stripped_years = re.sub(r"\b(18|19|20)\d{2}\b", "", cleaned)
        stripped_years = re.sub(r"\s+", " ", stripped_years).strip()
        if stripped_years and stripped_years != cleaned:
            variants.append(stripped_years)

        compact = re.sub(r"\b(spain|spanish|civil|war)\b", "", cleaned, flags=re.IGNORECASE)
        compact = re.sub(r"\s+", " ", compact).strip()
        compact_terms = compact.split()
        if compact and compact != cleaned and len(compact_terms) >= 3:
            variants.append(compact)
            variants.append(f"Spanish Civil War {compact}")

        if "barcelona" in cleaned.lower():
            variants.append(cleaned.replace("Barcelona", "Catalonia"))
        if "catalonia" in cleaned.lower():
            variants.append(cleaned.replace("Catalonia", "Barcelona"))
        if "madrid" in cleaned.lower():
            variants.append(cleaned.replace("Madrid", "Spanish Republic"))
        if "spain" in cleaned.lower():
            variants.append(cleaned.replace("Spain", "Spanish Civil War"))
        if "regions map" in cleaned.lower():
            variants.append("Second Spanish Republic regions map")
        lower_cleaned = cleaned.lower()
        if "militia" in lower_cleaned:
            variants.append(f"{cleaned} republican")
        if provider == "commons" and ("poster" in lower_cleaned or beat_type == "still"):
            variants.extend(_commons_poster_variants(cleaned))
        if "cartel" in lower_cleaned:
            variants.append(cleaned.replace("cartel", "poster"))
            variants.append(f"{cleaned} guerra civil")
        if "cartell" in lower_cleaned:
            variants.append(cleaned.replace("cartell", "cartel"))
            variants.append(cleaned.replace("cartell", "poster"))
        if "cnt" in lower_cleaned:
            variants.append(cleaned.replace("CNT", "Confederacion Nacional del Trabajo"))
        if "fai" in lower_cleaned:
            variants.append(cleaned.replace("FAI", "Federacion Anarquista Iberica"))
        if "ugt" in lower_cleaned:
            variants.append(cleaned.replace("UGT", "Union General de Trabajadores"))
        if provider == "commons" and ("republic" in lower_cleaned or "republicano" in lower_cleaned):
            variants.append(f"{cleaned} propaganda")
            if "poster" not in lower_cleaned and "cartel" not in lower_cleaned and "cartell" not in lower_cleaned:
                variants.append(f"{cleaned} poster")
        if provider == "commons" and "barcelona" in lower_cleaned and beat_type == "still":
            variants.append(f"{cleaned} labour")
            variants.append(f"{cleaned} sindicato")
        if provider == "internet_archive" and "newsreel" in lower_cleaned:
            variants.append(cleaned.replace("newsreel", "archive footage"))
            variants.append(cleaned.replace("newsreel", "documentary"))
        if provider == "internet_archive" and "archive footage" in lower_cleaned:
            variants.append(cleaned.replace("archive footage", "newsreel"))

    if beat_type in {"map", "map_move"}:
        variants.extend(
            [
                "Spain regional map",
                "Spain autonomous regions map",
                "Catalonia Basque Andalusia map",
                "Second Spanish Republic map",
            ]
        )
    elif beat_type in {"still", "doc_scan"} and provider == "commons":
        variants.extend(
            [
                "Spanish Civil War poster Barcelona",
                "Spanish Civil War newspaper Barcelona",
                "Spanish Republic propaganda poster",
                "CNT FAI UGT poster Spain",
                "Guerra Civil Espanola cartel",
                "cartel republicano",
                "cartel anarquista Barcelona",
                "Barcelona workers poster",
                "Catalonia labour poster",
                "Spanish Civil War union poster",
            ]
        )
    elif beat_type in {"archival_clip", "montage"} and provider == "internet_archive":
        variants.extend(
            [
                "Spanish Civil War newsreel",
                "Spanish Civil War archive footage",
                "Spanish Civil War documentary",
                "Spain war newsreel",
            ]
        )

    if provider == "internet_archive":
        ia_variants = []
        for variant in variants:
            ia_variants.append(variant)
            ia_variants.append(f"{variant} prelinger")
            ia_variants.append(f"{variant} newsreel")
        variants = ia_variants

    if warm_cache and provider == "commons":
        warmed = []
        for variant in variants:
            warmed.append(variant)
            warmed.append(f"{variant} photo")
            if "poster" not in variant.lower() and "cartel" not in variant.lower():
                warmed.append(f"{variant} poster")
        variants = warmed

    return unique_preserving_order(variants)


def _suggest_queries(keywords: list[str], beat_type: str) -> list[str]:
    provider = "internet_archive" if beat_type in {"archival_clip", "montage"} else "commons"
    expanded = _expand_queries(
        keywords,
        beat_type=beat_type,
        provider=provider,
        warm_cache=True,
    )
    suggestions = [query for query in expanded if query not in keywords]
    return suggestions[:6]


def _provider_queries(
    keywords: list[str],
    search: dict[str, list[str]],
    provider: str,
) -> list[str]:
    override = search.get(provider) if search else None
    if override:
        return override
    return keywords


def _commons_poster_variants(cleaned: str) -> list[str]:
    lower_cleaned = cleaned.lower()
    variants: list[str] = []
    if "propaganda" not in lower_cleaned:
        variants.append(f"{cleaned} propaganda")
    if "republican" not in lower_cleaned and "republicano" not in lower_cleaned:
        variants.append(f"{cleaned} republican")
    if "worker" not in lower_cleaned and "labour" not in lower_cleaned:
        variants.append(f"{cleaned} worker")
        variants.append(f"{cleaned} labour")
    if "union" not in lower_cleaned and "sindicato" not in lower_cleaned:
        variants.append(f"{cleaned} union")
    return variants
