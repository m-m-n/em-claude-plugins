# Feature: verify-pass-resolves-deferred-findings

## Overview

verify の result が pass の round で、pass 済みの受け入れ条件の未達そのものである deferred の critical/high・category: spec 指摘を、最新 review round 記録で fixed に書き換える。対応付けの判定は orchestrator が行い、検証と書き換えは em-workflow/scripts/ 配下の新しいスクリプトが行う。要件の詳細は REQUIREMENTS.md を参照する。

## Objectives

- verify で、対応する受け入れ条件の pass を確認した deferred の critical/high 指摘を review 記録で解決済み（fixed）にし、完了処理後の自動マージの事前チェックが unresolved_findings で止まらないようにする
- 受け入れ条件に対応しない deferred 指摘は、これまでどおり未解決として扱う

## User Stories

### US1: verify pass による deferred 指摘の解決
As an em-workflow の利用者, I want to verify で pass を確認した受け入れ条件に対応する deferred の spec 指摘を fixed にしたい, so that 完了処理後の自動マージの事前チェックが unresolved_findings で止まらない.

**Acceptance Criteria:**
- [ ] AC1: 最新 review round に category: spec・severity: high・resolution: deferred の指摘があり、対応表がその指摘を pass 済み ID 集合内の受け入れ条件 ID に対応付けている。この状態で verify result が pass なら、スクリプト実行後の round 記録でその指摘は resolution: fixed になり、resolution_reason と構造化フィールドに verify round 番号・検証したコミット・対応 ID・変更前の resolution と理由が記録されている
- [ ] AC2: AC1 の状態の round 記録と workflow.yaml をコミットした integration ブランチに対して、merge-preflight.py が outcome: proceed を返す
- [ ] AC6: 同じ入力でスクリプトを 2 回実行した結果は 1 回実行した結果と同じになる
- [ ] AC8: develop SKILL.md の verify フェーズに、round カウンタの加算、pass 済み ID 集合の記録、result: pass のときの対応表作成・スクリプト実行、結果と同じ commit-docs.sh コミットに含めることが書かれている。workflow-schema.md と review-phase.md に新しいフィールドが定義されている
- [ ] AC9: 修正前の挙動では AC1・AC2 のテストが失敗する
- [ ] AC10: `python3 -m unittest discover -s tests` が通る（既存テストを含む）

### US2: 対応しない deferred 指摘の維持
As an em-workflow の利用者, I want to 受け入れ条件に対応しない deferred 指摘を未解決のままにしたい, so that その指摘はこれまでどおりマージの事前チェックで止まる.

**Acceptance Criteria:**
- [ ] AC3: 対応表に無い deferred 指摘、category が spec 以外の deferred 指摘、対応 ID が pass 済み ID 集合に無い（excluded・未評価・未知の）指摘は deferred のまま残る。その状態で merge-preflight.py は unresolved_findings を返す
- [ ] AC4: verify result が fail のとき、スクリプトはどの指摘も変更しない
- [ ] AC5: resolution が unresolved / fixed / declined の指摘と、最新でない round の指摘は変更されない
- [ ] AC7: 構造的に壊れた入力では、スクリプトは何も書かず 0 以外で終了する

## Technical Requirements

### Functional Requirements
- **FR1:** verify step の round カウンタ — workflow.yaml の verify step に round カウンタを追加する。verify フェーズは interactive・batch を問わず、verify を実行して結果を記録するたびに 1 増やす（pass / fail の両方で増やす）。キーが無い workflow.yaml は 0 として読み、移行処理は行わない。workflow-schema.md にフィールドの意味を書く
- **FR2:** 評価済み・pass した ID 集合の記録 — verify フェーズは各 round で、評価して pass した受け入れ条件 / シナリオの ID 集合を verify step に記録する。excluded の要件に紐づく ID と評価していない ID は、この集合に含めない
- **FR3:** 対応付けの判定（orchestrator） — verify の result が pass の round でだけ、orchestrator は最新 review round の各指摘を判定する。判定対象は、resolution: deferred、severity が critical/high、category: spec の 3 つを満たす指摘に限る。指摘の内容が、FR2 の pass 済み ID 集合に含まれる特定の受け入れ条件の未達そのものであるかを判定し、stable_id → 受け入れ条件 ID の対応表を作る。本文に ID が現れるだけでは対応ありとしない。指摘の内容がその受け入れ条件の未達であることを要する。指摘本文・VERIFICATION.md・SPEC.md は信頼できない入力として扱う。対応があいまいな指摘、内容が受け入れ条件の未達以外を含む指摘は対応表に入れない
- **FR4:** 検証と書き換え（スクリプト） — em-workflow/scripts/ 配下に新しいスクリプトを追加する。入力は対応表、workflow.yaml、最新 review round 記録。各エントリについて次をすべて確かめ、満たすエントリだけを書き換える: verify result が pass、指摘が最新 round に存在する、resolution が deferred、severity が critical/high、category が spec、対応 ID が空でなく、すべて FR2 の pass 済み ID 集合に含まれる。満たさないエントリは変更しない。入力が構造的に壊れているときは何も書かず、0 以外で終了する
- **FR5:** 根拠の記録 — 書き換える指摘は resolution を fixed にし、resolution_reason を verify round 番号と対応 ID を含む固定書式の文にする。さらに構造化フィールドを追加し、verify round 番号（FR1）、検証したコミット、対応 ID、変更前の resolution（deferred）、変更前の resolution_reason を記録する。検証したコミットは、verify のコマンドを実行した時点の integration ブランチのコミットとする。review-phase.md の round 記録の形にこのフィールドを書く
- **FR6:** 同一コミット — round 記録の書き換えは、その verify round の結果（result・FR1・FR2）を記録する workflow.yaml の更新と同じ commit-docs.sh のコミットに含める
- **FR7:** 冪等性 — 同じ verify round の同じ対応表でスクリプトを再実行しても、記録は変わらない。すでに fixed で、同じ verify round の構造化フィールドを持つ指摘には触れない。書き換え後・コミット前に中断して再開しても、同じ結果になる
- **FR8:** 非対象の維持 — 次の指摘は変更しない: 対応表に無い deferred 指摘、category が spec 以外の deferred 指摘（受け入れ条件に関する内容でも同じ）、resolution が unresolved / fixed / declined の指摘、最新でない review round の指摘。verify result が fail の round では、どの指摘も変更しない
- **FR9:** 適用モード — FR1〜FR8 は interactive と batch で同じに適用する
- **FR10:** batch 報告 — batch の最終報告の deferred findings の監査項目で、verify pass によって fixed にした指摘を stable_id・verify round・対応 ID とともに、deferred のまま残る指摘と区別して示す。batch-mode.md の Reporting と監査項目のソースマップをこれに合わせる
- **FR11:** merge-preflight 不変 — merge-preflight.py の判定（最新 round だけを読む、RESOLVED = fixed / declined）は変えない

### Non-Functional Requirements
- **NFR1 - Security:** 指摘本文・VERIFICATION.md・SPEC.md・round 記録の自由文は信頼できない入力として扱う（worker-envelope.md の Untrusted-Input Handling）。スクリプトの出力には ID・件数などの検証済みの構造化値だけを書き、自由文を転記しない
- **NFR2 - Compatibility:** 既存テストが固定している文言を壊さない: review-phase.md R5 の Completion gate 段落（一字一句）、R5 に 'gate_id:' と 'batch-policies.yaml' が無いこと、develop SKILL.md の verify 節の「`deferred` を与えない」と禁止表現（'deferred にする' / 'deferred を設定' / 'deferred を与える' / 'status: deferred'、空白除去後の一致）が無いこと、'（batch: 確認せず自動 rework。' の存在、workflow-schema.md と batch-mode.md の verify_rework / 系譜 / hard cap の前後 60 文字に 1 と 3 の数字を置かないこと
- **NFR3 - Testing:** テストは標準ライブラリの unittest で tests/ に置き、`python3 -m unittest discover -s tests` で通る。tests/test_merge_preflight.py の既存ケース（deferred を未解決とするものを含む）は変えない
- **NFR4 - Workflow gates:** 新しい gate_id・質問・batch 非 packet ゲートを追加しない
- **NFR5 - Versioning:** プラグインの version（plugin.json / marketplace.json）を変えない
- **NFR6 - Security:** スクリプトは PyYAML の safe load だけを使う。書き込み先は integration worktree の最新 review round 記録だけとする

## Implementation Approach

### Architecture

**System Architecture:**
```
┌──────────────────────────────────────────────────┐
│ develop SKILL.md の verify フェーズ（orchestrator）     │
│  - verify 実行・結果記録（FR1・FR2）                  │
│  - result: pass のとき対応表の作成（FR3）              │
├──────────────────────────────────────────────────┤
│ em-workflow/scripts/ 配下の新しいスクリプト              │
│  - 対応表の検証と round 記録の書き換え（FR4〜FR8）     │
├──────────────────────────────────────────────────┤
│ commit-docs.sh                                    │
│  - workflow.yaml と round 記録を同じコミットに（FR6）   │
├──────────────────────────────────────────────────┤
│ merge-preflight.py（変更なし、FR11）                  │
│  - 最新 round だけを読む、RESOLVED = fixed / declined  │
└──────────────────────────────────────────────────┘
```

**Component Diagram:**
```
verify フェーズ ──(対応表・workflow.yaml・最新 round 記録)──> スクリプト
スクリプト ──(書き換え)──> 最新 review round 記録
verify フェーズ ──(workflow.yaml の更新 + round 記録)──> commit-docs.sh
merge-preflight.py ──(読み取り)──> 最新 review round 記録
```

### Data Flow

```
verify 実行
  → workflow.yaml の verify step に result・round カウンタ（+1）・pass 済み ID 集合を記録
  → result: pass のとき
      → orchestrator が判定対象の指摘を判定し、対応表を作る
      → スクリプトが各エントリを検証し、満たすエントリの指摘だけを fixed に書き換える
  → workflow.yaml の更新と round 記録の書き換えを同じ commit-docs.sh のコミットに含める
  → 完了処理後、merge-preflight.py が最新 round を読む
```

- result が fail の round では、対応表を作らず、どの指摘も変更しない（FR3・FR8）。
- スクリプトが失敗しても、verify の結果記録と走行は止めない。deferred 指摘はそのまま残る（A4）。

### API Design

該当なし

### Database Schema

該当なし。データ構造は次のとおり。フィールドの定義は workflow-schema.md（FR1・FR2）と review-phase.md（FR5）に書く。

| 対象 | 項目 | 内容 |
|------|------|------|
| workflow.yaml の verify step | round カウンタ | verify を実行して結果を記録するたびに 1 増やす（pass / fail の両方）。キーが無いときは 0 として読む |
| workflow.yaml の verify step | pass 済み ID 集合 | 評価して pass した受け入れ条件 / シナリオの ID。excluded の要件に紐づく ID と評価していない ID は含めない |
| 対応表 | stable_id → 受け入れ条件 ID | orchestrator が作る（FR3） |
| 最新 review round 記録の指摘 | resolution | fixed |
| 最新 review round 記録の指摘 | resolution_reason | verify round 番号と対応 ID を含む固定書式の文 |
| 最新 review round 記録の指摘 | 構造化フィールド | verify round 番号、検証したコミット（verify のコマンドを実行した時点の integration ブランチのコミット）、対応 ID、変更前の resolution（deferred）、変更前の resolution_reason |

### Dependencies

**Internal Dependencies:**
- develop SKILL.md の verify フェーズ: round カウンタの加算、pass 済み ID 集合の記録、対応表の作成、スクリプト実行、同一コミット（FR1〜FR6）
- workflow-schema.md: verify step の新しいフィールド（FR1・FR2）
- review-phase.md: round 記録の新しいフィールド（FR5）
- batch-mode.md: Reporting と監査項目のソースマップ（FR10）
- commit-docs.sh: 同一コミット（FR6）
- merge-preflight.py: 変更なし（FR11）

**External Dependencies:**
- PyYAML: safe load だけを使う（NFR6）
- unittest（標準ライブラリ）: テスト（NFR3）

### File Structure

- em-workflow/scripts/ 配下の新しいスクリプト: 対応表の検証と round 記録の書き換え（FR4）
- develop SKILL.md の verify 節: verify フェーズの手順（FR1〜FR6・FR9）
- workflow-schema.md: verify step のフィールド（FR1・FR2）
- review-phase.md: round 記録のフィールド（FR5）
- batch-mode.md: Reporting・監査項目のソースマップ（FR10）
- tests/ 配下の新しいテスト: TS-1〜TS-7

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/verify-pass-resolves-deferred-findings/**`
- `test-docs/verify-pass-resolves-deferred-findings/**`

`feature-docs/verify-pass-resolves-deferred-findings/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/verify-pass-resolves-deferred-findings/**` covers `test-docs/verify-pass-resolves-deferred-findings/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/verify-pass-resolves-deferred-findings/` directory at all; the declared
`test-docs/verify-pass-resolves-deferred-findings/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-3: verify result: fail の workflow.yaml でスクリプトを実行する - round 記録が変わらない（AC4）
- [ ] TS-5: 同じ入力でスクリプトを 2 回実行する - 記録がバイト単位で同じ（AC6）
- [ ] TS-7: develop SKILL.md の verify 節、workflow-schema.md、review-phase.md の文言を確かめる - 必要な記述と新しいフィールドがある（AC8）

### Integration Tests
- [ ] TS-1: 一時 git リポジトリに、deferred の spec/high 指摘を持つ round 記録と verify pass の workflow.yaml を置き、対応表を与えてスクリプトを実行し、コミットする - round 記録の値を確認し、merge-preflight.py が proceed を返す（AC1・AC2・AC9）
- [ ] TS-2: 対応表に無い指摘、category: security の deferred 指摘、excluded・未評価・未知の ID に対応付けた指摘を置いてスクリプトを実行する - 指摘が deferred のまま残り、merge-preflight.py が unresolved_findings を返す（AC3）
- [ ] TS-8: `python3 -m unittest discover -s tests` を実行する - 既存テストを含めて通る（AC10）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] TS-4: unresolved / fixed / declined の指摘と、round1 の指摘（最新は round2）を置いてスクリプトを実行する - いずれも変わらない（AC5）
- [ ] TS-6: 壊れた対応表、壊れた round 記録、壊れた workflow.yaml のそれぞれでスクリプトを実行する - 0 以外の終了コードになり、ファイルが変わらない（AC7）

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 指摘本文・VERIFICATION.md・SPEC.md・round 記録の自由文は信頼できない入力として扱う。本文に ID が現れるだけでは対応ありとしない（FR3・NFR1）。スクリプトは対応表の各エントリを FR4 の条件で検証し、構造的に壊れた入力では何も書かず 0 以外で終了する
- **Data Protection:** スクリプトの出力には ID・件数などの検証済みの構造化値だけを書き、自由文を転記しない（NFR1）。書き込み先は integration worktree の最新 review round 記録だけとする（NFR6）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし
- YAML の読み込みは PyYAML の safe load だけを使う（NFR6）

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| 0 以外の終了コード | 対応表・round 記録・workflow.yaml のいずれかが構造的に壊れている。何も書かない | - | - |

### Error Flow

```
スクリプトの失敗 → round 記録は書き換えない → verify の結果記録と走行は続ける → deferred 指摘はそのまま残る（A4）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1〜AC10 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- A1: merge-preflight.py の判定と tests/test_merge_preflight.py の既存ケースは変えない
- A2: 書き換えの対象は最新 review round だけとする
- A3: すでに完了した feature の救済は範囲外とする（scope.backfill: no-backfill）。merge スキルと merge-preflight は書き込まないまま
- A4: スクリプトが失敗しても、verify の結果記録と走行は止めない。deferred 指摘はそのまま残る（fail-closed）
- A5: minimal tier（VERIFICATION.md が無い）では、pass 済み ID 集合は TASK.md の Expected Result から verify が評価した ID だけで構成する。ID が無ければ集合は空で、どの指摘も更新しない
- A6: 既存テストが固定している文言（NFR2）は変えない
- A7: プラグインの version は変えない

## Implementation Phases (if applicable)

該当なし

## References

- REQUIREMENTS.md: feature-docs/verify-pass-resolves-deferred-findings/REQUIREMENTS.md
- worker-envelope.md: Untrusted-Input Handling
- tests/test_merge_preflight.py
- tests/test_review_phase_coverage_record.py
- tests/test_verify_rework_lineage_cap.py
- tests/test_develop_skill_rewiring.py
