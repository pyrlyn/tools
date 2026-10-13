#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["questionary"]
# ///
"""Interactive bulk merger for GitHub repositories.

Pick repositories (pyrlyn first), then optionally cancel all pending/running
GitHub Actions runs and admin-merge every open PR, bypassing branch protection.

Uses the `gh` CLI for authentication and API access. Workflow files and
workflow enable/disable state are never touched.

Usage:
    uv run tools/list.py [--dry-run] [--method squash|merge|rebase] [--include-drafts]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

import questionary

PRIORITY_OWNER = "pyrlyn"
ACTIVE_RUN_STATUSES = ("queued", "in_progress", "waiting", "requested", "pending")


# --------------------------------------------------------------------------- gh helpers


class GhError(RuntimeError):
    pass


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GhError((proc.stderr or proc.stdout).strip() or f"gh {' '.join(args)} failed")
    return proc


def gh_json(*args: str) -> Any:
    out = gh(*args).stdout.strip()
    return json.loads(out) if out else None


def gh_api_paginated(path: str) -> list[dict[str, Any]]:
    """GET a list endpoint across all pages (gh --paginate --slurp)."""
    pages = gh_json("api", "--paginate", "--slurp", path)
    return [item for page in pages or [] for item in page]


# --------------------------------------------------------------------------- data


@dataclass
class RepoResult:
    repo: str
    runs_cancelled: int = 0
    run_errors: list[str] = field(default_factory=list)
    merged: list[int] = field(default_factory=list)
    skipped: dict[int, str] = field(default_factory=dict)
    failed: dict[int, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- discovery


def ensure_gh_auth() -> str:
    try:
        return gh_json("api", "user")["login"]
    except GhError as exc:
        sys.exit(f"gh is not authenticated ({exc}). Run `gh auth login` first.")


def list_repos(login: str) -> list[str]:
    orgs = [o["login"] for o in gh_api_paginated("user/orgs")]
    repos: set[str] = set()
    for org in orgs:
        for r in gh_api_paginated(f"orgs/{org}/repos?per_page=100&type=all"):
            if not r.get("archived"):
                repos.add(r["full_name"])
    for r in gh_api_paginated("user/repos?per_page=100&affiliation=owner"):
        if not r.get("archived"):
            repos.add(r["full_name"])

    def sort_key(name: str) -> tuple[int, str]:
        owner = name.split("/", 1)[0].lower()
        return (0 if owner == PRIORITY_OWNER else 1 if owner == login.lower() else 2, name.lower())

    return sorted(repos, key=sort_key)


def open_prs(repo: str) -> list[dict[str, Any]]:
    prs = gh_json(
        "pr", "list", "--repo", repo, "--state", "open", "--limit", "500",
        "--json", "number,title,isDraft,headRefOid,createdAt,baseRefName",
    )
    return sorted(prs or [], key=lambda p: p["createdAt"])  # oldest first


def active_runs(repo: str) -> list[dict[str, Any]]:
    runs: dict[int, dict[str, Any]] = {}
    for status in ACTIVE_RUN_STATUSES:
        for run in gh_json(
            "run", "list", "--repo", repo, "--status", status, "--limit", "500",
            "--json", "databaseId,status,workflowName,headBranch",
        ) or []:
            runs[run["databaseId"]] = run
    return list(runs.values())


# --------------------------------------------------------------------------- actions


def cancel_runs(repo: str, result: RepoResult, dry_run: bool) -> None:
    for run in active_runs(repo):
        run_id = run["databaseId"]
        label = f"run {run_id} ({run.get('workflowName')} @ {run.get('headBranch')}, {run['status']})"
        if dry_run:
            print(f"    [dry-run] would cancel {label}")
            result.runs_cancelled += 1
            continue
        if gh("run", "cancel", str(run_id), "--repo", repo, check=False).returncode == 0:
            result.runs_cancelled += 1
            print(f"    cancelled {label}")
            continue
        forced = gh("api", "-X", "POST", f"repos/{repo}/actions/runs/{run_id}/force-cancel", check=False)
        if forced.returncode == 0:
            result.runs_cancelled += 1
            print(f"    force-cancelled {label}")
        else:
            msg = (forced.stderr or forced.stdout).strip()
            result.run_errors.append(f"{run_id}: {msg}")
            print(f"    ! could not cancel {label}: {msg}")


def current_head_sha(repo: str, number: int) -> str:
    return gh_json("pr", "view", str(number), "--repo", repo, "--json", "headRefOid")["headRefOid"]


def merge_pr(repo: str, number: int, method: str) -> str:
    """Admin-merge a PR. Returns merge commit sha; raises GhError on failure."""
    sha = current_head_sha(repo, number)  # re-fetch: earlier merges move the base
    cli = gh(
        "pr", "merge", str(number), "--repo", repo, f"--{method}",
        "--admin", "--delete-branch", "--match-head-commit", sha, check=False,
    )
    if cli.returncode == 0:
        info = gh_json("pr", "view", str(number), "--repo", repo, "--json", "mergeCommit")
        return (info.get("mergeCommit") or {}).get("oid", "")
    cli_err = (cli.stderr or cli.stdout).strip()
    api = gh(
        "api", "-X", "PUT", f"repos/{repo}/pulls/{number}/merge",
        "-f", f"sha={sha}", "-f", f"merge_method={method}", check=False,
    )
    if api.returncode == 0:
        return json.loads(api.stdout).get("sha", "")
    raise GhError(f"gh: {cli_err} | api: {(api.stderr or api.stdout).strip()}")


def process_repo(repo: str, args: argparse.Namespace) -> RepoResult:
    result = RepoResult(repo)
    print(f"\n== {repo}")
    print("  Cancelling active Actions runs...")
    cancel_runs(repo, result, args.dry_run)

    for pr in open_prs(repo):
        num = pr["number"]
        if pr["isDraft"]:
            if not args.include_drafts:
                result.skipped[num] = "draft"
                print(f"  - #{num} skipped (draft)")
                continue
            if args.dry_run:
                print(f"  [dry-run] would mark #{num} ready for review")
            else:
                ready = gh("pr", "ready", str(num), "--repo", repo, check=False)
                if ready.returncode != 0:
                    result.failed[num] = f"mark ready: {(ready.stderr or ready.stdout).strip()}"
                    print(f"  ! #{num} could not be marked ready")
                    continue
        if args.dry_run:
            print(f"  [dry-run] would admin-merge #{num} ({args.method}): {pr['title']}")
            result.merged.append(num)
            continue
        try:
            sha = merge_pr(repo, num, args.method)
            result.merged.append(num)
            print(f"  ✓ #{num} merged {sha[:10]}")
        except GhError as exc:
            result.failed[num] = str(exc).splitlines()[0][:200]
            print(f"  ✗ #{num} failed: {exc}")
    return result


# --------------------------------------------------------------------------- report


def print_report(results: list[RepoResult], dry_run: bool) -> None:
    title = "PLAN (dry run)" if dry_run else "REPORT"
    print(f"\n{'=' * 20} {title} {'=' * 20}")
    header = f"{'repo':<36} {'runs':>5}  merged / failed"
    print(header)
    print("-" * len(header))
    for r in results:
        merged = ", ".join(f"#{n}" for n in r.merged) or "-"
        print(f"{r.repo:<36} {r.runs_cancelled:>5}  merged: {merged}")
        for n, why in r.failed.items():
            print(f"{'':<43}failed #{n}: {why}")
        for n, why in r.skipped.items():
            print(f"{'':<43}skipped #{n}: {why}")
        for err in r.run_errors:
            print(f"{'':<43}run cancel error {err}")
    total_merged = sum(len(r.merged) for r in results)
    total_failed = sum(len(r.failed) for r in results)
    print(f"\nRepos: {len(results)}  merged: {total_merged}  failed: {total_failed}")


# --------------------------------------------------------------------------- main


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cancel Actions runs and admin-merge all open PRs in selected repos.")
    p.add_argument("--dry-run", action="store_true", help="print the plan only; change nothing")
    p.add_argument("--method", choices=("squash", "merge", "rebase"), default="squash")
    p.add_argument("--include-drafts", action="store_true", help="mark drafts ready and merge them too")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    login = ensure_gh_auth()
    print(f"Authenticated as {login}. Loading repositories...")
    repos = list_repos(login)
    if not repos:
        print("No repositories found.")
        return 0

    selected = questionary.checkbox(
        "Select repositories (space to toggle, type to filter):",
        choices=repos,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()
    if not selected:
        print("Nothing selected.")
        return 0

    action = questionary.select("Action:", choices=["Merge all open PRs", "Quit"]).ask()
    if action != "Merge all open PRs":
        return 0

    print("\nOpen PRs:")
    for repo in selected:
        prs = open_prs(repo)
        drafts = sum(p["isDraft"] for p in prs)
        print(f"  {repo:<36} {len(prs)} open ({drafts} draft)")

    mode = "DRY RUN — nothing will change. " if args.dry_run else ""
    warning = (
        f"{mode}This will CANCEL ALL queued/running Actions runs and ADMIN-MERGE "
        f"({args.method}) every open PR{' including drafts' if args.include_drafts else ' (drafts skipped)'}, "
        "BYPASSING branch protection and deleting head branches. Continue?"
    )
    if not questionary.confirm(warning, default=False).ask():
        print("Aborted.")
        return 0

    results = [process_repo(repo, args) for repo in selected]
    print_report(results, args.dry_run)
    return 1 if any(r.failed or r.run_errors for r in results) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
