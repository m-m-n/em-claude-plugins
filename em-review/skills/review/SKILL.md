---
name: review
description: 並列多観点コードレビューのエントリポイント（em-review）。em-workflow レビューフェーズのスタンドアロン版です。現在の git diff（なければコードベース全体）、または GitHub PR（番号 / URL 指定、report-only 固定）を対象に、baseline +（SPEC.md があれば spec）+ 裁量層で観点を動的選択し、観点スキル注入型の汎用レビュアー（+ 条件により Codex クロスバリデーション）を並列起動、bounded auto-fix（≤ 3 ループ、--report-only でスキップ）とレビュー記録の書き出し（デフォルト /tmp 配下、--records <dir> で変更可）まで行います。コミットは一切しません
argument-hint: "[PR番号|PR URL] [--report-only] [--records <dir>]"
disable-model-invocation: true
allowed-tools: Read, Edit, Glob, Grep, Bash, Task, AskUserQuestion
---

# em-review Standalone Review

## Execution Context

This skill runs **inline in the main session** — the parallel reviewer
`Task()` calls are issued from the main context so each reviewer gets a
fresh, independent context (the cross-model agreement signal depends on it).

## Main Execution

Read `${CLAUDE_PLUGIN_ROOT}/references/review-phase.md` and execute it inline:

- project_root = cwd; review target = `git diff HEAD` (fallback:
  whole-codebase mode per the protocol's size gates). A PR number / GitHub
  PR URL argument switches to **PR mode** (`gh pr diff` based, report-only
  forced — Phase R0-PR).
- Records: `{records_base}/reviews-{YYYYMMDD-HHMM}/round1.yaml`. Default
  records_base = `/tmp/em-review/{repo-key}` (keeps the project clean;
  repo-keyed so round_context survives across runs); `--records <dir>`
  overrides (human-typed, self-responsibility — no containment check).
  Report the record path at the end.
- Perspective selection: Layer-1 floor = `baseline` from review-rules.yaml
  (+ `spec` when a SPEC.md is discoverable). If the cwd DOES contain a
  matching `feature-docs/{feature}/workflow.yaml` (em-workflow co-installed)
  with tasks covering the current diff, you MAY use its domains/complexity
  for the full Layer-1 evaluation instead. Layer 2 (discretionary additions
  from the diff) always applies — additions only, with reasons.
- Codex cross-validation per review-rules.yaml (`codex_cross_validation`),
  subject to codex availability.
- Auto-fix: ON by default, ≤ 3 loops; skip with `--report-only` (aliases
  `--no-auto-fix`, `--no-fix`); ALWAYS skipped in PR mode (the PR's code is
  not in the working tree). **em-review never commits** — fixes stay in the
  working tree for the user to review.

If `${CLAUDE_PLUGIN_ROOT}` does not resolve, locate the plugin under
`$HOME/.claude/plugins` / `$HOME/.claude/skills` only (path filter
`*/em-review/*/references/*`) — never the cwd.

## ⚠️ Auto-apply caution

Critical/High findings with a directly-applicable unified-diff suggestion and
no cross-reviewer conflict are applied to the working tree **without an
approval prompt**. Reviewing a diff you do not fully trust (e.g. a
contributor's branch)? Pass `--report-only`.

$ARGUMENTS
