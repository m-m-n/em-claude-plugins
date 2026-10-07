# Feature: task-status-key-exact-match

## Overview

`em-workflow/hooks/queue_stop_guard.py` の `task_statuses_from_workflow` が、タスクブロック直下でキー名が `status` と一致する行だけを status の決定行として扱うようにする。feature task-status-direct-key で入った後退（`status:detail` のような別キーがあると直下の `status` が読まれなくなる）を解消し、再発をテストで検出できるようにする。

## Objectives

- `queue_stop_guard` の `task_statuses_from_workflow` が、タスクブロック直下でキー名が `status` と一致する行だけを status の決定行として扱うようにする
- feature task-status-direct-key で入った後退（`status:detail` のような別キーがあると直下の `status` が読まれなくなる）を解消し、再発をテストで検出できるようにする

## Acceptance Criteria

- [ ] **AC-1** (FR1): タスクブロックの直下が `status:detail: ignored`、`status: pending` の順のとき、`task_statuses_from_workflow` が `{'task0001': 'pending'}` を返す。
- [ ] **AC-2** (FR1): AC-1 と同じブロックに `routeback_failed_journal_line: 1` を加え、journal の 1 行目を task0001 の failed イベントにすると、フックが exit 2 で終わり、stderr に `launch=task0001` を含む。
- [ ] **AC-3** (FR2): 直下の値なし `    status:` が最初の status キー行のとき、後ろに `    status: pending` があってもタスクは結果から外れる。既存テスト `test_unextractable_first_direct_value_omits_the_task` の bare-colon ケースが引き続き通る。
- [ ] **AC-4** (FR3): FR3 のテストは base revision のフックで失敗し、修正後のフックで成功する。
- [ ] **AC-5** (FR1, FR2, NFR2, NFR3): `python3 -m unittest discover -s tests` がすべて成功する。
- [ ] **AC-6** (FR1, FR3): 直下の status 系の行が `    status:pending`（空白なし）だけのとき、`task_statuses_from_workflow` はそのタスクを結果から外す。
- [ ] **AC-7** (FR1, FR3): 直下が `    status:failed`（空白なし）、`    status: pending` の順のとき、`task_statuses_from_workflow` は `{'task0001': 'pending'}` を返す。

## Technical Requirements

### Functional Requirements

- **FR1:** status の決定行はキー名が status と一致する行だけにする。`em-workflow/hooks/queue_stop_guard.py` の `task_statuses_from_workflow` は、タスクブロックの直下インデントにある行のうち、`status:` の直後がスペース、タブ、行末のいずれかである行だけを決定行として扱う（`TASK_STATUS_KEY_RE` を `^\s+status:(?=[ \t]|$)` にする。`_find_key_colon` と同じ規則）。`status:detail: ignored` や `status:pending` のように、コロンの直後がスペースでもタブでも行末でもない行は決定行にせず、その後ろの行を読み続ける。
- **FR2:** 値なしの `status:` が決定行になる既存挙動を保つ。直下の `    status:`（値なしで行末まで続く行。ファイル末尾に改行がない場合も含む。workflow.yaml はテキストモードで読むので CRLF は LF として扱われる）は、これまでどおり決定行として扱う。値を取り出せないので、そのタスクは結果から外し、後ろの行は読まない。次の規則は変えない: 最初に現れた直下の status キー行で決めること、値の取り出し（`TASK_STATUS_RE`）、直下インデントの決め方、ブロックスカラーの本文・ネストしたマッピング・コメント行を読まないこと。
- **FR3:** 再発を検出するテスト。`tests/` 配下の unittest に、次の 3 つを確かめるテストを置く。(1) 直下に `status:detail: ignored`、その後ろに `status: pending` を置くと、`task_statuses_from_workflow` が `{'task0001': 'pending'}` を返す。(2) 直下の status 系の行が `status:pending`（空白なし）だけなら、タスクが結果から外れる。(3) 直下に `status:failed`（空白なし）、その後ろに `status: pending` を置くと pending を返す。どのテストも修正前のフック（base revision）では失敗し、修正後は成功する。

### Non-Functional Requirements

- **NFR1 - 依存:** フックは Python 標準ライブラリだけを使う。
- **NFR2 - 堅牢性:** どんな入力でも `task_statuses_from_workflow` は例外を出さない。フックは、失敗したときに exit 0 で終わる挙動（fail-open）を保つ。
- **NFR3 - 互換性:** `task_statuses_from_workflow`、`TASK_STATUS_RE`、`TASKS_SECTION_RE` の名前を変えない（`tests/test_queue_stop_guard_task_status_direct_key.py` の `TestContractIdentifiers` が参照している）。
- **NFR4 - テスト規約:** テストは `test/README.md` の規約に従う。unittest を使い、`tests/test_*.py` に置き、フィクスチャは一時ディレクトリに作り、フックは Stop フックの JSON を標準入力に渡してサブプロセスとして起動する。

## Assumptions

- **A-1:** 「キー名が status と一致する」とは、`status:` の直後がスペース、タブ、行末のいずれかであることを指す（`^\s+status:(?=[ \t]|$)`。`_find_key_colon` と同じ規則）。`    status:pending` はキー行ではない。回答 requirement.status-key-nospace-colon（strict_yaml_separator）で確定した。
- **A-2:** 修正対象は `task_statuses_from_workflow` の status キー判定（`TASK_STATUS_KEY_RE`）だけとする。`ROUTEBACK_RECORD_LINE_RE`、`STEP_STATUS_RE`、コロンの前に空白がある `status :`、引用符付きのキー `"status":` の扱いは変えない。
- **A-3:** 値なしの `status:` が決定行になり、そのタスクを結果から外す挙動は、既存テストで固定された事実として保つ。該当するのは `tests/test_queue_stop_guard_task_status_direct_key.py` の bare-colon ケースと、`tests/test_queue_stop_guard.py` の undeterminable ケース。

## Implementation Approach

### 変更箇所

- `em-workflow/hooks/queue_stop_guard.py`: `TASK_STATUS_KEY_RE` を `^\s+status:(?=[ \t]|$)` にする（FR1）。FR2 に挙げた規則は変えない。
- `tests/` 配下: FR3 のテストを `tests/test_*.py` に置く（NFR4）。

### Dependencies

**Internal Dependencies:**
- `tests/test_queue_stop_guard_task_status_direct_key.py`: `TestContractIdentifiers` が `task_statuses_from_workflow`、`TASK_STATUS_RE`、`TASKS_SECTION_RE` を参照する（NFR3）。bare-colon ケースを含む（A-3）。
- `tests/test_queue_stop_guard.py`: undeterminable ケースを含む（A-3）。

**External Dependencies:**
- なし（Python 標準ライブラリのみ。NFR1）

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を示す。この feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、feature 固有のパスに加えて、workflow が生成する次の 2 つを既定で宣言する。

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する成果物を含む。これらは各フェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを引用するだけで、規則は再掲しない。

`test-docs/{feature}/**` はタスクごとのテスト記録 `test-docs/{feature}/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを引用するだけで、規則は再掲しない。

この 2 つの既定の宣言は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載がないことを外したとはみなさない。外すのは意図的で明示的な絞り込みに限る。

この宣言は上位集合の主張である。検証時に観測される実際の変更集合は、宣言された集合に含まれていればよく、一致する必要はない。implement タスクを生まない feature は `test-docs/{feature}/` を生成しないが、その場合も `test-docs/{feature}/**` の宣言は正しい。宣言したパスが実際に作られないことは違反ではない。

## Test Scenarios

テストコマンド: `python3 -m unittest discover -s tests`

### Unit Tests

- [ ] **TS-1** (AC-1, AC-4): リーダーを直接呼ぶ。直下が [title, `status:detail: ignored`, `status: pending`] のとき `{'task0001': 'pending'}` を返す。
- [ ] **TS-3** (AC-1): 値なしでコロンで終わる別キー `status:detail:` が先にあり、後ろに `status: failed` があるとき、failed を返す。
- [ ] **TS-4** (AC-6, AC-4): 直下の status 系の行が `    status:pending` だけのとき、タスクは結果から外れる（戻り値は `{}`）。
- [ ] **TS-5** (FR1): コロンの直後がタブの `    status:\tpending` は決定行になり、pending を返す。
- [ ] **TS-6** (AC-3): 値なしの `    status:` が先にある既存ケースで、タスクが結果から外れたままになる。
- [ ] **TS-7** (AC-7, AC-4): 直下が `    status:failed`、`    status: pending` の順のとき、pending を返す。

### Integration Tests

- [ ] **TS-2** (AC-2): フックをサブプロセスで実行する。TS-1 のブロックに routeback の記録 1 を加え、journal の 1 行目を task0001 の failed にすると、exit 2 で task0001 を名指しする。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] Existing E2E tests pass without regression

## Error Handling

- `task_statuses_from_workflow` はどんな入力でも例外を出さない。フックは失敗したときに exit 0 で終わる（fail-open）（NFR2）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 から AC-7 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし
