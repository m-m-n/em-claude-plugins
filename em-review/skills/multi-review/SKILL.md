---
name: multi-review
description: Parallel multi-perspective code review across 9 reviewers (5 Claude + 4 GPT/Codex). Aggregates with cross-model agreement scoring; runs bounded multi-loop auto-fix (≤ 3 iterations) by default. Directly-applicable diff suggestions auto-apply via the bundled em-review-editor sub-agent with batch approval; natural-language suggestions go through per-finding AskUserQuestion. Re-runs reviewers after every productive loop; loop-cap also runs a final re-review for accurate residual counts. Skip with --report-only. Reviewer set is driven by the registry at references/reviewers.json. Final report in Japanese.
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

1. **Phase 0**: Resolve protocol/registry/schema; determine review target (diff or whole-codebase) + `changed_files`; locate SPEC.md; probe codex. The orchestrator does NOT materialize a diff/codebase payload — each reviewer fetches its own data inside its own sub-agent context via `git diff` / `Read`.
2. **Phase 1**: Launch reviewers in parallel in a single turn (per registry, skipping `requires_spec`/`requires_codex` mismatches).
3. **Phase 2**: Aggregate, sanitize (path/severity/category/source), deduplicate, score by cross-model agreement.
4. **Phase 3**: Multi-loop auto-fix (≤ 3 iterations) by default. Target = `severity ∈ {Critical, High}` AND `category != "spec"`. Candidates split into (a) **directly-applicable** — `suggestion` is a unified diff, dispatched after batch approval; (b) **needs-judgment** — natural-language suggestion, surfaced via per-finding `AskUserQuestion` so the user picks the approach before any edit. Each approved candidate dispatches to the bundled `em-review:em-review-editor` sub-agent (`Read`/`Edit` only, no Bash/git/formatters). Scope is verified via content-hash delta (`git hash-object` over the orchestrator's backup snapshots) — the editor's `files_modified` is informational. Loops 2/3 require approval for every NEW `stable_id` but allow same-id retry. After every productive loop (including loop 3), the orchestrator re-runs all reviewers — perspectives with modified findings get a `stable_id`-only preamble (no titles, no descriptions — closes the cross-context-injection path); others get a generic collateral-impact preamble. Modify-only, no commits. Skip with `--report-only` (aliases: `--no-auto-fix`, `--no-fix`).
5. **Phase 4**: Skip-aware final report in Japanese (タメ語, 女性). Per-loop stats + termination reason included.

Each reviewer is also usable standalone via `/em-review:<skill_name>` (skill_name is in the registry — e.g. `security`, `gpt.architecture`).

## Flags

- `--report-only` (aliases `--no-auto-fix`, `--no-fix`): skip Phase 3. Every finding is reported as 未修正; the working tree is untouched.
- `--auto-fix`: legacy no-op kept for backward compatibility (auto-fix is the default).

$ARGUMENTS
