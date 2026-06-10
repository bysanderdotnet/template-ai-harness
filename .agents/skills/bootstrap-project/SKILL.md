---
name: bootstrap-project
description: First-session setup for a project created from template-ai-harness. Use when TEMPLATE_SETUP.md exists in the repo root, or when the user asks to initialize/configure/bootstrap this project from the template.
---

# Bootstrap project from template

Configures the harness for a concrete project. Driven by the checklist in
`TEMPLATE_SETUP.md` — that file is the source of truth; this skill is the playbook.

## Steps

1. Read `TEMPLATE_SETUP.md`. If absent: setup already done, stop.
2. Gather facts, inferring before asking:
   - Stack/language: look at existing code, lockfiles, configs.
   - Commands: package.json scripts, Makefile, pyproject, CI configs.
   - If repo is empty of code, ask user: stack, purpose, first features.
3. Work checklist top to bottom:
   - `AGENTS.md`: project section, repo map rows, extra rules.
   - Register commands: `python3 .agents/harness.py cmd set <name> "<cmd>"`
     with `--verify` for definition-of-done steps (cheap/fast first) and
     `--init` for dependency/env smoke checks. Never edit `harness.py` itself.
   - `.github/workflows/agents.yml`: fill the toolchain `TODO(setup)` block.
   - `.agents/docs/*.md`: fill `TODO(setup)` markers. Delete sections that
     don't apply. Empty doc is fine if marked "nothing yet".
   - Seed scope: `harness.py feature add "<title>"` per feature agreed with user.
   - `README.md`: rewrite for the actual project.
4. Delete `TEMPLATE_SETUP.md` and the `TEMPLATE:` comment at the top of `AGENTS.md`.
5. Verify setup itself:
   - `python3 .agents/harness.py init` and `python3 .agents/harness.py verify` exit 0.
   - `git grep -nE "TODO\(setup\)|TEMPLATE:" -- ':!.agents/skills'` returns
     nothing (skill playbooks legitimately mention the markers).
   - Entrypoints intact: `CLAUDE.md` and `GEMINI.md` symlink to `AGENTS.md`,
     `.claude/skills` to `.agents/skills`, `.github/copilot-instructions.md`
     exists (init checks these).
6. `harness.py feature done F-000`. Record setup:
   `harness.py log "template setup" --done "..." --next "..."` (caveman style).
7. Commit: `chore: complete template setup`. Push if user expects it.

## Rules

- Ask the user only for facts not inferable from the repo (purpose, planned
  stack on empty repo, initial features).
- Don't invent commands. No test runner configured → register nothing and add
  a feature "set up test runner + verify commands" instead.
