# Token efficiency ("caveman") style

Goal: cut tokens in agent-to-agent and agent-to-state text without losing facts.
Tokens cost money + context. Filler words carry zero information.

## Where it applies

| Context | Style |
|---|---|
| `PROGRESS.md`, handoff notes, feature list | Caveman: max terse |
| Chat replies to user | Lean but readable. Full sentences for conclusions |
| Code, comments, identifiers, public docs, commit messages | Normal. NEVER caveman |
| Error reports | Facts first, full command + output excerpt |

## Rules

1. Drop filler: "I have successfully", "it appears that", "in order to", "please note".
2. Fragments over sentences in state files. "Tests green. Lint fails: 2 unused imports."
3. Lists + tables over prose.
4. Paths, commands, exact names — never paraphrase ("the config file" → `.agents/scripts/verify.sh`).
5. No repetition. Said once = enough.
6. Numbers over adjectives. "3 failures" not "several issues".
7. Omit what reader can derive. Don't restate the task back.

## Example

Bad (62 words):
> I have successfully completed the implementation of the user authentication
> feature. All of the tests are now passing. However, I noticed that there
> appears to be an issue with the linting, which shows two warnings that are
> related to unused imports, which I think we should probably address at some
> point in the future.

Good (16 words):
> Auth feature done. Tests green. Lint: 2 warnings (unused imports in
> `auth/session.py`), not blocking.
