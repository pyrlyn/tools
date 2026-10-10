# Consuming pyrlyn/tools

`ptools` is a std-only Rust binary, so installing it from git takes a few seconds.

## Pin

In the consumer's `mise.toml`, a tag is the normal pin:

```toml
"cargo:https://github.com/pyrlyn/tools" = "tag:v0.1.0"
```

`rev:<sha>` also works (use the full SHA); `branch:` pins are not allowed because they move.
Never point at `main`. Dependabot does not track mise pins, so bump the tag by hand when a new
release of this repository is wanted.

## Recipes

```just
# $CARGO_HOME sizes (no deletes) and the target directory
cache:
    mise exec -- ptools cache

# preview what cache-autoclean would remove
cache-dry-run:
    mise exec -- ptools cache --dry-run

# drop extracted crate/git checkouts; keep archives
cache-autoclean:
    mise exec -- ptools cache --autoclean

# Lossless cleanup of the target directory; a no-op without swarfr
swarfr:
    mise exec -- ptools swarfr
```

## Environment

`PTOOLS_CARGO_CACHE` and `PTOOLS_SWARFR` override the commands that are run (they may contain
arguments, split on whitespace). `CARGO_TARGET_DIR` moves the target directory.

## Releasing this repository

A release is a `vX.Y.Z` tag on `main` after a PR merge. Consumers pin the tag; nothing is
published to crates.io (`publish = false`).
