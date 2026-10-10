# Tools are pinned in mise.toml; override CARGO if mise is already activated.
cargo := env("CARGO", "mise exec -- cargo")

default: check

fmt:
    {{cargo}} fmt --all

fmt-check:
    {{cargo}} fmt --all -- --check

lint:
    {{cargo}} clippy --workspace --all-targets --locked -- -D warnings

test:
    {{cargo}} test --workspace --locked

# The gate every change must pass.
check: fmt-check lint test
