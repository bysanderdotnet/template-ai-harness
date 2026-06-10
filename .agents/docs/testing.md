# Testing & verification

Verification gates completion: no green `python3 .agents/harness.py verify`,
no "done".

## Run

| Scope | Command |
|---|---|
| Everything (definition of done) | `python3 .agents/harness.py verify` |
| One registered step (e.g. tests only) | `python3 .agents/harness.py run test` |
| Single test file | <!-- TODO(setup) --> |

Verify steps are registered commands (`harness.py cmd list`). New test/lint
step → `harness.py cmd set <name> "<cmd>" --verify`, don't edit scripts.

## Writing tests

<!-- TODO(setup): framework, file locations, naming pattern, fixtures. -->

## Expectations

- New feature → new tests. Bug fix → regression test first.
- <!-- TODO(setup): coverage threshold, e2e/smoke requirements. -->

## Known flaky / slow

None yet. <!-- Append: test name, symptom, workaround. -->
