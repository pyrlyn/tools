// Copyright (c) 2026 Ivan Tugay
// SPDX-License-Identifier: GPL-3.0-or-later
// Licensed under GPL-3.0 or later; see https://www.gnu.org/licenses/gpl-3.0.html

//! `ptools`: the development helpers that the justfiles of several pyrlyn repositories used to
//! carry as copy-pasted recipes. No dependencies, so `cargo install --git` builds in seconds.

use std::env;
use std::ffi::OsString;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};

const USAGE: &str = "\
ptools: shared development helpers

Usage:
  ptools cache [--autoclean | --dry-run]
      No flag: run cargo-cache (CARGO_HOME sizes, nothing deleted), then print the size of the
      cargo target directory. --autoclean drops extracted crate and git checkouts and keeps
      the archives. --dry-run previews --autoclean.
  ptools swarfr [TARGET_DIR]
      Lossless cleanup of the cargo target directory with swarfr (compress + dedupe, never
      deletes). A no-op when swarfr is not installed or the directory does not exist.
  ptools cpus
      Print the number of logical CPUs.

Environment:
  PTOOLS_CARGO_CACHE  cargo-cache command (default: cargo-cache)
  PTOOLS_SWARFR       swarfr command (default: swarfr)
  CARGO_TARGET_DIR    target directory (default: ./target)
";

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("cache") => cache(&args[1..]),
        Some("swarfr") => swarfr(&args[1..]),
        Some("cpus") => {
            println!("{}", cpus());
            ExitCode::SUCCESS
        }
        Some("-h" | "--help" | "help") => {
            print!("{USAGE}");
            ExitCode::SUCCESS
        }
        _ => {
            eprint!("{USAGE}");
            ExitCode::from(2)
        }
    }
}

fn cpus() -> usize {
    std::thread::available_parallelism().map_or(4, usize::from)
}

fn target_dir() -> PathBuf {
    env::var_os("CARGO_TARGET_DIR").map_or_else(|| PathBuf::from("target"), PathBuf::from)
}

fn command_from_env(var: &str, default: &str) -> Vec<String> {
    let value = env::var(var).unwrap_or_else(|_| default.to_owned());
    value.split_whitespace().map(str::to_owned).collect()
}

fn run(parts: &[String], extra: &[OsString]) -> Result<i32, String> {
    let (program, rest) = parts.split_first().ok_or("empty command")?;
    let status = Command::new(program)
        .args(rest)
        .args(extra)
        .status()
        .map_err(|e| format!("{program}: {e}"))?;
    Ok(status.code().unwrap_or(1))
}

fn cache(args: &[String]) -> ExitCode {
    let extra: Vec<OsString> = match args {
        [] => vec![],
        [flag] if flag == "--autoclean" => vec!["--autoclean".into()],
        [flag] if flag == "--dry-run" => vec!["--autoclean".into(), "--dry-run".into()],
        _ => {
            eprint!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    let cmd = command_from_env("PTOOLS_CARGO_CACHE", "cargo-cache");
    match run(&cmd, &extra) {
        Ok(0) => {}
        Ok(code) => return ExitCode::from(u8::try_from(code).unwrap_or(1)),
        Err(e) => {
            eprintln!("ptools cache: {e}");
            return ExitCode::from(1);
        }
    }
    if extra.is_empty() {
        let dir = target_dir();
        if dir.is_dir() {
            println!("target: {} ({})", human(dir_size(&dir)), dir.display());
        } else {
            println!("target: (missing)");
        }
    }
    ExitCode::SUCCESS
}

fn swarfr(args: &[String]) -> ExitCode {
    let dir = args.first().map_or_else(target_dir, PathBuf::from);
    let cmd = command_from_env("PTOOLS_SWARFR", "swarfr");
    if !on_path(&cmd[0]) {
        println!("swarfr not found; install it with: ketch install swarfr");
        return ExitCode::SUCCESS;
    }
    if !dir.is_dir() {
        return ExitCode::SUCCESS;
    }
    let extra = [OsString::from("run"), dir.into_os_string()];
    match run(&cmd, &extra) {
        // Exit 2 is swarfr's "nothing to do"; both are success for the recipe.
        Ok(0 | 2) => ExitCode::SUCCESS,
        Ok(code) => ExitCode::from(u8::try_from(code).unwrap_or(1)),
        Err(e) => {
            eprintln!("ptools swarfr: {e}");
            ExitCode::from(1)
        }
    }
}

fn on_path(program: &str) -> bool {
    if program.contains(std::path::MAIN_SEPARATOR) {
        return Path::new(program).is_file();
    }
    let Some(paths) = env::var_os("PATH") else {
        return false;
    };
    env::split_paths(&paths).any(|dir| {
        let plain = dir.join(program);
        plain.is_file() || (cfg!(windows) && dir.join(format!("{program}.exe")).is_file())
    })
}

fn dir_size(dir: &Path) -> u64 {
    let Ok(entries) = fs::read_dir(dir) else {
        return 0;
    };
    entries
        .flatten()
        .map(|entry| match entry.file_type() {
            Ok(t) if t.is_dir() => dir_size(&entry.path()),
            Ok(t) if t.is_file() => entry.metadata().map_or(0, |m| m.len()),
            _ => 0,
        })
        .sum()
}

#[allow(clippy::cast_precision_loss)]
fn human(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "KiB", "MiB", "GiB", "TiB"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1024.0 && unit < UNITS.len() - 1 {
        value /= 1024.0;
        unit += 1;
    }
    if unit == 0 {
        format!("{bytes} B")
    } else {
        format!("{value:.1} {}", UNITS[unit])
    }
}

#[cfg(test)]
mod tests {
    use super::human;

    #[test]
    fn human_sizes() {
        assert_eq!(human(0), "0 B");
        assert_eq!(human(1023), "1023 B");
        assert_eq!(human(1536), "1.5 KiB");
        assert_eq!(human(5 * 1024 * 1024 * 1024), "5.0 GiB");
    }
}
