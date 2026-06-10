# Template setup — complete on first session, then delete this file

This repo was created from `template-ai-harness`. The harness is scaffolded
but not configured. An agent (or human) must finish setup before feature work.

Agent: work through the checklist top to bottom. Ask the user for anything you
cannot infer from the codebase. When all boxes are checked, delete this file
and commit `chore: complete template setup`.

## Checklist

### 1. Project identity
- [ ] Fill `## Project` in `AGENTS.md` (name, stack, purpose).
- [ ] Rewrite `README.md` for the actual project (template text is placeholder).

### 2. Commands
- [ ] Fill the command table in `AGENTS.md` (build/test/lint/typecheck/dev).
      If the project has no code yet, fill in what's planned and mark `(planned)`.
- [ ] Implement the TODO blocks in `.agents/scripts/init.sh`
      (dependency install check, quick env sanity check).
- [ ] Implement the TODO blocks in `.agents/scripts/verify.sh`
      (test, lint, typecheck, build — whatever exists).
- [ ] Run both scripts. They must exit 0 on a healthy checkout.

### 3. Docs
- [ ] Fill `.agents/docs/architecture.md` (modules, data flow, key dirs).
- [ ] Fill `.agents/docs/conventions.md` (naming, formatting, commit style).
- [ ] Fill `.agents/docs/testing.md` (how to run/write tests, coverage expectations).
- [ ] Add source-dir rows to the repo map in `AGENTS.md`.

### 4. Scope & state
- [ ] Seed `.agents/state/feature_list.json` with initial features (with the user).
- [ ] Write a first entry in `.agents/state/PROGRESS.md` describing setup.

### 5. Guardrails
- [ ] Add project-specific rules / no-go zones to `## Rules` in `AGENTS.md`.
- [ ] Review `.gitignore` for the chosen stack.

### 6. Finish
- [ ] Search repo for remaining `TODO(setup)` markers — must be zero.
- [ ] Delete this file. Commit and push.
