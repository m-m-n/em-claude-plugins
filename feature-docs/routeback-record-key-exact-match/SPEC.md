# Feature: routeback-record-key-exact-match

## Overview

`em-workflow/hooks/queue_stop_guard.py` の route-back 記録の読み取りで、キー名が `routeback_failed_journal_line` と一致する行だけを記録キーの行として扱う。
コロンを含む別キーの行を記録と取り違えて、後ろにある本来の記録を読み落とさないようにする。

## Objectives

- queue_stop_guard の route-back 記録の読み取りで、キー名が `routeback_failed_journal_line` と一致する行だけを記録キーの行として扱う。コロンを含む別キーの行を記録と取り違えて、後ろにある本来の記録を読み落とさないようにする。

## Acceptance Criteria

- [ ] **AC-1** (FR1, FR2): タスクブロックの直下に `routeback_failed_journal_line:x: 1` を置き、その後ろに `routeback_failed_journal_line: 1` を置いた workflow.yaml に対して、`task_routeback_records_from_workflow` が `{"task0001": "1"}` を返す。
- [ ] **AC-2** (FR1, FR2): AC-1 と同じ workflow.yaml で task0001 が `pending`、ジャーナル 1 行目が task0001 の `failed` のとき、Stop フックは終了コード 2 を返し、stderr の `launch=` に task0001 を含む。
- [ ] **AC-3** (FR1, FR2): 直下に `routeback_failed_journal_line:1` を置き、その後ろに `routeback_failed_journal_line: 1` を置いた場合、`task_routeback_records_from_workflow` は `{"task0001": "1"}` を返す。
- [ ] **AC-4** (FR1): 既存の挙動を保つ。
    - (a) `routeback_failed_journal_line:<TAB>1` は記録 "1" として読まれる。
    - (b) 値の無い `routeback_failed_journal_line:` の後ろに `routeback_failed_journal_line: 1` があっても、先頭の出現が優先されるため記録なしのまま。
    - (c) `routeback_failed_journal_line:x: 1` だけがある場合は記録なし。
- [ ] **AC-5** (FR3): AC-1〜AC-3 で追加したテストは、修正前のコードで失敗する。
- [ ] **AC-6** (NFR1, NFR2): `python3 -m unittest discover -s tests` が全て通る。

## Technical Requirements

### Functional Requirements

- **FR1:** 記録キーの行はキー名の完全一致で判定する
    - `em-workflow/hooks/queue_stop_guard.py` の `ROUTEBACK_RECORD_LINE_RE` は、行頭の空白に続いて `routeback_failed_journal_line:` があり、そのコロンの直後がスペース・タブ・行末のいずれかである行だけに一致する。
    - 規則は同じファイルの `_find_key_colon` と `TASK_STATUS_KEY_RE` と同じにする。
- **FR2:** コロンの直後に空白以外が続く行は記録キーの出現に数えない
    - `task_routeback_records_from_workflow` は、タスク直下の行のうち `routeback_failed_journal_line:x: 1` や `routeback_failed_journal_line:1` のようにコロンの直後が空白でも行末でもない行を、記録キーの最初の出現として扱わない。
    - その後ろにある記録キーの行（例: `routeback_failed_journal_line: 1`）を最初の出現として読む。
- **FR3:** 再発を検出するテストを追加する
    - `tests/test_queue_stop_guard_routeback_record.py` に、FR1 / FR2 の挙動を確認するテストを追加する。
    - 読み取り関数を直接呼ぶテストと、フックをサブプロセスで実行するテストの両方を置く。

### Non-Functional Requirements

- **NFR1:** 標準ライブラリだけを使う
    - フックとテストは Python 標準ライブラリだけを import する。
- **NFR2:** 既存テストが全て通る
    - 変更後に `python3 -m unittest discover -s tests` の全テストが通る。

## Assumptions

- **A-1:** 変更は `ROUTEBACK_RECORD_LINE_RE` のコロン直後の規則に限る。値の判定（`ROUTEBACK_RECORD_VALUE_RE`）、直下キーのインデント判定、先頭の出現を優先する規則、多行の引用値・フロー値の本文行を読まない規則は変えない。
- **A-2:** `routeback_failed_journal_line:1` 単独の場合に記録なしとする既存テスト `test_value_without_a_space_after_the_colon_is_no_record` は、修正後も通る（記録キーの行ではなくなり、結果は同じく記録なし）。変わるのは、この形の行が後ろの本来の記録を隠さなくなる点だけ。
- **A-3:** `ROUTEBACK_RECORD_KEY` 直上のコメントと `task_routeback_records_from_workflow` の docstring を編集する場合も、既存の文言テスト（`TestDirectKeyWording`: "direct keys" / "block scalar bodies" / "nested"）が通る状態を保つ。
- **A-4:** workflow.yaml はテキストモード（改行コードの自動変換あり）で読まれるため、CRLF の行でもコロン直後の行末判定は LF と同じに働く。CRLF 用の特別な扱いは追加しない。

## Implementation Approach

### File Structure

```
em-workflow/
└── hooks/
    └── queue_stop_guard.py                      # ROUTEBACK_RECORD_LINE_RE の修正（FR1, FR2）
tests/
└── test_queue_stop_guard_routeback_record.py    # テストの追加（FR3）
```

### Design Step

- 設計工程: skipped
    - 理由: 画面を持たない Stop フックの正規表現の修正で、設計工程の対象が無い

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/routeback-record-key-exact-match/**`
- `test-docs/routeback-record-key-exact-match/**`

`feature-docs/routeback-record-key-exact-match/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/routeback-record-key-exact-match/**` covers `test-docs/routeback-record-key-exact-match/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/routeback-record-key-exact-match/` directory at all; the declared
`test-docs/routeback-record-key-exact-match/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (AC-1, AC-5 / FR1, FR2, FR3): コロンを含む別キーの後ろの本来の記録を読む（関数を直接呼ぶ） - `tests/test_queue_stop_guard_routeback_record.py`
- [ ] **TS-3** (AC-3, AC-5 / FR1, FR2, FR3): コロン直後に空白の無い行の後ろの本来の記録を読む - `tests/test_queue_stop_guard_routeback_record.py`
- [ ] **TS-4** (AC-4 / FR1): タブ区切り・値の無いキー・別キー単独の既存挙動 - `tests/test_queue_stop_guard_routeback_record.py`

### Integration Tests

- [ ] **TS-2** (AC-2, AC-5 / FR1, FR2, FR3): コロンを含む別キーの後ろの本来の記録でフックがブロックする（サブプロセス） - `tests/test_queue_stop_guard_routeback_record.py`
- [ ] **TS-5** (AC-6 / NFR1, NFR2): 全テスト実行 - `python3 -m unittest discover -s tests`

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] FR1〜FR3 が実装され、テストされている
- [ ] TS-1〜TS-5 が全て通る
- [ ] AC-1〜AC-6 を満たす

## Open Questions

なし

## References

- `em-workflow/hooks/queue_stop_guard.py`
- `tests/test_queue_stop_guard_routeback_record.py`
