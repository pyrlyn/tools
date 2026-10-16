# Consuming pyrlyn/tools

`ptools` is a strictly typed, standard-library-only Python package (Python 3.11 or newer). mise
installs it from git with uv, which takes a few seconds.

## Pin

In the consumer's `mise.toml`, a tag is the normal pin (the git ref goes in the version, without
a `tag:` or `rev:` prefix), next to the Python and uv that run it:

```toml
python = "3.12"
uv = "0.9"
"pipx:git+https://github.com/pyrlyn/tools.git" = "v0.1.0"
```

A full commit SHA also works; branch pins are not allowed because they move. The installed command
is still `ptools`, so `mise exec -- ptools ...` in tasks and hooks does not change.
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

# Remove build artifacts unused for 1 day (needs "cargo:cargo-sweep" = "0.8.0" in mise.toml)
sweep:
    mise exec -- ptools sweep
sweep-dry:
    mise exec -- ptools sweep --dry-run
```

`ptools sweep --days N` changes the threshold; `PTOOLS_SWEEP_DAYS` sets the default.

## Environment

`PTOOLS_CARGO_CACHE`, `PTOOLS_SWARFR` and `PTOOLS_CARGO_SWEEP` override the commands that are run (they may contain
arguments, split on whitespace). `CARGO_TARGET_DIR` moves the target directory.

## Releasing this repository

A release is a `vX.Y.Z` tag on `main` after a PR merge. Consumers pin the tag; nothing is
published to crates.io or PyPI.
