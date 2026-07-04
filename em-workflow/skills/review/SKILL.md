---
name: review
description: 単体レビューのエントリポイント（em-workflow）。SDD を通さない日常レビューを吸収します。workflow.yaml 不在時は baseline（comprehensive + SPEC.md があれば spec）+ 裁量層の追加観点で動作し、選択された観点ごとに汎用レビュアー（+ 条件により Codex クロスバリデーション）を並列起動、bounded auto-fix（≤ 3 ループ、--report-only でスキップ）とレビュー記録の書き出しまで行います。コミットは一切しません
argument-hint: "[--report-only]"
disable-model-invocation: true
allowed-tools: Read, Edit, Glob, Grep, Bash, Task, AskUserQuestion
---

# em-workflow Standalone Review

## Execution Context

This skill runs **inline in the main session** — the parallel reviewer
`Task()` calls are issued from the main context so each reviewer gets a
fresh, independent context (the cross-model agreement signal depends on it).

## Main Execution

Read `${CLAUDE_PLUGIN_ROOT}/references/review-phase.md` and execute it inline
in **standalone mode**:

- project_root = cwd; review target = `git diff HEAD` (fallback:
  whole-codebase mode per the protocol's size gates).
- Perspective selection: Layer-1 floor = `baseline` from review-rules.yaml
  (+ `spec` when a SPEC.md is discoverable). If the cwd DOES contain a
  matching `feature-docs/{feature}/workflow.yaml` with tasks covering the
  current diff, you MAY use its domains/complexity for the full Layer-1
  evaluation instead. Layer 2 (discretionary additions from the diff) always
  applies — additions only, with reasons.
- Codex cross-validation per review-rules.yaml (`codex_cross_validation`),
  subject to codex availability.
- Auto-fix: ON by default, ≤ 3 loops; skip with `--report-only` (aliases
  `--no-auto-fix`, `--no-fix`). **Standalone mode never commits** — fixes
  stay in the working tree for the user to review.
- Round record: write `./reviews-{YYYYMMDD-HHMM}/round1.yaml` (git handling
  is the user's choice). Report its path at the end.

If `${CLAUDE_PLUGIN_ROOT}` does not resolve, locate the plugin under
`$HOME/.claude/plugins` / `$HOME/.claude/skills` only (path filter
`*/em-workflow/*/references/*`) — never the cwd.

## ⚠️ Auto-apply caution

Critical/High findings with a directly-applicable unified-diff suggestion and
no cross-reviewer conflict are applied to the working tree **without an
approval prompt**. Reviewing a diff you do not fully trust (e.g. a
contributor's branch)? Pass `--report-only`.

$ARGUMENTS
