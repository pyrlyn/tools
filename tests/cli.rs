// Copyright (c) 2026 Ivan Tugay
// SPDX-License-Identifier: GPL-3.0-or-later
// Licensed under GPL-3.0 or later; see https://www.gnu.org/licenses/gpl-3.0.html

//! Runs the real binary with fake `cargo-cache` and `swarfr` stand-ins (shell scripts), so the
//! tests need no network and no installed tools. Unix only: the stand-ins are `sh` scripts.
#![cfg(unix)]

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::process::{Command, Output};

fn fake(dir: &Path, name: &str, script: &str) -> String {
    let path = dir.join(name);
    fs::write(&path, format!("#!/bin/sh\n{script}\n")).unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o755)).unwrap();
    path.to_string_lossy().into_owned()
}

fn ptools(cwd: &Path, args: &[&str], env: &[(&str, &str)]) -> Output {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_ptools"));
    cmd.args(args)
        .current_dir(cwd)
        .env_remove("CARGO_TARGET_DIR");
    for (k, v) in env {
        cmd.env(k, v);
    }
    cmd.output().unwrap()
}

fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}

#[test]
fn cache_runs_cargo_cache_then_reports_target_size() {
    let tmp = tempfile_dir("cache1");
    let cc = fake(
        &tmp,
        "cc",
        &format!("echo \"cc $*\" >> {}/log", tmp.display()),
    );
    fs::create_dir_all(tmp.join("target")).unwrap();
    fs::write(tmp.join("target/a"), vec![0u8; 2048]).unwrap();
    let out = ptools(&tmp, &["cache"], &[("PTOOLS_CARGO_CACHE", &cc)]);
    assert!(out.status.success());
    assert!(
        text(&out.stdout).contains("target: 2.0 KiB"),
        "{}",
        text(&out.stdout)
    );
    assert_eq!(fs::read_to_string(tmp.join("log")).unwrap(), "cc \n");
}

#[test]
fn cache_reports_missing_target() {
    let tmp = tempfile_dir("cache2");
    let cc = fake(&tmp, "cc", "exit 0");
    let out = ptools(&tmp, &["cache"], &[("PTOOLS_CARGO_CACHE", &cc)]);
    assert!(text(&out.stdout).contains("target: (missing)"));
}

#[test]
fn cache_autoclean_and_dry_run_pass_flags_and_skip_size() {
    let tmp = tempfile_dir("cache3");
    let cc = fake(&tmp, "cc", &format!("echo \"$*\" >> {}/log", tmp.display()));
    let out = ptools(
        &tmp,
        &["cache", "--autoclean"],
        &[("PTOOLS_CARGO_CACHE", &cc)],
    );
    assert!(out.status.success());
    assert!(!text(&out.stdout).contains("target:"));
    ptools(
        &tmp,
        &["cache", "--dry-run"],
        &[("PTOOLS_CARGO_CACHE", &cc)],
    );
    assert_eq!(
        fs::read_to_string(tmp.join("log")).unwrap(),
        "--autoclean\n--autoclean --dry-run\n"
    );
}

#[test]
fn cache_propagates_failure_and_rejects_bad_flags() {
    let tmp = tempfile_dir("cache4");
    let cc = fake(&tmp, "cc", "exit 7");
    let out = ptools(&tmp, &["cache"], &[("PTOOLS_CARGO_CACHE", &cc)]);
    assert_eq!(out.status.code(), Some(7));
    let out = ptools(&tmp, &["cache", "--nope"], &[]);
    assert_eq!(out.status.code(), Some(2));
}

#[test]
fn swarfr_is_a_noop_without_the_binary() {
    let tmp = tempfile_dir("sw1");
    fs::create_dir_all(tmp.join("target")).unwrap();
    let out = ptools(
        &tmp,
        &["swarfr"],
        &[("PTOOLS_SWARFR", "definitely-not-installed-swarfr")],
    );
    assert!(out.status.success());
    assert!(text(&out.stdout).contains("swarfr not found"));
}

#[test]
fn swarfr_is_a_noop_without_a_target_dir() {
    let tmp = tempfile_dir("sw2");
    let sw = fake(&tmp, "sw", &format!("echo ran >> {}/log", tmp.display()));
    let out = ptools(&tmp, &["swarfr"], &[("PTOOLS_SWARFR", &sw)]);
    assert!(out.status.success());
    assert!(!tmp.join("log").exists());
}

#[test]
fn swarfr_runs_on_target_and_maps_exit_codes() {
    let tmp = tempfile_dir("sw3");
    fs::create_dir_all(tmp.join("target")).unwrap();
    let log = format!("echo \"$*\" >> {}/log", tmp.display());
    for (code, ok) in [(0, true), (2, true), (1, false)] {
        let sw = fake(&tmp, "sw", &format!("{log}\nexit {code}"));
        let out = ptools(&tmp, &["swarfr"], &[("PTOOLS_SWARFR", &sw)]);
        assert_eq!(out.status.success(), ok, "exit {code}");
    }
    assert_eq!(
        fs::read_to_string(tmp.join("log")).unwrap(),
        "run target\nrun target\nrun target\n"
    );
}

#[test]
fn cpus_prints_a_positive_number() {
    let tmp = tempfile_dir("cpus");
    let out = ptools(&tmp, &["cpus"], &[]);
    assert!(text(&out.stdout).trim().parse::<usize>().unwrap() >= 1);
}

#[test]
fn sweep_defaults_to_one_day_recursive() {
    let tmp = tempfile_dir("sweep1");
    let cs = fake(&tmp, "cs", &format!("echo \"$*\" > {}/log", tmp.display()));
    let out = ptools(&tmp, &["sweep"], &[("PTOOLS_CARGO_SWEEP", &cs)]);
    assert!(out.status.success());
    assert_eq!(
        fs::read_to_string(tmp.join("log")).unwrap(),
        "--recursive --time 1 .\n"
    );
}

#[test]
fn sweep_passes_days_dry_run_and_dir() {
    let tmp = tempfile_dir("sweep2");
    let cs = fake(&tmp, "cs", &format!("echo \"$*\" > {}/log", tmp.display()));
    let out = ptools(
        &tmp,
        &["sweep", "--days", "3", "--dry-run", "work"],
        &[("PTOOLS_CARGO_SWEEP", &cs)],
    );
    assert!(out.status.success());
    assert_eq!(
        fs::read_to_string(tmp.join("log")).unwrap(),
        "--recursive --time 3 --dry-run work\n"
    );
}

#[test]
fn sweep_is_a_noop_without_cargo_sweep_and_rejects_bad_days() {
    let tmp = tempfile_dir("sweep3");
    let out = ptools(
        &tmp,
        &["sweep"],
        &[("PTOOLS_CARGO_SWEEP", "/nonexistent/cs")],
    );
    assert!(out.status.success());
    assert!(text(&out.stdout).contains("cargo-sweep not found"));
    let out = ptools(&tmp, &["sweep", "--days", "x"], &[]);
    assert_eq!(out.status.code(), Some(2));
}

fn tempfile_dir(name: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("ptools-test-{name}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    dir
}
