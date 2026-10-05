# Feature: exit4-ac2-test-id-drift

## Overview

`test-docs/exit4-tip-argument/task0002.tests.yaml` の AC-2 が、実在しない acceptance test ID
`tests.test_exit4_tip_argument_version_bump.TestMarketplaceEntryVersion.test_em_review_entry_has_no_version_key`
を列挙している。この ID を実在する
`tests.test_exit4_tip_argument_version_bump.TestMarketplaceEntryVersion.test_em_review_entry_version_not_bumped_with_em_workflow`
に差し替え、AC-2 の red_reason と `tests/test_exit4_tip_argument_version_bump.py` のモジュール docstring を実際のアサーションに揃える。
あわせて、同じ ID ドリフトの再発を検出するテストを追加する。

## Objectives

- `test-docs/exit4-tip-argument/task0002.tests.yaml` に列挙された acceptance test ID がすべて実在し、unittest で解決できる状態にする
- AC-2 の red_reason と `tests/test_exit4_tip_argument_version_bump.py` のモジュール docstring を実際のアサーションに揃える
- 同じ ID ドリフトの再発をテストで検出できるようにする

## Acceptance Criteria

- [ ] **AC-1** (FR1): `task0002.tests.yaml` の AC-2 に `test_em_review_entry_has_no_version_key` が無く、`test_em_review_entry_version_not_bumped_with_em_workflow` がある。`python3 -m unittest tests.test_exit4_tip_argument_version_bump.TestMarketplaceEntryVersion.test_em_review_entry_version_not_bumped_with_em_workflow` が成功する。
- [ ] **AC-2** (FR2): AC-2 の red_reason が、em-workflow の 2 テストで観測した red と、em-review の 2 テストが保持ガードであることを書いている。'that entry is untouched' を version キーが無いことの根拠にした記述は残っていない。
- [ ] **AC-3** (FR3, FR4): `tests/test_exit4_tip_argument_version_bump.py` のモジュール docstring に 'no `version` key' と 'no-version-key' が残っていない。AC-2 と AC-4 の記述は `test_em_review_entry_version_not_bumped_with_em_workflow` のアサーションと合っている。
- [ ] **AC-4** (FR5, FR6): 再発検出テストが `task0002.tests.yaml` の全 ID（11 件：AC-1 2 件、AC-2 4 件、AC-3 モジュール ID 1 件、AC-4 4 件）を解決でき、成功する。対象ファイルの一覧は明示的に列挙している。
- [ ] **AC-5** (FR7): 差し替え前の ID を解決失敗と判定する negative proof と、取り出した ID の一覧に対する non-vacuity guard がある。
- [ ] **AC-6** (NFR1, NFR2, NFR3, NFR4): 全テストスイートが成功する。変更したファイルは `task0002.tests.yaml`、`tests/test_exit4_tip_argument_version_bump.py`（docstring だけ）、新しいテストモジュールに限られる。`plugin.json` と `marketplace.json` は変わっていない。

## Technical Requirements

### Functional Requirements

- **FR1:** AC-2 の acceptance test ID の差し替え — `test-docs/exit4-tip-argument/task0002.tests.yaml` の AC-2 の tests にある `tests.test_exit4_tip_argument_version_bump.TestMarketplaceEntryVersion.test_em_review_entry_has_no_version_key` を `tests.test_exit4_tip_argument_version_bump.TestMarketplaceEntryVersion.test_em_review_entry_version_not_bumped_with_em_workflow` に差し替える。AC-2 のほかの 3 ID、ほかの AC、task_id / baseline_failures / final_failures は変えない。
- **FR2:** AC-2 の red_reason の書き換え — AC-2 の red_reason を実際のアサーションに合わせて書き換える。em-workflow エントリの 2 テストは 0.1.44 の時点で red を観測したこと（既存記述の 'AssertionError: 44 not greater than 44 ...' の部分）は残す。em-review の 2 テスト（source が `./em-review` のまま / em-review の version が em-workflow の plugin.json の version と一致しない）は、変更前から green の保持ガードであると書く。観測していない red を書かない。`red_confirmed: true` は維持する。
- **FR3:** モジュール docstring の AC-2 記述の修正 — `tests/test_exit4_tip_argument_version_bump.py` のモジュール docstring にある AC-2 の項目のうち 'the entry named `em-review` ... still carries no `version` key' を、em-review エントリの version が plugin manifest の version と一致しない（em-workflow の bump に連動しない）という実際のアサーションの記述に書き換える。
- **FR4:** モジュール docstring の AC-4 matcher インベントリの修正 — 同じ docstring の AC-4 matcher インベントリにある '`_marketplace_entry`'s lookups (`em-review` source / no-version-key)' を、source と version 非連動の 2 つのチェックに書き換える。どちらも negative proof の要らない保持ガードという分類は変えない。
- **FR5:** 再発を検出するテスト — `tests/` 配下に新しいテストモジュールを追加する。このモジュールは対象の tests.yaml を読み、acceptance_tests の各 AC の tests に並ぶ ID をすべて取り出す。そして各 ID が実在するモジュール / クラス / メソッドに解決できることを確かめる。失敗したときは、解決できなかった ID をすべてメッセージに並べる。
- **FR6:** 検出対象の限定 — FR5 のテストの対象は、モジュール内で明示的に列挙した tests.yaml だけにする。`test-docs/**` の glob 走査はしない。対象は `test-docs/exit4-tip-argument/task0002.tests.yaml` の 1 ファイルにする。ほかの feature に残っている、解決できない既存 ID（ID 約 769 件 / 約 115 ファイル）は、このテストを落とさない。
- **FR7:** 解決判定の negative proof と non-vacuity guard — FR5 の解決判定に negative proof を付ける。差し替え前の ID（`test_em_review_entry_has_no_version_key`）を渡すと、解決失敗と判定されることを確かめる。あわせて non-vacuity guard を付ける。対象ファイルから取り出した ID の一覧が空でなく、AC-2 の差し替え後の ID を含むことを確かめる。

### Non-Functional Requirements

- **NFR1:** テストコードは標準ライブラリだけを使う（`test/README.md`）。tests.yaml の読み取りに PyYAML を使わない。
- **NFR2:** `tests/test_exit4_tip_argument_version_bump.py` で変えるのはモジュール docstring だけにする。テストメソッドやヘルパーの本体は変えない。
- **NFR3:** プラグインのディレクトリ配下は変更しない。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は触らない（`.claude/rules/core-plugin-version-bump.md`）。
- **NFR4:** `python3 -m unittest discover -s tests` がリポジトリルートで成功する。

## Implementation Approach

### 変更対象

- `test-docs/exit4-tip-argument/task0002.tests.yaml` — AC-2 の acceptance test ID（FR1）と red_reason（FR2）
- `tests/test_exit4_tip_argument_version_bump.py` — モジュール docstring の AC-2 記述（FR3）と AC-4 matcher インベントリ（FR4）。docstring 以外は変えない（NFR2）
- `tests/` 配下の新しいテストモジュール — 再発検出テスト（FR5, FR6, FR7）

### Data Flow

```
task0002.tests.yaml（明示列挙した 1 ファイル）
  → acceptance_tests の各 AC の tests から ID を取り出す
  → 各 ID をモジュール / クラス / メソッドに解決する
  → 解決できなかった ID をすべてメッセージに並べて失敗する（無ければ成功）
```

### Dependencies

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）。PyYAML は使わない。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
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

- [ ] **TS1** (AC-1 / FR1): AC-2 の差し替え後の ID を unittest で名前を指定して実行し、成功する。
- [ ] **TS2** (AC-4 / FR5, FR6): `task0002.tests.yaml` から取り出した全 ID が、モジュール ID・クラス ID・メソッド ID のどれであっても解決できる。
- [ ] **TS3** (AC-5 / FR7): 差し替え前の ID（存在しないメソッド）を解決判定に渡すと、失敗と判定される。
- [ ] **TS4** (AC-5 / FR7): 取り出した ID の一覧が空でなく、差し替え後の AC-2 の ID を含む。`tests: []` の AC（AC-5）からは ID が出てこない。
- [ ] **TS5** (AC-3 / FR3, FR4): version_bump モジュールの docstring に、旧記述の文字列が無い。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] `unittest.TestLoader.loadTestsFromName` は、属性が無いとき例外を投げずに失敗プレースホルダ（`_FailedTest`）を返し、`loader.errors` に記録することがある。この場合も解決失敗と判定する。
- [ ] `tests.` 接頭辞付きの ID は、リポジトリルートが `sys.path` にあるときだけ解決できる（`tests/` はインストール可能なパッケージではない）。`discover -s tests` で走るときも解決できるよう、テスト側でリポジトリルートを `sys.path` に入れる。
- [ ] AC-3 の ID はモジュール単体の ID なので、メソッド ID と同じ解決手順で扱える。
- [ ] 解決時に version_bump モジュールを `tests.` 付きの名前で import しても、そのテストは実行中のスイートに加わらない（解決するだけで実行しない）。

## Assumptions

- 再発検出テストの対象は `task0002.tests.yaml` の 1 ファイルにする。`task0001.tests.yaml` が参照する `tests/test_exit4_tip_argument_consistency.py` は調査範囲外で、ID が解決できるか確認していないため対象に含めない。
- em-review の version 非連動のアサーションは保持ガードのままにする。新しい negative proof は追加しない。
- `feature-docs/exit4-tip-argument` 配下の過去の記録（`task0002.md`、review の記録など）は書き換えない。
- プラグインの version は変えない（`.claude/rules/core-plugin-version-bump.md`）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` がリポジトリルートで成功する

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- REQUIREMENTS.md: tier `reduced` のため作成しない
- `test-docs/exit4-tip-argument/task0002.tests.yaml`
- `tests/test_exit4_tip_argument_version_bump.py`
