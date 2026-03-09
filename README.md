# warcut

`warcut` builds short documentary-style video packages from episode YAML.

It is currently tuned for a Spanish Civil War workflow:

- source collection from Wikimedia Commons and Internet Archive
- deterministic manifest generation
- noir-doc slide rendering
- animatic export
- OTIO timeline export

This README is written as a handoff doc for another LLM or engineer. It should
be enough context to safely generate episode scripts, YAML, or small repo edits
without guessing the project structure.

## What This Repo Does

Input:

- `episodes/<episode>.yaml`

Primary outputs:

- `build/<episode>/manifest.json`
- `build/<episode>/credits.md`
- `build/<episode>/voice_cues.md`
- `build/<episode>/voice_cues.json`
- `build/<episode>/assets/`
- `build/<episode>/slides/*.png`
- `build/<episode>/animatic.mp4`
- `build/<episode>/timeline/<episode>.otio`

The manifest is the single source of truth for downstream steps.

## Current Status

Implemented:

- Episode YAML validation with Pydantic
- Wikimedia Commons search, metadata fetch, cache, and attribution
- Internet Archive search, metadata fetch, cache, trim pipeline, and attribution
- Pinned source overrides for known-good Commons titles / IA identifiers
- Noir-doc slide rendering
- Animatic generation with `ffmpeg`
- OTIO export
- Voice cue sheet generation from beat timings + `episodes/<id>.script.md`
- Coverage reporting with missing-beat notes and suggested queries

Not fully solved:

- Live search reliability depends on network stability
- Some beats still benefit from pinned sources instead of search
- Resolve scripting is still a stub bridge

## Install

```bash
cd warcut
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Runtime requirements:

- `python3`
- `ffmpeg`

Optional:

- DaVinci Resolve for future scripting integration

## Commands

```bash
scw init
scw cache episodes/ep01_smoke.yaml
scw build episodes/ep01_smoke.yaml --offline
scw build episodes/ep01.yaml
scw ingest episodes/ep01.yaml
scw voice episodes/ep01.yaml path/to/vo.wav
scw publish episodes/ep01.yaml
```

Voiceover workflow:

1. `scw build episodes/ep01.yaml --offline`
2. Read from `build/ep01/voice_cues.md` while watching `build/ep01/animatic.mp4`
3. Record a WAV
4. `scw voice episodes/ep01.yaml /absolute/path/to/your_vo.wav`

Current limitation:

- `scw voice` stores the narration path in the manifest
- it does not auto-retime beats yet

Asset library workflow:

1. `scw build episodes/ep01.yaml --offline`
2. `scw ingest episodes/ep01.yaml`
3. open `assets_curated/index.html`
4. edit `assets_curated/items/*.json` to refine tags, notes, and quality

This gives you a curated, local asset library before you are ready to record.

Recommended smoke-test flow:

```bash
cd warcut
PYTHONPATH=src python3 -m scw_builder.cli cache episodes/ep01_smoke.yaml
PYTHONPATH=src python3 -m scw_builder.cli build episodes/ep01_smoke.yaml --offline
```

## Repo Map

Core files:

- [src/scw_builder/cli.py](src/scw_builder/cli.py)
- [src/scw_builder/episode_schema.py](src/scw_builder/episode_schema.py)
- [src/scw_builder/manifest.py](src/scw_builder/manifest.py)
- [src/scw_builder/plan/planner.py](src/scw_builder/plan/planner.py)
- [src/scw_builder/render/slides.py](src/scw_builder/render/slides.py)
- [src/scw_builder/render/animatic.py](src/scw_builder/render/animatic.py)
- [src/scw_builder/edit/otio_builder.py](src/scw_builder/edit/otio_builder.py)
- [src/scw_builder/sources/commons.py](src/scw_builder/sources/commons.py)
- [src/scw_builder/sources/internet_archive.py](src/scw_builder/sources/internet_archive.py)
- [src/scw_builder/sources/licenses.py](src/scw_builder/sources/licenses.py)

Episode examples:

- [episodes/ep01.yaml](episodes/ep01.yaml)
- [episodes/ep01_smoke.yaml](episodes/ep01_smoke.yaml)

Renderer templates:

- [templates/lower_thirds.json](templates/lower_thirds.json)
- [templates/quote_card.json](templates/quote_card.json)
- [templates/map_frame.json](templates/map_frame.json)

Static assets:

- [assets_static/brand/map_base.svg](assets_static/brand/map_base.svg)

## Episode YAML Contract

Episode files live in:

- `episodes/<id>.yaml`

Minimal top-level shape:

```yaml
id: ep01_smoke
title: "spain isn't one country (smoke test)"
duration_target_sec: 90

voice:
  mode: voice_only
  narration_wav: null

style:
  theme: "noir_doc"
  aspect: "16:9"
  fps: 30
  font_family: "Inter"
  safe_margin_px: 80
  accent_color: "burnt_red"

beats: []

sources:
  enable_commons: true
  enable_internet_archive: true
  commons:
    max_assets_per_beat: 2
    min_resolution_px: 600
  internet_archive:
    max_assets_per_beat: 1
    max_clip_sec: 8

guardrails:
  require_license_metadata: true
  block_ai_generated_archival: true
  require_source_urls_in_credits: true
```

## Beat Format

Every beat must have:

- `id`
- `type`
- `duration_sec`
- `keywords`

Common optional fields:

- `search`
- `pinned`
- `on_screen_text`
- `caption`
- `motion`
- `noir`
- `lower_third`
- `map`
- `highlights`
- `arrows`
- `labels`
- `montage`
- `quote`
- `source`
- `layout`
- `accent_word`

Example beat:

```yaml
- id: archival_reel
  type: archival_clip
  duration_sec: 18
  keywords:
    - "Spanish Civil War newsreel"
    - "Spanish Civil War archive footage"
  search:
    internet_archive:
      - "Spanish Civil War newsreel"
      - "Spanish Civil War archive footage"
      - "Prelinger war newsreel Spain"
  pinned:
    ia_identifiers:
      - "61114-yesterdays-newsreel-the-spanish-civil-war-vwr"
  on_screen_text:
    - "the war enters the street"
  caption: "ARCHIVE REEL"
  noir:
    grade: "high_contrast"
    grain: 0.06
    vignette: 0.09
```

## Search vs Pinned Sources

There are now three layers of source selection:

1. `pinned`
2. `search`
3. `keywords`

Use them like this:

- `keywords`
  - broad semantic source intent
  - used for automatic query expansion and suggestions

- `search`
  - curated provider-specific query list
  - use when default expansion is noisy
  - shape:

```yaml
search:
  commons:
    - "Spanish Republic propaganda poster"
  internet_archive:
    - "Spanish Civil War newsreel"
```

- `pinned`
  - exact known source overrides
  - use when you have a specific Commons file title or IA identifier
  - shape:

```yaml
pinned:
  commons_titles:
    - "File:LLEGIU Catalunya.jpg"
  ia_identifiers:
    - "61114-yesterdays-newsreel-the-spanish-civil-war-vwr"
```

Rule:

- if `pinned` exists, `warcut` tries that first
- if pinned fetch fails or is unusable, it falls back to `search`
- if `search` is absent, it falls back to `keywords`

## What ChatGPT Should Produce

If another model is asked to help with episodes, it should usually produce one
of these:

1. A complete beat YAML block
2. A list of `search` queries for a beat
3. A list of `pinned.commons_titles`
4. A list of `pinned.ia_identifiers`
5. On-screen script text for `on_screen_text`, `caption`, `quote`, or
   `lower_third`

Preferred output style for YAML contributions:

- valid YAML only
- no markdown fences unless explicitly asked
- preserve existing field order where practical
- keep strings quoted when they contain punctuation

If asked for source candidates, the model should return:

- Commons:
  - exact file page titles like `File:LLEGIU Catalunya.jpg`
- Internet Archive:
  - exact identifiers like `61114-yesterdays-newsreel-the-spanish-civil-war-vwr`

Do not return vague prose like:

- "use a CNT poster from Commons"
- "find a Spanish Civil War video on IA"

Return machine-usable values.

## What ChatGPT Should Not Do

- Do not invent licenses
- Do not output fake Commons file titles
- Do not output fake IA identifiers
- Do not use YouTube mirror items on IA unless explicitly accepted as temporary
- Do not rewrite the renderer unless asked
- Do not change file paths or output conventions casually

## Output Locations

Generated episode build folders:

- `build/<episode_id>/`

Important outputs:

- `manifest.json`
  - authoritative chosen assets, timing, and render instructions
- `credits.md`
  - metadata-driven attribution
- `coverage.json`
  - beat-by-beat source coverage, missing beats, notes, suggested queries
- `voice_cues.md`
  - human-readable voiceover cue sheet with beat timing and script text
- `voice_cues.json`
  - machine-readable cue sheet with beat timing and script text
- `assets_curated/library.json`
  - curated asset index built from manifest-selected media
- `assets_curated/index.html`
  - local visual gallery for browsing the curated asset library
- `assets_curated/items/*.json`
  - per-asset editable sidecars with inferred tags
- `assets_curated/files/`
  - copied local media for the curated library
- `assets/commons/`
  - fetched Commons media plus adjacent metadata JSON
- `assets/ia_clips/`
  - trimmed IA clips plus adjacent metadata JSON
- `assets/_cache/commons/`
  - cached Commons search + metadata responses
- `assets/_cache/ia/`
  - cached IA search + metadata responses and source downloads
- `slides/*.png`
  - rendered frame sequence
- `timeline/<episode>.otio`
  - timeline export

## Coverage Reports

After `cache` or `build`, inspect:

- `build/<episode>/coverage.json`

This file tells you:

- which beats found Commons assets
- which beats found IA clips
- which beats still need sourced material
- which queries were suggested next
- why a beat failed, when known

## Noir Theme Notes

Current theme:

- `theme: noir_doc`
- accent color defaults to `burnt_red`
- renderer supports:
  - `montage`
  - `still`
  - `quote_card`
  - `map_move`
  - `doc_scan`
  - `archival_clip`

Renderer rules are in:

- [src/scw_builder/render/slides.py](src/scw_builder/render/slides.py)

## Suggested Workflow For Another Model

If another model is asked to help continue this project, the best workflow is:

1. Read [episodes/ep01_smoke.yaml](episodes/ep01_smoke.yaml)
2. Read [build/ep01_smoke/coverage.json](build/ep01_smoke/coverage.json) if it exists
3. Propose either:
   - better `search` queries
   - exact `pinned.commons_titles`
   - exact `pinned.ia_identifiers`
4. Avoid broad code changes unless the problem is clearly in the pipeline

## Current Smoke Episode State

The smoke episode is the active proving ground:

- [episodes/ep01_smoke.yaml](episodes/ep01_smoke.yaml)

At the time of writing:

- `cold_open` has usable Commons material
- `vignette_catalonia` has a pinned Commons title
- `archival_reel` has a pinned IA identifier
- live search can still be flaky, so pinned sources are the preferred stabilizer

## Episode 1 Status

Current files:

- [episodes/ep01.yaml](episodes/ep01.yaml)
- [episodes/ep01.script.md](episodes/ep01.script.md)
- [episodes/ep01.notes.md](episodes/ep01.notes.md)

Current build review:

- structure and timing are good enough to start voiceover rehearsal
- major dramatic beats have sourced media
- map beat is now using a real Spain-like outline instead of floating placeholder blocks
- weak editorial beats still need better hand-picked sources:
  - `vignette_andalusia`
  - `cold_open_montage` could use one stronger image replacement
  - `pressure_gauge` could use stronger political document/newspaper imagery

Recommended next steps after this checkpoint:

1. Review `build/ep01/animatic.mp4`
2. Run `scw ingest episodes/ep01.yaml`
3. Review and retag `assets_curated/items/*.json`
4. Record against `build/ep01/voice_cues.md` when ready

## Testing

Run:

```bash
cd warcut
python3 -m pytest -q
```

Current test coverage includes:

- schema loading
- Commons fixture-based search and attribution
- IA fixture-based search and clip trimming logic
- pinned source selection
- build output checks

## Short Prompt For ChatGPT

If you need to hand this to ChatGPT quickly, use:

```text
You are helping with the `warcut` repo.

Do not invent sources.
When suggesting media, return exact Wikimedia Commons file page titles or exact Internet Archive identifiers.
Episode files live in episodes/*.yaml.
If editing a beat, preserve YAML structure and field order.
Prefer adding or refining:
- search.commons
- search.internet_archive
- pinned.commons_titles
- pinned.ia_identifiers

The build outputs go to build/<episode>/ and coverage is tracked in build/<episode>/coverage.json.
The active smoke test is episodes/ep01_smoke.yaml.
```
