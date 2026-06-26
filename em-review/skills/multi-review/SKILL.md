---
name: multi-review
description: Parallel multi-perspective code review across 9 reviewers (5 Claude + 4 GPT/Codex). Aggregates with cross-model agreement scoring; runs bounded multi-loop auto-fix (≤ 3 iterations) by default. Critical/High findings with a directly-applicable unified-diff suggestion and no cross-reviewer contradiction are auto-applied without user approval; contradictions (multiple reviewers proposing incompatible fixes at the same site) and natural-language / multi-alternative suggestions go through per-finding AskUserQuestion. Terminates when no Critical/High remain, after 3 loops, or when no candidate path forward remains. Re-runs reviewers after every productive loop; loop-cap also runs a final re-review for accurate residual counts. After Phase 4 renders the report, a single-pass Phase 5 dispatches any residual `即座に対応` items to the editor **without AskUserQuestion** (the LLM's own classification is the authorization) — closes the "said immediate, didn't immediately do it" gap. Skip with --report-only. Reviewer set is driven by the registry at references/reviewers.json. Final report in Japanese.
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
4. **Phase 3**: Multi-loop auto-fix (≤ 3 iterations) by default. Target = `severity ∈ {Critical, High}` AND `category != "spec"`. Candidates are classified into three buckets: (a) **`auto-applicable`** — unified-diff suggestion with no cross-reviewer conflict at the same `coupling_id`; dispatched **without any AskUserQuestion** (this is the "Critical/High は自動で対応" path). (b) **`conflict`** — ≥ 2 Critical/High candidates at the same site propose mutually incompatible fixes; one AskUserQuestion per group lets the user pick the prevailing proposal. (c) **`needs-judgment`** — natural-language / multi-alternative suggestion or a diff that failed validation; per-finding AskUserQuestion. Each chosen candidate dispatches to the bundled `em-review:em-review-editor` sub-agent (`Read`/`Edit` only, no Bash/git/formatters). Scope is verified via content-hash delta (`git hash-object` over the orchestrator's backup snapshots) — the editor's `files_modified` is informational. After every productive loop (including loop 3), the orchestrator re-runs all reviewers — perspectives with modified findings get a `stable_id`-only preamble (no titles, no descriptions — closes the cross-context-injection path); others get a generic collateral-impact preamble. The loop terminates with `clean` as soon as no Critical/High non-spec finding remains. Modify-only, no commits. Skip with `--report-only` (aliases: `--no-auto-fix`, `--no-fix`).
5. **Phase 4**: Skip-aware final report in Japanese (タメ語, 女性). Per-loop stats + termination reason included. `推奨事項 > 即座に対応` lists residual Critical/High findings (with stable_ids) that Phase 5 will follow up on; `中長期的改善` lists Medium findings + Critical/High excluded from Phase 5 (spec / user-skipped / out-of-scope) with their exclusion reason.
6. **Phase 5**: Single-pass auto-follow-through on the `即座に対応` items. When the orchestrator places a finding under `即座に対応`, that classification IS the authoritative judgment — Phase 5 dispatches each `em-review:em-review-editor` **without any AskUserQuestion**, reusing the same BACKUP_DIR / TOCTOU / content-hash scope check as Phase 3. Respects `aborted_stable_ids` (Phase 3 user skips) and `fixed_history` (already applied). No re-review, no loop. Phase 5 results append to the report as `## 🔁 即座対応 追加修正結果（Phase 5）`. Skip with `--report-only` (same flag as Phase 3).

Each reviewer is also usable standalone via `/em-review:<skill_name>` (skill_name is in the registry — e.g. `security`, `gpt.architecture`).

## ⚠️ Auto-apply caution

Auto-fix is **ON by default**. Critical/High findings whose suggestion is a directly-applicable unified diff (and that have no cross-reviewer conflict at the same site) are written to the working tree **without any approval prompt** — their CONTENT is not human- or semantically reviewed, only structurally validated. This is safe when you are reviewing your own changes. **When reviewing a diff you do not fully trust (e.g. a contributor's branch), pass `--report-only`** so nothing is applied unattended. Conflicts and natural-language suggestions still go through `AskUserQuestion`.

## Flags

- `--report-only` (aliases `--no-auto-fix`, `--no-fix`): skip Phase 3. Every finding is reported as 未修正; the working tree is untouched.
- `--auto-fix`: legacy no-op kept for backward compatibility (auto-fix is the default).

$ARGUMENTS
