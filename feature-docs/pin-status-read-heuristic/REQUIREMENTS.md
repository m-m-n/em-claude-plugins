---
title: "pin-status-read-heuristic"
created_date: 2026-09-25
status: draft
---

# pin-status-read-heuristic - 要件定義書

## 1. 概要

### 1.1 背景
hook 分類 pin（`tests/test_hook_classification_pin.py`）の `reads_per_task_status()` は、per-task-status accessor の名前とその呼び出し（`_TASK_STATUS_NAME_RE`、`task_status_fn_names`、`called_names`）で、queue hook が `tasks.{T}.status` を読むかどうかを判定している。

### 1.2 目的
- hook 分類 pin が、ヘルパの識別子名に依存せずに、queue hook が `tasks.{T}.status` を読むかどうかを観測する。
- ドキュメント（`em-workflow/references/implement-phase.md` の Hook classification table）の分類と hook 実装が食い違ったら、その時点で pin テストが落ちる。

### 1.3 スコープ
- 対象: `tests/test_hook_classification_pin.py` の観測規則（`reads_per_task_status()`）、それに付随する説明文、回帰テストの追加。
- 変更は repo ルートの `tests/` 配下に限る。`em-workflow/` 配下は変更しない（NFR4）。
- `em-workflow/references/implement-phase.md` は変更しない（14.1 の A7）。

## 2. ビジネス要件

### 2.1 ビジネス目標
- hook 分類 pin が、ヘルパの識別子名に依存せずに、queue hook が `tasks.{T}.status` を読むかどうかを観測する。
- Hook classification table の分類と hook 実装が食い違ったら、その時点で pin テストが落ちる。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- ヘルパ名が旧規則に合わない status 読み出しを追加した場合も、分類との食い違いで pin テストが落ちる（AC1）。
- ヘルパ名を改名しても pin テストが偽の赤にならない（AC4）。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | 観測規則を識別子名に依存しない条件へ差し替える | docstring とコメントを除いたソース全体に `"workflow.yaml"` と `"status"` の両方が含まれるとき True |
| FR2 | 名前ヒューリスティックの削除 | `_TASK_STATUS_NAME_RE`、`task_status_fn_names`、`called_names`、不要になる `re` の import を削除する |
| FR3 | 既存の前提条件と docstring 除去を維持する | `ClassificationTableError` の送出、docstring とコメントの除去、公開名とシグネチャを維持する |
| FR4 | ヘルパ名が旧規則に合わない status 読み出しの回帰テスト | 旧規則に合わない名前のヘルパで status を読む合成ソースが True になることを固定する |
| FR5 | 再現手順が pin を落とすことのテスト | FR4 と同じ形の合成ソースを does not read と分類すると不一致が 1 件返ることを固定する |
| FR6 | 改名で偽の赤が出ないことのテスト | ヘルパ名を `statuses_from_workflow` に変えた合成ソースも True になることを固定する |
| FR7 | 大文字だけの STATUS は数えないことのテスト | 大文字の `STATUS` だけを含む合成ソースが False になることを固定する |
| FR8 | 呼ばれない status 読み出しヘルパも True になることのテスト | 呼ばれない status 読み出しヘルパを持つ合成ソースが True になることを固定する |
| FR9 | 説明文の更新と既知の限界の明記 | 旧規則を前提にした docstring とコメントを書き直し、既知の限界を明記する |

### 4.2 機能詳細

#### FR1: 観測規則を識別子名に依存しない条件へ差し替える

**説明**: `reads_per_task_status()` は、docstring とコメントを除いたソース全体（既存の `_strip_docstrings` による `ast.unparse` 結果。識別子・文字列リテラルを含む全文）に、部分文字列 `"workflow.yaml"` と部分文字列 `"status"` の両方が含まれるとき True、それ以外は False を返す。

**ビジネスルール**:
- `"status"` の照合は大文字小文字を区別する（小文字の `status` だけに一致する）。
- 照合対象を AST の文字列リテラルだけに絞らない。
- 関数名が正規表現に一致するかどうかは判定に使わない。
- 関数が呼ばれているかどうか・到達可能かどうかも判定に使わない。

#### FR2: 名前ヒューリスティックの削除

**説明**: `_TASK_STATUS_NAME_RE` と、それを使う関数名収集（`task_status_fn_names`）・呼び出し名収集（`called_names`）の処理を `tests/test_hook_classification_pin.py` から削除する。削除で使われなくなる import（`re`）も削除する。

#### FR3: 既存の前提条件と docstring 除去を維持する

**説明**: `hook_path` が既存のファイルを指さないときに `ClassificationTableError` を送出する挙動と、判定の前に docstring とコメントを除去する処理はそのまま残す。

**ビジネスルール**:
- `parse_classification_table` / `compare_table_to_sources` / `READS_STATUS` / `DOES_NOT_READ_STATUS` の名前とシグネチャは変えない（`tests/test_recycled_task_id_consistency.py` がこれらを import しているため）。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `ClassificationTableError` | `hook_path` が既存のファイルを指さない | 送出する（既存の挙動を維持） |

#### FR4: ヘルパ名が旧規則に合わない status 読み出しの回帰テスト

**説明**: workflow.yaml を読んで per-task の status を取り出す処理を、`"task"` と `"status"` が同一識別子に共起しない名前のヘルパ（例: `pending_from_workflow`）で持ち、そのヘルパを呼ぶ合成ソースを一時ファイルに書く。`reads_per_task_status()` が True を返すことを固定するテストを追加する。

#### FR5: 再現手順が pin を落とすことのテスト

**説明**: FR4 と同じ形の合成 hook ソース（一時ファイル、絶対パス）を does not read `tasks.{T}.status` と分類した行を `compare_table_to_sources()` に渡すと、その行が不一致として 1 件返ることを固定するテストを追加する。

**ビジネスルール**:
- `compare_table_to_sources` は `REPO_ROOT / 絶対パス` で絶対パスがそのまま使われるため、`em-workflow/hooks/` 配下のファイルを書き換えずに検証できる。

#### FR6: 改名で偽の赤が出ないことのテスト

**説明**: `queue_stop_guard.py` の読み出し処理を模した合成ソースで、ヘルパ名を `task_statuses_from_workflow` から `statuses_from_workflow` に変えたものも `reads_per_task_status()` が True を返すことを固定するテストを追加する。

#### FR7: 大文字だけの STATUS は数えないことのテスト

**説明**: 実行コードに `"workflow.yaml"` を含み、status を大文字の `STATUS` としてだけ含む（小文字の `status` をどこにも含まない）合成ソースに対して、`reads_per_task_status()` が False を返すことを固定するテストを追加する。

#### FR8: 呼ばれない status 読み出しヘルパも True になることのテスト

**説明**: 実行コードに `"workflow.yaml"` を含み、status を読むヘルパを定義するが一度も呼ばない合成ソースに対して、`reads_per_task_status()` が True を返すことを固定するテストを追加する。

#### FR9: 説明文の更新と既知の限界の明記

**説明**: モジュール docstring の観測規則の説明（2. `reads_per_task_status` の項）、`reads_per_task_status` の docstring、既存テスト内のコメントで旧規則（per-task-status accessor の名前・呼び出し）を前提にしている記述を、新しい規則に合わせて書き直す。

**ビジネスルール**:
- `reads_per_task_status` の docstring には次を明記する。
    - この規則は文字列の共起による近似で、per-task status を読むことの証明ではない。
    - 例として、`queue_stop_guard.py` は step 単位の status 読み出し（`STEP_STATUS_RE`、`implement_in_progress`）を持つので、per-task の読み出しを取り除いても True のままになる。

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | テストコードは標準ライブラリのみを import する（test/README.md の規則）。 |
| NFR2 | テストは `em-workflow/hooks/` 配下のファイルを書き換えない。合成ソースは tempfile で作る一時ファイルに限る。 |
| NFR3 | 観測規則は 1 つだけ定義し、全行に同じように適用する。hook ごとの特別扱いを入れない。pin テストは `TestHookClassificationPin` の 1 件のまま増やさない。 |
| NFR4 | 変更は repo ルートの `tests/` 配下に限る。`em-workflow/` 配下を変更しないため、plugin.json / marketplace.json の version は上げない。 |

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- テストコードは標準ライブラリのみを import する（NFR1）。
- テストは `em-workflow/hooks/` 配下のファイルを書き換えない（NFR2）。
- 観測規則は 1 つだけ定義し、hook ごとの特別扱いを入れない（NFR3）。
- 変更は repo ルートの `tests/` 配下に限り、version は上げない（NFR4）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/pin-status-read-heuristic/**`
- `test-docs/pin-status-read-heuristic/**`

`feature-docs/pin-status-read-heuristic/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/pin-status-read-heuristic/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/pin-status-read-heuristic/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/pin-status-read-heuristic/` ディレクトリを生成しないが、宣言された `test-docs/pin-status-read-heuristic/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 対応策 |
|------|--------|
| 規則は文字列の共起による近似で、per-task の読み出しの証明ではない。`queue_stop_guard.py` は step 単位の status 読み出しを持つため、per-task の読み出しを取り除いても True のままになる（A5） | 既知の限界として受け入れ、`reads_per_task_status` の docstring に明記する（FR9） |
| 文字列連結などで `"status"` や `"workflow.yaml"` を分割して書く実装は検出されない（A6） | 検出対象外とする |
| 呼ばれない status 読み出しヘルパも True になる（A4） | 受け入れ、テストで固定する（FR8） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR5）: `"task"` と `"status"` が同一識別子に共起しないヘルパで workflow.yaml から per-task status を読む合成 hook を does not read と分類した行に対して、`compare_table_to_sources()` が不一致を 1 件返す。
- [ ] AC2（FR1, FR3）: `queue_stop_guard.py` は True、`queue_launch_guard.py` / `queue_failure_net.py` / `queue_taskstop_net.py` / `bash_guard.py` は False と観測され、現状と同じ結果になる。実装済みの Hook classification table に対する pin テストは通る。
- [ ] AC3（FR4）: status 読み出しを追加したがヘルパ名が旧規則に合わない合成ソースに対して、`reads_per_task_status()` が True を返すことを固定するテストがある。
- [ ] AC4（FR6）: ヘルパ名を `statuses_from_workflow` に改名した合成ソースでも `reads_per_task_status()` が True を返す。
- [ ] AC5（FR1, FR7）: workflow.yaml を含み、status を大文字の `STATUS` としてだけ含む合成ソースに対して `reads_per_task_status()` が False を返す。
- [ ] AC6（FR1, FR8）: workflow.yaml を含み、status を読むが呼ばれないヘルパだけを持つ合成ソースに対して `reads_per_task_status()` が True を返す。
- [ ] AC7（FR2）: `tests/test_hook_classification_pin.py` に `_TASK_STATUS_NAME_RE`、`task_status_fn_names`、`called_names` が残っていない。
- [ ] AC8（FR9）: `reads_per_task_status` の docstring に、規則が文字列の共起による近似で per-task の読み出しの証明ではないこと、および `queue_stop_guard.py` の step 単位の status 読み出し（`STEP_STATUS_RE` / `implement_in_progress`）のために per-task の読み出しを取り除いても True になる限界が書かれている。
- [ ] AC9（FR1, FR3, NFR1, NFR2）: 既存テスト（bash_guard の否定例、status 読み出し除去で False になる例、docstring のみの言及で False になる例、存在しないパスで例外になる例、分類反転で不一致が出る例）がすべて通り、`python3 -m unittest discover -s tests` が新たな失敗なしで終わる。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1）: `pending_from_workflow` が `os.path.join(..., 'workflow.yaml')` を開き、正規表現 `r'^\s+status:\s*(\S+)'` で各タスクの status を取り出し、別の関数から呼ばれる合成ソースを一時ファイルに書く。その絶対パスを does not read と分類した 1 行を `compare_table_to_sources()` に渡し、戻り値が `[(パス, DOES_NOT_READ_STATUS, READS_STATUS)]` の 1 件であることを確認する。
- [ ] TS2（AC3）: TS1 と同じ合成ソースに対して `reads_per_task_status()` が True を返す。
- [ ] TS3（AC4）: `statuses_from_workflow` を定義して呼び、workflow.yaml のパスを組み立てる合成ソースに対して `reads_per_task_status()` が True を返す。
- [ ] TS4（AC5）: `'workflow.yaml'` をパスとして組み立て、`STATUS_KEY = 'STATUS'` のように大文字の `STATUS` だけを持ち、小文字の `status` を実行コードのどこにも含まない合成ソースに対して `reads_per_task_status()` が False を返す。
- [ ] TS5（AC6）: `'workflow.yaml'` をパスとして組み立て、`r'^\s+status:'` で status を読むヘルパを定義するが、どこからも呼ばない合成ソースに対して `reads_per_task_status()` が True を返す。
- [ ] TS6（AC2, AC9）: 既存の `TestHookClassificationPin` / `TestPinIsNotAVacuousCheck` / `TestObserveHookSource` を変更後の規則で実行し、すべて通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 実行コード | docstring とコメントを除いたソース（`_strip_docstrings` による `ast.unparse` 結果） |
| 合成ソース | テストが tempfile で作る一時ファイルに書く hook ソース |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: 新しい観測規則は「docstring とコメントを除いたソースに workflow.yaml と status の両方が出現する」条件を採る。現行 5 ファイルの実行コードを確認した。`queue_stop_guard.py` だけが両方を含み、他の 4 ファイルは実行コードに status を含まない。
- [x] A2: `"status"` の照合は大文字小文字を区別する。実際に読む対象は小文字の status（`queue_stop_guard.py:63` の `TASK_STATUS_RE`）。5 つの hook と既存の合成ソースで判定は変わらない。
- [x] A3: 照合対象は docstring とコメントを除いたソース全文で、識別子を含む。AST の文字列リテラルだけに絞らない。既存の正例の合成ソース（`test_hook_classification_pin.py:472`、`483`）は status を識別子の中にしか持たないため。
- [x] A4: 「ヘルパが呼ばれている」条件は落とし、到達可能かどうかも調べない。呼ばれない status 読み出しヘルパは True（赤）になることを受け入れ、そのことをテストで固定する。
- [x] A5: 既知の限界として受け入れる。この規則は文字列の共起による近似で、per-task の読み出しの証明ではない。`queue_stop_guard.py` は step 単位の status 読み出し（`STEP_STATUS_RE`:60、`implement_in_progress` 内の 105 行目、呼び出し 364 行目）を持つ。そのため per-task の読み出しを取り除いても True のままになる。
- [x] A6: 文字列連結などで `"status"` や `"workflow.yaml"` を分割して書く実装は検出対象外とする。
- [x] A7: `implement-phase.md` は観測規則の中身を記述しておらず、Hook classification table の分類も変わらないため変更しない。
- [x] A8: `tests/test_recycled_task_id_consistency.py` は `parse_classification_table` / `READS_STATUS` / `DOES_NOT_READ_STATUS` を import する（`test_hook_classification_pin.py` のモジュール docstring の記述による）。これらは変更しないので影響しない。そのファイル自体は今回の参照走査の対象に含まれていない。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- `tests/test_hook_classification_pin.py`
- `tests/test_recycled_task_id_consistency.py`
- `em-workflow/references/implement-phase.md`（Hook classification table）
- test/README.md
