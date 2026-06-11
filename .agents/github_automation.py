#!/usr/bin/env python3
"""GitHub automation helpers for template workflows."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".agents" / "agents.json"
MARKER = "<!-- agents-auto-merge-pr -->"
BAD_STATUS_STATES = {"failure", "error"}
BAD_CHECK_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}
OK_CHECK_CONCLUSIONS = {"success", "neutral", "skipped"}
PENDING_CHECK_STATUSES = {"queued", "requested", "waiting", "pending", "in_progress"}


def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def setting(cfg, section):
    return cfg.get("settings", {}).get(section, {})


def gh_json(*args):
    proc = subprocess.run(["gh", "api", *args], cwd=ROOT, text=True,
                          capture_output=True)
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        raise SystemExit(proc.returncode)
    return json.loads(proc.stdout or "null")


def gh_run(*args):
    proc = subprocess.run(["gh", *args], cwd=ROOT, text=True,
                          capture_output=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    return proc.returncode


def set_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def open_prs(repo):
    return gh_json(f"repos/{repo}/pulls", "-f", "state=open", "-f", "per_page=100")


def pr_details(repo, number):
    detail = None
    for _ in range(6):
        detail = gh_json(f"repos/{repo}/pulls/{number}")
        if detail.get("mergeable") is not None:
            break
        time.sleep(2)
    return detail


def ci_state(repo, sha):
    status = gh_json(f"repos/{repo}/commits/{sha}/status")
    check_runs = gh_json(f"repos/{repo}/commits/{sha}/check-runs", "-f", "per_page=100")

    statuses = status.get("statuses") or []
    checks = check_runs.get("check_runs") or []
    has_ci = bool(statuses or checks)

    failures = []
    pending = []

    for item in statuses:
        name = item.get("context") or "commit status"
        state = item.get("state")
        if state in BAD_STATUS_STATES:
            failures.append(f"{name}: {state}")
        elif state not in {"success"}:
            pending.append(f"{name}: {state}")

    for item in checks:
        name = item.get("name") or "check run"
        status_name = item.get("status")
        conclusion = item.get("conclusion")
        if status_name == "completed":
            if conclusion in BAD_CHECK_CONCLUSIONS:
                failures.append(f"{name}: {conclusion}")
            elif conclusion not in OK_CHECK_CONCLUSIONS:
                pending.append(f"{name}: {conclusion or 'unknown'}")
        elif status_name in PENDING_CHECK_STATUSES or status_name:
            pending.append(f"{name}: {status_name}")

    return has_ci, failures, pending


def comment_body(reason, tags):
    tag_line = " ".join(tags).strip()
    lead = f"{tag_line}\n\n" if tag_line else ""
    return (f"{lead}{MARKER}\n"
            "Auto-merge blocked. Fix needed:\n"
            f"- {reason}")


def ensure_comment(repo, number, body):
    comments = gh_json(f"repos/{repo}/issues/{number}/comments", "-f", "per_page=100")
    for comment in comments:
        if MARKER in (comment.get("body") or ""):
            if comment.get("body") == body:
                print(f"PR #{number}: blocked comment already current")
                return
            gh_run("api", f"repos/{repo}/issues/comments/{comment['id']}",
                   "-X", "PATCH", "-f", f"body={body}")
            print(f"PR #{number}: blocked comment updated")
            return
    gh_run("api", f"repos/{repo}/issues/{number}/comments", "-f", f"body={body}")
    print(f"PR #{number}: blocked comment posted")


def auto_merge_pr(args):
    cfg = load_config()
    cfg_set = setting(cfg, "auto_merge_pr")
    prs = open_prs(args.repo)
    set_output("auto_merge_enabled", str(bool(cfg_set.get("enabled"))).lower())

    if not cfg_set.get("enabled", False):
        print("auto-merge-pr disabled")
        set_output("has_open_prs", str(bool(prs)).lower())
        return

    notify = cfg_set.get("notify_on_blocked", False)
    tags = cfg_set.get("notify_tags") or []

    for pr in prs:
        number = pr["number"]
        detail = pr_details(args.repo, number)
        sha = detail["head"]["sha"]
        title = detail.get("title", "")
        print(f"PR #{number}: {title}")

        if detail.get("mergeable") is False:
            reason = "merge conflicts"
            print(f"PR #{number}: blocked: {reason}")
            if notify:
                ensure_comment(args.repo, number, comment_body(reason, tags))
            continue

        has_ci, failures, pending = ci_state(args.repo, sha)
        if failures:
            reason = "CI failing: " + "; ".join(failures)
            print(f"PR #{number}: blocked: {reason}")
            if notify:
                ensure_comment(args.repo, number, comment_body(reason, tags))
            continue
        if has_ci and pending:
            print(f"PR #{number}: waiting for CI: {'; '.join(pending)}")
            continue

        rc = gh_run("pr", "merge", str(number), "--merge", "--repo", args.repo)
        if rc == 0:
            print(f"PR #{number}: merged")
        else:
            print(f"PR #{number}: merge command failed")

    remaining = open_prs(args.repo)
    set_output("has_open_prs", str(bool(remaining)).lower())
    print(f"open_prs_remaining={len(remaining)}")


def open_features(cfg):
    return [f for f in cfg.get("features", []) if f.get("status") != "done"]


def call_webhook(url, repo):
    encoded = quote(repo, safe="")
    final_url = url.replace("{r}", encoded).replace("{repo}", encoded)
    req = Request(final_url, headers={"User-Agent": "template-ai-harness"})
    with urlopen(req, timeout=30) as resp:
        print(f"webhook_status={resp.status}")


def auto_create_pr(args):
    cfg = load_config()
    cfg_set = setting(cfg, "auto_create_pr")

    if not cfg_set.get("enabled", False):
        print("auto-create-pr disabled")
        return
    if args.has_open_prs == "true":
        print("open PRs remain; auto-create-pr stopped")
        return

    url = cfg_set.get("webhook_url", "")
    repo = cfg_set.get("repository", "")
    if not url or not repo:
        print("auto-create-pr needs webhook_url and repository; not calling URL")
        return

    feats = open_features(cfg)
    if not feats:
        print("no open features; auto-create-pr stopped")
        return

    print(f"open_features={len(feats)}")
    call_webhook(url, repo)


def build_parser():
    parser = argparse.ArgumentParser(description="GitHub automation for template-ai-harness")
    sub = parser.add_subparsers(dest="command", required=True)
    merge = sub.add_parser("auto-merge-pr")
    merge.add_argument("--repo", required=True, help="GitHub repository, org/name")
    merge.set_defaults(fn=auto_merge_pr)

    create = sub.add_parser("auto-create-pr")
    create.add_argument("--has-open-prs", choices=["true", "false"], required=True)
    create.set_defaults(fn=auto_create_pr)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
