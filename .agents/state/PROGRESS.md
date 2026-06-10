# Progress log

Newest entry first; never rewrite old entries. Caveman style (see
`.agents/docs/token-efficiency.md`).

Compaction: keep ≤10 entries here. Overflow moves to
`.agents/state/PROGRESS-archive.md` (newest first there too — insert at top).
`init.sh` warns at session start when over the limit.

Entry format:

```
## YYYY-MM-DD — short title
- Done: what shipped (paths, commits)
- Verified: verify.sh result, or "unverified" + why
- Broken/known issues: facts, exact errors
- Next: single most useful next step
- Blockers: what stops progress, or "none"
```

<!-- Entries below. First real entry comes from template setup. -->
