# AGENTS.md

If an AGENTS.md or CLAUDE.md exists higher in the tree, follow it too; on conflict, ask the creator.

## What this repo is

Shared development tooling for pyrlyn Rust and Swift repositories (cache, cleanup and test or
build helpers). CI workflows live in pyrlyn/ci. `origin` is `git@github.com:pyrlyn/tools.git`.

| Path | Role |
| --- | --- |
| `src/ptools/cli.py` | the `ptools` command (Python, standard library only): `cache`, `swarfr`, `sweep`, `cpus` |
| `tests/test_cli.py` | pytest: runs `python -m ptools` against fake `cargo-cache`, `swarfr` and `cargo-sweep` scripts (Unix only) |
| `pyproject.toml` | package metadata (`ptools` console script) and the strict mypy config |
| `tools/list.py` | standalone uv script (bulk PR merger), not part of the package |
| `docs/consuming.md` | how a repository pins and calls `ptools` |

## Commands

`just check` (`mypy --strict`, pytest). Python and uv are pinned in `mise.toml`.

## Rules

- English only in files, commits and PR text; Conventional Commits; PRs from a branch, never to
  `main` directly; draft while in progress.
- Python is strictly typed: `from __future__ import annotations` in every module, every function
  fully annotated, `mypy --strict` clean (config in `pyproject.toml`, run by `just typecheck` and CI).
- Standard library only at runtime; no dependencies without a reason.
- Consumers pin a tag or SHA of this repository: do not change a released tag's behavior;
  tag a new version.
