# Feature: self-write-exclusivity-window

## Overview

Rule R1 の返却時の手順に、比較の後、記録の phase-state 書き込みの前に行う再確認を足す。排他の前提の適用区間を、記録の phase-state 書き込みの完了まで延ばし、関係する文書とドキュメントテストを揃える。要件の詳細は `feature-docs/self-write-exclusivity-window/REQUIREMENTS.md` を参照する。

## Objectives

- scope verification の後、Layer 5 の記録より前に入った外部の書き換えが、self-write の置換で worker の成果物として隠れて記録されないようにする。
- 排他の前提の適用区間を、それに依拠する R1 の返却時の手順（再計算・置換・比較・再確認・Layer 5 の記録）と食い違わない形で述べる。

## User Stories

### US1: 返却時の再確認

オーケストレーターは、比較の後、記録の phase-state 書き込みの前に self-write set の各パスを再確認し、scope verification の後の書き換えを stale にする。

**Acceptance Criteria:**
- [ ] AC-1: worker-envelope.md R1『Order』が、比較の後、artifacts と self_write_set を記録する phase-state 書き込みの前に行う再確認を、オーケストレーターの手順として述べている。そこには、self-write set の各パスの現在の blob id・mode・種別を scope verification の観測値と比べることと、不一致または再確認の失敗で stale になることが含まれる。（FR1, FR2）
- [ ] AC-6: 再現手順（designer に extend_only で tokens.yaml を書かせ、scope verification の直後に外部が既存キーを書き換える）は、文書の規則上、再確認の不一致で stale になる。書き換え後の内容は Layer 5 に記録されない。（FR1, FR2）

### US2: 排他の前提の区間と関係文書の整合

**Acceptance Criteria:**
- [ ] AC-2: worker-envelope.md『Exclusivity assumption during dispatch』と create-spec-phase.md『Scope of applicability』が、同じ終点（記録の phase-state 書き込みの完了。stale のときはその判定まで）を述べている。（FR3, FR4）
- [ ] AC-3: Known limit が、scope verification より前の競合を前提に委ねる既存の文言を保ったまま、その後の変更は再確認が検出することを述べている。（FR5）
- [ ] AC-4: artifact-digest.md『Layer 5 recording』の『When』が、R1 の比較と再確認の後に記録の書き込みを行うことを、R1 を参照して述べている。（FR6）
- [ ] AC-5: 3 つの dispatch 箇所が、比較と記録書き込みの間にある再確認を R1 の参照として示しており、規則を繰り返して書いていない。既存の順序の anchor は保たれている。（FR7）

### US3: 再発の検出

**Acceptance Criteria:**
- [ ] AC-7: 新しいテストは、修正前の文書に対応する forged-text では失敗し、修正後の文書では通る。python3 -m unittest discover -s tests が全部通る。（FR8）

## Technical Requirements

### Functional Requirements
- **FR1:** R1 Order に返却時の再確認を足す。worker-envelope.md の Rule R1『Order』に、比較の後の手順を足す。オーケストレーターは、比較で stale にならず、Layer 5 の Calculation を終えた後で、artifacts と self_write_set を記録する phase-state 書き込みの前に、self-write set の各パスの現在の git blob id（`git hash-object --`）と mode・種別（file / symlink / absent）を読み直す。そして scope verification がそのパスについて観測した変更後の値と比べる。1 つでも不一致があるか、再確認を実行できなければ（読み取りの失敗を含む）、result を stale として扱う。stale の扱いは scope verification の stale handling（create-spec-phase.md）に従う。self-write set が空なら、再確認は何もせずに通る。既存の 4 段の手順とその文言は残し、再確認を後ろに足す。
- **FR2:** 再確認の比較対象。再確認では、scope verification と同じ種類の値（git blob id、mode、種別）どうしを比べる。raw-byte の sha256（artifact-digest.md の Calculation、digest_inputs）とは混ぜない。比較の基準にする観測値は、同じ run の scope verification が出した observed change set の値とする。
- **FR3:** worker-envelope.md の排他の前提の区間を延ばす。『Exclusivity assumption during dispatch』の適用区間を、dispatch の scope snapshot の取得から、run の artifacts と self_write_set を記録する phase-state 書き込みの完了までとする。written_artifacts が空の run では、返却された status と self_write_set を記録する書き込みの完了まで。result が stale と判定された場合は、その判定までとする。五つの worker に限ること、恒常的な制約ではないこと、review の wave-parallel auto-fix loop が例外であることは変えない。
- **FR4:** create-spec-phase.md の区間を揃える。『Exclusivity assumption (normative)』の『Scope of applicability』を、FR3 と同じ終点で述べる。worker-envelope.md と食い違わないようにする。
- **FR5:** Known limit の範囲を言い直す。R1 の『Known limit』は、scope verification より前に worker と別の主体が同じ permitted path を変えた場合を排他の前提に委ねる記述として残す（現在の文言を保つ）。そのうえで、scope verification の後の変更は FR1 の再確認が検出すること、再確認から記録までの残りの窓は延ばした区間が覆うことを足す。
- **FR6:** artifact-digest.md の Layer 5『When』を揃える。artifact-digest.md の『Layer 5 recording』の『When』を、layer 4 を通っただけでなく、R1 の返却時の比較と再確認で stale にならなかった後に記録の書き込みを行うことが読み取れる形に直す。R1（worker-envelope.md の『Recomputation and comparison timing』）を参照し、手順は繰り返して書かない。Calculation が再確認の前に走ることと、記録の書き込みが再確認の後に来ることを食い違わせない。
- **FR7:** 3 つの dispatch 箇所が参照で揃う。develop SKILL.md の design step 5、create-plan-phase.md の §8、rework-task-synthesis.md の §10 は、再確認を R1 の参照として示す。順序は、比較（または validate-worker-output.py での検証）の後、Layer 5 の記録と self_write_set の記録の書き込みの前。再確認で不一致か失敗なら stale になる。membership の表、置換、再確認の比較規則は繰り返して書かない。既存の『scope verification → self-write-digest.py → Layer 5 recording』の順と、各箇所の既存の文言は保つ。
- **FR8:** 再発を検出するドキュメントテスト。tests/ に unittest のドキュメントテストを足すか、既存のものを強める。固定する内容は 4 つ。(a) 2 文書の区間の終点が phase-state の記録書き込みまで延びていること。(b) R1 Order の再確認の手順。オーケストレーターが行い、blob id・mode・種別を scope verification の観測値と比べ、不一致や失敗で stale になり、比較の後かつ記録の前に置かれること。(c) artifact-digest.md の『When』。(d) 3 つの dispatch 箇所の参照と順序。どの probe にも forged-text の対照を付け、旧い文言で probe が反応することを示す。

### Non-Functional Requirements
- **NFR1 - テストの形式:** テストは Python 標準ライブラリの unittest だけを使い、python3 -m unittest discover -s tests で通る。ファイル名は test_<target>.py、クラス名は Test<Behavior>、メソッド名は test_<condition>_<expected_result> にする（test/README.md）。
- **NFR2 - テストの頑健性:** ドキュメントテストは見出しで切り出して空白を正規化した文字列で検証する。改行位置にも文書全体の一致にも依存しない。
- **NFR3 - 既存テストの維持:** 既存のテストは通ったままにする。R1 の領域に足す文で digest に触れるものは、オーケストレーターを主語にするか否定文にする（test_ac5_every_digest_sentence_of_the_self_write_rule_names_the_orchestrator_or_is_negated、find_worker_directed_digest_instructions、check_worker_digest_stance）。
- **NFR4 - R1 のラベル:** R1 にラベル付きのブロックを足す場合は、tests/test_self_write_digest_docs.py の R1_LABELS にも加え、各ラベルが 1 回だけ現れるようにする。再確認を既存の『Order』ブロックの中に書くなら、ラベルは足さない。
- **NFR5 - worker-envelope.md の不変部分:** worker-envelope.md に expect_digest のトークンを入れない。R1 の正規化の段落と digest_source の 7 つのキーは変えない。
- **NFR6 - スクリプトの不変:** scripts/self-write-digest.py は変えない（スクリプトは digest を計算しない）。再確認はオーケストレーターが行う。
- **NFR7 - version:** plugin の version は変更しない。

## Implementation Approach

### Architecture

変更はプロトコルの Markdown とドキュメントテストだけで、UI 成果物は無い。

**Component Diagram:**
```
worker-envelope.md R1『Order』（再確認の規則の SSOT）
  ├── worker-envelope.md『Known limit』『Exclusivity assumption during dispatch』
  ├── create-spec-phase.md『Scope of applicability』（同じ終点）
  ├── artifact-digest.md『Layer 5 recording』の『When』（R1 を参照）
  └── 3 つの dispatch 箇所（R1 を参照）
        ├── develop SKILL.md の design step 5
        ├── create-plan-phase.md の §8
        └── rework-task-synthesis.md の §10
tests/（ドキュメントテスト）
```

### Data Flow

返却時の手順の順序:

```
scope verification（observed change set）
  → 現在の digest_source の再計算
  → self-write-digest.py（置換）
  → 比較（stale でなければ次へ）
  → Layer 5 の Calculation
  → 再確認（self-write set の各パスの blob id・mode・種別を観測値と比べる。不一致・失敗で stale）
  → artifacts と self_write_set を記録する phase-state 書き込み
```

- written_artifacts が空の run では Layer 5 の Calculation が走らない。再確認は比較の後、status と self_write_set を記録する書き込みの前に行う。
- 排他の前提の区間: dispatch の scope snapshot の取得から、記録の phase-state 書き込みの完了まで。stale のときはその判定まで。

### API Design

該当なし

### Database Schema

該当なし（phase-state.md のスキーマは変えない）

### Dependencies

**Internal Dependencies:**
- `references/contracts/worker-envelope.md`: Rule R1『Order』『Known limit』『Recomputation and comparison timing』『Exclusivity assumption during dispatch』
- `references/phases/create-spec-phase.md`: scope verification、stale handling、『Exclusivity assumption (normative)』の『Scope of applicability』
- `references/artifact-digest.md`: 『Calculation』『Layer 5 recording』
- `tests/test_self_write_digest_docs.py`: 既存の Order・Known limit・digest-sentence のテスト、R1_LABELS

**External Dependencies:**
- Python 標準ライブラリ unittest

### File Structure

対象文書:

- `references/contracts/worker-envelope.md`
- `references/phases/create-spec-phase.md`
- `references/artifact-digest.md`
- develop SKILL.md
- create-plan-phase.md
- rework-task-synthesis.md
- `tests/` のドキュメントテスト

変更しないもの:

- `scripts/self-write-digest.py`
- `references/phase-state.md`
- analyst-contract.md:215-220
- spec-writer-contract.md:88-91、artifact-digest.md:116-119

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/self-write-exclusivity-window/**`
- `test-docs/self-write-exclusivity-window/**`

`feature-docs/self-write-exclusivity-window/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/self-write-exclusivity-window/**` covers `test-docs/self-write-exclusivity-window/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: worker-envelope.md の Exclusivity 節で、区間の終点が記録の phase-state 書き込みを名指していることを確かめる。旧文言（'through the end of that dispatch's scope verification' で終わるもの）の forged-text では probe が反応する。（AC-2）
- [ ] TS-2: create-spec-phase.md の Scope of applicability について、TS-1 と同じことを確かめる。旧文言（'through the end of verification'）の forged-text を対照にする。（AC-2）
- [ ] TS-3: R1 Order の切り出しに、再確認の要素が既存 4 段の anchor の後、記録の前の順で現れることを確かめる。要素は、オーケストレーターが主語であること、blob id・mode・種別、scope verification の観測値、不一致または失敗で stale、の 4 つ。再確認を欠いた forged の Order では probe が反応する。（AC-1）
- [ ] TS-4: 既存の Order・Known limit・digest-sentence のテスト（tests/test_self_write_digest_docs.py）がそのまま通ることを確かめる。（AC-1, AC-3）
- [ ] TS-5: Known limit が既存の 3 句を保ち、scope verification の後の変更は再確認が検出することを述べていることを確かめる。（AC-3）
- [ ] TS-6: artifact-digest.md の Layer 5 recording の『When』が R1 を参照し、比較と再確認の後の記録を述べていることを確かめる。旧文言（'after layer 4 (scope verification) passes' だけのもの）の forged-text を対照にする。（AC-4）
- [ ] TS-7: 3 つの dispatch 箇所それぞれで、SCRIPT_TOKEN → 再確認の参照 → Layer 5 recording（rework §10 では SCRIPT_TOKEN → step 3 validates → 再確認 → 記録）の順を確かめる。R1 を引用していることと、規則を繰り返していないことも確かめる。forged-text を対照にする。（AC-5）

### Integration Tests
- [ ] TS-8: python3 -m unittest discover -s tests の全体が通る。（AC-7）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] self-write set が空の run では、再確認は何もせずに通る。
- [ ] written_artifacts が空の run では Layer 5 の Calculation が走らない。再確認は比較の後、status と self_write_set を記録する書き込みの前に行う。
- [ ] created のパスは、absent から file への変化として観測される。再確認では、現在もその blob id・mode・種別のままかを見る。
- [ ] regenerate のターゲットは、source が member のときだけ self-write set に入る。入った場合は再確認の対象になる。
- [ ] 再確認の時点でパスが消えている、symlink に変わっている、または読めない場合は、不一致または失敗として stale にする。
- [ ] 書き換えて元に戻した（ABA）場合は、内容が同じなので検出されず、実害も無い。
- [ ] HEAD が動いた stale の経路では、再計算も再確認も記録も走らない。区間は stale の判定で終わる。
- [ ] 再開時（substitute_only）は、永続化された self_write_set を使う。記録の後の書き換えは、Resume decision table の read input 5（成果物の本文と記録した digest の比較）が検出する。

### Performance Tests

該当なし

## Security Considerations

- 排他の前提は、延ばした後も lock や hook では強制しない。再確認から記録の書き込みまでの窓は、前提で覆う。

## Error Handling

### Error Codes

該当なし

### Error Flow

```
再確認で不一致、または再確認を実行できない（読み取りの失敗を含む）
  → result を stale として扱う
  → scope verification の stale handling（create-spec-phase.md）に従う
```

## Performance Optimization

該当なし

## Assumptions

- A1: requirements-analyst の『Exclusivity assumption』節（analyst-contract.md:215-220）は変更しない。
- A2: spec-writer-contract.md:88-91 と artifact-digest.md:116-119 にある、pre-dispatch verification から worker の書き込みまでを排他の前提が守るという記述は変更しない。
- A3: 再確認の基準にする scope verification の観測値は、同じ run の中で保持するだけにして、phase-state には永続化しない。phase-state.md のスキーマは変えない。
- A4: plugin の version は変更しない（patch は Actions が上げる）。
- A5: 排他の前提は、延ばした後も lock や hook では強制しない。再確認から記録の書き込みまでの窓は、前提で覆う。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 から AC-7 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/self-write-exclusivity-window/REQUIREMENTS.md`
- `references/contracts/worker-envelope.md`
- `references/phases/create-spec-phase.md`
- `references/artifact-digest.md`
