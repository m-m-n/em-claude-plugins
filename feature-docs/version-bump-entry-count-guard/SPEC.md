# Feature: version-bump-entry-count-guard

## Overview

`tests/test_recycled_task_id_contract_version_bump.py` から marketplace エントリの件数ガードとエントリ全体の name/source スナップショットを撤去し、task0002 の AC-3 の検証を em-workflow エントリの name/source 検査に一本化する。あわせて `test-docs/recycled-task-id-contract/task0002.tests.yaml` の AC-3 の対応表を削除後の内容に合わせる。要件の詳細は `feature-docs/version-bump-entry-count-guard/REQUIREMENTS.md` を参照。

## Objectives

- マーケットプレイスへのプラグイン追加（`.claude-plugin/marketplace.json` の `plugins[]` へのエントリ追加）で、version bump 検証モジュール `tests/test_recycled_task_id_contract_version_bump.py` が落ちないようにする
- 同モジュールの AC-3（このタスクが触らないフィールドが変わっていないこと）の検証を em-workflow エントリに限定する

## User Stories

### US1: プラグインを追加しても同モジュールが落ちない
マーケットプレイスにプラグインを追加する開発者として、`.claude-plugin/marketplace.json` の `plugins[]` にエントリを追加しても `tests/test_recycled_task_id_contract_version_bump.py` が落ちないようにしたい。

**Acceptance Criteria:**
- [ ] AC-1（FR1, FR5）: `.claude-plugin/marketplace.json` の `plugins[]` に 3 つ目のエントリがあっても `tests/test_recycled_task_id_contract_version_bump.py` は落ちない。FR5(1) のテスト内の値による確認で示す。

### US2: AC-3 の検証を em-workflow エントリに限定する
同モジュールの保守者として、task0002 の AC-3 の検証を em-workflow エントリの name/source に限定したい。

**Acceptance Criteria:**
- [ ] AC-2（FR2, FR5）: em-workflow エントリの `name` または `source` が変わると同モジュールが落ちる。既存の `test_em_workflow_entry_name_and_source_unchanged` が残っていることと、FR5(2) のテスト内の値による確認で示す。
- [ ] AC-3（FR1, FR3）: 同モジュールに `MARKETPLACE_NAME_SOURCE_BASELINE`、`test_entry_count_unchanged`、`test_every_entry_name_and_source_matches_baseline` が残っていない。docstring に、エントリ数やエントリ全体の name/source を検査するという記述が残っていない。
- [ ] AC-4（FR4）: `task0002.tests.yaml` の AC-3 の tests に書かれているテスト ID はすべてモジュールに実在し、削除した 2 テストの ID は含まれない。
- [ ] AC-5（NFR1, NFR2, NFR3, NFR4）: `python3 -m unittest discover -s tests` が全体で通り、変更は NFR1 の 2 ファイルだけに収まっている。

## Technical Requirements

### Functional Requirements
- **FR1:** 件数ガードとエントリ全体スナップショットの撤去。`tests/test_recycled_task_id_contract_version_bump.py` から `TestMarketplaceOtherFieldsUnchanged` の 2 テスト（`test_entry_count_unchanged` / `test_every_entry_name_and_source_matches_baseline`）と、それらだけが参照する定数 `MARKETPLACE_NAME_SOURCE_BASELINE` を削除する。AC-3 の検証は既存の `TestMarketplaceEntryVersion.test_em_workflow_entry_name_and_source_unchanged` に一本化する（レビュー提案 (b)）。
- **FR2:** em-workflow エントリの name / source 検査の維持。em-workflow エントリの `name` または `source` が変わった場合に同モジュールが落ちる状態を維持する。`test_em_workflow_entry_name_and_source_unchanged` は削除も弱体化もしない。
- **FR3:** モジュール内の記述の整合。同モジュールの docstring（モジュール先頭の AC-3 の説明にある「the marketplace `plugins` array gains or loses no entry」、および全エントリの name/source を検査するという記述）を、em-workflow エントリに限定した検証内容に合わせる。
- **FR4:** テスト対応表の更新。`test-docs/recycled-task-id-contract/task0002.tests.yaml` の `acceptance_tests.AC-3.tests` から削除した 2 テストの ID を除き、`test_em_workflow_entry_name_and_source_unchanged` だけを残す。同じ AC-3 の `red_reason` にある件数（entry count）への言及も削除後の内容に合わせる。
- **FR5:** テスト内で作った値による確認。(1) em-workflow 以外に 3 つ目のエントリを持つ marketplace データで em-workflow エントリの検査が通ること、(2) em-workflow エントリの `source` が変わったデータ、および `name` が変わって em-workflow エントリが見つからないデータでは検査が落ちること、の 2 点を、テスト内で作った値で示す。リポジトリ上のファイルを書き換えて確かめる方法は取らない。

### Non-Functional Requirements
- **NFR1:** 変更するファイルは `tests/test_recycled_task_id_contract_version_bump.py` と `test-docs/recycled-task-id-contract/task0002.tests.yaml` の 2 つだけとする。
- **NFR2:** テストコードは標準ライブラリ（unittest / json / re / pathlib）だけを import し、JSON は必ずパースして読む（パターンマッチでは読まない）。
- **NFR3:** `em-workflow/` 配下のファイルと `.claude-plugin/marketplace.json` は変更しない。このためプラグインの version は上げない。
- **NFR4:** `python3 -m unittest discover -s tests` をリポジトリルートで実行し、全体が通る。

## Implementation Approach

### Architecture

**System Architecture:**
該当なし（テストコードとテスト対応表だけの修正）

**Component Diagram:**
```
tests/test_recycled_task_id_contract_version_bump.py
  ├── TestMarketplaceEntryVersion
  │     └── test_em_workflow_entry_name_and_source_unchanged   (残す: FR2)
  └── TestMarketplaceOtherFieldsUnchanged
        ├── test_entry_count_unchanged                          (削除: FR1)
        └── test_every_entry_name_and_source_matches_baseline   (削除: FR1)
  MARKETPLACE_NAME_SOURCE_BASELINE                              (削除: FR1)

test-docs/recycled-task-id-contract/task0002.tests.yaml
  └── acceptance_tests.AC-3.tests / red_reason                  (更新: FR4)
```

### Data Flow

```
.claude-plugin/marketplace.json ──(json でパース)──> em-workflow エントリの name/source 検査
テスト内で作った marketplace の dict ──────────────> em-workflow エントリの name/source 検査 (FR5)
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `.claude-plugin/marketplace.json`: em-workflow エントリの name/source 検査の読み取り対象（変更しない: NFR3）
- `test-docs/recycled-task-id-contract/task0002.tests.yaml`: 同モジュールのテスト ID の対応表（FR4）

**External Dependencies:**
- Python 標準ライブラリ（unittest / json / re / pathlib）のみ（NFR2）

### File Structure

```
tests/
└── test_recycled_task_id_contract_version_bump.py   # FR1, FR2, FR3, FR5
test-docs/
└── recycled-task-id-contract/
    └── task0002.tests.yaml                           # FR4
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/version-bump-entry-count-guard/**`
- `test-docs/version-bump-entry-count-guard/**`

`feature-docs/version-bump-entry-count-guard/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/version-bump-entry-count-guard/**` covers `test-docs/version-bump-entry-count-guard/{T}.tests.yaml`, the
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
- [ ] TS-1（AC-1）: 3 エントリの marketplace でも通る - em-review / em-workflow に 3 つ目のエントリを加えた marketplace の dict をテスト内で作り、em-workflow エントリの name/source 検査に渡す。検査が通る
- [ ] TS-2（AC-2）: em-workflow の source が変わると落ちる - em-workflow エントリの source を `./em-workflow` 以外にした dict をテスト内で作り、同じ検査に渡す。AssertionError になる
- [ ] TS-3（AC-2）: em-workflow の name が変わると落ちる - em-workflow エントリの name を別名にした（em-workflow エントリが無い）dict をテスト内で作り、同じ検査に渡す。AssertionError になる
- [ ] TS-4（AC-3, AC-4）: 削除した名前が残っていない - モジュールと `task0002.tests.yaml` から `MARKETPLACE_NAME_SOURCE_BASELINE` / `test_entry_count_unchanged` / `test_every_entry_name_and_source_matches_baseline` / `TestMarketplaceOtherFieldsUnchanged` を検索する。どれも見つからない

### Integration Tests
- [ ] TS-5（AC-5）: スイート全体の実行 - リポジトリルートで `python3 -m unittest discover -s tests` を実行する。失敗が 0 件。現在の marketplace.json（em-review / em-workflow の 2 件）で em-workflow の検査も通る

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] em-workflow エントリの `name` が変わり、em-workflow エントリが見つからない場合は検査が落ちる（TS-3）

### Performance Tests
該当なし

## Security Considerations

該当なし

## Error Handling

該当なし

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` がリポジトリルートで全体で通る（NFR4）
- [ ] 変更が `tests/test_recycled_task_id_contract_version_bump.py` と `test-docs/recycled-task-id-contract/task0002.tests.yaml` の 2 ファイルに収まっている（NFR1）

## Assumptions

- A-1: 修正範囲は `tests/test_recycled_task_id_contract_version_bump.py` と `test-docs/recycled-task-id-contract/task0002.tests.yaml` に限る。ほかの 3 モジュール（`tests/test_batch_policy_option_id_version_bump.py` の `OTHER_PLUGIN_ENTRIES_BASELINE` による件数・並び順の比較、`tests/test_goal_vs_spec_divergence_version_bump.py` / `tests/test_rework_contract_drift_version_bump.py` の `test_plugins_list_length_unchanged`）の件数固定はこの機能の範囲外とし、直さない。3 つ目のプラグインを追加すると、この 3 モジュールは引き続き落ちる。
- A-2: レビュー提案のうち (b)（2 テストを削除して `test_em_workflow_entry_name_and_source_unchanged` に一本化）を採る。(a)（`assertGreaterEqual` に緩める）は em-review エントリの name/source 検査を残してしまい、「em-workflow エントリに限定して検証する」という期待する挙動に合わないため採らない。
- A-3: `task0002.tests.yaml` の AC-4 の `red_reason` にあるテスト件数（「10 tests」「1462 tests」）は task0002 当時の実行記録として変更しない。タスク本文が更新を求めているのは AC-3 の tests 一覧だけである。

## Out of Scope

- `tests/test_batch_policy_option_id_version_bump.py`、`tests/test_goal_vs_spec_divergence_version_bump.py`、`tests/test_rework_contract_drift_version_bump.py` にある marketplace エントリ数の固定（batch_policy は並び順の比較も含む）。この機能では実装しない。別タスクとして起票する対象

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/version-bump-entry-count-guard/REQUIREMENTS.md`
