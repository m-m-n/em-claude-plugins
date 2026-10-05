# Feature: review-gate-abort-recovery

## Overview

review-sourced rework（`rework-task-synthesis.md` §10）で `rework.spec-change` の question が run を停止させたとき、`workflow[review].status` を `failed` ではなく `pending` に書く。再開時は停止条件 3 が発火せず、review ラウンドが再実行される。すでに `review: failed` になっている feature には、記録で確認できる場合に限る復旧手順を SSOT に書く。

要件定義書: `feature-docs/review-gate-abort-recovery/REQUIREMENTS.md`

## Objectives

- `rework.spec-change` ゲートの中断で停止した review から、手編集なしに正規の手順で復帰できるようにする
- review step の `status: failed` の意味を SSOT 間で矛盾なくそろえる

## User Stories

### US1: ゲート中断で review を failed にしない
As a オーケストレーター, I want to ゲート中断時に `workflow[review].status` を `pending` に書く, so that 停止条件 3 に掛からない。

**Acceptance Criteria:**
- [ ] AC1: review-phase.md R5 に FR1 の規則が 1 箇所で定義されている。対象となるゲート中断が列挙されており、どちらの status にも failed を書く手順が存在しない
- [ ] AC2: SKILL.md Step B の spec-change ゲート呼び出し段落が AC1 の定義元を引用しており、既存の固定文言を保っている
- [ ] AC4: review-phase.md の failed の予約宣言が perspective_runs の evaluator エントリを対象とすることが明記されている。review step の status の扱いと矛盾せず、workflow-schema.md の許容値も変わっていない

### US2: ゲート中断後の再開
As a em-workflow の利用者, I want to `/em-workflow:develop <feature>` で再開する, so that review ラウンドの再実行を経て spec-change の判断に進める。

**Acceptance Criteria:**
- [ ] AC3: SSOT の記述から、ゲート中断後に develop を再開すると Step B が review（pending）を選び、停止条件 3 が発火せずに review ラウンドが再実行されることが導ける。obsolete の packet は再提示されない

### US3: 既存の review: failed の復旧
As a オーケストレーター, I want to SSOT に書かれた復旧手順を実行する, so that 既存の `review: failed` の feature を手編集なしに再開できる。

**Acceptance Criteria:**
- [ ] AC5: 既存の review: failed の復旧手順（適用条件、戻す値、コミット）が SSOT に書かれている。停止条件 3 が review の failed で発火したときの停止報告と resume_conditions がこの手順を参照している

## Technical Requirements

### Functional Requirements
- **FR1:** ゲート中断時の review の status — review-sourced rework（`rework-task-synthesis.md` §10）の step 1 の後に、`rework.spec-change` の question が run を停止させたとき、オーケストレーターは `workflow[review].status` を `pending` に書く。トップレベルの `review.status = pending` と `review.needs_rework = true` は保持する。どちらの status にも `failed` を書かない。この書き込みは停止前に `commit-docs.sh` でコミットする。対象: Classification gate の verdict が stop の場合（inapplicable を含む）と、その question に対する fail-closed abort（origin membership 失敗、malformed pairing）
- **FR2:** 規則の定義元と引用 — FR1・FR3・FR4 の規則は `review-phase.md` Phase R5 の 1 箇所（Rework path / Batch mode の段落の後）で定義する。`SKILL.md` Step B の「spec-change 遷移のゲート呼び出し（バッチのみ）」段落は、この定義元を引用するだけで、内容を繰り返し書かない
- **FR3:** 再開経路 — FR1 の状態から `/em-workflow:develop <feature>` で再開すると、Step B は review（`pending`）を次の step として特定し、停止条件 3 は発火しない。review フェーズは新しいラウンドを実行し、R5 の Completion gate から通常の rework 経路に入る。interactive では、rework-planner が返す spec-change の question がユーザーに直接提示される。obsolete になった前回の packet は再提示しない。この経路を FR2 の定義元に書く。新しい再開分岐や停止条件 3 の例外は追加しない
- **FR4:** 既存の review: failed の復旧手順 — FR2 の定義元に復旧手順を書く。適用するのは、`workflow[review].status` が `failed` で、`phase-state/rework.yaml` の classification の最終エントリが `decision: stop` のときに限る。手順: `workflow[review].status` と `review.status` を `pending` に、`review.needs_rework` を `true` に戻し、`commit-docs.sh` でコミットする。記録で確認できない場合は手順を適用しない。停止条件 3 が review の `failed` で発火したときの停止報告（batch では `resume_conditions`）は、この手順を参照する
- **FR5:** failed の予約宣言の適用範囲 — `review-phase.md` の「status: failed is reserved for the two structural degradation triggers of Phase R3b」が perspective_runs の evaluator エントリの status を対象とすることを明記する。R5 に FR1 の規則（ゲート中断で review の status に `failed` を書かない）を置く。`workflow-schema.md` の status の許容値は変えない
- **FR6:** 回帰テスト — `tests/` にドキュメント構造テストを追加し、FR1〜FR5 の文言を固定する。各 matcher には、文言が欠けたときに検出できることを示す反例（negative twin）を付ける

### Non-Functional Requirements
- **NFR1:** 停止条件 3 の本文、自動再エントリの例外とその網羅性宣言、batch での verify cap の例外、implement の failed_kind ブロックを変更しない
- **NFR2:** interactive に新しい質問を追加しない（既存の「interactive はこの改訂で変更しない」の宣言と整合させる）
- **NFR3:** 規則の定義元を 1 箇所にし、他の文書は引用だけにする（cited, not restated）
- **NFR4:** 既存テストが固定している文言と出現順序を保つ（reference_impact 参照）
- **NFR5:** `workflow-schema.md` の status の許容値と `batch.review_rework_count` の扱いを変えない
- **NFR6:** plugin の version を触らない（`.claude/rules/core-plugin-version-bump.md`）
- **NFR7:** `python3 -m unittest discover -s tests` が通る

## Implementation Approach

### Architecture

**System Architecture:**
```
review-phase.md Phase R5（定義元: FR1 / FR3 / FR4）
  ├── Phase R3b の failed 予約宣言（適用範囲の明記: FR5）
  └── 引用元
        ├── SKILL.md Step B「spec-change 遷移のゲート呼び出し（バッチのみ）」（FR2）
        └── SKILL.md「停止時の報告（停止条件 2-4 のみ）」/ resume_conditions（FR4）
tests/（ドキュメント構造テスト: FR6）
```

**Component Diagram:**
```
review-phase.md R5 ──(引用)── SKILL.md Step B
review-phase.md R5 ──(参照)── SKILL.md 停止時の報告 / resume_conditions
tests/ ──(文言固定)── review-phase.md, SKILL.md
```

### Data Flow

ゲート中断時:
```
Step B: workflow[review].status = in_progress
§10 step 1: review.status = pending, review.needs_rework = true
rework.spec-change の question → Classification gate stop / inapplicable / fail-closed abort
  → workflow[review].status = pending（review.status = pending, review.needs_rework = true を保持）
  → commit-docs.sh でコミット → 停止
```

再開時:
```
/em-workflow:develop <feature>
  → Step B が review（pending）を特定（停止条件 3 は発火しない）
  → review ラウンドを再実行 → R5 Completion gate → 通常の rework 経路
  → rework-planner が spec-change の question を新しく発行
```

既存の review: failed の復旧:
```
workflow[review].status = failed かつ phase-state/rework.yaml の classification 最終エントリが decision: stop
  → workflow[review].status = pending, review.status = pending, review.needs_rework = true
  → commit-docs.sh でコミット
```

### API Design

該当なし

### Database Schema

該当なし。扱う状態フィールドは次のとおり。

| Field | Location | Description |
|-------|----------|-------------|
| `workflow[review].status` | `workflow.yaml` | Step B が `in_progress` に更新する。ゲート中断時は `pending` に書く |
| `review.status` | `workflow.yaml` | §10 step 1 で `pending` になる。ゲート中断時は保持する |
| `review.needs_rework` | `workflow.yaml` | ゲート中断時は `true` を保持する |
| `batch.review_rework_count` | `workflow.yaml` | ゲート中断では増えない |
| classification の最終エントリ | `phase-state/rework.yaml` | `decision: stop` のとき FR4 の手順を適用できる |

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/review-phase.md`: Phase R3b の failed 予約宣言、Phase R5（Rework path / Batch mode / Completion gate）
- `em-workflow/skills/develop/SKILL.md`: Step B、停止条件 3、停止時の報告（停止条件 2-4 のみ）
- `em-workflow/references/question-resolution.md`: Classification gate、obsolete packet の扱い
- `em-workflow/references/rework-task-synthesis.md`: §10 の SPEC-change transition
- `em-workflow/references/workflow-schema.md`: status の許容値、`batch.review_rework_count`
- `batch-terminal-line.md`: Fallback rule（`unmapped_stop`）
- `commit-docs.sh`: status の書き込みのコミット

**External Dependencies:**
- なし

### File Structure

```
em-workflow/
├── references/
│   └── review-phase.md      # FR1 / FR3 / FR4 / FR5
└── skills/
    └── develop/
        └── SKILL.md         # FR2 / FR4（引用と参照）
tests/                       # FR6（ドキュメント構造テストを追加）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/review-gate-abort-recovery/**`
- `test-docs/review-gate-abort-recovery/**`

`feature-docs/review-gate-abort-recovery/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/review-gate-abort-recovery/**` covers `test-docs/review-gate-abort-recovery/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/review-gate-abort-recovery/` directory at all; the declared
`test-docs/review-gate-abort-recovery/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1): review-phase.md の R5 節を切り出し、ゲート中断時に workflow[review].status を pending に書く規則、review.status = pending と review.needs_rework = true の保持、failed を書かない旨、対象（Classification gate の stop / inapplicable、origin membership 失敗、malformed pairing）がそろっていることを確認する。各文言を欠いた反例で matcher が失敗することも確認する
- [ ] TS2 (AC2): SKILL.md Step B の「spec-change 遷移のゲート呼び出し（バッチのみ）」段落が R5 の定義元を引用していること、tests/test_gate_outcome_packet_lifecycle.py が固定する既存文言がすべて残っていることを確認する
- [ ] TS3 (AC3): R5 の定義元に、再開時に Step B が review（pending）を選び、停止条件 3 が発火せず review ラウンドが再実行され、obsolete の packet を再提示しない経路が書かれていることを確認する
- [ ] TS4 (AC4): review-phase.md の「status: failed is reserved for the two structural degradation triggers of Phase R3b」の近傍に perspective_runs の evaluator エントリが対象である旨が書かれていること、workflow-schema.md の status の許容値が変わっていないことを確認する
- [ ] TS5 (AC5): 復旧手順の適用条件（workflow[review].status が failed かつ phase-state/rework.yaml の classification の最終エントリが decision: stop）、戻す値（両 status を pending、needs_rework を true）、commit-docs.sh でのコミット、記録で確認できない場合は適用しない旨が書かれていること、SKILL.md「停止時の報告（停止条件 2-4 のみ）」節と resume_conditions がこの手順を参照していることを確認する
- [ ] TS6 (AC6): 追加した各 matcher に対応する negative twin があり、文言を除いた入力で失敗することを確認する

### Integration Tests
- [ ] TS7 (AC7): python3 -m unittest discover -s tests を実行し、既存テスト（test_classification_gate.py、test_rework_synthesis_contract.py、test_gate_outcome_packet_lifecycle.py を含む）と新規テストが通ることを確認する

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] status は 2 つの別フィールドにある。workflow[review].status は Step B が in_progress に更新済みで、トップレベルの review.status は §10 step 1 で pending になっている
- [ ] Classification gate の stop / inapplicable で packet は obsolete になり、再開しても再提示されない。再開時の spec-change の question は、再実行した rework で新しく発行される
- [ ] ゲート中断では batch.review_rework_count が増えない。goal ブロックが無い feature を batch で再開すると、review ラウンドからゲート中断までを繰り返して停止する（A6）
- [ ] goal ブロックがある feature で verdict (a) goal_not_met による stop が起きた場合も FR1 の規則に従う
- [ ] rework.spec-change の question に対する fail-closed abort（origin membership 失敗、malformed pairing）も FR1 の対象。verify 由来の spec-change ゲート中断は対象外（A5）
- [ ] すでに review: failed の feature で、classification の記録が確認できない場合は FR4 の手順を適用せず、停止条件 3 の通常停止になる
- [ ] spec-change 遷移の 5 つの step はゲート中断時には 1 つも実行されないため、create-spec / create-plan / implement の status は変わらない
- [ ] status の書き込みで commit-docs.sh が exit 4 を返した場合は、既存の exit-4 リカバリに従って書き込みをやり直す
- [ ] ゲート中断による batch の停止は、batch-terminal-line.md の Fallback rule で unmapped_stop に束ねられる

### Performance Tests
該当なし

## Security Considerations

- **Input Validation:** task_description は信頼できない入力として扱った。指示の差し込み（injection）は見つからなかった
- **Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF:** 該当なし

## Error Handling

### Error Codes

| Code | Description | Handling |
|------|-------------|----------|
| commit-docs.sh exit 4 | status の書き込みのコミットが exit 4 を返す | 既存の exit-4 リカバリに従って書き込みをやり直す |
| 記録で確認できない | `phase-state/rework.yaml` の classification の記録が確認できない | FR4 の手順を適用せず、停止条件 3 の通常停止になる |

### Error Flow

```
停止条件 3 が review の failed で発火 → 停止報告（batch では resume_conditions）が FR4 の復旧手順を参照
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1: review-phase.md R5 に FR1 の規則が 1 箇所で定義されている。対象となるゲート中断が列挙されており、どちらの status にも failed を書く手順が存在しない
- [ ] AC2: SKILL.md Step B の spec-change ゲート呼び出し段落が AC1 の定義元を引用しており、既存の固定文言を保っている
- [ ] AC3: SSOT の記述から、ゲート中断後に develop を再開すると Step B が review（pending）を選び、停止条件 3 が発火せずに review ラウンドが再実行されることが導ける。obsolete の packet は再提示されない
- [ ] AC4: review-phase.md の failed の予約宣言が perspective_runs の evaluator エントリを対象とすることが明記されている。review step の status の扱いと矛盾せず、workflow-schema.md の許容値も変わっていない
- [ ] AC5: 既存の review: failed の復旧手順（適用条件、戻す値、コミット）が SSOT に書かれている。停止条件 3 が review の failed で発火したときの停止報告と resume_conditions がこの手順を参照している
- [ ] AC6: 追加したテストが AC1〜AC5 の文言を固定しており、各 matcher に反例（negative twin）がある
- [ ] AC7: python3 -m unittest discover -s tests が通る

## Assumptions

- A1: ゲート中断時は review の status を failed にせず pending のまま残す（keep_pending）。停止条件 3 の例外は追加しない
- A2: 既存の review: failed は、ゲート中断による failed と記録で確認できる場合に限り、両 status を pending・needs_rework を true に戻す手順を SSOT に書き、resume_conditions から参照する。exit4-tip-argument はすでに completed のため変更しない
- A3: review-phase.md 927 行目の failed の予約は perspective_runs の evaluator エントリを対象とする。R5 に適用範囲とゲート中断で failed を書かない規則を明記し、workflow-schema.md の許容値は変えない
- A4: 再開時は review ラウンドを再実行し、spec-change の question は再実行した rework で新しく発行させる。obsolete の packet は再提示しない
- A5: verify 由来の spec-change ゲート中断は対象外とする
- A6: ゲート中断では batch.review_rework_count を増やさない（既存の扱いを変えない）。goal ブロックが無い feature を batch で再開すると、review ラウンドからゲート中断までを繰り返して停止する
- A7: design step は実行しない（skip）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/review-gate-abort-recovery/REQUIREMENTS.md`
- `em-workflow/references/review-phase.md`
- `em-workflow/skills/develop/SKILL.md`
- `em-workflow/references/question-resolution.md`
- `em-workflow/references/rework-task-synthesis.md`
- `em-workflow/references/workflow-schema.md`
