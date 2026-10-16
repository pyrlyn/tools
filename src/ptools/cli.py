# Copyright (c) 2026 Ivan Tugay
# SPDX-License-Identifier: GPL-3.0-or-later
# Licensed under GPL-3.0 or later; see https://www.gnu.org/licenses/gpl-3.0.html

"""`ptools`: the development helpers that the justfiles of several pyrlyn repositories used to
carry as copy-pasted recipes. Standard library only. Behavior and exit codes match the former
Rust binary."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Sequence

USAGE = """\
ptools: shared development helpers

Usage:
  ptools cache [--autoclean | --dry-run]
      No flag: run cargo-cache (CARGO_HOME sizes, nothing deleted), then print the size of the
      cargo target directory. --autoclean drops extracted crate and git checkouts and keeps
      the archives. --dry-run previews --autoclean.
  ptools swarfr [TARGET_DIR]
      Lossless cleanup of the cargo target directory with swarfr (compress + dedupe, never
      deletes). A no-op when swarfr is not installed or the directory does not exist.
  ptools sweep [--days N] [--dry-run] [DIR]
      Remove cargo build artifacts not used for N days (default 1, or PTOOLS_SWEEP_DAYS) with
      cargo-sweep, recursively under DIR (default: .). --dry-run only reports. A no-op when
      cargo-sweep is not installed.
  ptools cpus
      Print the number of logical CPUs.

Environment:
  PTOOLS_CARGO_CACHE  cargo-cache command (default: cargo-cache)
  PTOOLS_SWARFR       swarfr command (default: swarfr)
  PTOOLS_CARGO_SWEEP  cargo-sweep command (default: cargo-sweep sweep)
  PTOOLS_SWEEP_DAYS   default age threshold in days for `sweep` (default: 1)
  CARGO_TARGET_DIR    target directory (default: ./target)
"""

_U32_MAX = 2**32 - 1
_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def _usage_error() -> int:
    sys.stderr.write(USAGE)
    return 2


def cpus() -> int:
    """Logical CPUs usable by this process; 4 when it cannot be determined."""
    counter = getattr(os, "process_cpu_count", None)
    if callable(counter):
        found = counter()
        if isinstance(found, int) and found > 0:
            return found
    if hasattr(os, "sched_getaffinity"):
        return max(1, len(os.sched_getaffinity(0)))
    return os.cpu_count() or 4


def target_dir() -> str:
    return os.environ.get("CARGO_TARGET_DIR", "target")


def command_from_env(var: str, default: str) -> list[str]:
    return os.environ.get(var, default).split()


def run(parts: Sequence[str], extra: Sequence[str]) -> int:
    """Run a command; return its exit code (1 when killed by a signal).

    Raises RuntimeError("<program>: <reason>") when it cannot be started.
    """
    if not parts:
        raise RuntimeError("empty command")
    try:
        completed = subprocess.run([*parts, *extra], check=False)
    except OSError as error:
        raise RuntimeError(f"{parts[0]}: {error.strerror or error}") from error
    return completed.returncode if completed.returncode >= 0 else 1


def exit_code(code: int) -> int:
    """Map a child's exit code into the 0..255 range (1 when it does not fit)."""
    return code if 0 <= code <= 255 else 1


def on_path(program: str) -> bool:
    if os.sep in program or (os.altsep is not None and os.altsep in program):
        return os.path.isfile(program)
    path = os.environ.get("PATH")
    if path is None:
        return False
    for directory in path.split(os.pathsep):
        if os.path.isfile(os.path.join(directory, program)):
            return True
        if sys.platform == "win32" and os.path.isfile(os.path.join(directory, program + ".exe")):
            return True
    return False


def dir_size(directory: str) -> int:
    """Total size in bytes of regular files below `directory` (symlinks count as 0)."""
    total = 0
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return 0
    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                total += dir_size(entry.path)
            elif entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
        except OSError:
            continue
    return total


def human(size: int) -> str:
    value = float(size)
    unit = 0
    while value >= 1024.0 and unit < len(_UNITS) - 1:
        value /= 1024.0
        unit += 1
    if unit == 0:
        return f"{size} B"
    return f"{value:.1f} {_UNITS[unit]}"


def cache(args: Sequence[str]) -> int:
    if not args:
        extra: list[str] = []
    elif list(args) == ["--autoclean"]:
        extra = ["--autoclean"]
    elif list(args) == ["--dry-run"]:
        extra = ["--autoclean", "--dry-run"]
    else:
        return _usage_error()
    command = command_from_env("PTOOLS_CARGO_CACHE", "cargo-cache")
    try:
        code = run(command, extra)
    except RuntimeError as error:
        sys.stderr.write(f"ptools cache: {error}\n")
        return 1
    if code != 0:
        return exit_code(code)
    if not extra:
        directory = target_dir()
        if os.path.isdir(directory):
            print(f"target: {human(dir_size(directory))} ({directory})")
        else:
            print("target: (missing)")
    return 0


def swarfr(args: Sequence[str]) -> int:
    directory = args[0] if args else target_dir()
    command = command_from_env("PTOOLS_SWARFR", "swarfr")
    if not command or not on_path(command[0]):
        print("swarfr not found; install it with: ketch install swarfr")
        return 0
    if not os.path.isdir(directory):
        return 0
    try:
        code = run(command, ["run", directory])
    except RuntimeError as error:
        sys.stderr.write(f"ptools swarfr: {error}\n")
        return 1
    # Exit 2 is swarfr's "nothing to do"; both are success for the recipe.
    if code in (0, 2):
        return 0
    return exit_code(code)


def sweep(args: Sequence[str]) -> int:
    days = os.environ.get("PTOOLS_SWEEP_DAYS", "1")
    dry_run = False
    directory = "."
    remaining = list(args)
    while remaining:
        arg = remaining.pop(0)
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--days":
            if not remaining:
                return _usage_error()
            days = remaining.pop(0)
        elif not arg.startswith("-"):
            directory = arg
        else:
            return _usage_error()
    if not re.fullmatch(r"\+?[0-9]+", days) or int(days) > _U32_MAX:
        sys.stderr.write(f"ptools sweep: --days must be a whole number, got {days!r}\n")
        return 2
    command = command_from_env("PTOOLS_CARGO_SWEEP", "cargo-sweep sweep")
    if not command or not on_path(command[0]):
        print('cargo-sweep not found; add "cargo:cargo-sweep" = "0.8.0" to mise.toml')
        return 0
    extra = ["--recursive", "--time", days]
    if dry_run:
        extra.append("--dry-run")
    extra.append(directory)
    try:
        code = run(command, extra)
    except RuntimeError as error:
        sys.stderr.write(f"ptools sweep: {error}\n")
        return 1
    return exit_code(code)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "cache":
        return cache(args[1:])
    if args and args[0] == "swarfr":
        return swarfr(args[1:])
    if args and args[0] == "sweep":
        return sweep(args[1:])
    if args and args[0] == "cpus":
        print(cpus())
        return 0
    if args and args[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    return _usage_error()
