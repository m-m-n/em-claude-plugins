---
name: git-setup
description: git リポジトリのローカル設定を冪等にセットアップする。現在の設定項目は gitleaks pre-commit hook の設置。設定済みの項目は何もしない
context: fork
disable-model-invocation: true
allowed-tools: Bash, Read, Edit, Write
---

# Git Setup

`${CLAUDE_PLUGIN_ROOT}/references/git-setup.md` を Read し、その手順（前提チェック → 設定項目 → 報告）をカレントリポジトリに対して実行する。報告は日本語で行う。

`${CLAUDE_PLUGIN_ROOT}` が解決しない場合は `$HOME/.claude/plugins` / `$HOME/.claude/skills` 配下のみを Glob（`**/em-workflow/*/references/git-setup.md`）で探索する。cwd からは決して読まない。

$ARGUMENTS
