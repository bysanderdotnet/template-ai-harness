# Harness engineering — distilled principles

Condensed from harness-engineering research (sources at bottom). This
template's design decisions trace back to these findings. Background reading;
not needed for day-to-day work.

## Core findings

1. **Harness beats model choice.** Agent performance gains come mostly from
   the environment around the model: repo-local instructions, machine-checkable
   definition of done, persistent state, isolated runtimes, fast feedback.
   OpenAI scaled an agent-first codebase to ~1M LOC / ~1.5k PRs this way.
2. **Start simpler than the hype suggests.** Single agent + sharp tools +
   evals first. Add planner/evaluator/multi-agent only when failure logs prove
   instruction complexity or tool overload is the bottleneck. Agentless hit
   32% on SWE-bench Lite at ~$0.70/run with a non-agentic pipeline.
3. **Big instruction files don't scale.** Short AGENTS.md as table of
   contents; detail docs loaded on demand (progressive disclosure).
4. **Compaction alone fails on long tasks.** Explicit handoff artifacts —
   progress log, feature list, init script — beat summarized context across
   sessions. Context resets + good handoffs > compaction.
5. **Verification is the highest-ROI subsystem.** Agents claim "done" too
   early and grade their own work too kindly. A mechanical gate
   (test/lint/typecheck/build) prevents it; fresh-context evaluators help on
   big builds.
6. **Full autonomy is expensive.** Published example runs: ~$200/6h and
   $124.70/3h50m (Anthropic), 6h+ single tasks (OpenAI). Reserve high
   autonomy for high-value-per-run work.
7. **Re-evaluate the harness on model upgrades.** New model generations make
   some scaffolding obsolete; delete what is no longer load-bearing.

## Five subsystems

Framework from learn-harness-engineering; mapping to this template:

| Subsystem | Job | Here |
|---|---|---|
| Instructions | What/how, progressive disclosure | `AGENTS.md` + `.agents/docs/` |
| State | Survive across sessions | `.agents/state/` |
| Verification | Mechanical definition of done | `harness.py verify` (registered commands) |
| Scope | One feature at a time | `feature_list.json` |
| Lifecycle | Clean start + clean handoff | `harness.py init` hook, session-handoff skill |

## Practices worth copying

- Repo = single source of truth. Decision worth keeping → write it to a file.
- Few sharp, well-documented tools over many; standardize interfaces (MCP).
- Prompt templates with variables over a zoo of one-off prompts.
- Isolate runs (worktrees/sandboxes); human approval before irreversible acts.
- Measure on real repo tasks; structural scores and benchmarks are proxies.
- Baseline with the strongest model, then downsize where quality allows.

## Sources

- OpenAI — Harness engineering: leveraging Codex in an agent-first world.
  <https://openai.com/index/harness-engineering>
- Anthropic — Effective harnesses for long-running agents.
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
- Anthropic — Harness design for long-running application development
  (planner–generator–evaluator architecture).
- learn-harness-engineering — curriculum + harness-creator skill.
  <https://github.com/walkinglabs/learn-harness-engineering>
- SWE-bench <https://arxiv.org/abs/2310.06770> · SWE-agent
  <https://arxiv.org/abs/2405.15793> · Agentless
  <https://arxiv.org/abs/2407.01489> · AFlow
  <https://openreview.net/forum?id=z5uVAKwmjf>
