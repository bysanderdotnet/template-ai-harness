#!/usr/bin/env python3
"""agents.py — the agent harness. One CLI guides the whole workflow.

Subcommands (each has --help with details and examples):

    setup     guided first-time project setup, one step at a time
    init      session-start health check + state snapshot (hook/CI run this)
    verify    run the registered definition of done; records the result
    handoff   end-of-session checklist with live status
    feature   scope: list / add / start / done / block / note
    log       record a progress entry (auto-stamps date, commit, verify result)
    progress  show recent progress entries (display bounded, never compact by hand)
    cmd       register project commands: set / rm / list
    run       run one registered command by name
    check     structure/state validation only
    ci        what CI runs: check, then init + verify once setup is complete

Standard library only; Python 3.8+. Config lives in .agents/agents.json,
state in .agents/state/ — owned by this script, never hand-edited. Register
new build/test/lint commands with `cmd set` instead of editing this file.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

SCRIPT = "python3 .agents/agents.py"


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
    # Fallback: this file lives at <root>/.agents/agents.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = find_root()
CONFIG_PATH = os.path.join(ROOT, ".agents", "agents.json")
PROGRESS_PATH = os.path.join(ROOT, ".agents", "state", "progress.json")
FEATURES_PATH = os.path.join(ROOT, ".agents", "state", "feature_list.json")
LAST_VERIFY_PATH = os.path.join(ROOT, ".agents", "state", "last_verify.json")
SKILLS_DIR = os.path.join(ROOT, ".agents", "skills")
DOCS_DIR = os.path.join(ROOT, ".agents", "docs")

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


def tip(msg):
    print(f"next: {msg}")


def load_config():
    cfg = load_json(CONFIG_PATH, default=None)
    if cfg is None:
        cfg = {"commands": {}}
    cfg.setdefault("commands", {})
    return cfg


def setup_pending(cfg=None):
    """Setup state dict while setup is incomplete, else None."""
    return (cfg or load_config()).get("setup")


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
    need_file(".agents/agents.json")
    need_file(".agents/state/progress.json")
    need_file(".agents/state/feature_list.json")

    for rel, path in ((".agents/agents.json", CONFIG_PATH),
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


# ---------- guided setup ----------
# Each step: (name, summary, instructions, check). check() returns
# (ok, detail); check=None means the step is confirmed manually.

SETUP_MARKER = "TODO" + "(setup)"  # built dynamically so the finalize scan skips this file cleanly


def _check_project():
    path = os.path.join(ROOT, "AGENTS.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return False, "AGENTS.md unreadable"
    m = re.search(r"^## Project\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return False, "AGENTS.md has no '## Project' section"
    section = m.group(1)
    if SETUP_MARKER in section:
        return False, f"AGENTS.md '## Project' still contains {SETUP_MARKER}"
    if not re.search(r"^- (Name|Stack|Purpose):\s*\S", section, re.M):
        return False, "AGENTS.md '## Project' fields look empty"
    return True, "AGENTS.md project section filled"


def _check_commands():
    cmds = load_config()["commands"]
    n = sum(1 for c in cmds.values() if c.get("verify"))
    if n:
        return True, f"{n} --verify command(s) registered"
    return False, "no --verify commands registered"


def _check_docs():
    leftover = []
    for dirpath, _dirs, files in os.walk(DOCS_DIR):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, encoding="utf-8") as fh:
                    if SETUP_MARKER in fh.read():
                        leftover.append(os.path.relpath(p, ROOT))
            except OSError:
                pass
    if leftover:
        return False, f"{SETUP_MARKER} left in: {', '.join(leftover)}"
    return True, "docs have no setup markers left"


def _check_scope():
    feats = load_features()["features"]
    rest = [f for f in feats if f.get("id") != "F-000"]
    if rest:
        return True, f"{len(rest)} feature(s) seeded"
    return False, "no features besides F-000"


SETUP_STEPS = [
    ("project", "Project identity (AGENTS.md + README.md)", f"""\
1. Fill '## Project' in AGENTS.md: name, stack, purpose (2-4 lines).
   Remove its {SETUP_MARKER} comment. Add source-dir rows to the repo map.
2. Rewrite README.md for the actual project (template text is placeholder).
Infer from the codebase first (code, lockfiles, configs, CI); ask the user
only what you cannot infer (purpose, planned stack on an empty repo).""",
     _check_project),

    ("commands", "Register project commands", f"""\
Find the real commands (package.json scripts, Makefile, pyproject, CI) and
register them — never edit agents.py itself:
  {SCRIPT} cmd set lint "npm run lint" --verify
  {SCRIPT} cmd set test "npm test" --verify        # --verify = definition of done, cheap/fast first
  {SCRIPT} cmd set deps "npm ci" --init            # --init = session-start smoke check
  {SCRIPT} cmd set dev "npm run dev"               # no flag = on-demand helper
Then fill the toolchain {SETUP_MARKER} block in .github/workflows/agents.yml
so CI can run them. Don't invent commands that don't exist.
Repo has no code yet? Delete that CI comment block anyway, add a feature
"set up toolchain + verify commands" in the scope step, and mark this step:
  {SCRIPT} setup done commands --force""",
     _check_commands),

    ("docs", "Fill deep-dive docs", f"""\
Fill the {SETUP_MARKER} markers in:
  .agents/docs/architecture.md   modules, data flow, key dirs
  .agents/docs/conventions.md    naming, formatting, commit style
  .agents/docs/testing.md        how to run/write tests, expectations
Delete sections that don't apply; "nothing yet" is a fine answer.""",
     _check_docs),

    ("scope", "Seed the feature list", f"""\
Agree initial features with the user, then:
  {SCRIPT} feature add "<title>" [--notes "..."]
One entry per feature, smallest shippable units first.""",
     _check_scope),

    ("guardrails", "Project rules + .gitignore", f"""\
1. Add project-specific rules / no-go zones to '## Rules' in AGENTS.md
   (e.g. "never edit /migrations"). Remove its {SETUP_MARKER} comment.
2. Review .gitignore for the stack; replace its {SETUP_MARKER} line.
Manual step — when finished, mark it:
  {SCRIPT} setup done guardrails""",
     None),
]


def scan_setup_markers():
    """Tracked files still containing the setup marker (this script excluded)."""
    out = subprocess.run(
        ["git", "grep", "-l", "-F", SETUP_MARKER, "--", ".", ":!.agents/agents.py"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def setup_finalize(cfg):
    """All steps recorded: run the final gates, then lift setup mode."""
    print("-- finalize: all steps recorded, running final gates --")
    blockers = []
    fails, _warns = collect_problems()
    blockers += [f"structure: {f}" for f in fails]
    leftover = scan_setup_markers()
    if leftover:
        blockers.append(f"{SETUP_MARKER} still in: {', '.join(leftover)}")
    steps = [(n, c) for n, c in cfg["commands"].items() if c.get("verify")]
    if steps and not run_verify_steps(steps):
        blockers.append("verify is red — fix before completing setup")
    if blockers:
        print("Setup NOT complete:")
        for b in blockers:
            print(f"  BLOCKED: {b}")
        tip(f"fix the blockers, then rerun: {SCRIPT} setup")
        sys.exit(1)

    feats = load_features()
    f000 = find_feature(feats, "F-000")
    if f000:
        f000["status"] = "done"
        save_json(FEATURES_PATH, feats)
    del cfg["setup"]
    save_json(CONFIG_PATH, cfg)
    append_log_entry({
        "date": now_utc(),
        "title": "project setup",
        "done": "setup complete: %d command(s) registered, %d feature(s) seeded"
                % (len(cfg["commands"]),
                   len([f for f in feats["features"] if f.get("id") != "F-000"])),
        "verified": verified_note(),
        "blockers": "none",
        "feature": "F-000",
    })
    print("== setup COMPLETE (progress entry written, F-000 closed) ==")
    tip("commit everything: git commit -m 'chore: complete project setup'; push if expected")
    tip(f"then start the first feature: {SCRIPT} feature start <id>")


def cmd_setup(args):
    cfg = load_config()
    state = setup_pending(cfg)
    if state is None:
        print("Setup already complete.")
        tip(f"{SCRIPT} init")
        return
    state.setdefault("done", [])
    names = [n for n, *_ in SETUP_STEPS]

    if args.action == "done":
        if not args.step or args.step not in names:
            die(f"setup done needs a step name: {', '.join(names)}")
        _, _, _, check = SETUP_STEPS[names.index(args.step)]
        if check and not args.force:
            ok, detail = check()
            if not ok:
                die(f"step '{args.step}' not done: {detail}. Fix it, or override with --force.")
        if args.step not in state["done"]:
            state["done"].append(args.step)
            save_json(CONFIG_PATH, cfg)
        print(f"step '{args.step}' recorded.")

    # Status, plus full instructions for the first pending step only —
    # the right information at the right time.
    print("== setup: guided project configuration ==")
    pending = []
    for name, summary, _instr, check in SETUP_STEPS:
        if name in state["done"]:
            print(f"  [ok] {name}: {summary}")
            continue
        if check:
            ok, detail = check()
            if ok:
                state["done"].append(name)
                save_json(CONFIG_PATH, cfg)
                print(f"  [ok] {name}: {summary} — auto-detected ({detail})")
                continue
            print(f"  [..] {name}: {summary} — {detail}")
        else:
            print(f"  [..] {name}: {summary} — manual confirm")
        pending.append(name)

    if not pending:
        setup_finalize(cfg)
        return
    name = pending[0]
    _n, summary, instructions, check = SETUP_STEPS[names.index(name)]
    print(f"-- current step: {name} — {summary} --")
    print(instructions)
    if check:
        tip(f"step auto-completes once its check passes — rerun: {SCRIPT} setup")
    sys.exit(1)


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


def append_log_entry(entry):
    data = load_json(PROGRESS_PATH, default=None) or {}
    data.setdefault("entries", [])
    data["entries"].append(entry)
    save_json(PROGRESS_PATH, data)


# ---------- init / verify / check / ci ----------

def cmd_init(_args):
    print("== init: session start ==")
    cfg = load_config()

    fails, warns = collect_problems()
    print("-- structure --")
    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")
    if not fails:
        print("structure OK")

    if setup_pending(cfg) is not None:
        done = setup_pending(cfg).get("done", [])
        print("-- SETUP MODE --")
        print(f"Project not configured yet ({len(done)}/{len(SETUP_STEPS)} steps recorded).")
        print("Complete guided setup before feature work — it shows status and")
        print(f"instructions for the current step: {SCRIPT} setup")
        sys.exit(1)

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
    wip, nxt = [], None
    try:
        feats = load_features()["features"]
        wip = [f for f in feats if f.get("status") == "in_progress"]
        todo = [f for f in feats if f.get("status") == "todo"]
        blocked = [f for f in feats if f.get("status") == "blocked"]
        nxt = todo[0] if todo else None
        if wip:
            print(f"in_progress: {fmt_feature(wip[0])}")
        elif nxt:
            print(f"nothing in_progress. Next todo: {fmt_feature(nxt)}")
        else:
            print("nothing in_progress, no todos left.")
        if blocked:
            print(f"blocked: {len(blocked)} "
                  f"({', '.join(f.get('id', '?') for f in blocked)})")
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass  # reported under structure

    print("-- progress --")
    entries = progress_entries()
    open_blocker = None
    if entries:
        latest = entries[-1]
        print(f"{len(entries)} entries. Latest:")
        print(render_entry(latest))
        blockers = latest.get("blockers", "")
        if blockers and blockers.lower() not in ("none", "none.", "no", "-"):
            open_blocker = blockers
        if len(entries) > 1:
            print(f"(older entries: {SCRIPT} progress)")
    else:
        print(f"no entries yet. Record work with: {SCRIPT} log")

    print("-- registered commands --")
    cmds = cfg["commands"]
    if cmds:
        for name, c in cmds.items():
            flags = "".join(f" [{f}]" for f in ("verify", "init") if c.get(f))
            print(f"  {name}: {c.get('run', '?')}{flags}")
    else:
        print(f"  none. Register with: {SCRIPT} cmd set <name> \"<cmd>\" [--verify] [--init]")
    if not any(c.get("verify") for c in cmds.values()):
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
    print("== init OK ==")
    if open_blocker:
        tip(f"resolve or re-confirm the open blocker first: {open_blocker}")
    if wip:
        tip(f"continue {wip[0].get('id')}; when done: {SCRIPT} verify, then {SCRIPT} handoff")
    elif nxt:
        tip(f"pick ONE item: user request, or {SCRIPT} feature start {nxt.get('id')}")
    else:
        tip(f"no open scope — agree next features with the user: {SCRIPT} feature add \"<title>\"")


def run_verify_steps(steps):
    """Run verify-flagged commands in order; record + return overall result."""
    failed = None
    for name, c in steps:
        print(f"-- {name}: {c['run']} --")
        rc = subprocess.run(c["run"], shell=True, cwd=ROOT).returncode
        if rc != 0:
            failed = f"{name} (exit {rc})"
            print(f"FAIL: step '{name}' exited {rc}; aborting remaining steps.")
            break
    record_verify("fail" if failed else "pass", failed=failed)
    return failed is None


def cmd_verify(_args):
    print("== verify: definition of done ==")
    cfg = load_config()
    if setup_pending(cfg) is not None:
        print(f"Project setup incomplete — finish it first: {SCRIPT} setup")
        sys.exit(1)
    steps = [(n, c) for n, c in cfg["commands"].items() if c.get("verify")]
    if not steps:
        print("No verify commands registered — nothing gates completion.")
        print("Register them (cheap/fast first), e.g.:")
        print(f'  {SCRIPT} cmd set lint "npm run lint" --verify')
        print(f'  {SCRIPT} cmd set test "npm test" --verify')
        record_verify("fail", failed="(no verify commands registered)")
        sys.exit(1)
    if run_verify_steps(steps):
        print(f"== verify OK: all {len(steps)} step(s) green ==")
        tip(f"{SCRIPT} handoff — log the work, close the feature, commit")
    else:
        print("== verify FAILED. Not done — fix and rerun. ==")
        sys.exit(1)


def record_verify(result, failed=None):
    save_json(LAST_VERIFY_PATH, {
        "result": result,
        "failed_step": failed,
        "date": now_utc(),
        "head": git("rev-parse", "--short", "HEAD") or None,
    })


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


def cmd_ci(args):
    cmd_check(args)
    if setup_pending() is not None:
        print("Project setup incomplete — structure gate only; init/verify skipped.")
        return
    cmd_init(args)   # exits non-zero on failure
    cmd_verify(args)


# ---------- log / progress / handoff ----------

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
    append_log_entry(entry)
    print("Logged:")
    print(render_entry(entry))
    if args.blockers:
        tip(f"if a feature is stuck on this, record it: {SCRIPT} feature block <id> --notes \"{args.blockers}\"")
    tip("commit state files together with the feature")


def cmd_progress(args):
    entries = progress_entries()
    if not entries:
        print(f"No progress entries yet. Record work with: {SCRIPT} log")
        return
    n = len(entries) if args.all else max(1, args.n)
    shown = entries[-n:]
    for e in reversed(shown):  # newest first
        print(render_entry(e))
        print()
    hidden = len(entries) - len(shown)
    if hidden:
        print(f"({hidden} older entr{'y' if hidden == 1 else 'ies'} hidden — use --all or -n)")


def cmd_handoff(_args):
    """End-of-session checklist; state on disk beats memory in context."""
    print("== handoff: end-of-session checklist ==")
    todo = 0

    def item(ok, label, detail):
        nonlocal todo
        todo += 0 if ok else 1
        print(f"  [{'ok' if ok else '..'}] {label}: {detail}")

    head = git("rev-parse", "--short", "HEAD") or None
    lv = load_json(LAST_VERIFY_PATH, default=None)
    if lv is None:
        item(False, "verify", f"no run recorded — run: {SCRIPT} verify")
    elif lv.get("result") != "pass":
        item(False, "verify", f"last run FAILED at {lv.get('failed_step')} — fix and rerun, "
                              "or hand off explicitly as unverified/broken in the log")
    elif lv.get("head") != head:
        item(False, "verify", f"last pass is from a different commit — rerun: {SCRIPT} verify")
    else:
        item(True, "verify", f"pass ({lv.get('date')})")

    entries = progress_entries()
    today = now_utc()[:10]
    latest = entries[-1] if entries else None
    if latest and latest.get("date", "").startswith(today):
        item(True, "log", f"entry recorded today: \"{latest.get('title')}\"")
    else:
        item(False, "log", f"no entry for this session — run: {SCRIPT} log \"<title>\" "
                           "--done \"...\" --next \"...\" (caveman style; cover what shipped, "
                           "known issues, next step, blockers)")

    wip = [f for f in load_features()["features"] if f.get("status") == "in_progress"]
    if wip:
        fid = wip[0].get("id")
        item(False, "scope", f"{fid} still in_progress — {SCRIPT} feature done {fid}, "
                             f"or feature block {fid} --notes \"why\" (half-done = block, not done)")
    else:
        item(True, "scope", "no feature left in_progress")

    if git("status", "--porcelain"):
        item(False, "commit", "working tree dirty — commit (state files included); "
                              "half-done work → 'wip:' commit on a feature branch")
    else:
        item(True, "commit", "working tree clean")
    unpushed = git("rev-list", "--count", "@{u}..HEAD")
    if unpushed and unpushed != "0":
        item(False, "push", f"{unpushed} unpushed commit(s) — remote/ephemeral sessions "
                            "lose unpushed work")
    elif unpushed == "0":
        item(True, "push", "in sync with upstream")
    else:
        item(True, "push", "no upstream configured (skip)")

    print("also consider:")
    print("  - durable decision made this session → one line in .agents/docs/architecture.md")
    print("  - repeated a multi-step procedure → capture a skill (.agents/skills/new-skill/SKILL.md)")
    print(f"  - commands/stack changed → {SCRIPT} cmd set ... + sync CI toolchain (.github/workflows/agents.yml)")
    if todo:
        print(f"== handoff incomplete: {todo} item(s) open above ==")
    else:
        print("== handoff clean: next session resumes from init output alone ==")


# ---------- feature ----------

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
            print(f"No features. Add one: {SCRIPT} feature add \"<title>\"")
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
    if args.action == "start":
        tip(f"implement {f['id']}; stay in scope. Done means: {SCRIPT} verify green")
    elif args.action == "done":
        nxt = next((x for x in feats if x.get("status") == "todo"), None)
        tip(f"{SCRIPT} handoff — log + commit"
            + (f"; next todo after that: {nxt['id']} — {nxt['title']}" if nxt else ""))


# ---------- cmd / run ----------

def cmd_cmd(args):
    cfg = load_config()
    cmds = cfg["commands"]

    if args.action == "list":
        if not cmds:
            print("No commands registered. Example:")
            print(f'  {SCRIPT} cmd set test "npm test" --verify')
            return
        for name, c in cmds.items():
            flags = "".join(f" [{f}]" for f in ("verify", "init") if c.get(f))
            desc = f"  # {c['desc']}" if c.get("desc") else ""
            print(f"  {name}: {c.get('run', '?')}{flags}{desc}")
        print(f"Run one: {SCRIPT} run <name>. [verify] steps run in listed order.")
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
    if args.verify or args.init:
        tip("keep CI able to run this: toolchain block in .github/workflows/agents.yml")


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
        prog="agents.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Agent harness — one CLI guides the whole workflow.",
        epilog=f"""\
session lifecycle:
  1. {SCRIPT} init                  health check + state snapshot (auto-run at session start)
  2. {SCRIPT} feature start <id>    pick ONE item (user request or next todo)
  3. implement                      stay in scope; follow a skill if one matches
  4. {SCRIPT} verify                definition of done; green = done, red = not done
  5. {SCRIPT} handoff               checklist: log entry, close feature, commit, push

State lives in .agents/ and is owned by this script — manage it through these
subcommands, never by hand-editing the JSON files. Each subcommand has --help.""",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name, fn, help_, epilog=None):
        sp = sub.add_parser(name, help=help_, description=help_, epilog=epilog,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
        sp.set_defaults(fn=fn)
        return sp

    st = add("setup", cmd_setup,
             "guided first-time project setup; shows status + instructions for the current step",
             epilog=f"""\
examples:
  {SCRIPT} setup                    status + current step instructions
  {SCRIPT} setup done guardrails    record a manual step as finished
Steps with an automatic check complete themselves once the check passes.
When every step is done, setup runs the final gates and lifts setup mode.""")
    st.add_argument("action", nargs="?", choices=["status", "done"], default="status")
    st.add_argument("step", nargs="?", help="step name (for 'done')")
    st.add_argument("--force", action="store_true",
                    help="record the step even if its automatic check fails")

    add("init", cmd_init,
        "session-start health check + state snapshot; suggests what to do next")

    add("verify", cmd_verify,
        "run the registered definition of done (commands flagged --verify, in order); "
        "records the result so `log` can report it")

    add("handoff", cmd_handoff,
        "end-of-session checklist with live status: verify, log, feature state, commit, push")

    lg = add("log", cmd_log,
             "record a progress entry; date, commit, and verify status are stamped automatically",
             epilog=f"""\
example:
  {SCRIPT} log "auth feature" --done "JWT login in src/auth/" \\
      --issues "refresh tokens untested" --next "wire logout" --feature F-002
Terse caveman style (.agents/docs/token-efficiency.md). Storage and history
are handled for you; nothing to compact or archive.""")
    lg.add_argument("title", help="short entry title")
    lg.add_argument("--done", required=True, help="what shipped (paths, behavior)")
    lg.add_argument("--issues", help="broken/known issues: facts, exact errors")
    lg.add_argument("--next", help="single most useful next step")
    lg.add_argument("--blockers", help="what stops progress (default: none)")
    lg.add_argument("--feature", help="related feature id, e.g. F-001")
    lg.add_argument("--verified", help="override the auto-detected verify status")

    pr = add("progress", cmd_progress, "show recent progress entries, newest first")
    pr.add_argument("-n", type=int, default=PROGRESS_DEFAULT_SHOWN,
                    help="how many entries (default %(default)s)")
    pr.add_argument("--all", action="store_true", help="show every entry")

    ft = add("feature", cmd_feature,
             "manage scope; one feature in_progress at a time (enforced)",
             epilog=f"""\
examples:
  {SCRIPT} feature list
  {SCRIPT} feature add "rate limiting" --notes "per-IP, 100 req/min"
  {SCRIPT} feature start F-003
  {SCRIPT} feature done F-003
  {SCRIPT} feature block F-004 --notes "waiting on API key"
""")
    ft.add_argument("action", choices=["list", "add", "start", "done", "block", "note"])
    ft.add_argument("title", nargs="?", help="title (for add) or feature id (for the rest)")
    ft.add_argument("--id", help="explicit id for add (default: next F-NNN)")
    ft.add_argument("--notes", help="notes text (add/block/note)")
    ft.add_argument("--all", action="store_true", help="list: include done features")

    cm = add("cmd", cmd_cmd,
             "register project commands (build/test/lint/dev) — data, not script edits",
             epilog=f"""\
examples:
  {SCRIPT} cmd set lint "npm run lint" --verify     part of the definition of done
  {SCRIPT} cmd set deps "npm ci" --init             session-start smoke check
  {SCRIPT} cmd set dev "npm run dev"                on-demand helper (use: run dev)
  {SCRIPT} cmd rm lint
verify steps run in listed order — register cheap/fast checks first.""")
    cm.add_argument("action", choices=["set", "rm", "list"])
    cm.add_argument("name", nargs="?", help="command name, e.g. test")
    cm.add_argument("command", nargs="?", help="shell command, e.g. \"npm test\"")
    cm.add_argument("--verify", action="store_true",
                    help="part of the definition of done (run by `verify`)")
    cm.add_argument("--init", action="store_true",
                    help="session-start smoke check (run by `init`)")
    cm.add_argument("--desc", help="one-line description")

    rn = add("run", cmd_run, "run a registered command by name")
    rn.add_argument("name")

    add("check", cmd_check, "structure/state validation only (no setup gate)")
    add("ci", cmd_ci, "what CI runs: check, then init + verify once setup is complete")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
