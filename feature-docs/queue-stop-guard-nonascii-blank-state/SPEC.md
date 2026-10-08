# Feature: queue-stop-guard-nonascii-blank-state

## Overview

`em-workflow/hooks/queue_stop_guard.py` の複数行の値の追跡（`_MultilineValueTracker`）で、ブロックスカラーの状態とプレーンスカラー継続の状態が、親の字下げ以下にある非 ASCII 空白だけの行で終わる経路を塞ぐ。この経路では後続の `- '…` が引用値を開き、本物の `routeback_failed_journal_line` 記録と後続タスクが隠れる。

## Objectives

- em-workflow/hooks/queue_stop_guard.py の複数行の値の追跡で、ブロックスカラーの状態とプレーンスカラー継続の状態が、親の字下げ以下にある非 ASCII 空白だけの行で終わる経路を塞ぐ。この経路では後続の `- '…` が引用値を開き、本物の routeback_failed_journal_line 記録と後続タスクが隠れる。
- 課題の 3 形で本物の記録と task0002 が読まれ、Stop フックが exit 2 で終わる。

## Acceptance Criteria

- [ ] AC-1 (FR1, FR2): 準備: ジャーナル 1 行目は task0001 の failed。task0001 は pending で、notes の後に直下キー `routeback_failed_journal_line: 1` がある。その後ろに、ジャーナルにイベントの無い pending の task0002 がある。notes を次の 3 形 × {U+3000, U+00A0} の 6 通りにし、それぞれを subTest で実行する: (a) `    notes: |` / `      body line` / 0 桁目にその文字だけの行 / `      - 'x`、(b) (a) のその文字の行を 4 個の空白の後に置いた形、(c) `    notes: hello` / 0 桁目にその文字だけの行 / `      - 'x`。hook のサブプロセスは BLOCK を出して exit 2 で終わり、起動リストに task0001 と task0002 が含まれる。
- [ ] AC-2 (FR1, FR2): AC-1 の各フィクスチャで、hook モジュールをファイルパスから読み込んで直接呼ぶと、`task_ids_from_workflow` は `[task0001, task0002]` を返し、`task_routeback_records_from_workflow` は task0001 を `"1"` に対応づける。
- [ ] AC-3 (FR3): 次の既存テストが変更なしで通る: `TestColumnZeroNonAsciiBlankLine`、`TestNonAsciiBlankLineDoesNotOpen`、`TestOtherNonAsciiWhitespaceIsNotBlank`、`TestBlockScalarKeepsANonAsciiBlankLine`、`TestBlockScalarEndsAtANonAsciiBlankLineByIndentation.test_a_deeper_non_ascii_line_stays_a_body_line`。
- [ ] AC-4 (NFR2): AC-1 の全フィクスチャと、ファイル末尾まで閉じない値を含む形で、タスク ID・タスクブロック走査・記録の各読み取り関数が例外を出さずに戻る。
- [ ] AC-5 (FR4): トラッカーのクラス docstring に FR4 の文言が書かれ、「or by its indentation inside a block scalar」が無い。
- [ ] AC-6 (FR5): 書き換えた既存テストが、0 桁目の U+3000 行の後の `      body line`・`      - 'x`・`      y'` がすべてブロックの走査に出ることを確かめ、通る。
- [ ] AC-7 (NFR4): リポジトリルートで `python3 -m unittest tests.test_queue_stop_guard_routeback_record` と `python3 -m unittest discover -s tests` が通る。

## Technical Requirements

### Functional Requirements

- **FR1:** ブロックスカラーの状態では非 ASCII 空白だけの行が状態を変えない — `_MultilineValueTracker.feed` のブロックスカラー分岐では、次の行が字下げ（0 桁目、親の字下げと同じ桁、それより深い桁）に関係なく、ブロックスカラーの状態を続けも終わらせもしない: 行末の改行を除いた後に `str.strip()` で空になり、かつ U+0020 の空白と U+0009 のタブだけからなる行ではないもの。`feed` はその行に `False` を返し、`_block_parent` を保ったまま、その行を `_read_line` に渡さない。
- **FR2:** プレーンスカラー継続の状態では非 ASCII 空白だけの行が状態を変えない — `_MultilineValueTracker._read_line` では、`_plain_parent` が設定されているとき、FR1 と同じ行は字下げに関係なくプレーンスカラー継続の状態を終わらせず、`_plain_parent` と `_pending` のどちらも変えない。キーの値（`notes: hello`）にも項目の内容（`- hello`）にも適用する。
- **FR3:** 変えない挙動 — 次の挙動は変えない。値の開始位置（pending）での routeback-record-quoted-open-residual の FR2: そのような行はプレーンスカラーとして読み、それより深い後続行はその継続行になる。0 桁目の非 ASCII 空白行の後の `- '…` が開く残余 A1 と、それを固定している `TestColumnZeroNonAsciiBlankLine`。空白・タブだけの行の扱い。非 ASCII 空白に続けて空白以外の文字がある行（例: `　x`）の扱い。トラッカーの外の読み取り関数（`task_ids_from_workflow`、`iter_task_block_lines`、`task_routeback_records_from_workflow`）の空行判定。
- **FR4:** docstring — トラッカーのクラス docstring の 2 段落に、ブロックスカラーの状態とプレーンスカラー継続の状態では FR1 の行が状態を続けも終わらせもしないことを書く: 空行の段落（現在 228〜232 行目）とプレーンスカラー継続の段落（現在 209〜216 行目）。「or by its indentation inside a block scalar」は削除する。モジュール docstring は変えない。
- **FR5:** 既存テストの書き換え — 既存テスト `TestBlockScalarEndsAtANonAsciiBlankLineByIndentation.test_the_block_scalar_ends_at_the_column_zero_non_ascii_line` を、同じフィクスチャ（`    notes: |` / `      body line` / 0 桁目の U+3000 だけの行 / `      - 'x` / `      y'`）のまま新しい挙動に書き換える。テスト名とクラスの docstring を新しい挙動に合わせる。0 桁目の U+3000 行でブロックスカラーが終わらず、`      body line`・`      - 'x`・`      y'` がすべて `iter_task_block_lines` の走査に出ることを確かめる。
- **FR6:** 前の feature の FR2 との関係 — この feature は、routeback-record-quoted-open-residual の FR2 のうち、ブロックスカラーの状態とプレーンスカラー継続の状態の部分を変える。値の開始位置での FR2 は保つ。routeback-record-quoted-open-residual の SPEC.md・THREAT-MODEL.md・VERIFICATION.md と test-docs/routeback-record-quoted-open-residual/ は変えない。

### Non-Functional Requirements

- **NFR1 - 依存:** hook は Python の標準ライブラリだけを import する。
- **NFR2 - fail-open:** トラッカーと読み取り関数は、新しいフィクスチャやファイル末尾まで閉じない値を含め、どんな行の内容でも例外を出さない。
- **NFR3 - 変更範囲:** 変更は `em-workflow/hooks/queue_stop_guard.py`、`tests/test_queue_stop_guard_routeback_record.py`、`feature-docs/queue-stop-guard-nonascii-blank-state/**`、`test-docs/queue-stop-guard-nonascii-blank-state/**` に限る。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` は変えない。
- **NFR4 - 回帰:** FR5 の 1 件を除き、既存テストのアサーションを変更・削除しない。リポジトリルートで `python3 -m unittest discover -s tests` が通る。

## Assumptions

- **A1:** 「半角空白・タブ以外の空白文字だけを含む行」は、行末の改行を除いた後に `str.strip()` で空になり、かつ空白・タブだけの行ではない行とする。トラッカーの外の読み取り関数（`line.strip()`）や基準リビジョン（`text.strip()`）と同じ空白の集合。
- **A2:** そのような行は、ブロックスカラーの状態では本文の行として扱わず（`feed` は `False` を返す）、`_read_line` にも渡さない。プレーンスカラー継続の状態ではトラッカーの状態を変えない。
- **A3:** 値の開始位置にある形（`notes:` / 0 桁目の非 ASCII 空白行 / `- '…`）は開いたまま残る（前の feature の残余 A1）。
- **A4:** プラグインの version は変えない。
- **A5:** 前の feature の文書（routeback-record-quoted-open-residual の SPEC.md・THREAT-MODEL.md・VERIFICATION.md と test-docs）は変えない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
em-workflow/hooks/queue_stop_guard.py
├── _MultilineValueTracker
│   ├── feed        — ブロックスカラー分岐（FR1）
│   └── _read_line  — プレーンスカラー継続（FR2）
└── 読み取り関数（変えない: FR3）
    ├── task_ids_from_workflow
    ├── iter_task_block_lines
    └── task_routeback_records_from_workflow
```

### Dependencies

**Internal Dependencies:**
- routeback-record-quoted-open-residual: この feature はその FR2 のうち、ブロックスカラーの状態とプレーンスカラー継続の状態の部分を変える（FR6）。

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）。

### File Structure

```
em-workflow/hooks/queue_stop_guard.py
tests/test_queue_stop_guard_routeback_record.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/queue-stop-guard-nonascii-blank-state/**`
- `test-docs/queue-stop-guard-nonascii-blank-state/**`

`feature-docs/queue-stop-guard-nonascii-blank-state/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/queue-stop-guard-nonascii-blank-state/**` covers `test-docs/queue-stop-guard-nonascii-blank-state/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/queue-stop-guard-nonascii-blank-state/` directory at all; the declared
`test-docs/queue-stop-guard-nonascii-blank-state/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS-2 (AC-2): AC-1 の各フィクスチャで、読み取り関数を直接呼ぶ。task_ids が `[task0001, task0002]`、`records[task0001] == "1"` になることを確かめる。基準リビジョンでは red（records が `{}`、task_ids が `['task0001']`）になる。
- [ ] TS-3 (AC-6): 書き換えた既存テスト（FR5）が、0 桁目の U+3000 行でブロックスカラーが終わらないことを確かめる。
- [ ] TS-4 (AC-4): 新しいフィクスチャと閉じない値の形で、3 つの読み取り関数が例外を出さずに戻ることを確かめる。
- [ ] TS-5 (FR1, FR2, FR3): エッジケースを確かめる。U+000B / U+000C だけの行、2 桁目の非 ASCII 空白行、項目の内容のプレーンスカラー（`      - hello` の後に 0 桁目の U+3000 行と `      - 'x`）、`>`・`|-`・`- |` の見出し、非 ASCII 空白行が続けて複数ある形で、記録と task0002 が読まれる。

### Integration Tests

- [ ] TS-1 (AC-1): Stop フックの JSON を stdin に渡す hook のサブプロセスを、AC-1 の 6 通り（subTest）で実行する。exit 2 で終わり、起動リストに task0001 と task0002 が含まれることを確かめる。基準リビジョン 65714d9f では red（exit 0）になる。

### Regression Tests

- [ ] TS-6 (AC-3, AC-7): リポジトリルートで `python3 -m unittest tests.test_queue_stop_guard_routeback_record` と `python3 -m unittest discover -s tests` を実行し、すべて通ることを確かめる。

### Inspection

- [ ] TS-7 (AC-5): トラッカーのクラス docstring に FR4 の文言があることを確かめる。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] U+000B / U+000C だけの行も FR1 / FR2 の対象
- [ ] 親の字下げと 0 桁目の間（例: 2 桁目）の非 ASCII 空白行も状態を変えない
- [ ] 項目の内容のプレーンスカラーでも継続が終わらない
- [ ] ブロックスカラーの見出しの別形（`>`、`|-`、項目の `- |`）でも同じ
- [ ] 非 ASCII 空白行が続けて複数ある場合も状態を変えない
- [ ] 値の開始位置の 0 桁目の非 ASCII 空白行と `- '…` は従来どおり開く（変えない）
- [ ] 非 ASCII 空白の後に空白以外の文字がある行（`　x`）は従来どおり字下げで判定する（変えない）

## Security Considerations

- **Input Validation:** workflow.yaml の notes の中の非 ASCII 空白だけの行を使って、ブロックスカラーやプレーンスカラーの継続を終わらせ、引用値を開かせることができない。本物の routeback_failed_journal_line 記録と後続タスクを隠せない。

## Error Handling

- トラッカーと読み取り関数は、どんな行の内容でも例外を出さない（NFR2）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] AC-1〜AC-7 を満たす

## Open Questions

なし

## References

- routeback-record-quoted-open-residual SPEC: `feature-docs/routeback-record-quoted-open-residual/SPEC.md`
