# Feature: routeback-record-direct-key

## Overview

`em-workflow/hooks/queue_stop_guard.py` の Stop hook が route-back 記録 `routeback_failed_journal_line` を読む範囲を、タスク自身の `tasks.{T}` マッピングの直下キーに限定する。
`tasks.{T}.notes`（implementer の報告から書かれる、信頼できない入力）の中のテキストが、Stop hook の未起動 / 失敗の分類に影響しないようにする。

## Objectives

- queue_stop_guard.py は route-back 記録 `routeback_failed_journal_line` を、タスク自身の `tasks.{T}` マッピングの直下キーからのみ読む。`tasks.{T}.notes` の中のテキストは、Stop hook の未起動 / 失敗の分類に影響しない。

## Technical Requirements

### Functional Requirements

- **FR1:** 記録の読み取りを `tasks.{T}` の直下キーに限定する。
    - `em-workflow/hooks/queue_stop_guard.py` の `task_routeback_records_from_workflow` は、`routeback_failed_journal_line:` 行がそのタスク自身の `taskNNNN:` マッピングの直下キーである場合、つまりマッピングの直下の子のインデントにある場合に限り、その行をタスクの記録として扱う。
    - 直下の子のインデントより深くインデントされた行は、記録として読まない。対象は次のとおり。
        - ブロックスカラーの本文（`|`、`|-`、`>`、`>-`、およびインデント指示子付きの形式）
        - 複数行のクォート付きスカラーの継続行
        - いずれかの直下キーの下にある、ネストしたマッピングやシーケンスのキー
- **FR2:** 直下キーの間では、既存の記録の意味を変えない。
    - 1 つのタスクブロック内にある直下キーの `routeback_failed_journal_line` 行の間では、引き続き最初の出現を採用する。
    - 正準値の規則を引き続き適用する。クォートなしの ASCII 10 進数字で、先頭の数字が 1〜9、末尾の空白は任意。それ以外は記録なしとする。
    - ブロックの範囲の規則を引き続き適用する。ステップレベルの行、トップレベルの行、兄弟タスクの行、`tasks:` の後ろの行、タスクキーと同じインデントの行は読まない。
    - hook の終了コードと stderr の形式は変えない。
- **FR3:** hook の docstring / コメントに、直下キーへの限定を書く。
    - モジュール docstring のうち 'The record is read only from the task's own `taskNNNN:` block, first occurrence wins' と書かれた項目、および記録読み取りの関数 docstring と正規表現のコメントを更新する。タスク自身のマッピングの直下キーだけを読むこと、ブロックスカラーの本文とネストした行は読まないことを書く。
    - `tests/test_queue_stop_guard_routeback_record.py` の `TestModuleDocstring` が固定している次の文言は、引き続き含める。
        - 'only when all three hold'
        - '`routeback_failed_journal_line` record'
        - 'Any other task whose last event is `failed` is failed'
        - "the task's own id, returned from `failed` to `pending` by route-back"
    - 次の文言は、引き続き含めない。
        - 'a recycled task id left behind by a route-back re-plan'
- **FR4:** このバグの再発を検出する回帰テストを追加する。
    - (a) `pending` かつジャーナル上 `failed` のタスクで、`notes: |` の本文に、失敗イベントの物理行番号と等しい値の `routeback_failed_journal_line:` を含み、直下キーの記録が無い場合、hook は終了コード 0 で終わる。
    - (b) `pending` かつジャーナル上 `failed` のタスクで、`notes: |` の本文（`workflow-schema.md` のキー順どおり、記録より前に置く）に一致しない値を含み、直下キーの記録が一致する場合、hook は終了コード 2 で終わり、そのタスクを名指しする。
    - テストで使うフィクスチャ生成関数は、null でない複数行の `notes` 値を出力できるようにする。

### Non-Functional Requirements

- **NFR1 - 依存:** `queue_stop_guard.py` は引き続き Python 標準ライブラリだけを import し、`workflow.yaml` を行単位で読む（YAML ライブラリは使わない）。
- **NFR2 - fail-open:** fail-open の動作を保つ。読めない・壊れた・不正な `workflow.yaml` の内容で hook がクラッシュすることはなく、ブロックを引き起こすこともない（既存の `TestFailOpen` のケースは通ったままにする）。
- **NFR3 - テスト規約:** テストコードは標準ライブラリだけを import し、他のテストモジュールを import しない（既存の queue hook テストの相互 import 禁止の規約）。hook の動作は `test/README.md` に従い、Stop hook の JSON を stdin に渡すサブプロセスとして実行する。単一の関数を直接呼ぶために、ファイルパスから hook モジュールを読み込むことは許容する（前例: `tests/test_queue_stop_guard.py` の `TestQueueStopGuardOwnershipAmbiguity`）。
- **NFR4 - バージョン:** プラグインの version は変えない。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` は触らない（プロジェクトルール `core-plugin-version-bump.md`）。
- **NFR5 - 回帰:** 既存スイート全体（`python3 -m unittest discover -s tests`）が通ったままにする。

## Acceptance Criteria

- [ ] **AC1**（FR1）: 再現フィクスチャ（task0001 が `status: pending`、`notes: |` の本文に `routeback_failed_journal_line: 3`、直下キーに `routeback_failed_journal_line: 1`）で、`task_routeback_records_from_workflow` が `{'task0001': '1'}` を返す（`'3'` ではない）。
- [ ] **AC2**（FR1, FR4）: notes の本文にジャーナルの `failed` イベントの物理行番号と一致する値があり、直下キーの記録が無い場合、hook は終了コード 0 で終わり、stderr に BLOCK が出ない。
- [ ] **AC3**（FR1, FR4）: notes の本文（記録より前）に一致しない値があり、直下キーの記録が一致する場合、hook は終了コード 2 で終わり、stderr の起動リストに task0001 が含まれる。
- [ ] **AC4**（FR1）: 一致する `routeback_failed_journal_line:` 行が、別の直下キーの下（ネストしたマッピング）または複数行のダブルクォート付き notes 値の中にあり、直下キーの記録が無い場合、hook は終了コード 0 で終わる。
- [ ] **AC5**（FR2, NFR2, NFR5）: `tests/test_queue_stop_guard.py`、`tests/test_queue_stop_guard_routeback_record.py`、`tests/test_queue_hook_status_read_pin.py` の既存テストが、アサーションの内容を変えずにすべて通り、スイート全体も通る。
- [ ] **AC6**（FR3）: hook のモジュール docstring に直下キーへの限定が書かれており、`TestModuleDocstring` が通ったままである。

## Assumptions

- **A1:** 直下キーとは、タスクマッピングの直下の子のインデントにある行を指す。このインデントは、タスクブロック内で最初の空行でもコメントでもない行から取る（空白のみで数え、既存のインデント計算と揃える）。正しい YAML では、ブロックスカラーの本文とクォート付き / プレーンの継続行は、それを持つキーより必ず深くインデントされるので、インデントだけで区別できる。空の `notes: |` の後に直下の子のインデントで続く行は、YAML 上は兄弟キーであり、兄弟キーとして読む。
- **A2:** 範囲は記録の読み取りだけとする。タスクごとの `status:` の読み取り（`task_statuses_from_workflow`、`TASK_STATUS_RE`）は、この機能で変える必要はない。既存テストでの観測できる動作は保つ。
- **A3:** 回帰テストは `tests/test_queue_stop_guard_routeback_record.py` に追加する（このファイルのフィクスチャ生成関数は、現状つねに `notes: null` を書く）。
- **A4:** `em-workflow/references/workflow-schema.md` と `implement-phase.md` は変えない。`workflow-schema.md` はすでに記録を「an optional key of a task's own `tasks.{T}` mapping」と定義しており、これは直下キーの読み方である。
- **A5:** 直下キーの間での最初の出現の採用と正準値の規則は、既存テスト（`test_first_occurrence_in_the_block_wins`、`TestRecordValueParsing`）が固定しているとおり保つ。
- **A6:** プラグインの version は変えない（プロジェクトルール）。

## Implementation Approach

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/queue_stop_guard.py` の `task_routeback_records_from_workflow`: 変更対象（FR1, FR2, FR3）。
- `em-workflow/hooks/queue_stop_guard.py` の `task_statuses_from_workflow` / `TASK_STATUS_RE`: 変更を求めない（A2）。

**External Dependencies:**
- なし（Python 標準ライブラリのみ。NFR1, NFR3）。

### File Structure

```
em-workflow/hooks/queue_stop_guard.py               # FR1, FR2, FR3
tests/test_queue_stop_guard_routeback_record.py     # FR4（A3）
```

変更しないファイル:

- `em-workflow/references/workflow-schema.md`、`implement-phase.md`（A4）
- `em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`（NFR4）

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を宣言する。上に挙げた機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` エントリから導出する（`references/phases/create-plan-phase.md`）。

上の機能固有のパスに加え、ワークフローが生成する次の 2 エントリを既定で宣言する。

- `feature-docs/routeback-record-direct-key/**`
- `test-docs/routeback-record-direct-key/**`

`feature-docs/routeback-record-direct-key/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する設計成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを参照するだけで、規則は再掲しない。

`test-docs/routeback-record-direct-key/**` はタスクごとのテスト記録 `test-docs/routeback-record-direct-key/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを参照するだけで、規則は再掲しない。

この 2 つの既定エントリは、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことをもって外したとはみなさない。外すことは、意図的かつ明示的な絞り込みである。

この宣言は上位集合の主張である。検証時に観測される実際の変更集合は、宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生まない機能では `test-docs/routeback-record-direct-key/` ディレクトリは生成されないが、その場合も `test-docs/routeback-record-direct-key/**` の宣言は正しい。宣言したパスが実在しないことは違反ではない。

## Test Scenarios

### Unit Tests

- [ ] **TS1**（AC1 / FR1）: ファイルパスから hook モジュールを読み込み、再現フィクスチャで `task_routeback_records_from_workflow` が `{'task0001': '1'}` を返すことを確かめる。

### Integration Tests

hook をサブプロセスとして実行する。

- [ ] **TS2**（AC2 / FR1, FR4）: ジャーナルの 1 行目が task0001 の `failed`。task0001 は `pending` で、`notes: |` の本文に `routeback_failed_journal_line: 1` の行があり、直下キーの記録は無い。終了コード 0。`|-`、`>`、`>-` の指示子でも同様に確かめる。
- [ ] **TS3**（AC3 / FR1, FR4）: ジャーナルの 1 行目が task0001 の `failed`。task0001 は `pending` で、`notes: |` の本文の `routeback_failed_journal_line: 3` の行が、直下キーの `routeback_failed_journal_line: 1` より前にある。終了コード 2 で、起動リストに task0001 が含まれる。
- [ ] **TS4**（AC2 / FR1, FR4）: 不一致の変形。notes の本文の一致する値（1）が、異なる値（2）の直下キーの記録より前にある。終了コード 0（直下キーの記録が優先される）。
- [ ] **TS5**（AC4 / FR1）: 一致する記録の行が、別の直下キーの下に 1 段深くネストしている（例: `    extra:` / `      routeback_failed_journal_line: 1`）。直下キーの記録は無い。終了コード 0。
- [ ] **TS6**（AC4 / FR1）: 複数行のダブルクォート付き notes 値の継続行が `routeback_failed_journal_line: 1` になっている。直下キーの記録は無い。終了コード 0。

### Regression Tests

- [ ] **TS7**（AC5, AC6 / FR2, FR3, NFR2, NFR5）: `python3 -m unittest tests.test_queue_stop_guard tests.test_queue_stop_guard_routeback_record tests.test_queue_hook_status_read_pin` と `python3 -m unittest discover -s tests` を実行し、すべて通る。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] ブロックスカラーの各指示子（`|`、`|-`、`>`、`>-`、インデント指示子付きの形式）の本文にある記録の行は読まない（FR1。TS2）。
- [ ] 複数行のクォート付きスカラーの継続行にある記録の行は読まない（FR1。TS6）。
- [ ] 直下キーの下にネストしたマッピングやシーケンスのキーとしての記録の行は読まない（FR1。TS5）。
- [ ] 空の `notes: |` の後に直下の子のインデントで続く記録の行は、兄弟キーとして読む（A1）。

## Success Criteria

- [ ] FR1〜FR4 が実装され、テストされている
- [ ] NFR1〜NFR5 を満たしている
- [ ] AC1〜AC6 を満たしている
- [ ] TS1〜TS7 がすべて通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（`status: tbd` の要件は無い）

## References

- `em-workflow/hooks/queue_stop_guard.py`
- `em-workflow/references/workflow-schema.md`
- `tests/test_queue_stop_guard_routeback_record.py`
- `tests/test_queue_stop_guard.py`
- `tests/test_queue_hook_status_read_pin.py`
