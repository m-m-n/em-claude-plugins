---
title: "scripts-test-bytecode-suppression"
created_date: 2026-11-07
status: draft
---

# scripts-test-bytecode-suppression - 要件定義書

## 1. 概要

### 1.1 背景
プラグイン配下は git の追跡対象かどうかに関係なく配布物にそのままコピーされる。

### 1.2 目的
`python3 -m unittest discover -s tests` の全体実行の後、`em-workflow/scripts/` 配下に `__pycache__` ができないようにする。

### 1.3 スコープ
- 対象: tests/ 配下のテストコードが `em-workflow/scripts/` 配下のスクリプトを読み込む・起動する箇所（FR1、FR2、FR3）
- 変更はテストコード側（tests/）に限る（NFR1）
- 対象外: `em-workflow/hooks/` 配下の読み込み、`report-name-entry.py` の本番での実行（14.2 の前提を参照）

## 2. ビジネス要件

### 2.1 ビジネス目標
- `python3 -m unittest discover -s tests` の全体実行の後、`em-workflow/scripts/` 配下に `__pycache__` ができないようにする。プラグイン配下は git の追跡対象かどうかに関係なく配布物にそのままコピーされる。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- テスト全体実行の後、`em-workflow/scripts/` 配下に `__pycache__` が存在しない

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | テストのプロセス内読み込みでバイトコードを書かない | `exec_module` での読み込みの間だけ `sys.dont_write_bytecode` を True にし、終了後に元の値へ戻す | resolved |
| FR2 | 子プロセスが兄弟スクリプトを読み込む経路でバイトコードを書かない | 兄弟スクリプトを読み込む子プロセスの起動にバイトコード抑止を付ける | resolved |
| FR3 | 他モジュールが漏らすフラグに頼らない | 抑止を各読み込み箇所・各起動箇所が自分で行う | resolved |

### 4.2 機能詳細

#### FR1: テストのプロセス内読み込みでバイトコードを書かない

**説明**: tests/ 配下のテストモジュールが `em-workflow/scripts/*.py` を `importlib.util.spec_from_file_location` + `exec_module` でプロセス内に読み込む箇所は、すべて読み込みの間だけ `sys.dont_write_bytecode` を True にし、終わったら（モジュール本体が例外を投げた場合も）呼び出し前の値に戻す。モジュール読み込み時（モジュールレベル）の呼び出しと、テスト実行中の呼び出しの両方が対象。

**ビジネスルール**:
- 読み込み後の `sys.dont_write_bytecode` は呼び出し前の値（True / False のどちらでも）に戻す
- モジュール本体が例外を投げた場合も呼び出し前の値に戻す

#### FR2: 子プロセスが兄弟スクリプトを読み込む経路でバイトコードを書かない

**説明**: テストが `em-workflow/scripts/` のスクリプトを子プロセスとして起動し、その子プロセスが兄弟スクリプトをプロセス内に読み込む場合（現状は `report-name-entry.py` が `validate-worker-output.py` を `exec_module` で読み込む経路。`tests/test_report_name_entry.py` の `run_entry` から起動される）、その起動にバイトコード抑止（インタプリタの `-B`、または起動時に渡す環境変数 `PYTHONDONTWRITEBYTECODE=1`）を付ける。

**ビジネスルール**:
- 抑止は該当する起動 1 回ごとの引数または env に限る（NFR2）

#### FR3: 他モジュールが漏らすフラグに頼らない

**説明**: FR1 / FR2 の抑止は各読み込み箇所・各起動箇所が自分で行い、他のテストモジュールが設定した `sys.dont_write_bytecode` の値（現状 `tests/test_merge_ci_wait.py` がモジュールレベルで True にして戻さない）や、実行順序に依存しない。

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | `em-workflow/scripts/` 配下のスクリプト本体は変更しない。変更はテストコード側（tests/）に限る。 |
| NFR2 | プロセス全体の `os.environ` を書き換えない。子プロセスのバイトコード抑止は該当する起動 1 回ごとの引数または env に限る（`tests/test_sca_child_env_path_filtering.py` などが子プロセスの環境変数を検査しているため、プロセス全体の環境変数を変えると判定に影響しうる）。 |
| NFR3 | テストコードは標準ライブラリだけを使う（test/README.md の規約）。 |
| NFR4 | 既存テストの検証内容（アサーション・テスト対象の振る舞い）を変えない。 |

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR4 を参照

### 5.5 互換性要件
該当なし

## 6. UI/UX要件

該当なし（画面・UI・視覚的な成果物が無い）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- `em-workflow/scripts/` 配下のスクリプト本体は変更しない（NFR1）
- プロセス全体の `os.environ` を書き換えない（NFR2）
- テストコードは標準ライブラリだけを使う（NFR3）

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/scripts-test-bytecode-suppression/**`
- `test-docs/scripts-test-bytecode-suppression/**`

`feature-docs/scripts-test-bytecode-suppression/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/scripts-test-bytecode-suppression/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/scripts-test-bytecode-suppression/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/scripts-test-bytecode-suppression/` ディレクトリを生成しないが、宣言された `test-docs/scripts-test-bytecode-suppression/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: `em-workflow/scripts/__pycache__` が存在しない状態からリポジトリルートで `python3 -m unittest discover -s tests` を実行した後、`em-workflow/scripts/` 配下に `__pycache__` が存在しない。（FR1、FR2、FR3）
- [ ] AC2: 同じ全体実行で、既存テストがすべて通る。（NFR4）
- [ ] AC3: プロセス内読み込みの後、`sys.dont_write_bytecode` は呼び出し前の値（True / False のどちらでも）に戻っている。モジュール本体が例外を投げた場合も戻っている。（FR1、FR3）
- [ ] AC4: `report-name-entry.py` を起動するテストを単独で実行した後も、`em-workflow/scripts/` 配下に `__pycache__` が存在しない。（FR2、FR3）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 全体実行（`python3 -m unittest discover -s tests`）の前後で `em-workflow/scripts/__pycache__` の有無を確かめる。
- [ ] 読み込み処理を、テスト専用の一時ディレクトリに置いたプローブモジュールに向け、読み込み中にフラグが True であること、開始値 True / False のそれぞれで終了後に開始値へ戻ること、本体が例外を投げても戻ることを確かめる（前例: `tests/test_destructive_guard_extglob_units.py` の `TestHookLoadWritesNoBytecode`。プローブを使うので、壊れた読み込み処理でも `em-workflow/` 配下に書かない）。
- [ ] モジュールレベルで読み込む test モジュール（例: `tests/test_check_plugin_invariants.py`、`tests/test_decide_tier_final_score.py`、`tests/test_final_path_correction.py`）を単独実行し、`em-workflow/scripts/__pycache__` ができないことを確かめる。
- [ ] `tests/test_report_name_entry.py` を単独実行し、子プロセス経由で `validate-worker-output` のバイトコードが書かれないことを確かめる。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| プロセス内読み込み | `importlib.util.spec_from_file_location` + `exec_module` でスクリプトをテストのプロセス内に読み込むこと |
| 兄弟スクリプト | 子プロセスとして起動されたスクリプトと同じ `em-workflow/scripts/` 配下にある別のスクリプト |

## 14. 確認事項

### 14.1 確認済み事項
該当なし

### 14.2 未確認・保留事項（前提）
- [ ] 対象は `em-workflow/scripts/` 配下だけ。`em-workflow/hooks/` 配下（例: `tests/test_report_name_entry.py` の `queue_stop_guard.py` 読み込み）は hook-test-bytecode-suppression の範囲で、この feature では扱わない。
- [ ] プロセス内読み込みの抑止は、既存の前例（`tests/test_destructive_guard_extglob_units.py` の `load_hook`、`tests/test_codex_hook_tty_reaper.py`）と同じ「保存・True に設定・finally で復元」の形にする。各ファイルに書くか、tests/ 配下の共通ヘルパーにまとめるかは計画段階で決める。
- [ ] `tests/test_merge_ci_wait.py` のモジュールレベルの `sys.dont_write_bytecode = True`（戻さない）はこの feature では変更しない。
- [ ] `report-name-entry.py` の本番での実行（兄弟の `validate-worker-output.py` を読み込むときにバイトコードを書きうる）は対象外。この feature の目標はテスト全体実行に限る。
- [ ] メインスクリプトとして直接起動されたファイル（`python3 <script>.py`）自体はバイトコードを書かないので、兄弟を読み込まない子プロセス起動には抑止を付けなくてよい。`runpy.run_path` でのソース実行もバイトコードを書かない。
- [ ] plugin のバージョンは触らない（`.claude/rules/core-plugin-version-bump.md`）。変更は tests/ だけなのでプラグイン配下のファイルも変わらない。

## 15. 参考資料

- `tests/test_destructive_guard_extglob_units.py`: `load_hook`、`TestHookLoadWritesNoBytecode`（前例）
- `tests/test_codex_hook_tty_reaper.py`: 前例
- test/README.md: テストコードの規約
