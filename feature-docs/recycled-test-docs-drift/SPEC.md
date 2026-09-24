# Feature: recycled-test-docs-drift

## Overview

feature `recycled-task-id-contract` の test-docs（`test-docs/recycled-task-id-contract/task0001.tests.yaml` / `task0002.tests.yaml`）を訂正する。
`em-workflow/agents/implementer.md` の tests.yaml スキーマを満たし、review round 1 の auto-fix 後の成果物の実態を説明する記録にする。

## Objectives

- feature recycled-task-id-contract の test-docs（task0001.tests.yaml / task0002.tests.yaml）が em-workflow/agents/implementer.md の tests.yaml スキーマを満たし、review round 1 auto-fix 後の成果物の実態を説明している状態にする
- 後続フェーズ（verify / retrospect）がこの記録を失敗の帰属根拠として読んでも誤らないようにする

## User Stories

ユーザーストーリーは定義しない。受け入れ基準は次のとおり。

**Acceptance Criteria:**
- [ ] AC-1（FR1）: task0002.tests.yaml の AC-4 に `red_confirmed: false` がある。task0001 / task0002 の acceptance_tests の全エントリが tests / red_confirmed / red_reason の 3 キーを持つ。
- [ ] AC-2（FR2）: task0001.tests.yaml の AC-3 `red_reason` が引用している文面が、em-workflow/references/implement-phase.md に（空白を正規化すれば）実在する。task0001.tests.yaml に文字列「All four hooks」が 0 件である。
- [ ] AC-3（FR3）: task0001.tests.yaml の AC-6 `tests:` に、FR3 の 3 件と既存の 4 件がすべて載っている。3 件はどれも tests/test_hook_classification_pin.py に実在するメソッドを指す。
- [ ] AC-4（FR4）: AC-6 の `red_reason` に、本 feature での再観測であること、基準コミット 48386b9^、3 テストそれぞれの失敗内容が書かれている（実測できなかった場合は、未観測であることが明記されている）。tests/test_hook_classification_pin.py に base との差分がない。
- [ ] AC-5（FR5）: task0001.tests.yaml の AC-7 が `red_confirmed: false` である。`red_reason` に 1493（1452+41、task0001 実装時点）と 1506（review round 1 auto-fix 適用後の integration）がいつの件数かとともに書かれ、false にした理由も書かれている。
- [ ] AC-6（FR6）: task0001.tests.yaml の `notes` に、AC-6 の再観測記録や AC-7 の red_confirmed: false と矛盾する全称の記述がない。
- [ ] AC-7（NFR1, NFR2, NFR3, NFR4）: base との差分が task0001.tests.yaml と task0002.tests.yaml の 2 ファイルだけである。変更対象外のエントリは変わっていない。2 ファイルが YAML として読み取れる。`python3 -m unittest discover -s tests` が失敗 0 で終わる。

## Technical Requirements

### Functional Requirements
- **FR1:** task0002 AC-4 に red_confirmed: false を追加 — `test-docs/recycled-task-id-contract/task0002.tests.yaml` の AC-4 エントリに `red_confirmed: false` を追加する。`tests: []` と既存の `red_reason` はそのまま残し、キーの並びは同じファイルの他エントリと同じ tests / red_confirmed / red_reason にする。
- **FR2:** task0001 AC-3 の引用を現在の文面に訂正 — `test-docs/recycled-task-id-contract/task0001.tests.yaml` の AC-3 `red_reason` が引用している「All four hooks detect a task as unlaunched solely from the absence ...」を、`em-workflow/references/implement-phase.md` の現在の文面「The other three queue hooks detect a task as **unlaunched** solely from the absence ...」に置き換える。引用した部分は implement-phase.md に実在する文字列（改行・空白の違いを除いて一致）にする。
- **FR3:** auto-fix で追加された 3 テストを task0001 AC-6 の tests: に記載 — task0001.tests.yaml の AC-6 `tests:` に、次の 3 件を同じファイル内の表記（module.Class.method）で追加する。既存の 4 件は残す。
    - `test_hook_classification_pin.TestObserveHookSource.test_bash_guard_reads_workflow_yaml_but_not_task_status`
    - `test_hook_classification_pin.TestObserveHookSource.test_bare_workflow_yaml_mention_without_status_accessor_is_false`
    - `test_hook_classification_pin.TestObserveHookSource.test_removing_the_status_carveout_flips_observation_to_false`
- **FR4:** 追加した 3 テストの red を再観測して記録 — `tests/test_hook_classification_pin.py` の `reads_per_task_status` を auto-fix 前の規則（48386b9^ の実装）に一時的に戻した作業コピーで FR3 の 3 テストを実行し、失敗を実測する。task0001.tests.yaml の AC-6 `red_reason` には次を記録する。実測が終わったら `tests/test_hook_classification_pin.py` を元に戻す。実測できなかった場合は、3 テストの red が未観測であることを `red_reason` にはっきり書く。
    - (a) 本 feature で行った再観測であり auto-fix 当時の観測ではないこと
    - (b) 戻した対象と基準コミット
    - (c) 3 テストそれぞれの失敗内容
- **FR5:** task0001 AC-7 の件数と red_confirmed を実態に合わせる — task0001.tests.yaml の AC-7 `red_reason` に、task0001 実装時点の件数 1493（baseline 1452 + 新規 41）と、review round 1 の auto-fix 適用後に integration で実行した件数 1506 の両方を、それぞれいつの件数かを明記して書く。1506 は task0001 単独の結果でも現在の件数でもないことが読み取れるようにする。`red_confirmed` は `false` にし、その理由（実装前の git diff が空なのは観測した失敗ではないこと）を `red_reason` に書く。既存の確認項目 (2)〜(4) の記述は残す。
- **FR6:** task0001 notes との整合 — task0001.tests.yaml の `notes` が、FR4 による AC-6 の再観測記録や FR5 による AC-7 の red_confirmed: false と矛盾しないようにする。「全 AC の red を再確認した」という全称の書き方は実態に合わせて直す。

### Non-Functional Requirements
- **NFR1 - 変更範囲を 2 ファイルに限定:** 最終的な差分は `test-docs/recycled-task-id-contract/task0001.tests.yaml` と `task0002.tests.yaml` の 2 ファイルだけにする。`em-workflow/` 配下（implementer.md / implement-phase.md / review-phase.md を含む）と `tests/` 配下は変更しない。FR4 で一時的に書き換えた `tests/test_hook_classification_pin.py` は差分に残さない。em-workflow/ 配下を変更しないので、プラグインの version bump は行わない。
- **NFR2 - 新しいテストを追加しない:** 確認は 4 つの完了条件を grep と YAML の読み取りで直接照合する方法と、既存 suite が成功することの確認で行う。新しいテストは追加しない。
- **NFR3 - 変更対象外のエントリを変えない:** task0001 の AC-1 / AC-2 / AC-4 / AC-5、task0002 の AC-1 / AC-2 / AC-3 / AC-5、および task0003.tests.yaml の内容は変更しない。
- **NFR4 - 記録ファイルの妥当性と suite 成功:** 変更後の 2 ファイルが YAML として読み取れること。リポジトリルートで実行する `python3 -m unittest discover -s tests` が失敗 0 で終わること。

## Implementation Approach

### Architecture

**System Architecture:**
該当なし（YAML の記録ファイル 2 件の訂正のみ）。

**Component Diagram:**
```
test-docs/recycled-task-id-contract/task0001.tests.yaml   ← FR2, FR3, FR4, FR5, FR6
test-docs/recycled-task-id-contract/task0002.tests.yaml   ← FR1
```

### Data Flow

```
tests/test_hook_classification_pin.py（48386b9^ の reads_per_task_status に一時的に戻す）
  → FR3 の 3 テストを実行して失敗を実測
  → 結果を task0001.tests.yaml の AC-6 red_reason に記録
  → tests/test_hook_classification_pin.py を元に戻す
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/agents/implementer.md`: tests.yaml のスキーマ（全 Acceptance Criterion エントリが tests / red_confirmed / red_reason を持つ）
- `em-workflow/references/implement-phase.md`: FR2 で引用する現在の文面
- `tests/test_hook_classification_pin.py`: FR3 の 3 テストの所在。FR4 の再観測で一時的に書き換える（差分には残さない）
- コミット 48386b9^: FR4 で戻す `reads_per_task_status` の基準

**External Dependencies:**
- なし

### File Structure

```
test-docs/
└── recycled-task-id-contract/
    ├── task0001.tests.yaml   # FR2 / FR3 / FR4 / FR5 / FR6 で変更
    ├── task0002.tests.yaml   # FR1 で変更
    └── task0003.tests.yaml   # 変更しない（NFR3）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/recycled-test-docs-drift/**`
- `test-docs/recycled-test-docs-drift/**`

`feature-docs/recycled-test-docs-drift/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/recycled-test-docs-drift/**` covers `test-docs/recycled-test-docs-drift/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/recycled-test-docs-drift/` directory at all; the declared
`test-docs/recycled-test-docs-drift/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

すべての確認は検査（inspection）と既存 suite の実行で行い、新しいテストは追加しない（NFR2）。

- [ ] TS-1（FR1, inspection）: task0002.tests.yaml を YAML として読み、acceptance_tests.AC-4.red_confirmed が false であることと、両ファイルの全エントリが 3 キーを持つことを確認する
- [ ] TS-2（FR2, inspection）: task0001.tests.yaml を「All four hooks」で grep して 0 件であることを確認する。AC-3 の red_reason から引用部分を取り出し、空白を正規化したうえで implement-phase.md に含まれることを確認する
- [ ] TS-3（FR3, inspection）: AC-6 の tests: に 7 件（既存 4 + 追加 3）があることを確認する。追加 3 件のメソッド名を tests/test_hook_classification_pin.py で grep し、それぞれ 1 件ずつ見つかることを確認する
- [ ] TS-4（FR4, inspection）: AC-6 の red_reason に「再観測」の旨、48386b9^、3 テスト名とそれぞれの失敗内容（または未観測である旨）があることを確認する。git diff で tests/test_hook_classification_pin.py に差分がないことを確認する
- [ ] TS-5（FR5, inspection）: AC-7 の red_confirmed が false であること、red_reason に 1493 と 1506 がそれぞれ時点の説明つきで書かれ、false の理由も書かれていることを確認する
- [ ] TS-6（FR6, inspection）: notes を読み、AC-6 / AC-7 の記録と矛盾する全称の記述がないことを確認する
- [ ] TS-7（NFR1, NFR2, NFR3, NFR4, inspection + existing suite）: git diff --stat で変更が 2 ファイルだけであることを確認する。変更対象外のエントリに差分がないことを確認する。python3 -m unittest discover -s tests を実行し、失敗 0 で終わることを確認する

### Unit Tests
- 追加しない（NFR2）

### Integration Tests
- [ ] 既存 suite: `python3 -m unittest discover -s tests` が失敗 0 で終わる（TS-7）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] FR4 で実測できなかった場合: 3 テストの red が未観測であることを AC-6 の `red_reason` に明記する（TS-4）

### Performance Tests
- 該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 該当なし
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし。

### Error Flow

```
FR4 の再観測が実測できない → AC-6 の red_reason に 3 テストの red が未観測であることを明記する
```

## Performance Optimization

### Performance Goals
- 該当なし

### Optimization Strategies
- 該当なし

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] FR1〜FR6 がすべて反映されている
- [ ] AC-1〜AC-7 を満たす
- [ ] TS-1〜TS-7 の確認がすべて通る
- [ ] `python3 -m unittest discover -s tests` が失敗 0 で終わる

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- **A1**（impact: medium, reversible）: 48386b9 は review round 1 loop 1 の auto-fix で reads_per_task_status を書き換えたコミットで、その親（48386b9^）には旧規則（docstring を除去したソースに "workflow.yaml" が含まれるかだけを見る判定）が残っている。根拠は回答 requirement.autofix-tests-red と reviews/round1.yaml の finding 56b64fea7f61b999。
- **A2**（impact: low, reversible）: 旧規則のもとでは 3 テストとも失敗する見込み。bash_guard.py は実行コード中に workflow.yaml を含むので assertFalse が True を受け取る。bare mention の合成ソースも True になる。carve-out を除去した合成ソースも True のままで assertFalse が落ちる。これはソースを読んで立てた見込みで、確定は FR4 の実測で行う。
- **A3**（impact: low, reversible）: FR4 で実測できなかった場合でも、AC-6 の red_confirmed は既存の 4 テストの観測を根拠に true のまま据え置き、追加 3 テストが未観測であることを red_reason に明記する。既存の AC-6 の red_reason も、観測したテストと最初から green だったテストを 1 つのエントリにまとめて書いている。
- **A4**（impact: low, reversible）: task0001.tests.yaml のテスト ID 表記は同じファイルの既存表記（module.Class.method）に合わせる。task0003.tests.yaml の Class::method 表記には合わせない。
- **A5**（impact: low, reversible）: 次の項目は本 feature の範囲外で、別タスクとして起票する: review-phase.md に「auto-fix 後に tests.yaml を追随させる責務」を追記すること。task0003.tests.yaml AC-6/7/8 と task0001 AC-6 の tests: から漏れている TestParseClassificationTableFailureModes / TestNonVacuityGuards。

## Implementation Phases (if applicable)

該当なし。

## References

- tests.yaml スキーマ: `em-workflow/agents/implementer.md`
- 引用元の文面: `em-workflow/references/implement-phase.md`
- 追加 3 テストの所在: `tests/test_hook_classification_pin.py`
- 変更対象: `test-docs/recycled-task-id-contract/task0001.tests.yaml`、`test-docs/recycled-task-id-contract/task0002.tests.yaml`
