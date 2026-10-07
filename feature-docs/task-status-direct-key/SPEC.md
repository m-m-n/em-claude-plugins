# Feature: task-status-direct-key

## Overview

`em-workflow/hooks/queue_stop_guard.py` は、タスクの status を `tasks.{T}` 直下のキーだけから読む。ブロックスカラーの本文や入れ子のマッピングの中の行（信頼できない文字列が入る `tasks.{T}.notes` を含む）は、status の読み取り元にならない。

## Objectives

- queue_stop_guard.py は、タスクの status を `tasks.{T}` 直下のキーだけから読む。ブロックスカラーの本文や入れ子のマッピングの中の行（信頼できない `tasks.{T}.notes` の文字列を含む）は、status の読み取り元にならない。

## Technical Requirements

### Functional Requirements

- **FR1: 直下キーからの status 読み取り** — `task_statuses_from_workflow` は、各タスクの status を、タスクブロックの直下インデントにある最初の `status:` キーから取る。直下インデントは、タスクブロック内で最初に現れる、空行でもコメント行でもない行のインデントとする。
- **FR2: ブロックスカラー本文の無視** — 直下キーに付いたブロックスカラー（`|` または `>`。チョンピング指示子・インデント指示子の有無を問わない）の本文行は、status として読まない。直下の `status:` キーがブロックスカラーより前にある場合、後ろにある場合、存在しない場合のいずれでも同じとする。
- **FR3: 入れ子マッピング行の無視** — 直下キーの下に入れ子になったマッピングの中の `status:` 行は、そのタスクの status として読まない。
- **FR4: 既存の分類の維持** — 直下の `status:` キーが無いタスク、または直下の `status:` の値を取り出せないタスクは、返すマッピングに含めない。直下の `status:` キーが複数あるときは最初のものを採る。`evaluate_feature` の 3 条件による除外は変えない。

### Non-Functional Requirements

- **NFR1:** フックは Python 標準ライブラリだけを import し、YAML ライブラリを使わない。
- **NFR2:** フックは fail-open を保つ。読めない、または壊れた workflow.yaml / journal の入力では、トレースバックを出さずに終了コード 0 で終わる。
- **NFR3:** 識別子 `task_statuses_from_workflow`、`TASK_STATUS_RE`、`TASKS_SECTION_RE` の名前を変えない。
- **NFR4:** queue_stop_guard.py のモジュール docstring は、`tests/test_queue_stop_guard_routeback_record.py` の `TestModuleDocstring` が固定している文言を保つ。
- **NFR5:** `task_routeback_records_from_workflow` と `iter_task_block_lines` は現在の挙動を保つ。

## Acceptance Criteria

- [ ] **AC1** (FR1, FR2): フィクスチャ — タスクブロックに `routeback_failed_journal_line: 1` と、本文に `status: pending` を含む `notes: |` があり、直下の `status:` キーが無い。そのタスクの journal の 1 行目は、そのタスクの `failed` イベントである。Stop フックは終了コード 0 で終わり、stderr に BLOCK が出ない。
- [ ] **AC2** (FR1, FR2): AC1 と同じフィクスチャで、notes のブロックスカラーの後ろに直下の `status: failed` を置くと、Stop フックは終了コード 0 で終わる。`task_statuses_from_workflow` はそのタスクについて `failed` を返す。
- [ ] **AC3** (FR2): notes のブロックスカラーが `>`、`|-`、`|+`、`|2` の指示子を使う場合も AC1 が成り立つ。
- [ ] **AC4** (FR3): 直下の `status:` キーが無く、直下キーの下の入れ子マッピングに `status: pending` を含むタスクブロックは、`task_statuses_from_workflow` の結果に含まれない。AC1 の journal と記録のもとで、Stop フックは終了コード 0 で終わる。
- [ ] **AC5** (FR1, FR4): notes のブロックスカラーの前または後ろに直下の `status: pending` があり、AC1 の記録と journal があるとき、Stop フックは終了コード 2 で終わり、そのタスクを名指しする（除外は引き続き適用される）。
- [ ] **AC6** (FR4, NFR1, NFR2, NFR3, NFR4, NFR5): `tests/test_queue_stop_guard.py`、`tests/test_queue_stop_guard_routeback_record.py`、`tests/test_queue_hook_status_read_pin.py` の既存テストが、変更なしで `python3 -m unittest discover -s tests` のもとで通る。
- [ ] **AC7** (FR1, FR2, FR3): AC1〜AC4 の新しいテストは `tests/` 配下に `test_*.py` として置く。AC1、AC2、AC4 は main の queue_stop_guard.py に対して失敗する。

## Implementation Approach

### Architecture

- 直下キーかどうかの判定は `task_statuses_from_workflow` の中で行う（A3）。
- 直下インデントは、タスクブロック内で最初に現れる、空行でもコメント行でもない行のインデントとする。そのインデントにちょうど一致する行だけを status キーの候補とする（A1）。
- 直下の status キーが複数あるときは最初のものを採る。status が無い、または決められないタスクはマッピングに含めない（A5）。

### Dependencies

**Internal Dependencies:**
- `iter_task_block_lines`: `task_statuses_from_workflow` が読むタスクブロックの行を返す。本 feature では変更しない（NFR5、A3）。
- `task_routeback_records_from_workflow`: 本 feature では変更しない（NFR5、A3）。
- `evaluate_feature`: `task_statuses_from_workflow` の結果を使う。3 条件による除外は変えない（FR4）。

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）。

### File Structure

```
em-workflow/hooks/
└── queue_stop_guard.py      # task_statuses_from_workflow の変更
tests/
└── test_*.py                # AC1〜AC4 の新しいテスト
```

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を述べる。上に挙げた feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上の feature 固有のパスに加えて、ワークフローが生成する次の 2 項目を既定で宣言する。

- `feature-docs/task-status-direct-key/**`
- `test-docs/task-status-direct-key/**`

`feature-docs/task-status-direct-key/**` は、`REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する成果物を含む。これらは各フェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを参照するだけで、規則は再掲しない。

`test-docs/task-status-direct-key/**` は、タスクごとのテスト記録 `test-docs/task-status-direct-key/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを参照するだけで、規則は再掲しない。

この 2 つの既定項目は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことをもって外したとはみなさない。外すのは意図的で明示的な絞り込みに限る。

この宣言は上位集合としての主張である。検証時に観測した実際の変更集合は、宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生まない feature では `test-docs/task-status-direct-key/` ディレクトリ自体が作られないが、その場合も `test-docs/task-status-direct-key/**` の宣言は正しい。宣言したパスが実在しなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] **TS2** (AC2): TS1 のフィクスチャで、notes の後ろに直下の `status: failed` を置く。終了コード 0 を期待する。`task_statuses_from_workflow` を直接呼ぶと `failed` を返す。
- [ ] **TS4** (AC4): 直下の status キーが無く、入れ子マッピング（例: `meta:` / `      status: pending`）がある。`task_statuses_from_workflow` の結果に含まれないこと、および終了コード 0 を期待する。
- [ ] **TS6** (AC5, FR1): タスクブロック内で最初のキーより前に置いたコメント行は、直下インデントをずらさない。直下の `status: pending` は引き続き読まれる。

### Integration Tests

- [ ] **TS1** (AC1): サブプロセスでフックを実行する。直下の status キーが無く、`notes: |` の本文に `    status: pending`（直下インデントより深い）を含み、対応する記録があり、journal の 1 行目が `failed`。終了コード 0 を期待する。
- [ ] **TS3** (AC3): TS1 を `>`、`|-`、`|+`、`|2` の指示子で subTest によりパラメータ化する。
- [ ] **TS5** (AC5): notes の前に直下の `status: pending` を置く場合と、notes の後ろに置く場合を別々に試す。notes の本文には `status: failed` を含める。終了コード 2 で、`launch=` にそのタスクが出ることを期待する。
- [ ] **TS7** (AC6): テストスイート全体を `python3 -m unittest discover -s tests` で実行する。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Assumptions

- **A1:** タスクブロックの直下インデントは、そのブロック内で最初に現れる、空行でもコメント行でもない行のインデントとする（PR #113 と同じ規則）。そのインデントにちょうど一致する行だけを status キーの候補とする。
- **A2:** 複数行にわたるシングルクォート・ダブルクォートのスカラーの継続行は、本 feature の範囲外とする。PR #114 がマージされるまでは、直下インデントにあるそのような行が status として読まれうる。
- **A3:** 直下キーかどうかの判定は `task_statuses_from_workflow` の中に実装する。`iter_task_block_lines` と `task_routeback_records_from_workflow` は変更しない（PR #113 / #114 が扱う）。
- **A4:** `task_statuses_from_workflow`、`TASK_STATUS_RE`、`TASKS_SECTION_RE` の名前を変えない。
- **A5:** 直下の status キーの中では最初に現れたものを採る。status が無い、または決められないタスクはマッピングに含めない。

## Out of Scope

- 複数行のクォートスカラーの継続行（A2）。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし
