# Testing & verification

Verification gates completion: no green `./agents.sh verify`, no "done".

## Run

| Scope | Command |
|---|---|
| Everything (definition of done) | `./agents.sh verify` |
| One registered step (e.g. harness checks) | `./agents.sh run harness-check` |
| Shell wrapper syntax | `sh -n agents.sh` |
| Python syntax | `python3 -m py_compile .agents/agents.py` |

Verify steps are registered commands (`./agents.sh cmd list`). New test/lint
step → `./agents.sh cmd set <name> "<cmd>" --verify`, don't edit harness scripts.

## Writing tests

- This template currently verifies harness structure, wrapper syntax, and Python syntax.
- Projects created from the template should register their real unit, lint, build, and smoke commands as soon as their stack exists.
- Prefer cheap checks first in the verify command order.

## Expectations

- New feature → new tests or an explicit reason a harness/doc-only check is sufficient.
- Bug fix → regression test first when the project has a test framework.
- CI must run the same definition of done through `./agents.sh ci`.

## Known flaky / slow

None yet. Append: test name, symptom, workaround.
