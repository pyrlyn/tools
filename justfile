# Tools are pinned in mise.toml; override UV if mise is already activated.
uv := env("UV", "mise exec -- uv")

default: check

# Strict typing: mypy --strict over src and tests (config in pyproject.toml).
typecheck:
    {{uv}} run --group dev mypy

test:
    {{uv}} run --group dev pytest

# The gate every change must pass.
check: typecheck test
