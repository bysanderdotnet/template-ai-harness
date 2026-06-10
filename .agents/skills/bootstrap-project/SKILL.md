---
name: bootstrap-project
description: First-session setup for a project created from template-ai-harness. Use when `./agents.sh init` reports SETUP MODE, or when the user asks to initialize/configure/bootstrap this project from the template.
---

# Bootstrap project from template

The harness itself guides setup — this skill just points you at it.

## Steps

1. Run `./agents.sh setup`. It shows step status and full
   instructions for the current step only.
2. Do what the current step says, then rerun `setup`. Steps with automatic
   checks complete themselves; manual steps end with `setup done <step>`.
3. Repeat until setup reports COMPLETE (it runs the final gates, closes
   feature F-000, and writes the first progress entry itself).
4. Commit `chore: complete project setup`. Push if the user expects it.

## Rules

- Infer facts from the repo first (code, lockfiles, configs, CI). Ask the
  user only what you cannot infer: purpose, planned stack on an empty repo,
  initial features.
- Don't invent commands that don't exist. No test runner yet → the setup
  instructions cover the skip path.
