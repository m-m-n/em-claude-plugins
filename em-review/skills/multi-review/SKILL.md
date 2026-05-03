---
name: multi-review
description: Parallel multi-perspective code review across 9 reviewers (5 Claude + 4 GPT/Codex). Aggregates with cross-model agreement scoring; opt-in scoped auto-fix loop. Reviewer set is driven by the registry at references/reviewers.json. Final report in Japanese.
disable-model-invocation: true
allowed-tools: Read, Edit, Glob, Grep, Bash, Task, AskUserQuestion
---

## Execution Context

This skill runs **inline in the main session**. The main session itself issues the parallel `Task()` calls from its own context, so each reviewer gets a fresh, independent context. This is what makes the Claude-vs-GPT cross-model agreement signal meaningful.

## Main Execution

**Orchestrator**: Read `${CLAUDE_PLUGIN_ROOT}/agents/multi-review-orchestrator.md` and follow its instructions inline.

If `${CLAUDE_PLUGIN_ROOT}` does not resolve, locate the orchestrator via Glob (`**/em-review/agents/multi-review-orchestrator.md`) under known-trusted install dirs (`$HOME/.claude/plugins`, `$HOME/.claude/skills`).

The main session performs the orchestration — it reads those instructions and executes each phase itself, issuing the parallel `Task` calls directly from its own context.

## Reviewer set

The set of reviewers is the **single-source-of-truth registry** at `${CLAUDE_PLUGIN_ROOT}/references/reviewers.json`. The orchestrator reads it to drive Phase 1 fan-out. To add or remove a perspective, edit the registry — this skill and the orchestrator pick it up automatically.

## Workflow Summary

1. **Phase 0**: Resolve protocol/registry/schema; determine review target; locate SPEC.md; probe codex; generate nonce; write payload to a temp file.
2. **Phase 1**: Launch reviewers in parallel in a single turn (per registry, skipping `requires_spec`/`requires_codex` mismatches).
3. **Phase 2**: Aggregate, sanitize (path/severity/category/source), deduplicate, score by cross-model agreement.
4. **Phase 3**: Opt-in scoped auto-fix loop (max 5 iterations) with identity-based regression detection and rollback. Modify-only — never creates or deletes files.
5. **Phase 4**: Skip-aware final report in Japanese (タメ語, 女性).

Each reviewer is also usable standalone via `/em-review:<skill_name>` (skill_name is in the registry — e.g. `security`, `gpt.architecture`).

$ARGUMENTS
