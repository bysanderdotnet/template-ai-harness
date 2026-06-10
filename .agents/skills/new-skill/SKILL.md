---
name: new-skill
description: Author a new skill in .agents/skills. Use when the user wants to capture a recurring task as a reusable playbook, or a task was painful and worth documenting for next time.
---

# Create a new skill

Skills = playbooks for recurring tasks. One dir per skill: `.agents/skills/<name>/SKILL.md`.
Claude Code discovers them via the `.claude/skills` symlink.

## When to create

- Task will recur (release, deploy, codegen, data migration, report).
- Task has non-obvious steps or ordering that cost effort to figure out.

Don't create for one-offs or things AGENTS.md already covers in 2 lines.

## Format

```md
---
name: kebab-case-name
description: What it does + when to use. Third person, specific trigger words. This is the ONLY part loaded by default — make it self-explanatory.
---

# Title

One line: goal of the playbook.

## Steps
Numbered, concrete, commands included. Cheap checks first.

## Rules / gotchas
Constraints, failure modes, what NOT to do.
```

## Steps

1. `mkdir -p .agents/skills/<name>`
2. Write `SKILL.md` per format above.
3. Helper scripts → same dir, reference by path.
4. Mention the skill in AGENTS.md only if it gates the core workflow.

## Quality bar

- Body ≤ ~80 lines. Longer → split details into extra files in the skill dir,
  reference them from SKILL.md (progressive disclosure).
- Commands copy-pasteable from repo root.
- Caveman style (see `.agents/docs/token-efficiency.md`).
- Test: could a fresh agent with zero conversation context execute it? If no, fix.
