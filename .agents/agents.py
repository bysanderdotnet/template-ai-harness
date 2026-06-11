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
    github       GitHub-only automations (auto-merge-pr, auto-create-pr):
                 `github settings` configures, `github automate` runs
                 (running works only inside GitHub Actions runners)

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
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

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
DEFAULT_AUTO_CREATE_PR_URL = "https://auto-create-pr.bysander.net/?repo={r}"
DEFAULT_AUTO_CREATE_PR_TOKEN_ENV = "AUTO_MERGE_PR"
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

def default_settings():
    return {
        "github": {
            "auto_merge_pr": {
                "enabled": False,
                "notify_on_blocked": False,
                "notify_tags": [],
            },
            "auto_create_pr": {
                "enabled": False,
                "webhook_url": DEFAULT_AUTO_CREATE_PR_URL,
                "repository": "",
                "token_env": DEFAULT_AUTO_CREATE_PR_TOKEN_ENV,
            },
        },
    }


def setting_enabled(on, off, current):
    if on and off:
        die("choose --on or --off, not both")
    if on:
        return True
    if off:
        return False
    return current


def section_error(cfg):
    """Wrong-typed sections (hand-edit damage); None when the shape is sane."""
    for key, typ in (("setup", dict), ("commands", dict), ("features", list),
                     ("progress", list), ("rules", list), ("settings", dict)):
        if key in cfg and not isinstance(cfg[key], typ):
            kind = "object" if typ is dict else "array"
            return f"'{key}' must be a JSON {kind}"
    for key in ("features", "progress", "rules"):
        if any(not isinstance(x, dict) for x in cfg.get(key, []) or []):
            return f"'{key}' entries must be JSON objects"
    if any(not isinstance(v, dict) for v in (cfg.get("commands") or {}).values()):
        return "'commands' entries must be JSON objects"
    settings = cfg.get("settings") or {}
    if "github" in settings and not isinstance(settings["github"], dict):
        return "'settings.github' must be a JSON object"
    github = settings.get("github") or {}
    for key in ("auto_merge_pr", "auto_create_pr"):
        if key in github and not isinstance(github[key], dict):
            return f"'settings.github.{key}' must be a JSON object"
    return None


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
    err = section_error(cfg)
    if err:
        die(f".agents/agents.json invalid: {err}. "
            "Restore from git history — never hand-edit.")
    for key, default in (("commands", {}), ("features", []),
                         ("progress", []), ("rules", []),
                         ("settings", default_settings())):
        cfg.setdefault(key, default)
    github = cfg["settings"].setdefault("github", {})
    merge = github.setdefault("auto_merge_pr", {})
    merge.setdefault("enabled", False)
    merge.setdefault("notify_on_blocked", False)
    merge.setdefault("notify_tags", [])
    create = github.setdefault("auto_create_pr", {})
    create.setdefault("enabled", False)
    create.setdefault("webhook_url", DEFAULT_AUTO_CREATE_PR_URL)
    create.setdefault("repository", "")
    create.setdefault("token_env", DEFAULT_AUTO_CREATE_PR_TOKEN_ENV)
    return cfg


def save_config(cfg):
    save_json(CONFIG_PATH, cfg)


def normalize_repo_slug(url):
    """Extract org/repo from hosted Git remote URL forms. Bare filesystem
    paths (e.g. a local clone source) are not repository slugs."""
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""

    if "://" in url:
        path = urlparse(url).path
    elif re.match(r"^[^@/]+@[^:/]+:", url):
        path = url.split(":", 1)[1]
    else:
        return ""

    path = path.strip().strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return ""
    org, repo = parts[-2], parts[-1]
    if not re.match(r"^[A-Za-z0-9_.-]+$", org):
        return ""
    if not re.match(r"^[A-Za-z0-9_.-]+$", repo):
        return ""
    return f"{org}/{repo}"


def git_remote_urls():
    out = subprocess.run(
        ["git", "remote", "-v"], capture_output=True, text=True, cwd=ROOT,
    )
    if out.returncode != 0:
        return []
    urls = []
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] not in urls:
            urls.append(parts[1])
    return urls


def detect_repository_slug():
    env_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", env_repo):
        return env_repo
    for url in git_remote_urls():
        slug = normalize_repo_slug(url)
        if slug:
            return slug
    return ""


def setup_automation_defaults(cfg):
    """Set first-setup-only automation defaults. Runs when setup finalizes —
    not on every init — so an unconfigured template checkout stays pristine."""
    github = cfg["settings"].setdefault("github", {})
    create = github.setdefault("auto_create_pr", {})
    changed = False
    if not create.get("webhook_url"):
        create["webhook_url"] = DEFAULT_AUTO_CREATE_PR_URL
        changed = True
    if not create.get("repository"):
        repo = detect_repository_slug()
        if repo:
            create["repository"] = repo
            changed = True
    if changed:
        save_config(cfg)


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
    if isinstance(cfg, dict) and section_error(cfg):
        fails.append(f".agents/agents.json invalid: {section_error(cfg)} — "
                     "restore from git history, never hand-edit")
        cfg = None
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

    setup_automation_defaults(cfg)
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
    """Content hash of the working tree (tracked + untracked non-ignored
    files), commit-independent and excluding .agents/ (harness state:
    log/feature updates after a verify run must not mark it stale). A verify
    stays fresh when the exact tree it checked is committed afterwards.
    Built via a throwaway index so new files count — `git stash create`
    would miss untracked files and mark fresh verifies stale on commit."""
    git_dir = git("rev-parse", "--absolute-git-dir")
    if not git_dir:
        return None
    idx = os.path.join(git_dir, "agents-tree-state.index")
    env = dict(os.environ, GIT_INDEX_FILE=idx)
    try:
        add = subprocess.run(["git", "add", "-A", "."], capture_output=True,
                             text=True, cwd=ROOT, env=env)
        if add.returncode != 0:
            return None
        wt = subprocess.run(["git", "write-tree"], capture_output=True,
                            text=True, cwd=ROOT, env=env)
        if wt.returncode != 0:
            return None
        tree = wt.stdout.strip()
    finally:
        try:
            os.remove(idx)
        except OSError:
            pass
    out = git("ls-tree", tree)
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
        if f.get("status") == "done":
            print(f"WARN: {f['id']} was done — reopening.")
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


def github_runner_note():
    print("note: GitHub automations execute only inside GitHub Actions runners; "
          "settings can be configured anywhere.")


def render_settings(settings):
    merge = settings["auto_merge_pr"]
    create = settings["auto_create_pr"]
    tags = " ".join(merge.get("notify_tags") or []) or "(none)"
    print("auto-merge-pr:")
    print(f"  enabled: {merge.get('enabled', False)}")
    print(f"  notify_on_blocked: {merge.get('notify_on_blocked', False)}")
    print(f"  notify_tags: {tags}")
    print("auto-create-pr:")
    print(f"  enabled: {create.get('enabled', False)}")
    print(f"  webhook_url: {create.get('webhook_url') or '(empty)'}")
    print(f"  repository: {create.get('repository') or '(empty)'}")
    print(f"  token_env: {create.get('token_env') or '(empty)'}")


def cmd_settings(args):
    github_runner_note()
    cfg = load_config()
    settings = cfg["settings"]["github"]

    if args.area == "show":
        render_settings(settings)
        return

    if args.area == "auto-merge-pr":
        merge = settings["auto_merge_pr"]
        merge["enabled"] = setting_enabled(args.on, args.off, merge.get("enabled", False))
        if args.notify_on and args.notify_off:
            die("choose --notify-on or --notify-off, not both")
        if args.notify_on:
            merge["notify_on_blocked"] = True
        if args.notify_off:
            merge["notify_on_blocked"] = False
        if args.tags is not None:
            merge["notify_tags"] = [t for t in args.tags.split() if t]
        save_config(cfg)
        render_settings(settings)
        return

    if args.area == "auto-create-pr":
        create = settings["auto_create_pr"]
        enabled = setting_enabled(args.on, args.off, create.get("enabled", False))
        webhook_url = args.url if args.url is not None else create.get("webhook_url", "")
        repository = args.repo if args.repo is not None else create.get("repository", "")
        token_env = (args.token_env if args.token_env is not None
                     else create.get("token_env", DEFAULT_AUTO_CREATE_PR_TOKEN_ENV))
        if enabled and (not webhook_url or not repository):
            die("auto-create-pr needs --url and --repo before --on")
        create["enabled"] = enabled
        create["webhook_url"] = webhook_url
        create["repository"] = repository
        create["token_env"] = token_env
        save_config(cfg)
        render_settings(settings)
        return

    die("unknown settings area")



# ---------- GitHub automation ----------

AUTO_MERGE_MARKER = "<!-- agents-auto-merge-pr -->"
BAD_STATUS_STATES = {"failure", "error"}
BAD_CHECK_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}
OK_CHECK_CONCLUSIONS = {"success", "neutral", "skipped"}
PENDING_CHECK_STATUSES = {"queued", "requested", "waiting", "pending", "in_progress"}


def setting(cfg, section):
    return cfg.get("settings", {}).get("github", {}).get(section, {})


def gh_proc(args):
    try:
        return subprocess.run(["gh", *args], cwd=ROOT, text=True,
                              capture_output=True)
    except FileNotFoundError:
        die("gh CLI not found — automations need GitHub CLI "
            "(preinstalled on GitHub Actions runners)")


def gh_json(*args):
    proc = gh_proc(["api", *args])
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        sys.exit(proc.returncode)
    return json.loads(proc.stdout or "null")


def gh_run(*args):
    proc = gh_proc(list(args))
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
    # query params in the URL: `gh api -f` would switch the request to POST
    return gh_json(f"repos/{repo}/pulls?state=open&per_page=100")


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
    check_runs = gh_json(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")
    statuses = status.get("statuses") or []
    checks = check_runs.get("check_runs") or []
    failures = []
    pending = []

    for item in statuses:
        name = item.get("context") or "commit status"
        state = item.get("state")
        if state in BAD_STATUS_STATES:
            failures.append(f"{name}: {state}")
        elif state != "success":
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

    return bool(statuses or checks), failures, pending


def comment_body(reason, tags):
    tag_line = " ".join(tags).strip()
    lead = f"{tag_line}\n\n" if tag_line else ""
    return (f"{lead}{AUTO_MERGE_MARKER}\n"
            "Auto-merge blocked. Fix needed:\n"
            f"- {reason}")


def ensure_comment(repo, number, body):
    comments = gh_json(f"repos/{repo}/issues/{number}/comments?per_page=100")
    for comment in comments:
        if AUTO_MERGE_MARKER in (comment.get("body") or ""):
            if comment.get("body") == body:
                print(f"PR #{number}: blocked comment already current")
                return
            gh_run("api", f"repos/{repo}/issues/comments/{comment['id']}",
                   "-X", "PATCH", "-f", f"body={body}")
            print(f"PR #{number}: blocked comment updated")
            return
    gh_run("api", f"repos/{repo}/issues/{number}/comments", "-f", f"body={body}")
    print(f"PR #{number}: blocked comment posted")


def cmd_automate(args):
    github_runner_note()
    if args.action == "auto-merge-pr":
        if not args.repo:
            die("github automate auto-merge-pr needs --repo org/repo")
        automate_auto_merge_pr(args)
    elif args.action == "auto-create-pr":
        automate_auto_create_pr(args)
    else:
        die("unknown automate action")


def automate_auto_merge_pr(args):
    cfg = load_config()
    cfg_set = setting(cfg, "auto_merge_pr")
    set_output("auto_merge_enabled", str(bool(cfg_set.get("enabled"))).lower())

    if not cfg_set.get("enabled", False):
        print("auto-merge-pr disabled")
        set_output("has_open_prs", "true")
        return

    prs = open_prs(args.repo)
    notify = cfg_set.get("notify_on_blocked", False)
    tags = cfg_set.get("notify_tags") or []

    for pr in prs:
        number = pr["number"]
        detail = pr_details(args.repo, number)
        sha = detail["head"]["sha"]
        print(f"PR #{number}: {detail.get('title', '')}")

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


def call_webhook(url, repo, token):
    encoded = quote(repo, safe="")
    final_url = url.replace("{r}", encoded).replace("{repo}", encoded)
    req = Request(final_url, method="POST", headers={
        "User-Agent": "template-ai-harness",
        "Authorization": f"Bearer {token}",
    })
    try:
        with urlopen(req, timeout=30) as resp:
            print(f"webhook_status={resp.status}")
    except OSError as e:  # URLError/HTTPError/socket errors
        die(f"webhook call failed ({final_url}): {e}")


def automate_auto_create_pr(args):
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

    token_env = cfg_set.get("token_env", DEFAULT_AUTO_CREATE_PR_TOKEN_ENV)
    token = os.environ.get(token_env, "") if token_env else ""
    if not token:
        print(f"auto-create-pr needs bearer token in ${token_env or '(unset token_env)'}; "
              "not calling URL")
        return

    open_features = [f for f in cfg.get("features", []) if f.get("status") != "done"]
    if not open_features:
        print("no open features; auto-create-pr stopped")
        return

    print(f"open_features={len(open_features)}")
    call_webhook(url, repo, token)


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
  github automation      {SCRIPT} github settings show
  run automation         {SCRIPT} github automate auto-merge-pr --repo org/repo

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

    gh = sub.add_parser(
        "github",
        help="GitHub-only automations (auto-merge-pr, auto-create-pr); "
             "running them works only inside GitHub Actions runners",
        description="GitHub-only automations (auto-merge-pr, auto-create-pr); "
                    "settings can be configured anywhere, but `github automate` "
                    "works only inside GitHub Actions runners",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ghsub = gh.add_subparsers(dest="github_command", required=True,
                              metavar="<command>")

    def gh_add(name, fn, help_, epilog=None):
        sp = ghsub.add_parser(name, help=help_, description=help_, epilog=epilog,
                              formatter_class=argparse.RawDescriptionHelpFormatter)
        sp.set_defaults(fn=fn)
        return sp

    au = gh_add("automate", cmd_automate,
                "run GitHub automations (GitHub Actions runners only)",
                epilog=f"""\
examples:
  {SCRIPT} github automate auto-merge-pr --repo org/repo
  {SCRIPT} github automate auto-create-pr --has-open-prs false""")
    au.add_argument("action", choices=["auto-merge-pr", "auto-create-pr"],
                    help="automation to run")
    au.add_argument("--repo", help="auto-merge-pr: GitHub repository, org/name")
    au.add_argument("--has-open-prs", choices=["true", "false"],
                    default="true", help="auto-create-pr: output from auto-merge-pr")

    st = gh_add("settings", cmd_settings,
                "configure GitHub automations: auto-merge-pr and auto-create-pr",
                epilog=f"""\
examples:
  {SCRIPT} github settings show
  {SCRIPT} github settings auto-merge-pr --on
  {SCRIPT} github settings auto-merge-pr --notify-on --tags "@jules @codex"
  {SCRIPT} github settings auto-create-pr --repo "org/repo" --on
  {SCRIPT} github settings auto-create-pr --url "https://example.com/?myparam={{r}}"
  {SCRIPT} github settings auto-create-pr --token-env "MY_TOKEN_VAR"
  {SCRIPT} github settings auto-create-pr --off
defaults: both off; blocked-PR messages off; no tags; auto-create URL preset; repo detected during setup when possible; bearer token read from $AUTO_MERGE_PR.""")
    st.add_argument("area", choices=["show", "auto-merge-pr", "auto-create-pr"],
                    help="settings group")
    st.add_argument("--on", action="store_true", help="enable this automation")
    st.add_argument("--off", action="store_true", help="disable this automation")
    st.add_argument("--notify-on", action="store_true",
                    help="auto-merge-pr: comment on failed CI/conflicts")
    st.add_argument("--notify-off", action="store_true",
                    help="auto-merge-pr: do not comment on failed CI/conflicts")
    st.add_argument("--tags", help="auto-merge-pr: space-separated tags for comments")
    st.add_argument("--url", help="auto-create-pr: webhook URL; use {r} for org/repo")
    st.add_argument("--repo", help="auto-create-pr: org/repo passed to webhook")
    st.add_argument("--token-env", dest="token_env",
                    help="auto-create-pr: env var holding the webhook bearer token")

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
