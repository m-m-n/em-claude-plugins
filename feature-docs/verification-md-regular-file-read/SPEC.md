# Feature: verification-md-regular-file-read

## Overview

`em-workflow/scripts/validate-worker-output.py` の `_load_scenario_ids` が VERIFICATION.md を読むとき、通常ファイルでないもの（FIFO、デバイスファイル、ディレクトリ、シンボリックリンク）は開いて読まずに `("unreadable", 理由)` を返す。通常ファイルはバイト上限付きで読み、UTF-8 でデコードする。rework-planner 出力の検証は、止まらずに拒否（fail-closed）で終わる。

## Objectives

- VERIFICATION.md が通常ファイルでなくても、validate-worker-output.py による rework-planner 出力の検証が止まらずに拒否（fail-closed）で終わり、無人実行が止まらない
- VERIFICATION.md の読み込みにバイト上限を設け、巨大な入力でメモリを使い切らない

## Acceptance Criteria

- [ ] AC-1: feature-dir の VERIFICATION.md が FIFO のとき、文書のみの回の rework-planner 出力の CLI 検証がタイムアウトせずに exit 1 で終わり、"cannot be read as text" とそのパスを含む rework-index エラーが出る（FR1, FR3）
- [ ] AC-2: feature-dir の VERIFICATION.md が /dev/zero へのシンボリックリンクのとき、同じく exit 1 と rework-index エラーで終わる（FR1, FR3）
- [ ] AC-3: baseline-dir 側の VERIFICATION.md が FIFO または /dev/zero へのシンボリックリンクで、その集合が必要な判定があるとき、同じく exit 1 と rework-index エラーで終わる（FR1, FR3）
- [ ] AC-4: バイト上限を超える通常ファイルの VERIFICATION.md は unreadable になり、全体を読み込まない（FR2）
- [ ] AC-5: 既存の `TestRenameCoverageDiff` / `TestRenameDiffFixtures`（ディレクトリ、UTF-8 でないバイト、ファイル無し、正常な rename を含む）がすべて通る（FR3）
- [ ] AC-6: AC-1〜AC-4 を確かめるテストが `tests/test_rework_docs_only_validator_rules.py` にあり、`python3 -m unittest tests.test_rework_docs_only_validator_rules` が通る（FR4, NFR1, NFR2）

## Technical Requirements

### Functional Requirements
- **FR1:** 通常ファイルでない VERIFICATION.md は開いて読まない。`_load_scenario_ids` は、対象パスが通常ファイルでないとき（FIFO、デバイスファイル、ディレクトリ、シンボリックリンク。/dev/zero へのシンボリックリンクを含む）、ブロックする読み込みを行わずに `("unreadable", 理由)` を返す。開くときはシンボリックリンクを辿らず（`O_NOFOLLOW`）、ブロックせず（`O_NONBLOCK`）に開き、開いた記述子が通常ファイルであることを `fstat` + `S_ISREG` で確かめてから読む。
- **FR2:** バイト上限付きで読んでから UTF-8 でデコードする。`_load_scenario_ids` は VERIFICATION.md をバイト上限付きで読み、上限を超えるファイルは `("unreadable", 理由)` とする。上限以内なら UTF-8 でデコードし、デコードできなければ `("unreadable", 理由)` とする。
- **FR3:** 既存の戻り値と拒否の振る舞いを保つ。`_load_scenario_ids` は `(state, value)` の形と例外を投げない性質を保つ。ファイルが無い場合は `("absent", None)`、通常ファイルとして読めた場合は `("ok", extract_verification_scenario_ids(text))`。`_VerificationDiff` が unreadable を記録し、必要になったものだけを rework-index エラー（メッセージに "cannot be read as text" とファイルのパスを含む）1 件として報告し、CLI が exit 1 と JSON のエラー詳細で終わる既存の振る舞いは変えない。
- **FR4:** 再発を検出するテスト。`tests/test_rework_docs_only_validator_rules.py` に、feature-dir 側と baseline-dir 側の VERIFICATION.md を FIFO（`mkfifo`）および /dev/zero へのシンボリックリンクに置き換えたケースを足す。CLI の検証はサブプロセスでタイムアウト付きで実行し、タイムアウトせずに exit 1 と "cannot be read as text" のエラーで終わることを確かめる。上限を超える通常ファイルが unreadable になることも確かめる。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみ:** validate-worker-output.py とテストは標準ライブラリだけを使う（既存の `TestStandardLibraryOnly` が検査する）。
- **NFR2 - テストが後退時に負荷をかけ続けない:** 修正が後退した状態でも、FIFO / /dev/zero のテストはサブプロセスのタイムアウトで短時間に打ち切られ、CPU やメモリを使い続けない。
- **NFR3 - version を触らない:** em-workflow の `plugin.json` と `marketplace.json` の version は変更しない（patch は main への push 時に Actions が上げる）。

## Implementation Approach

### Assumptions

- A1: シンボリックリンクは参照先が通常ファイルでも unreadable とする（`O_NOFOLLOW` で開く）。参照先が存在しないシンボリックリンクも absent ではなく unreadable になる。
- A2: バイト上限は、同じファイルで文書読み込みにすでに使っている `MAX_PLAN_READ_BYTES`（1,000,000）を使う。
- A3: unreadable の理由文字列（エラーメッセージの括弧内）は変わってよい。既存テストが固定しているのは "cannot be read as text" という文言とパスだけで、理由文字列は固定していない。
- A4: FIFO のテストは `os.mkfifo` が使える POSIX 環境で、/dev/zero のテストは /dev/zero がある環境で実行する。それ以外の環境ではスキップする。

### Architecture

変更は `validate-worker-output.py` の `_load_scenario_ids` 1 関数に収まる。呼び出し側の `_VerificationDiff` と CLI の振る舞いは変えない（FR3）。

**Component Diagram:**
```
CLI (validate-worker-output.py)
  └─ _VerificationDiff
       └─ _load_scenario_ids(path)
            ├─ ファイル無し                         → ("absent", None)
            ├─ 通常ファイルでない / 上限超過 / UTF-8 でない → ("unreadable", 理由)
            └─ 通常ファイルとして読めた             → ("ok", extract_verification_scenario_ids(text))
```

### Data Flow

```
_load_scenario_ids(path)
  → O_NOFOLLOW | O_NONBLOCK で開く
  → fstat + S_ISREG で通常ファイルか確かめる
  → バイト上限（MAX_PLAN_READ_BYTES）付きで読む
  → UTF-8 でデコードする
  → extract_verification_scenario_ids(text)
_VerificationDiff
  → unreadable を記録し、必要になったものだけを rework-index エラー 1 件として報告する
CLI
  → exit 1 と JSON のエラー詳細で終わる
```

### Dependencies

**Internal Dependencies:**
- `_VerificationDiff`: `_load_scenario_ids` の `(state, value)` を受け取る
- `extract_verification_scenario_ids`: 読めたテキストからシナリオ ID を取り出す
- `MAX_PLAN_READ_BYTES`: バイト上限（A2）

**External Dependencies:**
- なし（標準ライブラリのみ。NFR1）

### File Structure

```
em-workflow/
└── scripts/
    └── validate-worker-output.py              # _load_scenario_ids を変更
tests/
└── test_rework_docs_only_validator_rules.py   # FIFO / /dev/zero / 上限超過のケースを追加
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/verification-md-regular-file-read/**`
- `test-docs/verification-md-regular-file-read/**`

`feature-docs/verification-md-regular-file-read/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/verification-md-regular-file-read/**` covers `test-docs/verification-md-regular-file-read/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/verification-md-regular-file-read/` directory at all; the declared
`test-docs/verification-md-regular-file-read/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Integration Tests
- [ ] TS-1: feature-dir の VERIFICATION.md を FIFO にして CLI で rework-planner 出力を検証する（サブプロセス、タイムアウト付き） - タイムアウトせず exit 1、"cannot be read as text" とパスを含む rework-index エラー 1 件
- [ ] TS-2: feature-dir の VERIFICATION.md を /dev/zero へのシンボリックリンクにして CLI で検証する（サブプロセス、タイムアウト付き） - タイムアウトせず exit 1、rework-index エラー 1 件
- [ ] TS-3: baseline-dir の VERIFICATION.md を FIFO / /dev/zero へのシンボリックリンクにし、baseline 集合が必要な rename を宣言して CLI で検証する - タイムアウトせず exit 1、baseline 側のパスを含む rework-index エラー 1 件

### Unit Tests
- [ ] TS-4: `_load_scenario_ids` に FIFO、/dev/zero へのシンボリックリンク、通常ファイルへのシンボリックリンクを渡す - いずれもブロックせず `("unreadable", 理由)` を返す
- [ ] TS-5: `_load_scenario_ids` にバイト上限を超える通常ファイルを渡す - `("unreadable", 理由)` を返す
- [ ] TS-6: 既存の AC-7 系テスト（ディレクトリ、UTF-8 でないバイト、ファイル無し、正常な rename）を実行する - 変更前と同じ結果で通る

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし

## Error Handling

### Error Flow

```
_load_scenario_ids が ("unreadable", 理由) を返す
  → _VerificationDiff が unreadable を記録する
  → 必要になったものだけを rework-index エラー 1 件として報告する
     （メッセージに "cannot be read as text" とファイルのパスを含む）
  → CLI が exit 1 と JSON のエラー詳細で終わる
```

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest tests.test_rework_docs_only_validator_rules` が通る

## Open Questions

なし

## References

- 検証スクリプト: `em-workflow/scripts/validate-worker-output.py`
- テスト: `tests/test_rework_docs_only_validator_rules.py`
