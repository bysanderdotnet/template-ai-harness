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
   - `AGENTS.md`: project section, command table, repo map rows, extra rules.
   - `.agents/scripts/init.sh` + `verify.sh`: replace `TODO(setup)` blocks with
     real commands. Delete the `TEMPLATE:` guard blocks in both scripts and the
     trailing `exit 1` fallback in verify.sh.
   - `.agents/docs/*.md`: fill `TODO(setup)` markers. Delete sections that
     don't apply. Empty doc is fine if marked "nothing yet".
   - `.agents/state/feature_list.json`: seed with features agreed with user.
   - `README.md`: rewrite for the actual project.
4. Delete `TEMPLATE_SETUP.md`.
5. Verify setup itself:
   - `bash .agents/scripts/init.sh` and `bash .agents/scripts/verify.sh` exit 0.
   - `git grep -n "TODO(setup)" -- ':!.agents/skills'` returns nothing
     (skill playbooks legitimately mention the marker).
   - `CLAUDE.md` still symlinks to `AGENTS.md`; `.claude/skills` to `.agents/skills`.
6. Mark feature F-000 done. Write first `PROGRESS.md` entry (caveman style).
7. Commit: `chore: complete template setup`. Push if user expects it.

## Rules

- Ask the user only for facts not inferable from the repo (purpose, planned
  stack on empty repo, initial features).
- Don't invent commands. No test runner configured → put `(none yet)` in the
  table and add a feature "set up test runner" to feature_list.json.
