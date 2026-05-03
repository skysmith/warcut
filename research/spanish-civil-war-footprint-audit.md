# Spanish Civil War Footprint Audit

Updated: 2026-04-23

## Short Answer

Yes: there is already an active Spanish Civil War project footprint in `lab/media/warcut`.

Yes: the requested routing scaffolding now exists as an Atlas wiki page at `wiki/atlas/spanish-civil-war-research.md` and a project-local map at `lab/media/warcut/mind-map.md`.

No: there is still not yet a dedicated research hub page inside `lab/media/warcut/research/` for longer-form synthesis beneath the wiki page and the project-level mind map.

## Relationship Map

- Atlas wiki routing page: `wiki/atlas/spanish-civil-war-research.md`
- Canonical project home: `../PROJECT.md`
- Project-local orientation anchor: `../mind-map.md`
- Durable research folder entrypoint: `README.md`
- Active episode spine: `../episodes/ep01.yaml`

## What Already Exists

- Project scope already points at the topic.
  - `README.md` says `warcut` is "currently tuned for a Spanish Civil War workflow."
- Canonical routing is already established.
  - `PROJECT.md` says the canonical home for the Spanish Civil War / Spanish history research thread is `lab/media/warcut`.
  - `wiki/atlas/spanish-civil-war-research.md` is the Atlas wiki routing page.
  - `mind-map.md` is now the project-local orientation map.
- There is an actual episode draft, not just tooling.
  - `episodes/ep01.yaml` is a full episode outline for "many spains."
  - `episodes/ep01.script.md` is a full narration draft about regional fragmentation, Catalonia, the Basque Country, Andalusia, and the July 1936 coup.
  - `episodes/ep01.notes.md` tracks weak beats and next asset improvements.
- There is a topic-specific research/asset sweep already underway.
  - `episodes/library_newsreels.yaml` is a Spanish Civil War newsreel sweep across uprising, Madrid, Barcelona, Guernica, brigades, propaganda, and the war's end.
  - `research/library/ia_vetted_newsreels.json` is a vetted Internet Archive candidate list.
- Curated archival assets already exist locally.
  - `assets_curated/` contains Spanish Civil War-relevant Commons and Internet Archive items, including Barcelona militia imagery, 1931/1933/1936 election maps, regional maps, and Civil War newsreels.
- Built outputs already prove the project has been exercised on this topic.
  - `build/ep01/` contains an animatic, credits, slides, voice cues, and timeline output for the Spanish Civil War episode.

## What Is Missing

- No dedicated research hub page inside `warcut` that organizes questions, themes, chronology, factions, sources, and future episode ideas in one place.
- Research material is still shaped around production assets and one episode, not yet around a broader reusable history knowledge base.

## Recommendation

Keep `lab/media/warcut` as the canonical home instead of creating a brand-new project folder.

Reason:

- The topic already has a real production home in `warcut`.
- The routing layer now exists in both the root wiki and the project-local mind map.
- Existing scripts, episode files, curated assets, and built outputs are all there.
- The remaining gap is a deeper research hub note, not a missing project.

Best next structure:

- keep `mind-map.md` at the Warcut root as the project-level orientation note
- keep `wiki/atlas/spanish-civil-war-research.md` as the cross-workspace Atlas routing page
- add a project-local research hub such as `research/spanish-civil-war-hub.md` if the research layer needs a more structured synthesis note

Create a separate new folder only if the work expands beyond documentary production into a broader standalone Spain-history research system.

## Sources

- `lab/media/warcut/README.md`
- `lab/media/warcut/PROJECT.md`
- `wiki/atlas/spanish-civil-war-research.md`
- `lab/media/warcut/mind-map.md`
- `lab/media/warcut/episodes/ep01.yaml`
- `lab/media/warcut/episodes/ep01.script.md`
- `lab/media/warcut/episodes/ep01.notes.md`
- `lab/media/warcut/episodes/library_newsreels.yaml`
- `lab/media/warcut/research/library/ia_vetted_newsreels.json`
- `lab/media/warcut/assets_curated/`
- `lab/media/warcut/build/ep01/`
