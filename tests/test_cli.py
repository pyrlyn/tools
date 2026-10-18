# Copyright (c) 2026 Ivan Tugay
# SPDX-License-Identifier: GPL-3.0-or-later
# Licensed under GPL-3.0 or later; see https://www.gnu.org/licenses/gpl-3.0.html

"""Runs the real CLI (`python -m ptools`) with fake `cargo-cache`, `swarfr` and `cargo-sweep`
stand-ins (shell scripts), so the tests need no network and no installed tools. Unix only: the
stand-ins are `sh` scripts."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from ptools.cli import human

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="stand-ins are sh scripts")


def fake(directory: Path, name: str, script: str) -> str:
    path = directory / name
    path.write_text(f"#!/bin/sh\n{script}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


def ptools(
    cwd: Path, args: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = {k: v for k, v in os.environ.items() if k not in ("CARGO_TARGET_DIR", "PTOOLS_SWEEP_DAYS")}
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "ptools", *args],
        cwd=cwd,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


def test_human_sizes() -> None:
    assert human(0) == "0 B"
    assert human(1023) == "1023 B"
    assert human(1536) == "1.5 KiB"
    assert human(5 * 1024**3) == "5.0 GiB"


def test_cache_runs_cargo_cache_then_reports_target_size(tmp_path: Path) -> None:
    cc = fake(tmp_path, "cc", f'echo "cc $*" >> {tmp_path}/log')
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "a").write_bytes(bytes(2048))
    out = ptools(tmp_path, ["cache"], {"PTOOLS_CARGO_CACHE": cc})
    assert out.returncode == 0
    assert "target: 2.0 KiB" in out.stdout
    assert (tmp_path / "log").read_text() == "cc \n"


def test_cache_reports_missing_target(tmp_path: Path) -> None:
    cc = fake(tmp_path, "cc", "exit 0")
    out = ptools(tmp_path, ["cache"], {"PTOOLS_CARGO_CACHE": cc})
    assert "target: (missing)" in out.stdout


def test_cache_autoclean_and_dry_run_pass_flags_and_skip_size(tmp_path: Path) -> None:
    cc = fake(tmp_path, "cc", f'echo "$*" >> {tmp_path}/log')
    out = ptools(tmp_path, ["cache", "--autoclean"], {"PTOOLS_CARGO_CACHE": cc})
    assert out.returncode == 0
    assert "target:" not in out.stdout
    ptools(tmp_path, ["cache", "--dry-run"], {"PTOOLS_CARGO_CACHE": cc})
    assert (tmp_path / "log").read_text() == "--autoclean\n--autoclean --dry-run\n"


def test_cache_propagates_failure_and_rejects_bad_flags(tmp_path: Path) -> None:
    cc = fake(tmp_path, "cc", "exit 7")
    assert ptools(tmp_path, ["cache"], {"PTOOLS_CARGO_CACHE": cc}).returncode == 7
    assert ptools(tmp_path, ["cache", "--nope"]).returncode == 2


def test_swarfr_is_a_noop_without_the_binary(tmp_path: Path) -> None:
    (tmp_path / "target").mkdir()
    out = ptools(tmp_path, ["swarfr"], {"PTOOLS_SWARFR": "definitely-not-installed-swarfr"})
    assert out.returncode == 0
    assert "swarfr not found" in out.stdout


def test_swarfr_is_a_noop_without_a_target_dir(tmp_path: Path) -> None:
    sw = fake(tmp_path, "sw", f"echo ran >> {tmp_path}/log")
    assert ptools(tmp_path, ["swarfr"], {"PTOOLS_SWARFR": sw}).returncode == 0
    assert not (tmp_path / "log").exists()


def test_swarfr_runs_on_target_and_maps_exit_codes(tmp_path: Path) -> None:
    (tmp_path / "target").mkdir()
    log = f'echo "$*" >> {tmp_path}/log'
    for code, ok in [(0, True), (2, True), (1, False)]:
        sw = fake(tmp_path, "sw", f"{log}\nexit {code}")
        out = ptools(tmp_path, ["swarfr"], {"PTOOLS_SWARFR": sw})
        assert (out.returncode == 0) == ok, f"exit {code}"
    assert (tmp_path / "log").read_text() == "run target\n" * 3


def test_sweep_defaults_to_one_day_recursive(tmp_path: Path) -> None:
    cs = fake(tmp_path, "cs", f'echo "$*" > {tmp_path}/log')
    assert ptools(tmp_path, ["sweep"], {"PTOOLS_CARGO_SWEEP": cs}).returncode == 0
    assert (tmp_path / "log").read_text() == "--recursive --time 1 .\n"


def test_sweep_passes_days_dry_run_and_dir(tmp_path: Path) -> None:
    cs = fake(tmp_path, "cs", f'echo "$*" > {tmp_path}/log')
    out = ptools(
        tmp_path, ["sweep", "--days", "3", "--dry-run", "work"], {"PTOOLS_CARGO_SWEEP": cs}
    )
    assert out.returncode == 0
    assert (tmp_path / "log").read_text() == "--recursive --time 3 --dry-run work\n"


def test_sweep_reads_days_from_env(tmp_path: Path) -> None:
    cs = fake(tmp_path, "cs", f'echo "$*" > {tmp_path}/log')
    ptools(tmp_path, ["sweep"], {"PTOOLS_CARGO_SWEEP": cs, "PTOOLS_SWEEP_DAYS": "5"})
    assert (tmp_path / "log").read_text() == "--recursive --time 5 .\n"


def test_sweep_is_a_noop_without_cargo_sweep_and_rejects_bad_days(tmp_path: Path) -> None:
    out = ptools(tmp_path, ["sweep"], {"PTOOLS_CARGO_SWEEP": "/nonexistent/cs"})
    assert out.returncode == 0
    assert "cargo-sweep not found" in out.stdout
    assert ptools(tmp_path, ["sweep", "--days", "x"]).returncode == 2


def test_cpus_prints_a_positive_number(tmp_path: Path) -> None:
    assert int(ptools(tmp_path, ["cpus"]).stdout.strip()) >= 1


def test_help_and_usage_errors(tmp_path: Path) -> None:
    helped = ptools(tmp_path, ["--help"])
    assert helped.returncode == 0
    assert helped.stdout.startswith("ptools: shared development helpers")
    bare = ptools(tmp_path, [])
    assert bare.returncode == 2
    assert bare.stderr.startswith("ptools: shared development helpers")
    assert ptools(tmp_path, ["bogus"]).returncode == 2
