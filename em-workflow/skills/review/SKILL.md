---
name: review
description: 単体レビューのエントリポイント（em-workflow）。SDD を通さない日常レビューを吸収します。workflow.yaml 不在時は baseline（comprehensive + SPEC.md があれば spec）+ 裁量層の追加観点で動作し、選択された各観点は primary_chain 先頭の利用可能な非 Claude レビュアー（Codex、および別途 vertex-review プラグインが導入済みなら LiteLLM 経由の Vertex AI / Muse）を 1 体だけ起動、チェーン全滅時のみ Claude 汎用レビュアーがフォールバックします。全観点確定後は Opus 評価者が 1 体、ラウンドを評価します。その上で bounded auto-fix（≤ 3 ループ、--report-only でスキップ）とレビュー記録の書き出しまで行います。コミットは一切しません
argument-hint: "[--report-only]"
disable-model-invocation: true
model: opus
allowed-tools: Read, Edit, Glob, Grep, Bash, Task, AskUserQuestion
---

# em-workflow Standalone Review

## Execution Context

This skill runs **inline in the main session** — the parallel reviewer
`Task()` calls are issued from the main context so each perspective's
primary (or fallback) reviewer gets a fresh, independent context. The
evaluator `Task()` call is issued once every perspective's result is final.

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
- Each selected perspective dispatches ONE non-Claude primary reviewer taken
  from the front of that perspective's `primary_chain` (reviewers.yaml);
  when no chain entry is available, the perspective falls back to the
  Claude generic reviewer instead — the two are mutually exclusive. After
  every perspective's result is final, one Opus evaluator subagent
  evaluates the whole round.
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
