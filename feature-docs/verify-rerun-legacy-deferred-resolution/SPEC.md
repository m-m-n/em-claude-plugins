# Feature: verify-rerun-legacy-deferred-resolution

## Overview

verify step に round / passed_ids が無い旧形式の workflow.yaml を持つ完了済み feature で verify をやり直したとき、develop SKILL.md の「#### verify pass による deferred 指摘の解決」と同じ手順を行う。スクリプトは変えず、SKILL.md の記述とテストで満たす。要件は `REQUIREMENTS.md` を参照する。

## Objectives

- 完了済み feature で verify をやり直したとき、review で deferred になった critical/high・category spec の指摘を、verify の合格に基づいて fixed にできるようにする。
- verify step に round / passed_ids が無い旧形式の workflow.yaml でも、verify のやり直しで resolve-verified-findings.py が実行され、merge-preflight.py が unresolved_findings で止まらないようにする。

## User Stories

### US1: 旧形式の workflow.yaml での verify のやり直しで deferred 指摘を解決する
develop のオーケストレーターとして、verify step に round / passed_ids が無い workflow.yaml で verify をやり直したときも同じ手順を行い、deferred 指摘を fixed にして merge-preflight.py を proceed にしたい。

**Acceptance Criteria:**
- [ ] AC1: develop SKILL.md の「#### verify pass による deferred 指摘の解決」に、verify step に round / passed_ids が無い workflow.yaml で verify をやり直したときも同じ手順を行い、round が 1 になり passed_ids を書き、pass なら対応づけとスクリプトの実行を行うことが書かれている。これがテストで固定されている。（FR1, FR4）
- [ ] AC3: verify step に round / passed_ids が無い workflow.yaml と、deferred・high・category spec の指摘を持つ最新 review round 記録の fixture で、verify のやり直しを記録してスクリプトを実行しコミットすると、指摘が fixed になり merge-preflight.py が proceed を返す。やり直しの前の状態では merge-preflight.py が unresolved_findings を返す。これがテストで固定されている。（FR5）

### US2: 対応づけの規則
develop のオーケストレーターとして、指摘の主張がその基準 ID の未達であれば書き添えがあっても対応づけ、それ以外の指摘は対応づけないようにしたい。

**Acceptance Criteria:**
- [ ] AC2: 同じ小節に、指摘の主張がその基準 ID の未達であれば原因の分析・修正案・範囲の判断が書き添えてあっても対応づけること、対応が曖昧な指摘・pass 済みでない別の基準の未達や別の欠陥も主張している指摘・本文に ID が現れるだけの指摘は対応づけないことが書かれている。これがテストで固定され、旧文言を固定していたテストが更新されている。（FR3, FR4）

### US3: 既存のスクリプトと文書を変えない
em-workflow の保守者として、既存のスクリプト・既存テスト・先行 feature の文書が変わらないまま、テストスイートが通るようにしたい。

**Acceptance Criteria:**
- [ ] AC4: resolve-verified-findings.py、merge-preflight.py、tests/test_resolve_verified_findings.py の既存テスト、先行 feature の REQUIREMENTS.md / SPEC.md が変わっておらず、python3 -m unittest discover -s tests が通る。（FR2, FR6）

## Technical Requirements

### Functional Requirements
- **FR1:** 旧形式の workflow.yaml での verify のやり直し — develop SKILL.md の「#### verify pass による deferred 指摘の解決」に、verify step に round / passed_ids が無い workflow.yaml で verify をやり直したときも同じ手順を行うことを明記する。その場合 round は 1 になり、result を書くのと同じ workflow.yaml の書き込みで passed_ids を書く。result が pass なら対応づけとスクリプトの実行を行う。
- **FR2:** スクリプトは変えない — em-workflow/scripts/resolve-verified-findings.py は変えない。round >= 1 の条件と、その条件を固定する既存テスト（tests/test_resolve_verified_findings.py）は変えない。
- **FR3:** 対応づけの規則 — develop SKILL.md の同じ小節の対応づけの規則を次のとおりにする。指摘の主張がその基準 ID の未達であれば、原因の分析・修正案・範囲の判断が書き添えてあっても対応づける。対応が曖昧な指摘、pass 済みでない別の基準の未達や別の欠陥も主張している指摘、本文に ID が現れるだけの指摘は対応づけない。
- **FR4:** 手順の記述をテストで固定する — tests/test_verify_pass_resolution_procedure.py で FR1 と FR3 の記述を固定する。FR3 で置き換える現行の除外文言「未達そのもの以外の内容を含む指摘は対応づけない」を固定している箇所（TestAC2MappingRule.test_ac2_ambiguous_and_mixed_content_findings_are_left_out）は、新しい文言に合わせて更新する。
- **FR5:** やり直しから merge-preflight までのシナリオテスト — verify step に round / passed_ids が無く、最新の review round 記録に deferred・high・category spec の指摘（ある受け入れ条件の未達）を持つ fixture で、verify のやり直し（round 1、その受け入れ条件を含む passed_ids、result pass の記録）、対応づけファイル、resolve-verified-findings.py の実行、integration ブランチへのコミットを行うと、指摘が fixed になり merge-preflight.py が proceed を返すことをテストで固定する。
- **FR6:** 変えない文書とスクリプト — merge-preflight.py の判定条件は変えない。先行 feature verify-pass-resolves-deferred-findings の REQUIREMENTS.md / SPEC.md は変えない。verify のやり直しの扱いはこの feature の文書に書く。

### Non-Functional Requirements
- **NFR1 - テストの形:** テストは標準ライブラリだけを import し、スクリプトは子プロセスとして実行する（tests/test_resolve_verified_findings.py と同じ形）。テストは一時ディレクトリの git リポジトリを fixture にする。
- **NFR2 - SKILL.md の固定文言を保つ:** develop SKILL.md の小節は、既存の固定文言（interactive でも batch でも同じ、ゲートも質問も batch の non-packet ゲートも追加しない、未達そのものであるときだけ、本文に ID が現れているだけでは足りない、対応が曖昧な指摘、Untrusted-Input Handling の参照など）を保つ。gate_id / AskUserQuestion / batch-policies.yaml を書かない。verify の残りに deferred を与える文言を書かない。verify フェーズ内で category の語彙を backtick で囲まない。
- **NFR3 - ゲートを追加しない:** ゲート・質問・batch の non-packet ゲートを追加しない。手順は interactive と batch で同じ。
- **NFR4 - version を手で変えない:** プラグインの version は手で変えない。

## Implementation Approach

### Architecture

スクリプトは変えない（FR2, FR6）。変更は develop SKILL.md の記述と tests/ 配下のテストに限る。

**Component Diagram:**
```
develop SKILL.md「#### verify pass による deferred 指摘の解決」
  ├── FR1: 旧形式の workflow.yaml での verify のやり直し
  └── FR3: 対応づけの規則
tests/test_verify_pass_resolution_procedure.py   ── FR1 / FR3 の記述を固定（FR4）
シナリオテスト（tests/ 配下）                     ── FR5
resolve-verified-findings.py / merge-preflight.py ── 変更なし（子プロセスとして実行）
```

### Data Flow

```
旧形式の workflow.yaml（verify step に round / passed_ids が無い）
  + 最新 review round 記録（deferred・high・category spec の指摘）
  → merge-preflight.py: unresolved_findings
  → verify のやり直し（round 1、passed_ids、result pass を同じ書き込みで記録）
  → 対応づけファイル（stable_id とその基準 ID）
  → resolve-verified-findings.py
  → integration ブランチへのコミット
  → 指摘: resolution fixed + verify_resolution
  → merge-preflight.py: proceed
```

既存の読み方: round が無い workflow.yaml は round 0、passed_ids が無いものは空集合として読む（workflow-schema.md「`round` and `passed_ids`」の既存規則）。この規則は変えない。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- em-workflow/scripts/resolve-verified-findings.py: 変更せず、テストから子プロセスとして実行する。
- merge-preflight.py: 判定条件を変更せず、テストから子プロセスとして実行する。
- workflow-schema.md「`round` and `passed_ids`」: 既存の読み方の規則。

**External Dependencies:**
- なし（テストは標準ライブラリだけを import する）

### File Structure

```
develop SKILL.md                                  # 「#### verify pass による deferred 指摘の解決」を更新
tests/
├── test_verify_pass_resolution_procedure.py      # FR1 / FR3 の固定を追加、旧文言の固定を更新
└── （FR5 のシナリオテスト）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/verify-rerun-legacy-deferred-resolution/**`
- `test-docs/verify-rerun-legacy-deferred-resolution/**`

`feature-docs/verify-rerun-legacy-deferred-resolution/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/verify-rerun-legacy-deferred-resolution/**` covers `test-docs/verify-rerun-legacy-deferred-resolution/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/verify-rerun-legacy-deferred-resolution/` directory at all; the declared
`test-docs/verify-rerun-legacy-deferred-resolution/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: SKILL.md の小節に、round / passed_ids が無い workflow.yaml での verify のやり直しに同じ手順を行うこと、round が 1 になること、passed_ids を書くこと、pass なら対応づけとスクリプトの実行を行うことが書かれていることを確かめる。（AC1: FR1, FR4）
- [ ] TS-2: SKILL.md の小節に、書き添え（原因の分析・修正案・範囲の判断）があっても対応づけること、曖昧な指摘・別の基準の未達や別の欠陥も主張する指摘・ID が現れるだけの指摘を対応づけないことが書かれていること、旧文言「未達そのもの以外の内容を含む指摘は対応づけない」が無いことを確かめる。（AC2: FR3, FR4）

### Integration Tests
- [ ] TS-3: 旧形式の workflow.yaml（verify step に round / passed_ids が無い、全 step completed / skipped）と round2 の記録（deferred・high・category spec の指摘 1 件）をコミットし、merge-preflight.py が unresolved_findings を返すことを確かめる。（AC3: FR5）
- [ ] TS-4: 同じ fixture で verify step に round 1・その受け入れ条件を含む passed_ids・result pass を記録し、stable_id とその基準 ID の対応づけファイルで resolve-verified-findings.py を実行し、コミットしたあと、指摘が resolution fixed と verify_resolution を持ち、merge-preflight.py が proceed を返すことを確かめる。（AC3: FR5）
- [ ] TS-5: python3 -m unittest discover -s tests を実行し、既存テストを含めて通ることを確かめる。（AC4: FR2, FR6）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- やり直しの前の状態（verify step に round / passed_ids が無い）は TS-3 で扱う。
- 対応づけない指摘（対応が曖昧な指摘、pass 済みでない別の基準の未達や別の欠陥も主張している指摘、本文に ID が現れるだけの指摘）の記述は TS-2 で扱う。

### Performance Tests
該当なし

## Security Considerations

- **Input Validation:** develop SKILL.md の小節は Untrusted-Input Handling の参照を保つ（NFR2）。
- その他: 該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| unresolved_findings | やり直しの前の状態で merge-preflight.py が返す（TS-3） | - | - |

### Error Flow

```
result が pass でない → 対応づけとスクリプトの実行を行わない
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] python3 -m unittest discover -s tests が通る

## Assumptions

- A1: AC1 はスクリプトを変えず、SKILL.md の記述とテストで満たす。resolve-verified-findings.py の round >= 1 の条件と既存テストは変えない。
- A2: 対応づけは、指摘の主張がその基準 ID の未達であれば書き添えがあっても行う。曖昧な指摘、pass 済みでない別の基準の未達や別の欠陥も主張する指摘、ID が現れるだけの指摘は除外する。現行の除外文言を置き換えるため tests/test_verify_pass_resolution_procedure.py の固定文言を合わせて更新する。
- A3: 先行 feature verify-pass-resolves-deferred-findings の REQUIREMENTS.md / SPEC.md は変えない。verify のやり直しの扱いはこの feature の文書に書く。
- A4: round が無い workflow.yaml は round 0、passed_ids が無いものは空集合として読む（workflow-schema.md「`round` and `passed_ids`」の既存規則）。この規則は変えない。
- A5: verify をやり直す起点（verify を pending に戻す操作）はこの feature の範囲外とする。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/verify-rerun-legacy-deferred-resolution/REQUIREMENTS.md`
- develop SKILL.md「#### verify pass による deferred 指摘の解決」
- workflow-schema.md「`round` and `passed_ids`」
- tests/test_verify_pass_resolution_procedure.py
- tests/test_resolve_verified_findings.py
