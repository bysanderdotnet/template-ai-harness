# Conventions

## Code style

- Shell: POSIX `sh` for root wrappers; keep scripts small, strict (`set -eu`), and portable.
- Python: stdlib-only Python 3.8+; clear function names; no import-time side effects beyond constants.
- Harness internals: do not edit `.agents/agents.py` for normal project commands. Register commands with `./agents.sh cmd set ...`.
- JSON state: never hand-edit `.agents/agents.json` or `.agents/state/*.json`; use the harness CLI.

## Commits

- One feature/fix per commit. Imperative subject ≤72 chars.
- Use conventional prefixes when they fit: `feat:`, `fix:`, `docs:`, `chore:`.
- Commit generated harness state only when it records intentional project progress.

## Branches

- Keep work on the current branch unless the user requests a branch change.
- PRs should summarize behavior changes and list verification commands.

## Errors & logging

- CLI errors should be actionable and include the next command when possible.
- Progress log entries use terse agent-to-agent style; public docs use normal prose.
