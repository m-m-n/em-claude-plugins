# Feature: pin-status-read-heuristic

## Overview

hook 分類 pin（`tests/test_hook_classification_pin.py`）の `reads_per_task_status()` の観測規則を、ヘルパの識別子名に依存しない条件（docstring とコメントを除いたソースに `"workflow.yaml"` と `"status"` の両方が含まれるか）へ差し替える。旧規則の名前ヒューリスティックを削除し、新規則の挙動を固定する回帰テストを追加する。要件の詳細は `feature-docs/pin-status-read-heuristic/REQUIREMENTS.md` を参照する。

## Objectives

- hook 分類 pin が、ヘルパの識別子名に依存せずに、queue hook が `tasks.{T}.status` を読むかどうかを観測する。
- ドキュメント（`em-workflow/references/implement-phase.md` の Hook classification table）の分類と hook 実装が食い違ったら、その時点で pin テストが落ちる。

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1:** 観測規則を識別子名に依存しない条件へ差し替える。`reads_per_task_status()` は、docstring とコメントを除いたソース全体（既存の `_strip_docstrings` による `ast.unparse` 結果。識別子・文字列リテラルを含む全文）に、部分文字列 `"workflow.yaml"` と部分文字列 `"status"` の両方が含まれるとき True、それ以外は False を返す。`"status"` の照合は大文字小文字を区別する（小文字の `status` だけに一致する）。照合対象を AST の文字列リテラルだけに絞らない。関数名が正規表現に一致するかどうかは判定に使わない。関数が呼ばれているかどうか・到達可能かどうかも判定に使わない。
- **FR2:** 名前ヒューリスティックの削除。`_TASK_STATUS_NAME_RE` と、それを使う関数名収集（`task_status_fn_names`）・呼び出し名収集（`called_names`）の処理を `tests/test_hook_classification_pin.py` から削除する。削除で使われなくなる import（`re`）も削除する。
- **FR3:** 既存の前提条件と docstring 除去を維持する。`hook_path` が既存のファイルを指さないときに `ClassificationTableError` を送出する挙動と、判定の前に docstring とコメントを除去する処理はそのまま残す。`parse_classification_table` / `compare_table_to_sources` / `READS_STATUS` / `DOES_NOT_READ_STATUS` の名前とシグネチャは変えない（`tests/test_recycled_task_id_consistency.py` がこれらを import しているため）。
- **FR4:** ヘルパ名が旧規則に合わない status 読み出しの回帰テスト。workflow.yaml を読んで per-task の status を取り出す処理を、`"task"` と `"status"` が同一識別子に共起しない名前のヘルパ（例: `pending_from_workflow`）で持ち、そのヘルパを呼ぶ合成ソースを一時ファイルに書く。`reads_per_task_status()` が True を返すことを固定するテストを追加する。
- **FR5:** 再現手順が pin を落とすことのテスト。FR4 と同じ形の合成 hook ソース（一時ファイル、絶対パス）を does not read `tasks.{T}.status` と分類した行を `compare_table_to_sources()` に渡すと、その行が不一致として 1 件返ることを固定するテストを追加する。`compare_table_to_sources` は `REPO_ROOT / 絶対パス` で絶対パスがそのまま使われるため、`em-workflow/hooks/` 配下のファイルを書き換えずに検証できる。
- **FR6:** 改名で偽の赤が出ないことのテスト。`queue_stop_guard.py` の読み出し処理を模した合成ソースで、ヘルパ名を `task_statuses_from_workflow` から `statuses_from_workflow` に変えたものも `reads_per_task_status()` が True を返すことを固定するテストを追加する。
- **FR7:** 大文字だけの STATUS は数えないことのテスト。実行コードに `"workflow.yaml"` を含み、status を大文字の `STATUS` としてだけ含む（小文字の `status` をどこにも含まない）合成ソースに対して、`reads_per_task_status()` が False を返すことを固定するテストを追加する。
- **FR8:** 呼ばれない status 読み出しヘルパも True になることのテスト。実行コードに `"workflow.yaml"` を含み、status を読むヘルパを定義するが一度も呼ばない合成ソースに対して、`reads_per_task_status()` が True を返すことを固定するテストを追加する。
- **FR9:** 説明文の更新と既知の限界の明記。モジュール docstring の観測規則の説明（2. `reads_per_task_status` の項）、`reads_per_task_status` の docstring、既存テスト内のコメントで旧規則（per-task-status accessor の名前・呼び出し）を前提にしている記述を、新しい規則に合わせて書き直す。`reads_per_task_status` の docstring には次を明記する。この規則は文字列の共起による近似で、per-task status を読むことの証明ではない。例として、`queue_stop_guard.py` は step 単位の status 読み出し（`STEP_STATUS_RE`、`implement_in_progress`）を持つので、per-task の読み出しを取り除いても True のままになる。

### Non-Functional Requirements
- **NFR1:** テストコードは標準ライブラリのみを import する（test/README.md の規則）。
- **NFR2:** テストは `em-workflow/hooks/` 配下のファイルを書き換えない。合成ソースは tempfile で作る一時ファイルに限る。
- **NFR3:** 観測規則は 1 つだけ定義し、全行に同じように適用する。hook ごとの特別扱いを入れない。pin テストは `TestHookClassificationPin` の 1 件のまま増やさない。
- **NFR4:** 変更は repo ルートの `tests/` 配下に限る。`em-workflow/` 配下を変更しないため、plugin.json / marketplace.json の version は上げない。

## Implementation Approach

### Architecture

`reads_per_task_status(hook_path)` の判定手順:

```
hook_path が既存のファイルを指さない → ClassificationTableError を送出（FR3）
        ↓
_strip_docstrings で docstring とコメントを除去し ast.unparse した全文を得る（FR3）
        ↓
全文に部分文字列 "workflow.yaml" と部分文字列 "status"（大文字小文字を区別）の両方が含まれる → True
それ以外 → False（FR1）
```

### Data Flow

該当なし

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `_strip_docstrings`: 照合対象の全文を作る既存の処理（FR1, FR3）
- `tests/test_recycled_task_id_consistency.py`: `parse_classification_table` / `READS_STATUS` / `DOES_NOT_READ_STATUS` を import する。これらの名前とシグネチャは変えない（FR3, A8）

**External Dependencies:**
- 標準ライブラリのみ（NFR1）

### File Structure

```
tests/
└── test_hook_classification_pin.py   # 観測規則の差し替え、名前ヒューリスティックの削除、説明文の更新、回帰テストの追加
```

変更は repo ルートの `tests/` 配下に限る（NFR4）。`em-workflow/references/implement-phase.md` は変更しない（A7）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/pin-status-read-heuristic/**`
- `test-docs/pin-status-read-heuristic/**`

`feature-docs/pin-status-read-heuristic/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/pin-status-read-heuristic/**` covers `test-docs/pin-status-read-heuristic/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/pin-status-read-heuristic/` directory at all; the declared
`test-docs/pin-status-read-heuristic/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1（AC1 / FR1, FR5）: `pending_from_workflow` が `os.path.join(..., 'workflow.yaml')` を開き、正規表現 `r'^\s+status:\s*(\S+)'` で各タスクの status を取り出し、別の関数から呼ばれる合成ソースを一時ファイルに書く。その絶対パスを does not read と分類した 1 行を `compare_table_to_sources()` に渡す - 戻り値が `[(パス, DOES_NOT_READ_STATUS, READS_STATUS)]` の 1 件である
- [ ] TS2（AC3 / FR4）: TS1 と同じ合成ソース - `reads_per_task_status()` が True を返す
- [ ] TS3（AC4 / FR6）: `statuses_from_workflow` を定義して呼び、workflow.yaml のパスを組み立てる合成ソース - `reads_per_task_status()` が True を返す
- [ ] TS4（AC5 / FR1, FR7）: `'workflow.yaml'` をパスとして組み立て、`STATUS_KEY = 'STATUS'` のように大文字の `STATUS` だけを持ち、小文字の `status` を実行コードのどこにも含まない合成ソース - `reads_per_task_status()` が False を返す
- [ ] TS5（AC6 / FR1, FR8）: `'workflow.yaml'` をパスとして組み立て、`r'^\s+status:'` で status を読むヘルパを定義するが、どこからも呼ばない合成ソース - `reads_per_task_status()` が True を返す
- [ ] TS6（AC2, AC9 / FR1, FR3, NFR1, NFR2）: 既存の `TestHookClassificationPin` / `TestPinIsNotAVacuousCheck` / `TestObserveHookSource` を変更後の規則で実行する - すべて通る

### Integration Tests
該当なし

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 大文字の `STATUS` だけを含むソース - False（FR7）
- [ ] status を読むが呼ばれないヘルパだけを持つソース - True（FR8、A4）
- [ ] 文字列連結などで `"status"` や `"workflow.yaml"` を分割して書く実装 - 検出対象外（A6）

### Performance Tests
該当なし

## Security Considerations

該当なし

## Error Handling

### Error Codes

| Code | Description |
|------|-------------|
| `ClassificationTableError` | `hook_path` が既存のファイルを指さないときに送出する（FR3、既存の挙動を維持） |

### Error Flow

```
hook_path が既存のファイルを指さない → ClassificationTableError を送出
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1（FR1, FR5）: `"task"` と `"status"` が同一識別子に共起しないヘルパで workflow.yaml から per-task status を読む合成 hook を does not read と分類した行に対して、`compare_table_to_sources()` が不一致を 1 件返す。
- [ ] AC2（FR1, FR3）: `queue_stop_guard.py` は True、`queue_launch_guard.py` / `queue_failure_net.py` / `queue_taskstop_net.py` / `bash_guard.py` は False と観測され、現状と同じ結果になる。実装済みの Hook classification table に対する pin テストは通る。
- [ ] AC3（FR4）: status 読み出しを追加したがヘルパ名が旧規則に合わない合成ソースに対して、`reads_per_task_status()` が True を返すことを固定するテストがある。
- [ ] AC4（FR6）: ヘルパ名を `statuses_from_workflow` に改名した合成ソースでも `reads_per_task_status()` が True を返す。
- [ ] AC5（FR1, FR7）: workflow.yaml を含み、status を大文字の `STATUS` としてだけ含む合成ソースに対して `reads_per_task_status()` が False を返す。
- [ ] AC6（FR1, FR8）: workflow.yaml を含み、status を読むが呼ばれないヘルパだけを持つ合成ソースに対して `reads_per_task_status()` が True を返す。
- [ ] AC7（FR2）: `tests/test_hook_classification_pin.py` に `_TASK_STATUS_NAME_RE`、`task_status_fn_names`、`called_names` が残っていない。
- [ ] AC8（FR9）: `reads_per_task_status` の docstring に、規則が文字列の共起による近似で per-task の読み出しの証明ではないこと、および `queue_stop_guard.py` の step 単位の status 読み出し（`STEP_STATUS_RE` / `implement_in_progress`）のために per-task の読み出しを取り除いても True になる限界が書かれている。
- [ ] AC9（FR1, FR3, NFR1, NFR2）: 既存テスト（bash_guard の否定例、status 読み出し除去で False になる例、docstring のみの言及で False になる例、存在しないパスで例外になる例、分類反転で不一致が出る例）がすべて通り、`python3 -m unittest discover -s tests` が新たな失敗なしで終わる。

## Open Questions

なし

## Assumptions

- **A1:** 新しい観測規則は「docstring とコメントを除いたソースに workflow.yaml と status の両方が出現する」条件を採る。現行 5 ファイルの実行コードを確認した。`queue_stop_guard.py` だけが両方を含み、他の 4 ファイルは実行コードに status を含まない。
- **A2:** `"status"` の照合は大文字小文字を区別する。実際に読む対象は小文字の status（`queue_stop_guard.py:63` の `TASK_STATUS_RE`）。5 つの hook と既存の合成ソースで判定は変わらない。
- **A3:** 照合対象は docstring とコメントを除いたソース全文で、識別子を含む。AST の文字列リテラルだけに絞らない。既存の正例の合成ソース（`test_hook_classification_pin.py:472`、`483`）は status を識別子の中にしか持たないため。
- **A4:** 「ヘルパが呼ばれている」条件は落とし、到達可能かどうかも調べない。呼ばれない status 読み出しヘルパは True（赤）になることを受け入れ、そのことをテストで固定する。
- **A5:** 既知の限界として受け入れる。この規則は文字列の共起による近似で、per-task の読み出しの証明ではない。`queue_stop_guard.py` は step 単位の status 読み出し（`STEP_STATUS_RE`:60、`implement_in_progress` 内の 105 行目、呼び出し 364 行目）を持つ。そのため per-task の読み出しを取り除いても True のままになる。
- **A6:** 文字列連結などで `"status"` や `"workflow.yaml"` を分割して書く実装は検出対象外とする。
- **A7:** `implement-phase.md` は観測規則の中身を記述しておらず、Hook classification table の分類も変わらないため変更しない。
- **A8:** `tests/test_recycled_task_id_consistency.py` は `parse_classification_table` / `READS_STATUS` / `DOES_NOT_READ_STATUS` を import する（`test_hook_classification_pin.py` のモジュール docstring の記述による）。これらは変更しないので影響しない。そのファイル自体は今回の参照走査の対象に含まれていない。

## References

- 要件定義書: `feature-docs/pin-status-read-heuristic/REQUIREMENTS.md`
- `tests/test_hook_classification_pin.py`
- `tests/test_recycled_task_id_consistency.py`
- `em-workflow/references/implement-phase.md`（Hook classification table）
- test/README.md
