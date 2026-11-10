# Feature: spec-change-rework-reentry

## Overview

rework の SPEC変更遷移を経たフィーチャーが、`workflow.yaml` の手編集なしで review → verify → retrospect まで進むようにする。SPEC変更遷移で verify も pending に戻し、implement Step I.0 に SPEC変更再進入の経路を加え、rework-task-synthesis.md Section 11 の Invariant 1 の対象範囲を明記する。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- rework の SPEC変更遷移を経たフィーチャーが、`--batch` 実行と対話実行のどちらでも、`workflow.yaml` を誰も手で編集せずに review → verify → retrospect まで進む。
- 無人の `--batch` 実行で自動リトライでは解消できない 2 つの停止を取り除く。implement Step I.0 の ABORT と、古い `verify: failed` に対する停止条件 3 の発火。

## User Stories

### US1: SPEC変更遷移の後、手編集なしで retrospect まで進む
em-workflow の実行者として、SPEC変更遷移を経たフィーチャーを `workflow.yaml` の手編集なしで review → verify → retrospect まで進めたい。

**Acceptance Criteria:**
- [ ] AC1: 3 文書すべてで、SPEC変更遷移の手順 2 が verify を含み、5 手順の番号付けが保たれている。
- [ ] AC5: rework-task-synthesis.md の Invariant 1 が SPEC変更遷移を対象外として挙げ、Step I.0 を引用している。不変条件は引き続き 11 件である。
- [ ] AC6: develop/SKILL.md「verify フェーズ」の 6 が、SPEC変更遷移によって verify が pending に戻ることを引用している。

### US2: 無人実行で解消できない 2 つの停止を取り除く
em-workflow の実行者として、無人の `--batch` 実行が implement Step I.0 の ABORT と、古い `verify: failed` に対する停止条件 3 の発火で止まらないようにしたい。

**Acceptance Criteria:**
- [ ] AC2: implement-phase.md Step I.0 が SPEC変更再進入を進入経路として挙げ、pending タスク 0 件かつ failed タスク 0 件でその経路に進入しても ABORT しないことを記載している。
- [ ] AC3: Step I.0 が、タスク 0 件の SPEC変更再進入では implementer を起動せず、Step I.3 でフェーズを完了することを記載している。
- [ ] AC4: SPEC変更再進入ではなく、pending タスクも failed タスクも無い非初回進入に対しては、即時の ABORT が引き続き成り立つ。SPEC変更再進入を識別する基準は、コミット済みの事実だけで記述されている。
- [ ] AC7: この変更より前の文言に対して実行すると、新しいテストが FR7 の (a)〜(d) のそれぞれで失敗する。

## Technical Requirements

### Functional Requirements
- **FR1:** SPEC変更遷移で verify も pending に戻す。SPEC変更遷移の手順 2（rework-task-synthesis.md Section 10 の `When rework needs a SPEC.md change` ブロック）を、create-plan / implement / review → pending から create-plan / implement / review / verify → pending に変更する。rework-planner-contract.md の `## Specification-change transition` にある 5 手順の手順 2、および agents/rework-planner.md の `## Specification-change transition` にある 5 手順の要約にも同じ変更を入れる。手順数 5 と番号付け（1〜5）は維持する。
- **FR2:** Step I.0 が SPEC変更再進入を正当な進入経路として認識する。implement-phase.md Step I.0（step 5）の Re-entry precondition の進入経路に、SPEC変更再進入を追加する。これは SPEC変更遷移（rework-task-synthesis.md Section 10）と、それに続く create-spec → create-plan の再実行の後に、`implement: pending` へ進入する経路である。この経路では、status == pending のタスクが 0 件かつ reconciled state が failed のタスクが 0 件（全タスクが merged）の状態で進入しても、プロトコルエラーではなく、フェーズを ABORT しない。
- **FR3:** タスク 0 件の SPEC変更再進入はフェーズ完了へ直行する。FR2 の経路で pending タスクが無い状態で進入した場合、implementer を起動しない。Step I.2 のタスクループを飛ばし、Step I.3 のフェーズ完了手順（capture → refresh → write → commit）で implement を completed にする。空のキューを待ってターンを終えない。再計画で新しいタスクが 1 件以上登録された場合は、通常どおり Step I.2 を実行する。
- **FR4:** それ以外の状態では ABORT を維持する。FR2 の SPEC変更再進入ではない非初回進入で、pending タスクが無く、reconciled state が failed のタスクも無い場合は、現行どおり即座にプロトコルエラーとして ABORT する。SPEC変更再進入の識別は、コミット済みの事実（workflow.yaml と phase-state/rework.yaml の spec_change 記録、および git のコミット祖先関係）だけから行い、セッションの記憶や worker の自然言語出力は使わない。
- **FR5:** Invariant 1 の対象範囲を明記する。rework-task-synthesis.md Section 11 の Invariant 1（implement が pending に戻る前に少なくとも 1 件のタスクが登録される）は、SPEC変更遷移を対象としないことを明記する。この遷移はタスクを登録しない（Invariant 9）が、implement を pending に戻す。その再進入の前提条件は implement-phase.md Step I.0 が所有する（引用のみで再掲しない）。新しい不変条件は追加せず、件数は 11 のまま保つ。
- **FR6:** develop スキルからの相互参照。develop/SKILL.md「verify フェーズ」の項目 6 に、rework-planner が `gate_id` `rework.spec-change` を返し SPEC変更遷移が選ばれた場合、rework-task-synthesis.md Section 10 によって verify も pending に戻ることを引用として追記する（遷移の内容は再掲しない）。停止条件 3 の発火条件は変えない。
- **FR7:** 再発を検知するテスト。どちらの停止の再発も検知する unittest のテスト（標準ライブラリのみ）を tests/ 配下に追加する。(a) 3 文書すべてで SPEC変更遷移の手順 2 が verify を含む。(b) Step I.0 が SPEC変更再進入の経路、その経路では pending タスク 0 件でも ABORT しないこと、Step I.3 へ進むことを記載している。(c) SPEC変更再進入以外の状態に対する ABORT が残っている。(d) Invariant 1 が SPEC変更遷移を対象外として明記している。このスイートの慣例に従い、各マッチャーには、その記述を欠く合成テキストに対する否定の証明を付ける。
- **FR8:** 影響を受ける既存の固定テストを更新する。FR1〜FR5 によって固定文字列・ダイジェスト・件数が変わる既存テストを、同じ変更の中で新しい文言に更新する（該当する範囲で tests/test_failed_kind_resume_reentry.py、tests/test_rework_synthesis_contract.py、tests/test_rework_docs_only_route_doc.py、tests/test_worker_contracts_planning.py）。引き続き成り立つアサーションは意味を保つ。これには、不変条件 11 件の件数、5 手順の番号付け、前提条件が起動選択より前に現れることを含む。

### Non-Functional Requirements
- **NFR1 - 所有の分担:** 既存の所有の分担を保つ。各文書は相手のルールを引用し、再掲しない（Invariant 1 ↔ Step I.0、Section 10 ↔ rework-planner-contract / agents/rework-planner.md、SKILL.md ↔ Section 10）。
- **NFR2 - version:** em-workflow の version を変更しない（main への push 時に Actions が patch を上げる）。
- **NFR3 - テスト:** テストは Python 標準ライブラリの unittest だけを使い、`python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` の両方が通る。
- **NFR4 - 文書の言語と秘匿:** 各文書は既存の言語で書く（implement-phase.md、rework-task-synthesis.md、契約・エージェントのファイルは英語、SKILL.md は日本語）。変更した文書は Notion の URL とホームディレクトリ配下の絶対パスを含まない。
- **NFR5 - 他の進入経路:** 他の進入経路の既存の振る舞いを変えない。対象は、初回の通過、既存の rework 再進入、batch の infra 自動再開、Step A.6 の failed 進入の復元。

## Implementation Approach

### Architecture

**System Architecture:**

SPEC変更遷移から retrospect までの流れ。

```
rework（gate_id rework.spec-change、SPEC変更遷移を選択）
  → 手順 2: create-plan / implement / review / verify → pending        (FR1)
  → create-spec → create-plan の再実行
  → implement Step I.0: SPEC変更再進入を識別                          (FR2, FR4)
      ├─ pending タスク 1 件以上 → Step I.1 → Step I.2 → Step I.3
      └─ pending タスク 0 件     → Step I.1 → Step I.3（Step I.2 を飛ばす） (FR3)
  → review → verify → retrospect
```

**Component Diagram:**

```
rework-task-synthesis.md Section 10   ←引用─ rework-planner-contract.md
  （SPEC変更遷移）                    ←引用─ agents/rework-planner.md
                                      ←引用─ develop/SKILL.md「verify フェーズ」6
rework-task-synthesis.md Section 11 Invariant 1 ─引用→ implement-phase.md Step I.0
```

### Data Flow

SPEC変更再進入は、コミット済みの事実だけから識別し、次のすべてが成り立つことを条件とする（A2）。

1. create-spec と create-plan が completed であり、implement が base_commit と以前の completed_at_commit を持つ。
2. phase-state/rework.yaml に、`consumed: true` かつ `replan_authorized: false` の spec_change 記録がある。
3. 以前の implement の completed_at_commit が記録の recorded_at_commit の真の祖先であり、recorded_at_commit が現在の integration の先端の祖先である（タイムスタンプは比較しない）。
4. その記録を伴う SPEC変更遷移が implement を pending に戻したことを、コミット履歴が示している（tier-upgrade の手順も同じ記録を書くが implement を pending に戻さないため、フラグだけでは足りない）。
5. タスク集合が空ではなく、全タスクが merged である。

同じ再進入の Step I.1 が書いた in_progress からの再開も受け付ける（A2）。

タスク 0 件の SPEC変更再進入でも、Step I.1（gitignore guard、base_commit の保持、implement → in_progress のコミット）は通常どおり実行する。飛ばすのは Step I.2 だけで、Step I.3 は作業が 0 件でも completed_at_commit を更新し、同じ記録が後の再進入に持ち越されないようにする（A3）。

verify を pending に戻すのは orchestrator の遷移書き込みで行う（worker のパッチではない）。設定するのは status だけで、verify の result / failed_items は verify の再実行時に上書きされる（A4）。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- rework-task-synthesis.md Section 10: SPEC変更遷移の所有元（FR1）
- rework-task-synthesis.md Section 11: Invariant 1 と Invariant 9（FR5）
- implement-phase.md Step I.0〜I.3: 進入の前提条件とフェーズ完了手順（FR2〜FR4）
- rework-planner-contract.md、agents/rework-planner.md: SPEC変更遷移の 5 手順（FR1）
- develop/SKILL.md「verify フェーズ」: 項目 6 と停止条件 3（FR6）

**External Dependencies:**
- Python 標準ライブラリの unittest（NFR3）

### File Structure

変更対象の文書:

```
rework-task-synthesis.md       # Section 10 手順 2（FR1）、Section 11 Invariant 1（FR5）
rework-planner-contract.md     # ## Specification-change transition 手順 2（FR1）
agents/rework-planner.md       # ## Specification-change transition 要約の手順 2（FR1）
implement-phase.md             # Step I.0 Re-entry precondition（FR2〜FR4）
develop/SKILL.md               # 「verify フェーズ」項目 6（FR6）
```

テスト:

```
tests/
├── （新規）再発検知テスト                        # FR7
├── test_failed_kind_resume_reentry.py           # 該当する範囲で更新（FR8）
├── test_rework_synthesis_contract.py            # 該当する範囲で更新（FR8）
├── test_rework_docs_only_route_doc.py           # 該当する範囲で更新（FR8）
└── test_worker_contracts_planning.py            # 該当する範囲で更新（FR8）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/spec-change-rework-reentry/**`
- `test-docs/spec-change-rework-reentry/**`

`feature-docs/spec-change-rework-reentry/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/spec-change-rework-reentry/**` covers `test-docs/spec-change-rework-reentry/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/spec-change-rework-reentry/` directory at all; the declared
`test-docs/spec-change-rework-reentry/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 3 文書から SPEC変更遷移の手順 2 を抜き出し、verify を含むことを確認する（空白は正規化する）。否定の証明: 旧来の 3 段の文言がマッチャーで失敗する。（FR1）
- [ ] TS-2: implement-phase.md の Step I.0 の節を抜き出し、SPEC変更再進入の経路、pending タスク 0 件で ABORT しないこと、Step I.3 へ進むことの記載を確認する。否定の証明: 現行の 3 経路の文言が失敗する。（FR2, FR3）
- [ ] TS-3: Step I.0 の節に、SPEC変更再進入以外の状態に対する即時の ABORT が残っていることを確認する。（FR4）
- [ ] TS-4: Section 11 の不変条件が 11 件であり、Invariant 1 が SPEC変更遷移を対象外として挙げ、Step I.0 を引用していることを確認する。（FR5）
- [ ] TS-5: develop/SKILL.md「verify フェーズ」の項目 6 が、SPEC変更遷移によって verify が pending に戻ることを引用していることを確認する。（FR6）

### Integration Tests
- [ ] TS-6: 既存の固定を更新した後、スイート全体と check-plugin-invariants.py が通る。（FR8, NFR3）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
該当なし

### Performance Tests
該当なし

## Security Considerations

該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| — | プロトコルエラー: 非初回進入、SPEC変更再進入ではない、pending タスクが無い、reconciled state が failed のタスクが無い（FR4） | — | 即座に ABORT する |

### Error Flow

```
implement 非初回進入 → SPEC変更再進入か（コミット済みの事実で判定）
  ├─ はい → pending 0 件なら Step I.3 へ
  └─ いいえ → pending 0 件かつ failed 0 件なら即座に ABORT
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1〜AC7（User Stories を参照）を満たす
- [ ] AC8: `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` の両方が通る

## Assumptions

- A1: 修正方針は、Step I.0 に SPEC変更再進入の経路を加え（FR2/FR3）、Invariant 1 の対象範囲を明記する（FR5）こと。再計画でタスクが 0 件のとき create-plan の直後に implement を completed に戻す案は採らない。この案は新しい書き込み主体を要し、2 つの書き込みの間で中断すると同じ停止が残る（Codex 相談で決定）。
- A2: SPEC変更再進入の識別条件（Data Flow の 1〜5 と、Step I.1 が書いた in_progress からの再開の受け付け）（Codex 相談で決定）。
- A3: タスク 0 件の SPEC変更再進入でも Step I.1 は通常どおり実行し、飛ばすのは Step I.2 だけとする。Step I.3 は作業 0 件でも completed_at_commit を更新する。
- A4: verify を pending に戻すのは orchestrator の遷移書き込みで行い、status だけを設定する。verify の result / failed_items は verify の再実行時に上書きされる。
- A5: review 起点の SPEC変更では verify は通常すでに pending のため、FR1 の書き込みは効果を持たない。修正は対話実行と batch 実行に同じように適用される。
- A6: batch の verify カウンター（`batch.verify_rework.*`）は変更しない。
- A7: tier-upgrade の手順は対象外とし、変更しない。
- A8: 停止条件 3 そのものは変更しない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/spec-change-rework-reentry/REQUIREMENTS.md`
