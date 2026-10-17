---
title: "codex-guard-anon-fn-pipe"
created_date: 2026-10-17
status: draft
---

# codex-guard-anon-fn-pipe - 要件定義書

## 1. 概要

### 1.1 背景
`codex-hook-interactive-guard.py`（em-workflow と em-review の 2 つのコピー）について、zsh の無名関数 `function () { ...; }` の頭にパイプまたは標準入力のリダイレクトを受けたときの、本体にあるプログラム指定なしの `python3` の扱いを対象とする。

### 1.2 目的
- `codex-hook-interactive-guard.py`（em-workflow と em-review の 2 つのコピー）は、頭にパイプまたは標準入力のリダイレクトを受けた zsh の無名関数 `function () { ...; }` の本体にある、プログラム指定なしの `python3` を deny しない。
- 誤検知の deny が再発しないよう、挙動を回帰ケースで固定する。

### 1.3 スコープ
- `tests/test_codex_hook_interactive_guard.py` の `CASES` に回帰ケースを 3 件追加する（FR4）。
- フックスクリプト 2 つ（`em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`）は、追加したケースが現行コードで失敗した場合に限り変更する（FR5）。

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 に同じ。

### 2.2 対象ユーザー
該当なし。

### 2.3 期待される効果
該当なし。

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 |
|----|--------|
| FR1 | `function ()` へのパイプが本体につながる |
| FR2 | パイプを受けた `function ()` 本体の `-i` は引き続き deny する |
| FR3 | `function` と `()` の間の標準入力リダイレクトが本体につながる |
| FR4 | `CASES` への回帰ケース追加 |
| FR5 | フックの変更は新ケースが失敗した場合に限る |

### 4.2 機能詳細

#### FR1: `function ()` へのパイプが本体につながる

**入力**: `zsh -c 'printf "print(1)\n" | function () { python3; }'`

**出力**: フックの 2 つのコピーはいずれも終了コード 0 で終わり、標準出力・標準エラー出力に何も書かない。

#### FR2: パイプを受けた `function ()` 本体の `-i` は引き続き deny する

**入力**: `zsh -c 'printf "print(1)\n" | function () { python3 -i; }'`

**出力**: フックの 2 つのコピーはいずれも deny の判定（`permissionDecision: deny`）を 1 件出力する。

#### FR3: `function` と `()` の間の標準入力リダイレクトが本体につながる

**入力**: `zsh -c 'function < /dev/null () { python3; }'`（再現手順 3）

**出力**: フックの 2 つのコピーはいずれも終了コード 0 で終わり、標準出力・標準エラー出力に何も書かない。

#### FR4: `CASES` への回帰ケース追加

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に、`(期待する判定, ラベル, コマンド)` の形で次の 3 件を追加する。

- silent: `zsh -c 'printf "print(1)\n" | function () { python3; }'`
- deny: `zsh -c 'printf "print(1)\n" | function () { python3 -i; }'`
- silent: `zsh -c 'function < /dev/null () { python3; }'`

**ルール**:
- ラベルは既存のエントリと同じく日本語で書く。
- 配置の目安:
    - パイプの 2 件は、zsh の無名関数の形のセクション（既存の `echo x | function () { python3; }` のエントリの近く）に置く。
    - リダイレクトの 1 件は、頭の標準入力リダイレクトのセクション（`function < /dev/null { python3; }` の近く）に置く。
- Python のリテラルとしては次のように書く。

```python
"zsh -c 'printf \"print(1)\\n\" | function () { python3; }'"
"zsh -c 'printf \"print(1)\\n\" | function () { python3 -i; }'"
"zsh -c 'function < /dev/null () { python3; }'"
```

- 3 件のコマンドはいずれも `CASES` にまだ無い（grep で確認済み）。`test_cases_are_unique` は引き続き通る。

#### FR5: フックの変更は新ケースが失敗した場合に限る

**説明**: フックスクリプトは、追加したケースが現行コードで失敗した場合に限り変更する。変更する場合は 2 つのコピーを同じ変更の中で直し、バイト単位で同一に保つ。

## 5. 非機能要件

- **NFR1:** `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` はバイト単位で同一に保つ（`TestCopies.test_the_two_copies_are_byte_identical` で固定）。
- **NFR2:** 既存の `CASES` のエントリは削除も変更もしない（`.claude/rules/hook-tests.md`: 既存の deny ケースは消さない）。
- **NFR3:** テストコードは Python の標準ライブラリだけを使う（`test/README.md`）。
- **NFR4:** プラグインの version は変更しない（`.claude/rules/core-plugin-version-bump.md`）。patch 相当の変更で、Actions が上げる。

## 6. UI/UX要件

該当なし（デザインステップは skipped。フックのテスト表へのテストケース追加（と、必要ならパーサーの修正）であり、ユーザーインターフェースや見た目の設計は無い）。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- 5 章の NFR1〜NFR4 に同じ。

### 9.2 ビジネス上の制約
該当なし。

### 9.3 スケジュール制約
該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-fn-pipe/**`
- `test-docs/codex-guard-anon-fn-pipe/**`

`feature-docs/codex-guard-anon-fn-pipe/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-fn-pipe/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-fn-pipe/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-anon-fn-pipe/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-anon-fn-pipe/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 2 つのコピーはいずれも `zsh -c 'printf "print(1)\n" | function () { python3; }'` に対し、終了コード 0、標準出力・標準エラー出力ともに空になる。（FR1）
- [ ] AC2: 2 つのコピーはいずれも `zsh -c 'printf "print(1)\n" | function () { python3 -i; }'` に対し、deny の判定を出力する。（FR2）
- [ ] AC3: 2 つのコピーはいずれも `zsh -c 'function < /dev/null () { python3; }'` に対し、終了コード 0、標準出力・標準エラー出力ともに空になる。（FR3）
- [ ] AC4: `CASES` に FR4 の 3 件があり、`python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る（`test_cases_are_unique` と `test_cases_run_against_both_copies` を含む）。（FR4）
- [ ] AC5: `TestCopies.test_the_two_copies_are_byte_identical` が通る。（FR5、NFR1）
- [ ] AC6: 基準リビジョン `ceefe2b5` 時点にあった `CASES` のエントリが、すべて変更されずに残っている。（NFR2）

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1、AC2、AC3、AC4）: `tests.test_codex_hook_interactive_guard.TestCasesTable.test_cases_run_against_both_copies` — `CASES` の表が、追加したエントリを 2 つのコピーの両方に流す。
- [ ] TS2（AC4）: `tests.test_codex_hook_interactive_guard.TestCasesTable.test_cases_are_unique` — 追加したコマンドが既存のものと重複しない。
- [ ] TS3（AC5）: `tests.test_codex_hook_interactive_guard.TestCopies.test_the_two_copies_are_byte_identical` — 2 つのコピーがバイト単位で同一である。
- [ ] TS4（AC6）: `tests/test_codex_hook_interactive_guard.py` の `ceefe2b5` との差分確認 — 差分は `CASES` の行の追加だけである。

## 13. 用語定義

該当なし。

## 14. 確認事項

### 14.1 確認済み事項
- [x] FR4 の 3 件のコマンドが `CASES` に既にあるか: いずれもまだ無い（grep で確認済み）。

### 14.2 未確認・保留事項（前提）
- [ ] A1: 基準リビジョンで挙動は既に正しい。オーケストレーターが `dfe45b1a` で行った事前調査でフックを実行し、3 件のコマンドについて silent / silent / deny を確認している。コードを読んだ結果もこれを裏付ける。`_open_group`（em-workflow のコピーの 646〜669 行、em-review のコピーも同じ行）は `_flush()` の前に `anon_pipe = self.pipe_pending` と `anon_stdin = anon and self.stdin` を読み、空の `()` を閉じた時点で `anon_head` を通じて続く `{` の本体に引き渡す。このためフックのコード変更は想定しない。要件分析ではコマンド実行の手段が無く、フックを再実行していない。（取り消し可能）
- [ ] A2: タスクの完了条件が挙げる `CASES` のエントリは 2 件である。再現手順 3 のリダイレクトの形（`function < /dev/null () { python3; }`）を 3 件目の silent エントリとして加える。再現手順のどの再発もテストで検出する、という完了条件を満たすためである。テスト 1 行の追加で、外すのも容易である。（取り消し可能）
- [ ] A3: 追加する `CASES` エントリの配置とラベルの文言は SPEC と実装に任せる。固定するのは期待する判定とコマンド文字列だけである。エントリの挿入で `SAMPLE_CASES = CASES[::12]` がずれるが、正しさには影響しない。（取り消し可能）

## 15. 参考資料

- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
- `test/README.md`
