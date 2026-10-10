# pyrlyn/tools

Shared development tooling for pyrlyn Rust and Swift repositories: the helpers that several
repositories used to carry as copy-pasted justfile recipes and scripts. Shared CI lives in
[pyrlyn/ci](https://github.com/pyrlyn/ci), not here.

## What is here

| Tool | What it does | Replaces |
| --- | --- | --- |
| `ptools cache [--autoclean \| --dry-run]` | cargo-cache report, cleanup of extracted checkouts, and the target directory size | the `cache`, `cache-autoclean` and `cache-dry-run` recipes of cox, ketch and rtok |
| `ptools swarfr [DIR]` | lossless target cleanup with swarfr; a no-op without swarfr or a target dir | the `swarfr` recipe of cox, ketch and rtok |
| `ptools cpus` | logical CPU count | rtok's `cpus` shell snippet |

Swift: nothing shared yet. The Swift scripts in the repositories (injecta-swift benchmarks,
slint-bindings recipes) are each used in one place only.

## Using it from another repository

Pin a tag (or a full commit SHA) in the repository's `mise.toml`:

```toml
"cargo:https://github.com/pyrlyn/tools" = "tag:v0.1.0" # `just cache`, `just swarfr` (ptools)
```

and call it from the justfile:

```just
cache:
    mise exec -- ptools cache
```

See [docs/consuming.md](docs/consuming.md) for the details and how to bump the pin.

## Development

`just check` runs fmt, clippy and the tests. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).
