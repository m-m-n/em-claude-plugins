---
title: "hook-test-bytecode-suppression"
created_date: 2026-11-01
status: draft
---

# hook-test-bytecode-suppression - 要件定義書

## 1. 概要

### 1.1 背景
`tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` は、`em-workflow/hooks/destructive-guard.py` を `spec.loader.exec_module()` で読み込む。

### 1.2 目的
`tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` の実行で `em-workflow/hooks/__pycache__/` にバイトコードが書かれないようにする。

### 1.3 スコープ
- 対象: `tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` の 2 本（`tests/` 配下）。
- 対象外: `em-workflow/hooks/destructive-guard.py`（変更しない）。
- 対象外: サブプロセスでフックを起動する経路（`tests/test_destructive_guard_lexer_agreement.py` の `hook_verdict()`、`em-workflow/hooks/tests/run-destructive-guard.py` の `verdict()`）と、フック自身の `load_merge_exception()` による `merge_pr_allow.py` の読み込み。

## 2. ビジネス要件

### 2.1 ビジネス目標
`tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` の実行で `em-workflow/hooks/__pycache__/` にバイトコードが書かれないようにする。

### 2.2 対象ユーザー
該当なし。

### 2.3 期待される効果
- 上記 2 本のテストの単体実行、および `python3 -m unittest discover -s tests` の実行の後、`em-workflow/hooks/` 配下に `__pycache__` ができない。

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | extglob_units のフック読み込みでバイトコードを書かない | `tests/test_destructive_guard_extglob_units.py` の `load_hook()` が、読み込み中だけ `sys.dont_write_bytecode` を `True` にする | 高 |
| FR2 | lexer_agreement のフック読み込みでバイトコードを書かない | `tests/test_destructive_guard_lexer_agreement.py` の `_load_hook()` が、読み込み中だけ `sys.dont_write_bytecode` を `True` にする | 高 |
| FR3 | 全体実行でも em-workflow/hooks/ 配下に __pycache__ ができない | `python3 -m unittest discover -s tests` の後、`em-workflow/hooks/` 配下に `__pycache__` ができない | 高 |

### 4.2 機能詳細

#### FR1: extglob_units のフック読み込みでバイトコードを書かない

**説明**: `tests/test_destructive_guard_extglob_units.py` の `load_hook()` は、`em-workflow/hooks/destructive-guard.py` を `spec.loader.exec_module()` で読み込むときに `sys.dont_write_bytecode` を `True` にする。読み込みの後（読み込みが例外を投げた場合も含む）は、読み込み前の値に戻す。

**ビジネスルール**:
- 読み込みの後の `sys.dont_write_bytecode` は、読み込み前の値と同じ。
- 読み込みが例外を投げた場合も、読み込み前の値に戻す。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 読み込み中の例外 | `spec.loader.exec_module()` が例外を投げる | `sys.dont_write_bytecode` を読み込み前の値に戻す |

#### FR2: lexer_agreement のフック読み込みでバイトコードを書かない

**説明**: `tests/test_destructive_guard_lexer_agreement.py` の `_load_hook()`（モジュール読み込み時に `H = _load_hook()` として呼ばれる）は、`em-workflow/hooks/destructive-guard.py` を `spec.loader.exec_module()` で読み込むときに `sys.dont_write_bytecode` を `True` にする。読み込みの後（読み込みが例外を投げた場合も含む）は、読み込み前の値に戻す。

**ビジネスルール**:
- 読み込みの後の `sys.dont_write_bytecode` は、読み込み前の値と同じ。
- 読み込みが例外を投げた場合も、読み込み前の値に戻す。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 読み込み中の例外 | `spec.loader.exec_module()` が例外を投げる | `sys.dont_write_bytecode` を読み込み前の値に戻す |

#### FR3: 全体実行でも em-workflow/hooks/ 配下に __pycache__ ができない

**説明**: リポジトリルートで `python3 -m unittest discover -s tests` を実行した後、`em-workflow/hooks/` 配下（`em-workflow/hooks/tests/` を含む）に `__pycache__` ができない。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし。

### 5.2 セキュリティ要件
該当なし。

### 5.3 可用性要件
該当なし。

### 5.4 保守性要件
- NFR1: 既存テストはすべて通る（`python3 -m unittest discover -s tests` と `python3 em-workflow/hooks/tests/run-destructive-guard.py`）。
- NFR2: テストコードは標準ライブラリだけを使う（test/README.md、および両ファイルの `TestModuleContract` が標準ライブラリだけの import を確かめている）。

### 5.5 互換性要件
- NFR3: 読み込み後の `sys.dont_write_bytecode` は読み込み前の値と同じ。同じプロセスで動く他のテストモジュールの挙動を変えない。

## 6. UI/UX要件

該当なし（テストコードの読み込み処理だけの変更で、画面や利用者に見える振る舞いの変更が無い）。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- 修正は 2 本のテストファイル（`tests/` 配下）だけで行う。`em-workflow/hooks/destructive-guard.py` は変更しない。
- テストコードは標準ライブラリだけを使う。
- サブプロセスでフックを起動する経路（`tests/test_destructive_guard_lexer_agreement.py` の `hook_verdict()`、`em-workflow/hooks/tests/run-destructive-guard.py` の `verdict()`）と、フック自身の `load_merge_exception()` による `merge_pr_allow.py` の読み込みは変更対象にしない。

### 9.2 ビジネス上の制約
- 変更は `tests/` 配下だけで、プラグイン配下のファイルを変更しないため、version の変更は伴わない。

### 9.3 スケジュール制約
該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/hook-test-bytecode-suppression/**`
- `test-docs/hook-test-bytecode-suppression/**`

`feature-docs/hook-test-bytecode-suppression/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/hook-test-bytecode-suppression/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/hook-test-bytecode-suppression/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/hook-test-bytecode-suppression/` ディレクトリを生成しないが、宣言された `test-docs/hook-test-bytecode-suppression/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし。

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR1）: `em-workflow/hooks/` 配下に `__pycache__` が無い状態から `python3 -m unittest tests.test_destructive_guard_extglob_units` を実行した後、`em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] AC-2（FR2）: `em-workflow/hooks/` 配下に `__pycache__` が無い状態から `python3 -m unittest tests.test_destructive_guard_lexer_agreement` を実行した後、`em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] AC-3（FR3）: `em-workflow/hooks/` 配下に `__pycache__` が無い状態から `python3 -m unittest discover -s tests` を実行した後、`em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] AC-4（NFR1、NFR2、NFR3）: 既存テストはすべて通る。

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（AC-1）: `em-workflow/hooks/` 配下に `__pycache__` が無い状態で `tests.test_destructive_guard_extglob_units` を単体実行し、テストが通り、実行後も `em-workflow/hooks/` 配下に `__pycache__` が無いことを確かめる。
- [ ] TS-2（AC-2）: 同じ開始状態で `tests.test_destructive_guard_lexer_agreement` を単体実行し、テストが通り、実行後も `em-workflow/hooks/` 配下に `__pycache__` が無いことを確かめる。
- [ ] TS-3（AC-3、AC-4）: 同じ開始状態でリポジトリルートから `python3 -m unittest discover -s tests` を実行し、全テストが通り、実行後も `em-workflow/hooks/` 配下に `__pycache__` が無いことを確かめる。
- [ ] TS-4（AC-4）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全ケース通る。
- [ ] TS-5（NFR3）: `load_hook()` / `_load_hook()` を呼ぶ前と後で `sys.dont_write_bytecode` の値が同じ。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `sys.dont_write_bytecode` | `True` のとき、Python がモジュールの読み込みでバイトコード（`__pycache__/` 配下の `.pyc`）を書かない |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 修正範囲: 修正は 2 本のテストファイル（`tests/` 配下）だけで行う。`em-workflow/hooks/destructive-guard.py` は変更しない。
- [x] 変更対象にしない経路: サブプロセスでフックを起動する経路（lexer_agreement の `hook_verdict()`、`run-destructive-guard.py` の `verdict()`）は、フックをスクリプトとして実行するのでフック本体のバイトコードを書かない。隣のモジュール `merge_pr_allow.py` はフック自身の `load_merge_exception()` が `sys.dont_write_bytecode` を立てて読み込む。この経路は変更対象にしない。
- [x] 確認の開始状態: 受け入れ条件の確認は `em-workflow/hooks/` 配下に `__pycache__` が無い状態から始める。`__pycache__/` は `.gitignore` で無視されているため、以前の実行で残ったものは `git status` に出ない。
- [x] version: 変更は `tests/` 配下だけで、プラグイン配下のファイルを変更しないため、version の変更は伴わない。
- [x] デザインステップ: スキップ（テストコードの読み込み処理だけの変更で、画面や利用者に見える振る舞いの変更が無い）。

### 14.2 未確認・保留事項
なし。

## 15. 参考資料

- `tests/test_destructive_guard_extglob_units.py`
- `tests/test_destructive_guard_lexer_agreement.py`
- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/run-destructive-guard.py`
