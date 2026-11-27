# Feature: orchestrator-spec-edit-overwrite

## Overview

create-plan 中にオーケストレーター自身が自 feature の SPEC.md / REQUIREMENTS.md を変更してコミットするとき、そのパスとダイジェストを `phase-state/create-plan.yaml` に記録する。create-spec の書き込み方針（action）決定では、既存ターゲットの現在のダイジェストがこの記録の最後のエントリと一致すれば `replace_own` にする。要件の詳細は同じディレクトリの `REQUIREMENTS.md` を参照する。

`references/`・`skills/`・`scripts/` は em-workflow プラグイン内のパスを指す。

## Objectives

- バッチ実行で、オーケストレーターが create-plan 中に直してコミットした SPEC.md が、spec-change 後の create-spec 再実行で digest 不一致による preserve にならず、決定済みの SPEC 変更が書き込まれて run が止まらないようにする
- 人の手など、ほかの経路で変わった SPEC.md は従来どおり digest-mismatch 分岐で守る

## User Stories

### US1: create-plan 中に直した SPEC.md を create-spec 再実行で上書きする
As an em-workflow のバッチ実行の利用者, I want to create-plan 中にオーケストレーターが直してコミットした SPEC.md を、spec-change 後の create-spec 再実行で `replace_own` として上書きさせる, so that 決定済みの SPEC 変更が書き込まれて run が止まらない.

**Acceptance Criteria:**
- [ ] AC-1（FR1）: SKILL.md に、create-plan 中にオーケストレーターが自 feature の SPEC.md / REQUIREMENTS.md を変更してコミットするとき、パスと artifact digest を phase-state/create-plan.yaml の記録に追加し、同じコミットに含める手順が書かれている
- [ ] AC-2（FR2）: phase-state.md のスキーマに、phase: create-plan だけが持つ追記専用の記録（path / sha256 / reason）が定義され、generation が増えても残ること、無い既存ファイルも有効であることが書かれている
- [ ] AC-3（FR3）: spec-writer-contract.md の owner セクションに、create-spec の既存ターゲットの現ダイジェストが create-spec.yaml の最後のエントリ、または create-plan.yaml の記録の最後のエントリと一致すれば replace_own、どちらとも一致しなければ digest-mismatch 分岐、と書かれている
- [ ] AC-4（FR4）: owner セクションに、create-plan.yaml の記録を数える条件（phase と feature の一致）と、記録なしとして扱う 5 つの場合、判定が create-spec.yaml との比較だけになること、Legacy records の引用が書かれている

### US2: ほかの経路で変わった SPEC.md を守る
As an em-workflow の利用者, I want to 人の手など、ほかの経路で変わった SPEC.md を従来どおり digest-mismatch 分岐で守らせる, so that オーケストレーターが記録していない変更が上書きされない.

**Acceptance Criteria:**
- [ ] AC-5（FR5）: create-plan の planning-lineage rule の既存の記述（No other condition gives replace_own を含む）と design step の扱いが変わっていない
- [ ] AC-6（FR6、NFR1）: replace_own 行が既存の文を残し、create-spec の記録版を owner セクションの引用で含め、行の中に last artifacts entry や phase-state/rework.yaml を書いていない。action 表は 7 行のまま
- [ ] AC-7（FR7、NFR3）: 追加したテストを含め、python3 -m unittest discover -s tests がすべて通る。追加した存在検査はそれぞれ、偽の写しで失敗する
- [ ] AC-8（NFR2、NFR4）: artifact-digest.md の level-2 セクション数、create-spec-phase.md の見出しの並び、batch-policies.yaml の create-spec.artifact-overwrite の決定が変わっていない

## Technical Requirements

### Functional Requirements
- **FR1:** create-plan 中のオーケストレーターによる自 feature 文書修正の記録。create-plan 中に、オーケストレーター自身が自 feature の SPEC.md または REQUIREMENTS.md を変更してコミットするとき、変更後のパスと、`references/artifact-digest.md`（`Calculation`）で計算したその時点のダイジェストを、`phase-state/create-plan.yaml` の追記専用の記録に 1 件追加する。この記録は文書の変更と同じコミットに含める。ダイジェストの計算が失敗したときは記録しない。この手順は `skills/develop/SKILL.md` に書き、記録の形は `references/phase-state.md` を引用する。
- **FR2:** 記録のスキーマ。`references/phase-state.md` に FR1 の記録のフィールドを定義する。`phase: create-plan` のときだけ持ち、追記専用で、書き換えも消去もしない。phase の再開始（`generation` の増加）でも残る。各エントリは `path`、`sha256`（`references/artifact-digest.md` の `Digest definition` が定める値）、`reason` を持つ。このフィールドが無い既存のファイルも有効のままとする。
- **FR3:** create-spec の書き込み方針決定で記録版を replace_own にする。`references/contracts/spec-writer-contract.md` の「How the orchestrator chooses each target's action before dispatch」で、create-spec の既存ターゲットについて、現在のダイジェストが次のどちらかと一致すれば `replace_own` にする。(a) 直前の同フェーズ出力（`phase-state/create-spec.yaml` にある、そのパスの最後の `artifacts` エントリ）。(b) `phase-state/create-plan.yaml` の FR1 の記録にある、そのパスの最後のエントリ。どちらとも一致しなければ、従来どおり digest-mismatch 分岐に入る（interactive では `create-spec.artifact-overwrite` ゲート、batch では `references/batch-policies.yaml` の決定）。
- **FR4:** 記録を読むときの条件。FR3 (b) の記録を数えるのは、`phase-state/create-plan.yaml` のマッピングが phase `create-plan` を持ち、feature が workflow の feature と等しいときだけとする。ファイルが無い、読めない、壊れている、phase や feature が合わない、そのパスのエントリが無い、のどれも「(b) の記録なし」として扱い、判定は (a) との比較だけで決める。記録された値の比較は、ほかの記録値と同じく `references/artifact-digest.md` の「Legacy records」に従う。
- **FR5:** 適用範囲を create-spec に限る。FR3 (b) の一致条件は create-spec の action 決定だけに加える。design step の決定と create-plan の planning-lineage rule（`No other condition gives replace_own` を含む）は変えない。spec-change の記録や再計画の許可が `replace_own` の根拠にならないことも、従来どおりとする。
- **FR6:** replace_own 行と create-spec §9 の整合。spec-writer-contract.md の「The `write_policy` actions」表の `replace_own` 行は、既存の文を残したまま、create-spec の spec-writer dispatch では「同フェーズ出力」に FR3 (b) の記録版が含まれることを、owner セクションを引用して述べる。行の中に最後のエントリの規則やファイル名を書き直さない。`references/phases/create-spec-phase.md` §9 の `write_policy` の記述は owner セクションと食い違わないようにし、規則を書き直さずに引用する。
- **FR7:** 再発検出テスト。`tests/` に unittest を追加し、FR1 から FR6 の記述がそれぞれの文書にあることを検査する。各存在検査には、その記述を取り除いた偽の写しで失敗することを確かめるテストを付け、各不在検査には、その語句を入れた偽の写しで検出することを確かめるテストを付ける（既存の `tests/test_artifact_digest_docs.py` の方式に合わせる）。

### Non-Functional Requirements
- **NFR1 - write_policy の action を増やさない:** 新しい action は追加しない。spec-writer-contract.md の action 表は 7 行のままとし、`scripts/self-write-digest.py` の `ACTIONS` と self-write の表は変えない。
- **NFR2 - 文書構造の固定を壊さない:** `references/artifact-digest.md` の level-2 セクションは 6 つのまま、`references/phases/create-spec-phase.md` の level-2 見出しは今の並びのままとする。`references/batch-policies.yaml` の `create-spec.artifact-overwrite` の決定（`preserve_and_reuse`）は変えない。
- **NFR3 - 既存テストがすべて通る:** `python3 -m unittest discover -s tests` がすべて通る。既存のテストメソッドは消さず、弱めない。
- **NFR4 - 引用で済ませ、書き直さない:** 規則は owner 文書（spec-writer-contract.md、phase-state.md、artifact-digest.md）に一度だけ書き、ほかの文書はパスとセクション名で引用する。`git hash-object` を手段として新しく書かない。

## Implementation Approach

### Architecture

**System Architecture:**

action decision は文書（オーケストレーターの手順）で決まり、判定するスクリプトは無い（A-1）。変更はすべて Markdown のプロトコル文書と unittest に対して行う。新しい action は追加せず、既存の `replace_own` を使う（A-2）。

**Component Diagram:**
```
skills/develop/SKILL.md                       FR1 の記録手順（記録の形は phase-state.md を引用）
references/phase-state.md                     FR2 の記録のスキーマ（owner）
references/contracts/spec-writer-contract.md  FR3 / FR4 / FR5 の action 決定（owner セクション）
                                              FR6 の action 表 replace_own 行（owner セクションを引用）
references/phases/create-spec-phase.md        FR6 の §9 write_policy の記述（owner セクションを引用）
references/artifact-digest.md                 Calculation / Digest definition / Legacy records /
                                              Pre-dispatch verification（引用元、変更しない）
tests/                                        FR7 の再発検出テスト
```

### Data Flow

```
create-plan 中のオーケストレーターによる SPEC.md / REQUIREMENTS.md の変更
  → Calculation でダイジェストを計算（失敗したら記録しない）
  → phase-state/create-plan.yaml の記録に {path, sha256, reason} を 1 件追記
  → 文書の変更と記録を同じコミットに含める

spec-change 後の create-spec 再実行
  → 既存ターゲットの現在のダイジェストを計算
  → (a) phase-state/create-spec.yaml の、そのパスの最後の artifacts エントリと比較
  → (b) phase-state/create-plan.yaml の記録の、そのパスの最後のエントリと比較（FR4 の条件を満たすときだけ）
  → どちらかと一致: replace_own
  → どちらとも一致しない: digest-mismatch 分岐
  → 起動直前の expect_digest の照合（Pre-dispatch verification）をそのまま適用（A-11）
```

### API Design

該当なし

### Database Schema

#### `phase-state/create-plan.yaml` の記録

フィールド名は A-3 の例 `orchestrator_doc_edits` を用いる（A-3）。置き場所は既存の `other_feature_doc_fixes` と同じく `phase-state/create-plan.yaml` とする。

| Column | Type | Null | Default | Description |
|--------|------|------|---------|-------------|
| path | string | NO | - | 変更後の文書のパス |
| sha256 | string | NO | - | `references/artifact-digest.md` の `Digest definition` が定める値 |
| reason | string | NO | - | 変更の理由 |

- `phase: create-plan` のときだけ持つ。
- 追記専用で、書き換えも消去もしない。phase の再開始（`generation` の増加）でも残る。
- このフィールドが無い既存のファイルも有効のままとする。

### Dependencies

**Internal Dependencies:**
- `references/artifact-digest.md`: `Calculation`、`Digest definition`、`Legacy records`、`Pre-dispatch verification` を引用する
- `references/batch-policies.yaml`: `create-spec.artifact-overwrite` の決定（`preserve_and_reuse`）を変えずに使う
- `commit-docs.sh`: 記録を含むコミットが exit 4 になった場合は、既存の exit-4 リカバリに従い、最新ツリーの上で編集を作り直した本文からダイジェストを計算し直して、記録と一緒に再試行する（A-10）

**External Dependencies:**
- なし

### File Structure

```
skills/develop/SKILL.md                         # FR1
references/phase-state.md                       # FR2
references/contracts/spec-writer-contract.md    # FR3, FR4, FR5, FR6
references/phases/create-spec-phase.md          # FR6
tests/                                          # FR7（unittest を追加）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/orchestrator-spec-edit-overwrite/**`
- `test-docs/orchestrator-spec-edit-overwrite/**`

`feature-docs/orchestrator-spec-edit-overwrite/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/orchestrator-spec-edit-overwrite/**` covers `test-docs/orchestrator-spec-edit-overwrite/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/orchestrator-spec-edit-overwrite/` directory at all; the declared
`test-docs/orchestrator-spec-edit-overwrite/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Action Decision Scenarios
- [ ] TS-1: batch の create-plan でオーケストレーターが SPEC.md を直してコミットし、その版のダイジェストを create-plan.yaml に記録した。その後 spec-change で create-spec が needs_update になった。create-spec が spec-writer を起動する前に書き込み方針を決める - SPEC.md の現ダイジェストが記録と一致するので replace_own になり、preserve_and_reuse に入らず、決定済みの SPEC 変更が書き込まれる（FR1、FR3）
- [ ] TS-2: 記録した後に人の手で SPEC.md が変わり、現ダイジェストが create-spec.yaml の最後のエントリとも create-plan.yaml の記録とも一致しない。create-spec の書き込み方針を決める - digest-mismatch 分岐に入る（batch では preserve_and_reuse）（FR3）
- [ ] TS-3: create-plan.yaml が無い、壊れている、phase か feature が合わない、または SPEC.md のエントリが無い。create-spec の書き込み方針を決める - (b) の記録なしとして扱い、create-spec.yaml との比較だけで決まる（FR4）
- [ ] TS-4: 同じパスの記録が複数あり、現ダイジェストが最後のエントリではなく前のエントリとだけ一致する。create-spec の書き込み方針を決める - 一致として数えず、digest-mismatch 分岐に入る（FR3）
- [ ] TS-5: create-plan のターゲットまたは design step のターゲットの書き込み方針を決める - create-plan.yaml の新しい記録は判定に使われず、既存の規則のまま決まる（FR5）

### Unit Tests
- [ ] TS-6: 変更後の文書群に対して、追加したテストと既存のテストを走らせる - 存在検査と不在検査がすべて通り、各存在検査は記述を取り除いた偽の写しで失敗し、action 表 7 行・見出しの並び・level-2 セクション数の固定も通る（FR7、FR6、NFR1、NFR2）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- create-spec が新しい版を書いた後に本文が create-plan で記録した版と同じバイト列に戻った場合も、(b) との一致で replace_own になる。これは許容する（A-9）。
- (b) によって replace_own になったターゲットにも、起動直前の expect_digest の照合（`references/artifact-digest.md` の Pre-dispatch verification）をそのまま適用する（A-11）。

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** `phase-state/create-plan.yaml` の記録は、マッピングが phase `create-plan` を持ち、feature が workflow の feature と等しいときだけ数える。無い・読めない・壊れているファイルは記録なしとして扱う（FR4）。
- **Data Protection:** 記録の無い変更は digest-mismatch 分岐で保護する（FR3）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| - | ダイジェストの計算が失敗した（FR1） | - | 記録しない |
| - | 記録を含むコミットが `commit-docs.sh` の exit 4 になった（A-10） | - | 既存の exit-4 リカバリに従い、ダイジェストを計算し直して記録と一緒に再試行する |
| - | `phase-state/create-plan.yaml` が無い・読めない・壊れている・phase や feature が合わない・エントリが無い（FR4） | - | (b) の記録なしとして扱い、(a) との比較だけで決める |

### Error Flow

```
(b) の記録を数えられない → (b) の記録なしとして扱う → (a) との比較だけで action を決める
```

## Performance Optimization

### Performance Goals
- 該当なし

### Optimization Strategies
- 該当なし

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` がすべて通る（NFR3）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- A-1: action decision は文書（オーケストレーターの手順）で決まり、判定するスクリプトは無い。再発検出テストは、既存の test_artifact_digest_docs.py と同じ文書検査（偽の写しによる非空虚性の確認つき）とする
- A-2: 新しい action は追加せず、既存の replace_own を使う（create-plan で rework-planner の記録版を replace_own に含めた先例に合わせる）。action 表 7 行と self-write-digest.py の ACTIONS は既存テストで固定されている
- A-3: 記録のフィールド名は spec 側で決める（例: orchestrator_doc_edits）。置き場所は既存の other_feature_doc_fixes と同じく phase-state/create-plan.yaml とする
- A-4: 対象は自 feature の SPEC.md と REQUIREMENTS.md（spec-writer のターゲット）とする。minimal tier の TASK.md は spec-writer が書かないので対象外とする
- A-5: 一致条件はモードによらず適用する。条件はオーケストレーターが記録した版とのダイジェスト一致であり、interactive でも同じ版を上書きしてよい版として扱える
- A-6: create-plan 以外のフェーズ（review / verify / rework）でのオーケストレーターによる SPEC.md 変更は対象外とする
- A-7: 記録の無い過去の修正で既に止まっている別 feature は、この変更で自動的には復旧しない。その再開は対象外とする
- A-8: plugin の version は触らない（core-plugin-version-bump.md、patch は Actions が上げる）
- A-9: (a) と (b) のどちらかとの一致で replace_own にするため、create-spec が新しい版を書いた後に本文が create-plan で記録した版と同じバイト列に戻った場合も replace_own になる。これは許容する（記録した版はオーケストレーターが承認した版である）
- A-10: 記録を含むコミットが commit-docs.sh の exit 4 になった場合は、既存の exit-4 リカバリに従い、最新ツリーの上で編集を作り直した本文からダイジェストを計算し直して、記録と一緒に再試行する
- A-11: (b) によって replace_own になったターゲットにも、起動直前の expect_digest の照合（references/artifact-digest.md の Pre-dispatch verification）をそのまま適用する

## References

- Requirements document: `feature-docs/orchestrator-spec-edit-overwrite/REQUIREMENTS.md`
- `references/contracts/spec-writer-contract.md`
- `references/phase-state.md`
- `references/artifact-digest.md`
- `references/phases/create-spec-phase.md`
- `references/batch-policies.yaml`
- `tests/test_artifact_digest_docs.py`
