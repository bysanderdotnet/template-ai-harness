#!/usr/bin/env python3
"""Agent harness CLI — single source of truth for the session workflow.

Agents drive everything through this script; they never hand-edit the state
files behind it.

    init       session-start health check + state snapshot (hook/CI run this)
    verify     run the registered definition of done; records the result
    check      structure/state validation only (CI-safe before bootstrap)
    feature    scope: list / add / start / done / block / note
    log        record a progress entry (auto-stamps date, commit, verify result)
    progress   show recent progress entries (display is bounded, no compaction)
    cmd        register project commands: set / rm / list
    run        run one registered command by name

Standard library only; Python 3.8+. Config lives in .agents/harness.json,
state in .agents/state/. Register new build/test/lint commands with
`cmd set` instead of editing this file.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone


def find_root():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except OSError:
        pass
    # Fallback: this file lives at <root>/.agents/harness.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = find_root()
CONFIG_PATH = os.path.join(ROOT, ".agents", "harness.json")
PROGRESS_PATH = os.path.join(ROOT, ".agents", "state", "progress.json")
FEATURES_PATH = os.path.join(ROOT, ".agents", "state", "feature_list.json")
LAST_VERIFY_PATH = os.path.join(ROOT, ".agents", "state", "last_verify.json")
SKILLS_DIR = os.path.join(ROOT, ".agents", "skills")
TEMPLATE_GUARD = os.path.join(ROOT, "TEMPLATE_SETUP.md")

PROGRESS_DEFAULT_SHOWN = 5  # entries shown by `progress` / referenced by `init`


# ---------- small helpers ----------

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def git(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT)
    return out.stdout.strip() if out.returncode == 0 else ""


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_config():
    cfg = load_json(CONFIG_PATH, default=None)
    if cfg is None:
        cfg = {"commands": {}}
    cfg.setdefault("commands", {})
    return cfg


def load_features():
    data = load_json(FEATURES_PATH, default=None)
    if data is None:
        data = {"features": []}
    data.setdefault("features", [])
    return data


def find_feature(data, fid):
    for f in data["features"]:
        if f.get("id") == fid:
            return f
    return None


def fmt_feature(f):
    s = f"{f.get('id', '?')} — {f.get('title', '?')}"
    if f.get("notes"):
        s += f"  ({f['notes']})"
    return s


# ---------- structure / state checks ----------

def collect_problems():
    """Return (fails, warns) about harness structure and state files."""
    fails, warns = [], []

    def need_file(rel):
        if not os.path.isfile(os.path.join(ROOT, rel)):
            fails.append(f"{rel} missing")

    def need_link(rel):
        if not os.path.islink(os.path.join(ROOT, rel)):
            fails.append(f"{rel} symlink missing")

    need_file("AGENTS.md")
    need_link("CLAUDE.md")
    need_link("GEMINI.md")
    need_link(".claude/skills")
    need_file(".github/copilot-instructions.md")
    need_file(".agents/harness.json")
    need_file(".agents/state/progress.json")
    need_file(".agents/state/feature_list.json")

    for rel, path in ((".agents/harness.json", CONFIG_PATH),
                      (".agents/state/progress.json", PROGRESS_PATH),
                      (".agents/state/feature_list.json", FEATURES_PATH)):
        if os.path.isfile(path):
            try:
                load_json(path)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                fails.append(f"{rel} is not valid JSON: {e}")

    try:
        feats = load_features()["features"]
        wip = [f for f in feats if f.get("status") == "in_progress"]
        if len(wip) > 1:
            warns.append("%d features in_progress (policy: max 1): %s"
                         % (len(wip), ", ".join(f.get("id", "?") for f in wip)))
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass  # already reported as a fail above

    if os.path.isdir(SKILLS_DIR):
        for name in sorted(os.listdir(SKILLS_DIR)):
            d = os.path.join(SKILLS_DIR, name)
            if not os.path.isdir(d):
                continue
            md = os.path.join(d, "SKILL.md")
            if not os.path.isfile(md):
                warns.append(f".agents/skills/{name}/ has no SKILL.md")
            elif not skill_description(md):
                warns.append(f".agents/skills/{name}/SKILL.md missing 'description:' frontmatter")
    return fails, warns


def skill_description(md_path):
    """First 'description:' line in the frontmatter block."""
    try:
        with open(md_path, encoding="utf-8") as fh:
            in_frontmatter = False
            for i, line in enumerate(fh):
                if line.strip() == "---":
                    if in_frontmatter:
                        break
                    in_frontmatter = i == 0
                elif in_frontmatter and line.startswith("description:"):
                    return line.partition(":")[2].strip()
    except OSError:
        pass
    return ""


def list_skills():
    rows = []
    if os.path.isdir(SKILLS_DIR):
        for name in sorted(os.listdir(SKILLS_DIR)):
            md = os.path.join(SKILLS_DIR, name, "SKILL.md")
            if os.path.isfile(md):
                rows.append((name, skill_description(md) or "(no description)"))
    return rows


# ---------- progress rendering ----------

def render_entry(e, indent="  "):
    head = f"{e.get('date', '?')} — {e.get('title', '?')}"
    if e.get("feature"):
        head += f"  [{e['feature']}]"
    lines = [head]
    for key in ("done", "verified", "issues", "next", "blockers"):
        if e.get(key):
            lines.append(f"{indent}{key}: {e[key]}")
    if e.get("commit"):
        lines.append(f"{indent}commit: {e['commit']}")
    return "\n".join(lines)


def progress_entries():
    data = load_json(PROGRESS_PATH, default=None) or {}
    return data.get("entries", [])


# ---------- commands: init / verify / check ----------

def template_guard(action):
    if os.path.isfile(TEMPLATE_GUARD):
        print(f"TEMPLATE_SETUP.md exists: template setup incomplete; {action} blocked.")
        print("Complete the checklist in TEMPLATE_SETUP.md before feature work")
        print("(playbook: .agents/skills/bootstrap-project/SKILL.md).")
        sys.exit(1)


def cmd_check(_args):
    fails, warns = collect_problems()
    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print("== check FAILED ==")
        sys.exit(1)
    print("== check OK: harness structure and state files valid ==")


def cmd_init(_args):
    print("== harness init: session start ==")
    template_guard("init")

    fails, warns = collect_problems()
    print("-- structure --")
    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")
    if not fails:
        print("structure OK")

    print("-- skills (playbooks; follow them when the task matches) --")
    skills = list_skills()
    for name, desc in skills:
        print(f"  {name}: {desc}")
    if not skills:
        print("  (none)")

    print("-- git --")
    print(git("status", "--short", "--branch") or "(not a git checkout)")
    print(git("log", "--oneline", "-5") or "(no commits yet)")

    print("-- scope --")
    try:
        feats = load_features()["features"]
        wip = [f for f in feats if f.get("status") == "in_progress"]
        todo = [f for f in feats if f.get("status") == "todo"]
        blocked = [f for f in feats if f.get("status") == "blocked"]
        if wip:
            print(f"in_progress: {fmt_feature(wip[0])}")
        elif todo:
            print(f"nothing in_progress. Next todo: {fmt_feature(todo[0])}")
        else:
            print("nothing in_progress, no todos left.")
        if blocked:
            print(f"blocked: {len(blocked)} "
                  f"({', '.join(f.get('id', '?') for f in blocked)})")
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass  # reported under structure

    print("-- progress --")
    entries = progress_entries()
    if entries:
        latest = entries[-1]
        print(f"{len(entries)} entries. Latest:")
        print(render_entry(latest))
        blockers = latest.get("blockers", "")
        if blockers and blockers.lower() not in ("none", "none.", "no", "-"):
            print(f"NOTE: open blocker from last session: {blockers}")
        if len(entries) > 1:
            print(f"(older entries: python3 .agents/harness.py progress)")
    else:
        print("no entries yet. Record work with: python3 .agents/harness.py log")

    print("-- registered commands --")
    cfg = load_config()
    cmds = cfg["commands"]
    if cmds:
        for name, c in cmds.items():
            flags = "".join(
                f" [{f}]" for f in ("verify", "init") if c.get(f))
            print(f"  {name}: {c.get('run', '?')}{flags}")
    else:
        print("  none. Register with: python3 .agents/harness.py cmd set <name> \"<cmd>\" [--verify] [--init]")
    if not any(c.get("verify") for c in cmds.values()):
        warns.append("no --verify commands registered: `verify` has nothing to run")
        print("WARN: no --verify commands registered: `verify` has nothing to run.")

    init_cmds = [(n, c) for n, c in cmds.items() if c.get("init")]
    if init_cmds:
        print("-- init checks --")
        for name, c in init_cmds:
            print(f"-> {name}: {c['run']}")
            rc = subprocess.run(c["run"], shell=True, cwd=ROOT).returncode
            if rc != 0:
                fails.append(f"init check '{name}' failed (exit {rc})")
                print(f"FAIL: init check '{name}' exited {rc}")

    if fails:
        print("== init FAILED: fix the FAILs above before feature work. ==")
        sys.exit(1)
    print("== init OK. Pick ONE item: user request or the next todo above. ==")


def cmd_verify(_args):
    print("== harness verify: definition of done ==")
    template_guard("verify")

    cfg = load_config()
    steps = [(n, c) for n, c in cfg["commands"].items() if c.get("verify")]
    if not steps:
        print("No verify commands registered — nothing gates completion.")
        print("Register them (cheap/fast first), e.g.:")
        print('  python3 .agents/harness.py cmd set lint "npm run lint" --verify')
        print('  python3 .agents/harness.py cmd set test "npm test" --verify')
        record_verify("fail", failed="(no verify commands registered)")
        sys.exit(1)

    failed = None
    for name, c in steps:
        print(f"-- {name}: {c['run']} --")
        rc = subprocess.run(c["run"], shell=True, cwd=ROOT).returncode
        if rc != 0:
            failed = f"{name} (exit {rc})"
            print(f"FAIL: step '{name}' exited {rc}; aborting remaining steps.")
            break

    record_verify("fail" if failed else "pass", failed=failed)
    if failed:
        print(f"== verify FAILED at {failed}. Not done. ==")
        sys.exit(1)
    print(f"== verify OK: all {len(steps)} step(s) green ==")


def record_verify(result, failed=None):
    save_json(LAST_VERIFY_PATH, {
        "result": result,
        "failed_step": failed,
        "date": now_utc(),
        "head": git("rev-parse", "--short", "HEAD") or None,
    })


# ---------- commands: log / progress ----------

def verified_note():
    lv = load_json(LAST_VERIFY_PATH, default=None)
    if not lv:
        return "unverified (no verify run recorded)"
    note = f"{lv.get('result', '?')} ({lv.get('date', '?')} @ {lv.get('head') or 'no-commit'})"
    if lv.get("result") == "fail" and lv.get("failed_step"):
        note += f" — failed at {lv['failed_step']}"
    head = git("rev-parse", "--short", "HEAD") or None
    if lv.get("head") != head:
        note += " — STALE: HEAD moved since that run, re-verify"
    return note


def cmd_log(args):
    data = load_json(PROGRESS_PATH, default=None) or {}
    data.setdefault("entries", [])
    entry = {
        "date": now_utc(),
        "title": args.title,
        "done": args.done,
        "verified": args.verified or verified_note(),
    }
    if args.issues:
        entry["issues"] = args.issues
    if args.next:
        entry["next"] = args.next
    entry["blockers"] = args.blockers or "none"
    if args.feature:
        if find_feature(load_features(), args.feature) is None:
            print(f"WARN: feature '{args.feature}' not in feature list; logging anyway.")
        entry["feature"] = args.feature
    head = git("rev-parse", "--short", "HEAD")
    if head:
        entry["commit"] = head + (" (+ uncommitted changes)" if git("status", "--porcelain") else "")
    data["entries"].append(entry)
    save_json(PROGRESS_PATH, data)
    print("Logged:")
    print(render_entry(entry))
    print("Remember: commit state files with the feature.")


def cmd_progress(args):
    entries = progress_entries()
    if not entries:
        print("No progress entries yet. Record work with: python3 .agents/harness.py log")
        return
    n = len(entries) if args.all else max(1, args.n)
    shown = entries[-n:]
    for e in reversed(shown):  # newest first
        print(render_entry(e))
        print()
    hidden = len(entries) - len(shown)
    if hidden:
        print(f"({hidden} older entr{'y' if hidden == 1 else 'ies'} hidden — use --all or -n)")


# ---------- commands: feature ----------

def cmd_feature(args):
    data = load_features()
    feats = data["features"]

    if args.action == "list":
        by = {"in_progress": [], "todo": [], "blocked": [], "done": []}
        for f in feats:
            by.setdefault(f.get("status", "todo"), []).append(f)
        for status in ("in_progress", "todo", "blocked"):
            if by[status]:
                print(f"{status}:")
                for f in by[status]:
                    print(f"  {fmt_feature(f)}")
        if args.all:
            if by["done"]:
                print("done:")
                for f in by["done"]:
                    print(f"  {fmt_feature(f)}")
        elif by["done"]:
            print(f"done: {len(by['done'])} (use --all to show)")
        if not feats:
            print("No features. Add one: python3 .agents/harness.py feature add \"<title>\"")
        return

    if args.action == "add":
        if not args.title:
            die("feature add needs a title: feature add \"<title>\"")
        fid = args.id
        if fid is None:
            nums = [int(m.group(1)) for f in feats
                    for m in [re.match(r"F-(\d+)$", f.get("id", ""))] if m]
            fid = f"F-{(max(nums) + 1 if nums else 1):03d}"
        if find_feature(data, fid):
            die(f"feature id '{fid}' already exists")
        f = {"id": fid, "title": args.title, "status": "todo"}
        if args.notes:
            f["notes"] = args.notes
        feats.append(f)
        save_json(FEATURES_PATH, data)
        print(f"Added: {fmt_feature(f)}")
        return

    # remaining actions operate on an existing id
    if not args.title:
        die(f"feature {args.action} needs an id, e.g.: feature {args.action} F-001")
    f = find_feature(data, args.title)
    if f is None:
        die(f"no feature with id '{args.title}' (see: feature list --all)")

    if args.action == "start":
        wip = [x for x in feats if x.get("status") == "in_progress" and x is not f]
        if wip:
            die(f"{wip[0].get('id')} already in_progress (policy: max 1). "
                f"Finish it (feature done {wip[0].get('id')}) or block it first.")
        f["status"] = "in_progress"
    elif args.action == "done":
        f["status"] = "done"
    elif args.action == "block":
        f["status"] = "blocked"
        if args.notes:
            f["notes"] = args.notes
        elif not f.get("notes"):
            print("WARN: blocked without a reason — pass --notes \"why\".")
    elif args.action == "note":
        if not args.notes:
            die("feature note needs --notes \"text\"")
        f["notes"] = args.notes
    save_json(FEATURES_PATH, data)
    print(f"{f['id']} -> {f['status']}" + (f" ({f['notes']})" if f.get("notes") else ""))


# ---------- commands: cmd / run ----------

def cmd_cmd(args):
    cfg = load_config()
    cmds = cfg["commands"]

    if args.action == "list":
        if not cmds:
            print("No commands registered. Example:")
            print('  python3 .agents/harness.py cmd set test "npm test" --verify')
            return
        for name, c in cmds.items():
            flags = "".join(f" [{f}]" for f in ("verify", "init") if c.get(f))
            desc = f"  # {c['desc']}" if c.get("desc") else ""
            print(f"  {name}: {c.get('run', '?')}{flags}{desc}")
        print("Run one: python3 .agents/harness.py run <name>. "
              "[verify] steps run in listed order.")
        return

    if not args.name:
        die(f"cmd {args.action} needs a name")
    if args.action == "rm":
        if args.name not in cmds:
            die(f"no command named '{args.name}'")
        del cmds[args.name]
        save_json(CONFIG_PATH, cfg)
        print(f"Removed '{args.name}'.")
        return

    # set
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", args.name):
        die("command name must be lowercase letters/digits/dashes/underscores")
    if not args.command:
        die('cmd set needs the shell command: cmd set <name> "<shell command>"')
    entry = {"run": args.command}
    if args.verify:
        entry["verify"] = True
    if args.init:
        entry["init"] = True
    if args.desc:
        entry["desc"] = args.desc
    existed = args.name in cmds
    cmds[args.name] = entry  # keeps position if existing, appends if new
    save_json(CONFIG_PATH, cfg)
    flags = "".join(f" [{f}]" for f in ("verify", "init") if entry.get(f))
    print(f"{'Updated' if existed else 'Registered'} {args.name}: {args.command}{flags}")
    if args.verify:
        print("Reminder: keep CI toolchain (.github/workflows/agents.yml) able to run this.")


def cmd_run(args):
    cfg = load_config()
    c = cfg["commands"].get(args.name)
    if c is None:
        die(f"no command named '{args.name}' (see: cmd list)")
    print(f"-- {args.name}: {c['run']} --")
    sys.exit(subprocess.run(c["run"], shell=True, cwd=ROOT).returncode)


# ---------- argument parsing ----------

def build_parser():
    p = argparse.ArgumentParser(
        prog="harness.py",
        description="Agent harness: init -> pick ONE feature -> implement -> "
                    "verify -> log + feature done -> commit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="State lives in .agents/; manage it through these subcommands, "
               "never by hand-editing the JSON files.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="session-start health check + state snapshot").set_defaults(fn=cmd_init)
    sub.add_parser("verify", help="run the registered definition of done").set_defaults(fn=cmd_verify)
    sub.add_parser("check", help="structure/state validation only (CI-safe pre-bootstrap)").set_defaults(fn=cmd_check)

    lg = sub.add_parser("log", help="record a progress entry (terse 'caveman' style)")
    lg.add_argument("title", help="short entry title")
    lg.add_argument("--done", required=True, help="what shipped (paths, behavior)")
    lg.add_argument("--issues", help="broken/known issues: facts, exact errors")
    lg.add_argument("--next", help="single most useful next step")
    lg.add_argument("--blockers", help="what stops progress (default: none)")
    lg.add_argument("--feature", help="related feature id, e.g. F-001")
    lg.add_argument("--verified", help="override auto-detected verify status")
    lg.set_defaults(fn=cmd_log)

    pr = sub.add_parser("progress", help="show recent progress entries, newest first")
    pr.add_argument("-n", type=int, default=PROGRESS_DEFAULT_SHOWN, help="how many entries (default %(default)s)")
    pr.add_argument("--all", action="store_true", help="show every entry")
    pr.set_defaults(fn=cmd_progress)

    ft = sub.add_parser("feature", help="manage scope (feature_list.json)")
    ft.add_argument("action", choices=["list", "add", "start", "done", "block", "note"])
    ft.add_argument("title", nargs="?", help="title (for add) or feature id (for start/done/block/note)")
    ft.add_argument("--id", help="explicit id for add (default: next F-NNN)")
    ft.add_argument("--notes", help="notes text (add/block/note)")
    ft.add_argument("--all", action="store_true", help="list: include done features")
    ft.set_defaults(fn=cmd_feature)

    cm = sub.add_parser("cmd", help="register project commands (build/test/lint/...)")
    cm.add_argument("action", choices=["set", "rm", "list"])
    cm.add_argument("name", nargs="?", help="command name, e.g. test")
    cm.add_argument("command", nargs="?", help="shell command, e.g. \"npm test\"")
    cm.add_argument("--verify", action="store_true", help="part of the definition of done (run by `verify`)")
    cm.add_argument("--init", action="store_true", help="session-start smoke check (run by `init`)")
    cm.add_argument("--desc", help="one-line description")
    cm.set_defaults(fn=cmd_cmd)

    rn = sub.add_parser("run", help="run a registered command by name")
    rn.add_argument("name")
    rn.set_defaults(fn=cmd_run)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
