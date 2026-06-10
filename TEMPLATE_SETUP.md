# Template setup — complete on first session, then delete this file

This repo was created from `template-ai-harness`. The harness is scaffolded
but not configured. An agent (or human) must finish setup before feature work.

Agent: work through the checklist top to bottom. Ask the user for anything you
cannot infer from the codebase. The final section deletes this file and
commits `chore: complete template setup`.

While this file exists, `harness.py init` and `verify` exit 1 by design;
the final run check is in section 6. Every other harness subcommand
(`cmd`, `feature`, `log`, ...) already works — use them during setup.

## Checklist

### 1. Project identity
- [ ] Fill `## Project` in `AGENTS.md` (name, stack, purpose).
- [ ] Rewrite `README.md` for the actual project (template text is placeholder).

### 2. Commands
- [ ] Register project commands with the harness (no script editing):
      `python3 .agents/harness.py cmd set lint "npm run lint" --verify`,
      same for typecheck/test/build (`--verify`, registered cheap/fast first),
      dependency/env checks with `--init`, and dev/run helpers with neither
      flag. If the project has no code yet, skip and add a feature
      "set up toolchain + verify commands" in step 4 instead.
- [ ] Add toolchain setup to `.github/workflows/agents.yml` (the
      `TODO(setup)` block) so CI can run `harness.py verify`.

### 3. Docs
- [ ] Fill `.agents/docs/architecture.md` (modules, data flow, key dirs).
- [ ] Fill `.agents/docs/conventions.md` (naming, formatting, commit style).
- [ ] Fill `.agents/docs/testing.md` (how to run/write tests, coverage expectations).
- [ ] Add source-dir rows to the repo map in `AGENTS.md`.

### 4. Scope & state
- [ ] Seed initial features (with the user):
      `python3 .agents/harness.py feature add "<title>"` per feature.
- [ ] Record setup as the first progress entry:
      `python3 .agents/harness.py log "template setup" --done "..." --next "..."`.

### 5. Guardrails
- [ ] Add project-specific rules / no-go zones to `## Rules` in `AGENTS.md`.
- [ ] Review `.gitignore` for the chosen stack.

### 6. Finish
- [ ] Mark feature F-000 done: `python3 .agents/harness.py feature done F-000`.
- [ ] Delete this file. Delete the `TEMPLATE:` comment at the top of `AGENTS.md`.
- [ ] `python3 .agents/harness.py init` and `python3 .agents/harness.py verify` exit 0.
- [ ] `git grep -nE "TODO\(setup\)|TEMPLATE:" -- ':!.agents/skills'` returns
      nothing (skill playbooks legitimately mention the markers).
- [ ] Commit `chore: complete template setup`. Push.
