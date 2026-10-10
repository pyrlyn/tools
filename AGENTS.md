# AGENTS.md

If an AGENTS.md or CLAUDE.md exists higher in the tree, follow it too; on conflict, ask the creator.

## What this repo is

Shared development tooling for pyrlyn Rust and Swift repositories (cache, cleanup and test or
build helpers). CI workflows live in pyrlyn/ci. `origin` is `git@github.com:pyrlyn/tools.git`.

| Path | Role |
| --- | --- |
| `src/main.rs` | the `ptools` binary: `cache`, `swarfr`, `cpus` |
| `tests/cli.rs` | runs the binary against fake `cargo-cache` and `swarfr` scripts (Unix only) |
| `docs/consuming.md` | how a repository pins and calls `ptools` |

## Commands

`just check` (fmt-check, clippy with `-D warnings`, tests). Tools are pinned in `mise.toml`.

## Rules

- English only in files, commits and PR text; Conventional Commits; PRs from a branch, never to
  `main` directly; draft while in progress.
- No dependencies without a reason; `unsafe` is forbidden.
- Consumers pin a tag or SHA of this repository: do not change a released tag's behavior;
  tag a new version.
