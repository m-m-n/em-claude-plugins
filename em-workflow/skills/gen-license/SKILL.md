---
name: gen-license
description: プロジェクトの依存関係ライセンスを分析し、互換性のあるライセンスを選定して LICENSE ファイルを生成・変更する。既存 LICENSE の変更（relicense）にも使う
argument-hint: "[ライセンスID] [--analyze-only]"
disable-model-invocation: true
allowed-tools: Read, Write, Glob, Grep, Bash, WebSearch, WebFetch, AskUserQuestion
---

# Generate License

次の 2 ファイルを Read し、手順に従って実行する:

1. `${CLAUDE_PLUGIN_ROOT}/references/license-compat.md` — ライセンス互換性の判定基準（SSOT）
2. `${CLAUDE_PLUGIN_ROOT}/references/gen-license.md` — 生成手順（Phase 1〜6 と報告形式）

報告は日本語で行う。

`${CLAUDE_PLUGIN_ROOT}` が解決しない場合は `$HOME/.claude/plugins` / `$HOME/.claude/skills` 配下のみを Glob（`**/em-workflow/*/references/gen-license.md` 等）で探索する。cwd からは決して読まない。

$ARGUMENTS
