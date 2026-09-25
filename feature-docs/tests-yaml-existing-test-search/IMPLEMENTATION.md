# Implementation Plan: tests-yaml-existing-test-search

## Overview

implementer が `*.tests.yaml` に「既存テストが無い」と記録する前に、変更対象ファイルを参照する既存テストをリポジトリ相対パスとファイル名で検索する規律を tdd-testing スキルに置き、implementer エージェント定義の Step 4c から参照させる。規律の記述は新規テストモジュールで静的に検査し、em-workflow の version を 0.2.8 から 0.2.9 に上げる。

## Technology Stack

- **文書**: Markdown — スキル定義 `em-workflow/skills/tdd-testing/SKILL.md` とエージェント定義 `em-workflow/agents/implementer.md`。追記する本文は既存本文と同じ英語で書く。
- **テスト**: Python 3 標準ライブラリの unittest のみ（`test/README.md`）
- **マニフェスト**: JSON — `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json`
- **新規依存**: なし（ライセンスを記録する新規依存はない。`project.license` は `none`）

## Layer Structure

| 層 | 責務 | 依存の向き |
|----|------|-----------|
| 規律の SSOT | tdd-testing/SKILL.md に新設するセクション。既存テスト検索の必須化（FR1）と、見つかった場合の記録方法（FR2）を定める | 他の層に依存しない |
| 規律の参照元 | implementer.md の Step 4c。SSOT のセクションをスキル名と見出し名で参照する（FR3） | SSOT を参照する |
| 静的検査 | 新規テストモジュール。上の 2 文書を読み取り専用で検査する（FR4） | 2 文書を読む |
| 配布メタデータ | 2 つのマニフェストの version（FR5） | 既存の version テストが検査する（NFR3） |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| 該当なし | — | 本フィーチャーは task0001 の 1 タスクで構成され、タスク間で共有する契約はない | — |

## Conventions

- プラグイン文書への追記は既存本文と同じ英語で書き、見出しの階層は既存構造に合わせる。
- テストの命名は NFR1 に従う（ファイル `test_<target>.py`、クラス `Test<Behavior>`、メソッド `test_<condition>_<expected_result>`）。
- `em-workflow/` 配下の変更と version bump は同じコミットに含める（`.claude/rules/core-plugin-version-bump.md`）。
- version の検査は既存テストの耐久不変条件（形式・patch 前進・レジストリ一致・キー集合）に任せ、version 専用の新規テストは作らない（NFR3）。値 0.2.9 そのものは verify で 2 ファイルを直接読んで確認する。
- `em-workflow/agents/implementer.md` に `# Task assignment` 見出しを追加しない（NFR4）。

## Cross-task Design Decisions

### D1: 1 タスク構成

- **決定**: FR1〜FR5 と NFR1〜NFR4 をすべて task0001 にまとめる。
- **理由**:
  - 新規テストモジュールは SKILL.md と implementer.md の記述を検査する。テストと文書変更を別タスクにすると、テスト側のタスクは自分の worktree に文書変更を持たず、新規テストが red のまま終わる。タスクは完全並列で順序を付けられないため、red から green までを同じタスクで完結させる。
  - version bump は `em-workflow/` 配下の変更と同じコミットに含める規則がある。version bump を別タスクにすると、文書変更のコミットが version bump を含まない。
- **影響タスク**: task0001

### D2: 規律の置き場所

- **決定**: 規律の本文は tdd-testing/SKILL.md の新設セクションに置く。implementer.md の Step 4c は、そのセクションを tdd-testing というスキル名とセクション見出しの文字列で参照する。
- **根拠**: SPEC.md FR1 / FR3
- **影響タスク**: task0001

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| tests/ 配下の全モジュールを走査する既存テスト（標準ライブラリ以外の import の検査、major/minor 固定の検査、共有ヘルパー関数名の重複検査など）が新規モジュールも検査する | 中 | 中 | 着手前にベースラインを記録し、完了時の全件実行と比べる |
| em-workflow/ 配下の文書を走査する既存テスト（特定語句の不在検査、禁止見出し検査）が SKILL.md と implementer.md への追記も検査する | 中 | 中 | 同上。`# Task assignment` 見出しを追加しない |
| マッチャーが文言に密着しすぎて将来の言い換えで壊れる、または緩すぎて規律を欠いた文書でも通る | 中 | 低 | 判定範囲を見出しで切り出したセクションに限り、要素ごとの識別語で判定する。規律の要素を欠いた偽サンプルを弾く否定テストを付ける |
| version bump を含まないコミットがコミット時の version bump 検査で拒否される | 低 | 中 | `em-workflow/` 配下の変更と 2 つのマニフェストの version 変更を同じコミットにする |

## Open Questions

- なし
