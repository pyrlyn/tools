# Contributing

Follow the organization rules in [pyrlyn/.github](https://github.com/pyrlyn/.github): English
everywhere, Conventional Commits, one pull request per change, squash merge, no direct pushes
to `main`.

- `mise install` installs the pinned toolchain; `just check` is the gate (fmt, clippy, tests).
- A new tool belongs here only when at least two repositories carry the same code today, or a
  second repository is moved onto it in the same series of pull requests.
- Tools take no runtime dependencies unless they earn it: consumers build them from source.
- CI workflows do not live here; the thin caller in `.github/workflows/ci.yml` uses
  pyrlyn/ci.
