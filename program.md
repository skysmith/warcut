# warcut autoresearch

This file defines the first autonomous research target for `warcut`.

## Goal

Improve the planner benchmark score without breaking the normal repo tests.

The benchmark exercises the real planning path with a fixed benchmark episode and fixed fake provider responses. It is intentionally narrow: we want better source selection and query expansion, not broad product changes.

## In-scope files

Read these first:

- `README.md`
- `episodes/autoresearch_planner.yaml`
- `src/scw_builder/benchmark.py`
- `src/scw_builder/plan/planner.py`

The default editable surface is:

- `src/scw_builder/plan/planner.py`

If you have a very strong reason, you may also edit:

- `src/scw_builder/sources/commons.py`
- `src/scw_builder/sources/internet_archive.py`

Do not edit the benchmark itself while trying to improve the score:

- `src/scw_builder/benchmark.py`
- `episodes/autoresearch_planner.yaml`
- `tests/test_planner_benchmark.py`

## Objective

Maximize the planner score from:

```bash
PYTHONPATH=src python3 -m scw_builder.benchmark
```

or:

```bash
PYTHONPATH=src python3 -m scw_builder.cli benchmark-planner
```

Higher is better.

The benchmark already reports:

- `planner_score`
- required-beat coverage
- duplicate assets
- per-beat chosen assets

## Constraints

- Keep the benchmark deterministic.
- Prefer planner/query-selection improvements over broad refactors.
- Do not add dependencies.
- Keep `pytest -q` green.
- Simplicity matters. A tiny score gain is not worth a messy change.

## Good directions

- Better query ordering.
- Smarter fallback sequencing.
- Avoiding duplicate assets across beats when a better unused option exists.
- Better handling of low-signal queries before filling the asset limit.

## Bad directions

- Editing the benchmark to make the score easier.
- Disabling attribution, rights, or resolution filters.
- Breaking the normal `build` / `cache` path to win the benchmark.
