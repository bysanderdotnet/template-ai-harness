#!/usr/bin/env python3
"""agents.py — agent harness. One CLI guides whole workflow.

Don't read or change this file for project work. Usage: ./AGENTS.sh help

Subcommands (details + examples: ./AGENTS.sh help <command>):

    init         session start: health check + state snapshot; fresh project →
                 guided setup until complete (hook/CI run this)
    verify       run registered definition of done; records result
    handoff      end-of-session checklist, live status
    feature      scope: list / add / start / done / block / note
    log          record progress entry (auto-stamps date, commit, verify result)
    progress     show recent progress entries (display bounded, never compact by hand)
    docs         live project docs: generated repo map + curated rules
    maintenance  health sweep: update, combine, prune, re-check
    cmd          register project commands: set / rm / list
    run          run one registered command by name
    check        structure/state validation only
    ci           what CI runs: check, then init + verify once setup complete

Stdlib only; Python 3.8+. Durable state: .agents/agents.json; scratch:
.agents/agents.scratch.json (gitignored). Both owned by this script — never
hand-edit. New build/test/lint commands → `cmd set`, not edits here.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

SCRIPT = "./AGENTS.sh"


def find_root():
    # This file lives at <root>/.agents/agents.py. Anchor on the script, not
    # the caller's cwd: invoked via absolute path from inside another repo,
    # a cwd-based root would read/write that repo's files.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = find_root()
CONFIG_PATH = os.path.join(ROOT, ".agents", "agents.json")
SCRATCH_PATH = os.path.join(ROOT, ".agents", "agents.scratch.json")
SKILLS_DIR = os.path.join(ROOT, ".agents", "skills")

PROGRESS_DEFAULT_SHOWN = 5   # entries shown by `progress` / referenced by `init`
RULE_CATEGORIES = ("architecture", "conventions", "testing")
RULES_SOFT_CAP = 12          # per category; above this, maintenance says combine/prune
RULE_STALE_DAYS = 90         # rules older than this get flagged for a re-check
TREE_MAX_DEPTH = 3           # repo map: directories deeper than this are collapsed
TREE_MAX_ENTRIES = 12        # repo map: entries shown per directory


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


# ---------- state (single file: agents.json; scratch: agents.scratch.json) ----------

def load_config():
    """All durable harness state. Top-level keys are independent sections so
    future harness versions can add more without migrations."""
    if not os.path.isfile(CONFIG_PATH):
        die(".agents/agents.json missing. "
            "Restore from git history or re-copy from the template — never hand-edit.")
    try:
        cfg = load_json(CONFIG_PATH, default=None)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        die(f".agents/agents.json not valid JSON: {e}. "
            "Restore from git history — never hand-edit.")
    if not isinstance(cfg, dict):
        die(".agents/agents.json is not a JSON object. "
            "Restore from git history — never hand-edit.")
    for key, default in (("commands", {}), ("features", []),
                         ("progress", []), ("rules", [])):
        cfg.setdefault(key, default)
    return cfg


def save_config(cfg):
    save_json(CONFIG_PATH, cfg)


def load_scratch():
    try:
        data = load_json(SCRATCH_PATH, default=None)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}  # scratch is disposable; a corrupt one is treated as absent
    return data if isinstance(data, dict) else {}


def save_scratch(data):
    save_json(SCRATCH_PATH, data)


def setup_pending(cfg=None):
    """Setup state dict while setup is incomplete, else None."""
    return (cfg or load_config()).get("setup")


def find_feature(feats, fid):
    for f in feats:
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
    """Return (fails, warns) about harness structure and state."""
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

    cfg = None
    if os.path.isfile(CONFIG_PATH):
        try:
            cfg = load_json(CONFIG_PATH)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            fails.append(f".agents/agents.json is not valid JSON: {e}")
    if isinstance(cfg, dict):
        wip = [f for f in cfg.get("features", []) if f.get("status") == "in_progress"]
        if len(wip) > 1:
            warns.append("%d features in_progress (policy: max 1): %s"
                         % (len(wip), ", ".join(f.get("id", "?") for f in wip)))
        for cat in RULE_CATEGORIES:
            n = sum(1 for r in cfg.get("rules", []) if r.get("category") == cat)
            if n > RULES_SOFT_CAP:
                warns.append(f"{n} {cat} rules (soft cap {RULES_SOFT_CAP}) — "
                             f"combine/prune: {SCRIPT} maintenance")

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
    empty = [field for field in ("Name", "Stack", "Purpose")
             if not re.search(rf"^- {field}:[ \t]*\S", section, re.M)]
    if empty:
        return False, "AGENTS.md '## Project' fields empty: " + ", ".join(empty)
    return True, "AGENTS.md project section filled"


def _check_commands():
    cmds = load_config()["commands"]
    n = sum(1 for c in cmds.values() if c.get("verify"))
    if n:
        return True, f"{n} --verify command(s) registered"
    return False, "no --verify commands registered"


def _check_rules():
    rules = load_config()["rules"]
    missing = [c for c in RULE_CATEGORIES
               if not any(r.get("category") == c for r in rules)]
    if missing:
        return False, "no rules yet for: " + ", ".join(missing)
    return True, "rules cover " + ", ".join(RULE_CATEGORIES)


def _check_scope():
    feats = load_config()["features"]
    rest = [f for f in feats if f.get("id") != "F-000"]
    if rest:
        return True, f"{len(rest)} feature(s) seeded"
    return False, "no features besides F-000"


SETUP_STEPS = [
    ("project", "Project identity (AGENTS.md + README.md)", f"""\
1. Fill '## Project' in AGENTS.md: name, stack, purpose (2-4 lines).
   Remove its {SETUP_MARKER} comment.
2. Rewrite README.md for actual project (template text = placeholder).
Infer from codebase first (code, lockfiles, configs, CI); ask user only
what you can't infer (purpose, planned stack on empty repo).""",
     _check_project),

    ("commands", "Register project commands", f"""\
Find real commands (package.json scripts, Makefile, pyproject, CI) and
register — never edit .agents/agents.py itself:
  {SCRIPT} cmd set lint "npm run lint" --verify
  {SCRIPT} cmd set test "npm test" --verify        # --verify = definition of done, cheap/fast first
  {SCRIPT} cmd set deps "npm ci" --init            # --init = session-start smoke check
  {SCRIPT} cmd set dev "npm run dev"               # no flag = on-demand helper
Don't invent commands. CI runs these via {SCRIPT} ci; CI needs toolchain
steps (e.g. node install) → tell user — CI human-owned, never edit.
No code yet? Add feature "set up toolchain + verify commands" in scope
step, mark this one: {SCRIPT} init done commands --force""",
     _check_commands),

    ("rules", "Record project rules (architecture / conventions / testing)", f"""\
Record what agent must know — one terse rule per call:
  {SCRIPT} docs add architecture "<modules, data flow, key dirs>"
  {SCRIPT} docs add conventions "<naming, style, commit format>"
  {SCRIPT} docs add testing "<how to run tests, expectations>"
Infer from codebase. Nothing to record yet (e.g. no tests)? Record that
fact as the rule. Min one rule per category. Repo map generated live by
`{SCRIPT} docs` — don't describe the file tree.""",
     _check_rules),

    ("scope", "Seed the feature list", f"""\
Agree initial features with user, then:
  {SCRIPT} feature add "<title>" [--notes "..."]
One entry per feature, smallest shippable units first.""",
     _check_scope),

    ("guardrails", "Project rules + .gitignore", f"""\
1. Add project no-go zones to '## Rules' in AGENTS.md
   (e.g. "never edit /migrations"). Remove its {SETUP_MARKER} comment.
2. Add stack-specific ignores to .gitignore; replace its {SETUP_MARKER} line.""",
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
        blockers.append("verify red — fix before completing setup")
    if blockers:
        print("Setup NOT complete:")
        for b in blockers:
            print(f"  BLOCKED: {b}")
        tip(f"fix blockers, rerun: {SCRIPT} init")
        sys.exit(1)

    f000 = find_feature(cfg["features"], "F-000")
    if f000:
        f000["status"] = "done"
    del cfg["setup"]
    cfg["progress"].append({
        "date": now_utc(),
        "title": "project setup",
        "done": "setup complete: %d command(s) registered, %d feature(s) seeded, %d rule(s) recorded"
                % (len(cfg["commands"]),
                   len([f for f in cfg["features"] if f.get("id") != "F-000"]),
                   len(cfg["rules"])),
        "verified": verified_note(),
        "blockers": "none",
        "feature": "F-000",
    })
    save_config(cfg)
    print("== setup COMPLETE (progress entry written, F-000 closed) ==")
    tip("commit everything: git commit -m 'chore: complete project setup'; push if expected")


def setup_flow(cfg, mark_step=None, force=False):
    """Guided setup, driven by init while the project is unconfigured.
    Exits 1 while steps remain; returns once setup finalizes so init can
    continue into a normal session."""
    state = cfg["setup"]
    state.setdefault("done", [])
    names = [n for n, *_ in SETUP_STEPS]

    if mark_step:
        if mark_step not in names:
            die(f"init done needs a step name: {', '.join(names)}")
        _, _, _, check = SETUP_STEPS[names.index(mark_step)]
        if check and not force:
            ok, detail = check()
            if not ok:
                die(f"step '{mark_step}' not done: {detail}. Fix, or override with --force.")
        if mark_step not in state["done"]:
            state["done"].append(mark_step)
            save_config(cfg)
        print(f"step '{mark_step}' recorded.")

    # Status, plus full instructions for the first pending step only —
    # the right information at the right time.
    print("-- SETUP MODE: project not configured yet; finish setup before feature work --")
    pending = []
    for name, summary, _instr, check in SETUP_STEPS:
        if name in state["done"]:
            print(f"  [ok] {name}: {summary}")
            continue
        if check:
            ok, detail = check()
            if ok:
                state["done"].append(name)
                save_config(cfg)
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
        tip(f"step auto-completes once check passes — rerun: {SCRIPT} init")
    else:
        tip(f"manual step — when finished, record: {SCRIPT} init done {name}")
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


# ---------- init / verify / check / ci ----------

def cmd_init(args):
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

    in_setup = setup_pending(cfg) is not None
    mark_step = None
    if getattr(args, "action", None) == "done":
        if not in_setup:
            print("note: setup already complete — 'init done' only applies during setup.")
        elif not getattr(args, "step", None):
            die("init done needs a step name: "
                + ", ".join(n for n, *_ in SETUP_STEPS))
        else:
            mark_step = args.step
    if in_setup:
        setup_flow(cfg, mark_step=mark_step, force=getattr(args, "force", False))
        cfg = load_config()  # setup just finalized; continue into a normal session

    print("-- skills (playbooks; follow when task matches) --")
    skills = list_skills()
    for name, desc in skills:
        print(f"  {name}: {desc}")
    if not skills:
        print("  (none)")

    print("-- project docs --")
    rules = cfg["rules"]
    if rules:
        counts = ", ".join(
            f"{sum(1 for r in rules if r.get('category') == c)} {c}"
            for c in RULE_CATEGORIES)
        print(f"  rules: {counts}  (read before coding: {SCRIPT} docs)")
    else:
        print(f"  no rules recorded — {SCRIPT} docs add <category> \"<rule>\"")

    print("-- git --")
    print(git("status", "--short", "--branch") or "(not a git checkout)")
    print(git("log", "--oneline", "-5") or "(no commits yet)")

    print("-- scope --")
    feats = cfg["features"]
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

    print("-- progress --")
    entries = cfg["progress"]
    open_blocker = None
    if entries:
        latest = entries[-1]
        print(f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}. Latest:")
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
        print("WARN: no --verify commands registered — `verify` has nothing to run.")

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
        print("== init FAILED: fix FAILs above before feature work. ==")
        sys.exit(1)
    print("== init OK ==")
    if open_blocker:
        tip(f"resolve or re-confirm open blocker first: {open_blocker}")
    if wip:
        tip(f"continue {wip[0].get('id')}; when done: {SCRIPT} verify, then {SCRIPT} handoff")
    elif nxt:
        tip(f"pick ONE item: user request, or {SCRIPT} feature start {nxt.get('id')}")
    else:
        tip(f"no open scope — agree next features with user: {SCRIPT} feature add \"<title>\"")


def run_verify_steps(steps):
    """Run verify-flagged commands in order; record + return overall result."""
    failed = None
    for name, c in steps:
        print(f"-- {name}: {c['run']} --")
        rc = subprocess.run(c["run"], shell=True, cwd=ROOT).returncode
        if rc != 0:
            failed = f"{name} (exit {rc})"
            print(f"FAIL: step '{name}' exited {rc}; remaining steps skipped.")
            break
    record_verify("fail" if failed else "pass", failed=failed)
    return failed is None


def cmd_verify(_args):
    print("== verify: definition of done ==")
    cfg = load_config()
    if setup_pending(cfg) is not None:
        print(f"Project setup incomplete — finish first: {SCRIPT} init")
        sys.exit(1)
    steps = [(n, c) for n, c in cfg["commands"].items() if c.get("verify")]
    if not steps:
        print("No verify commands registered — nothing gates completion.")
        print("Register (cheap/fast first), e.g.:")
        print(f'  {SCRIPT} cmd set lint "npm run lint" --verify')
        print(f'  {SCRIPT} cmd set test "npm test" --verify')
        record_verify("fail", failed="(no verify commands registered)")
        sys.exit(1)
    if run_verify_steps(steps):
        print(f"== verify OK: all {len(steps)} step(s) green ==")
        tip(f"{SCRIPT} handoff — log work, close feature, commit")
    else:
        print("== verify FAILED. Not done — fix and rerun. ==")
        sys.exit(1)


def tree_state():
    """Content hash of the tracked working tree, commit-independent and
    excluding .agents/ (harness state: log/feature updates after a verify run
    must not mark it stale). A verify stays fresh when the exact tree it
    checked is committed afterwards."""
    stash = git("stash", "create")  # tree of HEAD + uncommitted tracked changes
    out = git("ls-tree", (stash or "HEAD") + "^{tree}")
    if not out:
        return None
    lines = [l for l in out.splitlines() if not l.endswith("\t.agents")]
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()


def record_verify(result, failed=None):
    scratch = load_scratch()
    scratch["last_verify"] = {
        "result": result,
        "failed_step": failed,
        "date": now_utc(),
        "head": git("rev-parse", "--short", "HEAD") or None,
        "tree": tree_state(),
    }
    save_scratch(scratch)


def cmd_check(_args):
    fails, warns = collect_problems()
    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print("== check FAILED ==")
        sys.exit(1)
    print("== check OK: harness structure and state valid ==")


def cmd_ci(args):
    cmd_check(args)
    if setup_pending() is not None:
        print("Project setup incomplete — structure gate only; init/verify skipped.")
        return
    cmd_init(args)   # exits non-zero on failure
    cmd_verify(args)


# ---------- log / progress / handoff ----------

def verified_note():
    lv = load_scratch().get("last_verify")
    if not lv:
        return "unverified (no verify run recorded)"
    note = f"{lv.get('result', '?')} ({lv.get('date', '?')} @ {lv.get('head') or 'no-commit'})"
    if lv.get("result") == "fail" and lv.get("failed_step"):
        note += f" — failed at {lv['failed_step']}"
    if lv.get("tree") != tree_state():
        note += " — STALE: files changed since that run, re-verify"
    return note


def cmd_log(args):
    cfg = load_config()
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
        if find_feature(cfg["features"], args.feature) is None:
            print(f"WARN: feature '{args.feature}' not in feature list; logging anyway.")
        entry["feature"] = args.feature
    head = git("rev-parse", "--short", "HEAD")
    if head:
        entry["commit"] = head + (" (+ uncommitted changes)" if git("status", "--porcelain") else "")
    cfg["progress"].append(entry)
    save_config(cfg)
    print("Logged:")
    print(render_entry(entry))
    if args.blockers:
        tip(f"if a feature is stuck on this, record it: {SCRIPT} feature block <id> --notes \"{args.blockers}\"")
    tip("commit .agents/agents.json together with the feature")


def cmd_progress(args):
    entries = load_config()["progress"]
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
    cfg = load_config()
    if setup_pending(cfg) is not None:
        print(f"Project setup incomplete — finish first: {SCRIPT} init")
        sys.exit(1)
    todo = 0

    def item(ok, label, detail):
        nonlocal todo
        todo += 0 if ok else 1
        print(f"  [{'ok' if ok else '..'}] {label}: {detail}")

    lv = load_scratch().get("last_verify")
    if lv is None:
        item(False, "verify", f"no run recorded — run: {SCRIPT} verify")
    elif lv.get("result") != "pass":
        item(False, "verify", f"last run FAILED at {lv.get('failed_step')} — fix and rerun, "
                              "or hand off explicitly as unverified/broken in the log")
    elif lv.get("tree") != tree_state():
        item(False, "verify", f"files changed since last pass — rerun: {SCRIPT} verify")
    else:
        item(True, "verify", f"pass ({lv.get('date')})")

    entries = cfg["progress"]
    today = now_utc()[:10]
    latest = entries[-1] if entries else None
    if latest and latest.get("date", "").startswith(today):
        item(True, "log", f"entry recorded today: \"{latest.get('title')}\"")
    else:
        item(False, "log", f"no entry for this session — run: {SCRIPT} log \"<title>\" "
                           "--done \"...\" --next \"...\" (caveman style; cover shipped, "
                           "known issues, next step, blockers)")

    wip = [f for f in cfg["features"] if f.get("status") == "in_progress"]
    if wip:
        fid = wip[0].get("id")
        item(False, "scope", f"{fid} still in_progress — {SCRIPT} feature done {fid}, "
                             f"or feature block {fid} --notes \"why\" (half-done = block, not done)")
    else:
        item(True, "scope", "no feature left in_progress")

    if git("status", "--porcelain"):
        item(False, "commit", "working tree dirty — commit (.agents/agents.json included); "
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
    print(f"  - learned a durable fact → {SCRIPT} docs add <category> \"<rule>\"")
    print("  - repeated a multi-step procedure → capture a skill (.agents/skills/new-skill/SKILL.md)")
    print(f"  - build/test commands changed → {SCRIPT} cmd set ...; CI needs toolchain "
          "changes → tell user (CI human-owned, never edit)")
    if todo:
        print(f"== handoff incomplete: {todo} item(s) open above ==")
        tip(f"close the open items, then rerun: {SCRIPT} handoff")
        sys.exit(1)
    print("== handoff clean: next session resumes from init output alone ==")


# ---------- feature ----------

def cmd_feature(args):
    cfg = load_config()
    feats = cfg["features"]

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
        elif by["in_progress"]:
            tip(f"continue {by['in_progress'][0].get('id')}; when done: {SCRIPT} verify")
        elif by["todo"]:
            tip(f"start one: {SCRIPT} feature start <id>")
        return

    if args.action == "add":
        if not args.title:
            die("feature add needs a title: feature add \"<title>\"")
        fid = args.id
        if fid is None:
            nums = [int(m.group(1)) for f in feats
                    for m in [re.match(r"F-(\d+)$", f.get("id", ""))] if m]
            fid = f"F-{(max(nums) + 1 if nums else 1):03d}"
        elif not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]*$", fid):
            die("feature id must be letters/digits/dashes/underscores, e.g. F-001")
        if find_feature(feats, fid):
            die(f"feature id '{fid}' already exists")
        f = {"id": fid, "title": args.title, "status": "todo"}
        if args.notes:
            f["notes"] = args.notes
        feats.append(f)
        save_config(cfg)
        print(f"Added: {fmt_feature(f)}")
        tip(f"start it when ready: {SCRIPT} feature start {fid}")
        return

    # remaining actions operate on an existing id
    if not args.title:
        die(f"feature {args.action} needs an id, e.g.: feature {args.action} F-001")
    f = find_feature(feats, args.title)
    if f is None:
        die(f"no feature with id '{args.title}' (see: feature list --all)")

    if args.action == "start":
        wip = [x for x in feats if x.get("status") == "in_progress" and x is not f]
        if wip:
            die(f"{wip[0].get('id')} already in_progress (policy: max 1). "
                f"Finish (feature done {wip[0].get('id')}) or block it first.")
        f["status"] = "in_progress"
    elif args.action == "done":
        if f.get("status") != "in_progress":
            print(f"WARN: {f['id']} was '{f.get('status')}', not in_progress — marking done anyway.")
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
    save_config(cfg)
    print(f"{f['id']} -> {f['status']}" + (f" ({f['notes']})" if f.get("notes") else ""))
    if args.action == "start":
        tip(f"implement {f['id']}; stay in scope. When finished: {SCRIPT} verify "
            f"(must be green), then {SCRIPT} handoff")
    elif args.action == "done":
        nxt = next((x for x in feats if x.get("status") == "todo"), None)
        tip(f"{SCRIPT} handoff — log + commit"
            + (f"; next todo after that: {nxt['id']} — {nxt['title']}" if nxt else ""))


# ---------- docs: generated repo map + curated rules ----------

def _tree_file_count(node):
    n = 0
    for child in node.values():
        n += 1 if child is None else _tree_file_count(child)
    return n


def repo_tree_lines():
    """Bounded file tree from git ls-files — always current, never hand-kept."""
    out = git("ls-files")
    if not out:
        return ["(no tracked files — not a git checkout?)"]
    tree = {}
    for path in out.splitlines():
        parts = path.split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = None

    lines = ["."]

    def render(node, prefix, depth):
        entries = sorted(node.items(),
                         key=lambda kv: (not kv[0].endswith("/"), kv[0]))
        shown = entries[:TREE_MAX_ENTRIES]
        hidden = len(entries) - len(shown)
        for i, (name, child) in enumerate(shown):
            last = i == len(shown) - 1 and hidden == 0
            branch = "└── " if last else "├── "
            cont = "    " if last else "│   "
            if child is None:
                lines.append(prefix + branch + name)
            elif depth + 1 >= TREE_MAX_DEPTH:
                count = _tree_file_count(child)
                lines.append(f"{prefix}{branch}{name} ({count} file{'s' if count != 1 else ''})")
            else:
                lines.append(prefix + branch + name)
                render(child, prefix + cont, depth + 1)
        if hidden:
            lines.append(prefix + f"└── … +{hidden} more")

    render(tree, "", 0)
    return lines


def cmd_docs(args):
    cfg = load_config()
    rules = cfg["rules"]

    if args.action == "add":
        if args.target not in RULE_CATEGORIES:
            die(f"docs add needs a category: {' | '.join(RULE_CATEGORIES)}")
        if not args.text:
            die('docs add needs the rule text: docs add <category> "<rule>"')
        if len(args.text) > 160:
            print("WARN: long rule — caveman style, split or trim.")
        nums = [int(m.group(1)) for r in rules
                for m in [re.match(r"R-(\d+)$", r.get("id", ""))] if m]
        rule = {
            "id": f"R-{(max(nums) + 1 if nums else 1):03d}",
            "category": args.target,
            "text": args.text,
            "added": now_utc()[:10],
        }
        rules.append(rule)
        save_config(cfg)
        print(f"Added {rule['id']} [{rule['category']}]: {rule['text']}")
        n = sum(1 for r in rules if r.get("category") == args.target)
        if n > RULES_SOFT_CAP:
            print(f"WARN: {n} {args.target} rules (soft cap {RULES_SOFT_CAP}) — "
                  f"combine overlapping ones, rm stale ones: {SCRIPT} maintenance")
        return

    if args.action == "rm":
        if not args.target:
            die("docs rm needs a rule id, e.g.: docs rm R-003")
        kept = [r for r in rules if r.get("id") != args.target]
        if len(kept) == len(rules):
            die(f"no rule with id '{args.target}' (see: {SCRIPT} docs)")
        cfg["rules"] = kept
        save_config(cfg)
        print(f"Removed {args.target}.")
        return

    # show
    print("== docs: live repo map + curated rules ==")
    print("-- repo map (generated from git ls-files; collapsed dirs show file counts) --")
    for line in repo_tree_lines():
        print(line)
    print("-- rules --")
    for cat in RULE_CATEGORIES:
        in_cat = [r for r in rules if r.get("category") == cat]
        print(f"{cat}:")
        for r in in_cat:
            print(f"  {r.get('id', '?')}: {r.get('text', '?')}")
        if not in_cat:
            print(f"  (none — add: {SCRIPT} docs add {cat} \"<rule>\")")
    tip(f"learned a durable fact → {SCRIPT} docs add <category> \"<rule>\" (terse, one fact per rule)")


# ---------- maintenance ----------

def cmd_maintenance(_args):
    """Health sweep: suggest what to update, combine, prune, or re-check."""
    cfg = load_config()
    if setup_pending(cfg) is not None:
        print(f"Project setup incomplete — finish first: {SCRIPT} init")
        sys.exit(1)

    print("== maintenance: harness + knowledge health ==")
    flagged = 0

    def item(ok, label, detail):
        nonlocal flagged
        flagged += 0 if ok else 1
        print(f"  [{'ok' if ok else '..'}] {label}: {detail}")

    print("-- structure --")
    fails, warns = collect_problems()
    for f in fails:
        item(False, "structure", f)
    for w in warns:
        item(False, "structure", w)
    if not fails and not warns:
        item(True, "structure", "no FAILs or WARNs")

    print("-- rules (project docs) --")
    rules = cfg["rules"]
    for cat in RULE_CATEGORIES:
        in_cat = [r for r in rules if r.get("category") == cat]
        if not in_cat:
            item(False, cat, f"0 rules — record at least one: {SCRIPT} docs add {cat} \"<rule>\"")
        elif len(in_cat) > RULES_SOFT_CAP:
            item(False, cat, f"{len(in_cat)} rules (soft cap {RULES_SOFT_CAP}) — combine "
                             f"overlapping, rm stale: {SCRIPT} docs rm <id>")
        else:
            item(True, cat, f"{len(in_cat)} rule(s)")
    stale = []
    now = datetime.now(timezone.utc)
    for r in rules:
        try:
            added = datetime.strptime(r.get("added", ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if (now - added).days > RULE_STALE_DAYS:
            stale.append(r.get("id", "?"))
    if stale:
        item(False, "stale rules", f"{len(stale)} older than {RULE_STALE_DAYS} days "
                                   f"({', '.join(stale)}) — spot-check against code; "
                                   "still true → rm + re-add (refreshes date); drifted → fix or rm")
    else:
        item(True, "stale rules", f"none older than {RULE_STALE_DAYS} days")

    print("-- scope --")
    feats = cfg["features"]
    blocked = [f for f in feats if f.get("status") == "blocked"]
    if blocked:
        item(False, "blocked", f"{len(blocked)} feature(s) blocked "
                               f"({', '.join(f.get('id', '?') for f in blocked)}) — "
                               "unblock, re-scope, or close with the user")
    else:
        item(True, "blocked", "no blocked features")
    done = sum(1 for f in feats if f.get("status") == "done")
    print(f"  (info) features: {done} done / {len(feats)} total; "
          f"progress entries: {len(cfg['progress'])} (append-only, display bounded — leave as is)")

    print("-- skills --")
    skills = list_skills()
    if skills:
        item(False, "skills", f"{len(skills)} skill(s) — reread each SKILL.md: commands still "
                              "exist? steps still match the code? Fix or delete drifted ones")
    else:
        item(True, "skills", "none to review")

    print("-- commands / CI --")
    wf = os.path.join(ROOT, ".github", "workflows", "agents.yml")
    try:
        with open(wf, encoding="utf-8") as fh:
            ci_ok = "AGENTS.sh ci" in fh.read()
    except OSError:
        ci_ok = False
    if ci_ok:
        item(True, "ci", ".github/workflows/agents.yml runs ./AGENTS.sh ci")
    else:
        item(False, "ci", ".github/workflows/agents.yml missing or doesn't run "
                          "./AGENTS.sh ci — report to user; CI human-owned, don't edit")
    item(False, "commands", f"reread {SCRIPT} cmd list — every command still real? "
                            f"definition of done still complete? Then run: {SCRIPT} verify")

    print("-- manual sweep --")
    print("  - AGENTS.md '## Project' and '## Rules' still accurate?")
    print("  - README.md still describes the actual project?")
    print("  - .gitignore still matches the stack?")

    print(f"== maintenance: {flagged} item(s) to act on above ==")
    tip(f"fix small items now; bigger → {SCRIPT} feature add \"maintenance: <what>\"")
    if fails:
        sys.exit(1)


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
        save_config(cfg)
        print(f"Removed '{args.name}'.")
        return

    # set
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", args.name):
        die("command name must be lowercase letters/digits/dashes/underscores")
    if not args.command:
        die('cmd set needs the shell command: cmd set <name> "<shell command>"')
    entry = {"run": args.command}
    old = cmds.get(args.name, {})
    for key in ("verify", "init", "desc"):  # updates keep flags/desc — clear via cmd rm
        if old.get(key):
            entry[key] = old[key]
    if args.verify:
        entry["verify"] = True
    if args.init:
        entry["init"] = True
    if args.desc:
        entry["desc"] = args.desc
    existed = args.name in cmds
    cmds[args.name] = entry  # keeps position if existing, appends if new
    save_config(cfg)
    flags = "".join(f" [{f}]" for f in ("verify", "init") if entry.get(f))
    print(f"{'Updated' if existed else 'Registered'} {args.name}: {args.command}{flags}")


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
        prog="./AGENTS.sh",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Agent harness — one CLI guides the whole workflow.",
        epilog=f"""\
which command when:
  session start          {SCRIPT} init                 auto-run by hooks; fresh project → guided setup
  pick work              {SCRIPT} feature start <id>   ONE item at a time (see: feature list)
  finished implementing  {SCRIPT} verify               green = done, red = not done
  ending the session     {SCRIPT} handoff              checklist: log, close feature, commit, push
  learned a durable fact {SCRIPT} docs add <category> "<rule>"
  blocked                {SCRIPT} log "<title>" --done "..." --blockers "..."   then ask user
  asked to do upkeep     {SCRIPT} maintenance

Every command prints a `next:` hint — follow it. State lives in
.agents/agents.json, owned by this script: manage through these
subcommands, never hand-edit. Details per command: {SCRIPT} help <command>.""",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name, fn, help_, epilog=None):
        sp = sub.add_parser(name, help=help_, description=help_, epilog=epilog,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
        sp.set_defaults(fn=fn)
        return sp

    ini = add("init", cmd_init,
              "session start: health check + state snapshot; on a fresh project it "
              "walks guided setup until complete",
              epilog=f"""\
First runs: init enters SETUP MODE, guides configuration one step at a time.
Steps with an automatic check complete themselves on rerun; manual steps are
recorded with: {SCRIPT} init done <step>. Rerun init after each step; once
setup completes, init reports state and the next action.""")
    ini.add_argument("action", nargs="?", choices=["done"],
                     help="'done' — record a manual setup step as finished")
    ini.add_argument("step", nargs="?", help="setup step name (for 'done')")
    ini.add_argument("--force", action="store_true",
                     help="record the step even if its automatic check fails")

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
Terse caveman style (AGENTS.md '## Style'). Storage/history handled for you;
nothing to compact or archive.""")
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

    dc = add("docs", cmd_docs,
             "live project docs: generated repo map + curated rules "
             "(architecture / conventions / testing)",
             epilog=f"""\
examples:
  {SCRIPT} docs                                     repo map + all rules
  {SCRIPT} docs add conventions "commits: imperative, <=72 chars"
  {SCRIPT} docs rm R-003
Repo map generated from git ls-files — never drifts. Rules are the curated
part: one terse fact each, added when learned, pruned when stale
(`{SCRIPT} maintenance` flags categories past {RULES_SOFT_CAP}).""")
    dc.add_argument("action", nargs="?", choices=["show", "add", "rm"], default="show")
    dc.add_argument("target", nargs="?",
                    help="category (for add: %s) or rule id (for rm)"
                         % " | ".join(RULE_CATEGORIES))
    dc.add_argument("text", nargs="?", help="rule text (for add)")

    add("maintenance", cmd_maintenance,
        "health sweep for an upkeep session: flags rules to combine/prune, blocked "
        "features, skills and commands to re-check, docs to refresh")

    cm = add("cmd", cmd_cmd,
             "register project commands (build/test/lint/dev) — data, not script edits",
             epilog=f"""\
examples:
  {SCRIPT} cmd set lint "npm run lint" --verify     part of the definition of done
  {SCRIPT} cmd set deps "npm ci" --init             session-start smoke check
  {SCRIPT} cmd set dev "npm run dev"                on-demand helper (use: run dev)
  {SCRIPT} cmd rm lint
verify steps run in listed order — register cheap/fast checks first.
re-running set on an existing name keeps its flags/desc; clear with cmd rm.""")
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
    add("ci", cmd_ci, "what CI runs: check, then init + verify once setup complete")

    hp = add("help", lambda a: p.parse_args(([a.topic] if a.topic else []) + ["--help"]),
             "show usage; `help <command>` for one command's details")
    hp.add_argument("topic", nargs="?", help="command name, e.g. feature")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except BrokenPipeError:
        # output piped into e.g. `head` that exited early — not an error
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(141)  # 128 + SIGPIPE


if __name__ == "__main__":
    main()
