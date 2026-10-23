# Implementation Plan: codex-guard-procsub-in-wordlist

## Overview

codex-hook-interactive-guard の 2 つのコピーで、zsh の `for name (words)` の語一覧の最も外側の項目の語の先頭にあるプロセス置換を、コマンド列 p として読むバグ修正。タスクは task0001 の 1 つで、この文書にはタスク分割の判断とフィーチャー全体の取り決めだけを書く。

## Technology Stack

- **Language**: Python 3（既存のフックスクリプトとテスト）
- **Key libraries**: Python 標準ライブラリだけ（テストは unittest）
- **New dependencies**: なし（ライセンスの記録対象なし。`project.license` は none）

## Layer Structure

| 層 | ファイル | 役割 |
|----|----------|------|
| フック本体 | `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py` | コマンド文字列を字句として読み、deny / silent を決める。2 つはバイト単位で同一のコピー |
| テスト | `tests/test_codex_hook_interactive_guard.py` | 同じ CASES と構造・文書の検査を両コピーに流す |

依存の向きはテスト → フック本体だけ。フック本体はテストを参照しない。

## Shared Components

該当なし。タスクは task0001 の 1 つだけで、タスク間で使い合うコンポーネントは無い。

## Conventions

- 2 つのコピーは同じ変更の中で一緒に直し、バイト単位で同一に保つ（FR3）。
- CASES の行は `(期待する判定, ラベル, コマンド)` の形で、期待する判定は deny か silent。
- 既存の CASES の行は消さず、期待する判定も変えない（NFR4）。
- テストは Python 標準ライブラリの unittest だけを使う（NFR2）。
- 各プラグインの `plugin.json` と `.claude-plugin/marketplace.json` は変更しない（NFR3）。

## Cross-task Design Decisions

### D1: 1 タスクにまとめる

- **判断**: 2 つのコピーとテストファイルを task0001 の 1 つで変える。
- **理由**: FR3 は 2 つのコピーを同じ変更の中で直すことを求める。並列のタスクで同じファイルを分け合わない。CASES の行は読みの変更と対になる TDD の契約で、別タスクに分けるとどちらも単独では通らない。
- **影響タスク**: task0001

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 既存の読みが退行し、既存の CASES の行が落ちる | 中 | 高 | 既存の CASES と既存テストをすべて流す（NFR4、VERIFICATION.md TS-15、TS-19） |
| 語の先頭の判定が広すぎ、入れ子の w を p と読んで拒否漏れになる | 中 | 高 | 境界の行 TS-6〜TS-13 を CASES に置く（THREAT-MODEL.md TM-2） |
| 2 つのコピーが食い違う | 低 | 高 | TestCopies のバイト同一検査（VERIFICATION.md TS-18） |
| 語の途中・入れ子の項目の中のプロセス置換で読みのずれが残る | — | 中 | 対象外。SPEC.md の Known Limitations に記録済み |

## Open Questions

なし。
