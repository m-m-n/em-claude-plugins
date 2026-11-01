# Feature: rework-docs-only-medium-fixes

## Overview

`em-workflow/scripts/validate-worker-output.py` の文書のみの回・シナリオ ID 改名・tests 参照置換の検査を SSOT の規則に揃え、rework-docs-only-task-routing の review round 1 で残った medium 指摘 4 件（c588505add1da8c7 / 33f072c3b90c3aea / 6ed87da72e3f5de3 / a3ac237a09af8436）を解消する。要件は `feature-docs/rework-docs-only-medium-fixes/REQUIREMENTS.md` を参照する。

## Objectives

- `em-workflow/scripts/validate-worker-output.py` の文書のみの回・シナリオ ID 改名・tests 参照置換の検査を SSOT の規則に揃え、rework-docs-only-task-routing の review round 1 で残った medium 指摘 4 件（c588505add1da8c7 / 33f072c3b90c3aea / 6ed87da72e3f5de3 / a3ac237a09af8436）を解消する

## User Stories

### US1: medium 指摘 4 件の解消

**Acceptance Criteria:**
- [ ] AC-1: FR1〜FR4 の 4 件それぞれについて、不正な出力を拒否する invalid- fixture とテストがあり、validator がそれを終了コード 1 で拒否する（FR1, FR2, FR3, FR4, FR6）
- [ ] AC-2: 既存の valid- fixture がすべて引き続き終了コード 0 で受理される（valid-mixed-round-renamed-scenario-declared は feature-dir / baseline-dir を足した状態で）（FR7）
- [ ] AC-3: rework-task-synthesis.md Section 12、rework-planner-contract.md の check 2、workflow-patch.md の Tests replacement 節が FR1〜FR4 の規則を述べている（FR5）
- [ ] AC-4: `python3 -m unittest discover -s tests` が通る（NFR1, NFR2, NFR3）

## Technical Requirements

### Functional Requirements
- **FR1:** 改名による受理は文書の差分で裏付ける（c588505add1da8c7）。rework_index の covered_by_existing のうち verification_index のキーでない ID を、payload.doc_corrections[].scenario_renames の申告済み pair で受理するのは、次の条件がすべて成り立つときに限る: pair の from が verification_index のキーである、`--feature-dir` と `--baseline-dir` の両方が与えられ feature-dir に VERIFICATION.md がある、to が変更後 VERIFICATION.md の ID 集合にある、from が baseline VERIFICATION.md の ID 集合にある、from が変更後 VERIFICATION.md の ID 集合にない。どちらかのディレクトリが無いとき、または feature-dir に VERIFICATION.md が無いときは、改名による受理をせず rework-index で拒否する（fail-closed）。このときのメッセージは、文書の差分が取れないために改名を確かめられないことを示し、改名の申告が無い場合のメッセージと区別できる。
- **FR2:** 改名で消えた旧 ID を受理しない（33f072c3b90c3aea）。申告済みの改名 pair の from である ID は、verification_index のキーであっても covered_by_existing として受理せず、rework-index で拒否する。加えて `--feature-dir` と `--baseline-dir` の両方が与えられ feature-dir に VERIFICATION.md があるときは、covered_by_existing の各 ID が変更後 VERIFICATION.md の ID 集合にあることを求め、無い ID を rework-index で拒否する（改名に関係しない ID にも適用する）。どちらのディレクトリも無い場合に、改名に関係しない verification_index のキーの ID を受理する既存の動作は変えない。
- **FR3:** 文書のみの回の step_patches を SSOT の規則どおりに検査する（6ed87da72e3f5de3）。operation が append_rework で tasks_patch.entries が無いか空の patch は、step_patches がちょうど 1 件で、その step_id が起点ステップで、set.status が pending であるときだけ受理する。起点ステップは、入力 envelope に rework_source.type があるときはその値と一致しなければならず、得られないとき（`--kind workflow-patch` 単体、または envelope に rework_source.type が無いとき）は verify か review のどちらかでなければならない。implement を対象にする entry は set.status の値によらず拒否する。step_patches が 0 件、2 件以上、起点以外の step を含む、set.status が pending 以外、のいずれも拒否する。検査は `--dry-run-apply` の有無によらず構造検査として行い、`--kind worker-result` と `--kind workflow-patch` の両方の経路で効く。
- **FR4:** from と to が重なる tests_replace を拒否する（a3ac237a09af8436）。requirements_patch の 1 つの entry の set.tests_replace で、from の集合と to の集合に共通する ID があるときは、構造検査で requirements_patch として拒否する。連鎖（TS-1→TS-2 と TS-2→TS-3）と入れ替え（TS-1→TS-2 と TS-2→TS-1）がどちらも対象になる。`--dry-run-apply` の有無によらず拒否する。
- **FR5:** SSOT を検査規則に揃える。FR1〜FR4 の規則を SSOT に書く: `em-workflow/references/rework-task-synthesis.md` Section 12 の Rename-aware coverage の項と、tasks_patch.entries が空の append_rework patch の項（step_patches は起点ステップ 1 件で set.status は pending、起点の照合元）、`em-workflow/references/contracts/rework-planner-contract.md` の check 2、`em-workflow/references/workflow-patch.md` の Tests replacement 節（from と to の重なりの禁止）。
- **FR6:** 拒否例の fixture とテスト。FR1〜FR4 のそれぞれについて、不正な出力を拒否する invalid- fixture と、それを検査するテストを足す。FR1: 架空の to（変更後 VERIFICATION.md に無い ID）を申告した改名と、差分を取れない（`--feature-dir` / `--baseline-dir` が無い）改名申告。FR2: 申告した改名の from を covered_by_existing に挙げた出力。FR3: implement を pending 以外の status にする entry、step_patches が空、起点以外の step が混ざる、起点の set.status が pending 以外、envelope の rework_source.type と step_id が食い違う、の各ケース。FR4: 連鎖と入れ替え。tests_replace を含む fixture は rework-planner の 6 件（test_ac6_no_fixture_uses_tests_replace が対象にするもの）以外に置く。
- **FR7:** 既存の成功例 fixture を受理し続ける。`em-workflow/references/fixtures/` 配下の既存の valid- fixture はすべて受理され続ける。valid-mixed-round-renamed-scenario-declared には feature-dir/VERIFICATION.md（TS-3 を含み TS3 を含まない）と baseline-dir/VERIFICATION.md（TS3 を含む）を足し、FR1 の条件を満たすようにする。`tests/test_rework_docs_only_validator_rules.py` の TestFixtures._run は、fixture に feature-dir / baseline-dir があればそれを `--feature-dir` / `--baseline-dir` として渡す。

### Non-Functional Requirements
- **NFR1 - Robustness:** 不正な入力で例外を出さない。FR1〜FR4 で足す検査は、形の崩れた入力（rework_source が mapping でない、type が文字列でない、step_patches の要素が mapping でない、tests_replace の pair が崩れている、VERIFICATION.md が読めない形など）に対しても例外を出さず、エラーとして報告する。CLI は終了コード 1 と JSON のエラー詳細を返し、2 にならない。
- **NFR2 - Dependencies:** テストは標準ライブラリだけを使う。追加・変更するテストは Python 標準ライブラリの unittest だけを使い、サードパーティのパッケージを import しない。
- **NFR3 - Test suite:** テストスイート全体が通る。`python3 -m unittest discover -s tests` がリポジトリルートから通る。

## Implementation Approach

### Architecture

変更対象は次のとおり。

- 検査: `em-workflow/scripts/validate-worker-output.py`（FR1〜FR4、NFR1）
- SSOT: `em-workflow/references/rework-task-synthesis.md` Section 12、`em-workflow/references/contracts/rework-planner-contract.md` の check 2、`em-workflow/references/workflow-patch.md` の Tests replacement 節（FR5）
- fixture: `em-workflow/references/fixtures/` 配下（FR6、FR7）
- テスト: `tests/test_rework_docs_only_validator_rules.py`（FR6、FR7）

### Rules

**改名による受理（FR1）と covered_by_existing（FR2）**

「差分が取れる」は、`--feature-dir` と `--baseline-dir` の両方が与えられ、feature-dir に VERIFICATION.md がある状態を指す。

| covered_by_existing の ID | 差分が取れる | 差分が取れない |
|---|---|---|
| 申告済み改名 pair の from | rework-index で拒否 | rework-index で拒否 |
| verification_index のキーでなく、申告済み改名 pair の to | FR1 の条件をすべて満たせば受理、満たさなければ rework-index で拒否 | rework-index で拒否（差分が取れない旨のメッセージ） |
| verification_index のキーで、改名に関係しない | 変更後 VERIFICATION.md の ID 集合になければ rework-index で拒否 | 従来どおり受理 |

**文書のみの回の step_patches（FR3）**

| 入力 | 起点ステップ |
|---|---|
| envelope に rework_source.type がある（review / verify） | その値 |
| `--kind workflow-patch` 単体、または envelope に rework_source.type が無い | verify か review |
| rework_source が mapping でない、または type が review / verify 以外 | 照合を満たせないものとして拒否（fail-closed） |

- 受理するのは、step_patches がちょうど 1 件、step_id が起点ステップ、set.status が pending のときだけ。
- 新しい envelope フィールドは足さない。
- 既存の valid-docs-only-round の envelope は rework_source を持たないため、起点ステップを verify か review とする扱いで受理される。

**tests_replace の重なり（FR4）**

- 1 つの entry の set.tests_replace で from 集合と to 集合が共通の ID を持てば、requirements_patch で拒否する。
- 複数の pair が同じ to を持つ tests_replace（TS1→X, TS2→X）は FR4 の対象外とし、既存の「to が既にあれば from を消す」適用規則のままにする。

### Dependencies

**Internal Dependencies:**
- rework-docs-only-task-routing（PR #50）: マージ済みで、この integration ブランチの基点に含まれている。

**External Dependencies:**
- なし（NFR2）

### File Structure

```
em-workflow/
├── scripts/
│   └── validate-worker-output.py
└── references/
    ├── rework-task-synthesis.md
    ├── workflow-patch.md
    ├── contracts/
    │   └── rework-planner-contract.md
    └── fixtures/
tests/
└── test_rework_docs_only_validator_rules.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/rework-docs-only-medium-fixes/**`
- `test-docs/rework-docs-only-medium-fixes/**`

`feature-docs/rework-docs-only-medium-fixes/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/rework-docs-only-medium-fixes/**` covers `test-docs/rework-docs-only-medium-fixes/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/rework-docs-only-medium-fixes/` directory at all; the declared
`test-docs/rework-docs-only-medium-fixes/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 改名申告の to が変更後 VERIFICATION.md に無いと拒否される（架空の to、例 TS3→TS-9999）（FR1）
- [ ] TS-2: 改名申告の from が変更後 VERIFICATION.md に残っていると拒否される（FR1）
- [ ] TS-3: 改名申告の from が baseline VERIFICATION.md に無いと拒否される（FR1）
- [ ] TS-4: `--feature-dir` か `--baseline-dir` が無いと改名による受理をせず拒否し、差分が取れない旨のメッセージを出す（FR1）
- [ ] TS-5: feature-dir に VERIFICATION.md が無いと改名による受理をせず拒否する（FR1）
- [ ] TS-6: 3 条件を満たす改名申告（baseline に TS3、変更後に TS-3 があり TS3 が無い）は受理される（FR1, FR7）
- [ ] TS-7: 申告した改名の from（TS3）を covered_by_existing に挙げると、verification_index のキーであっても拒否される（FR2）
- [ ] TS-8: 差分が取れるとき、変更後 VERIFICATION.md に無い covered_by_existing の ID は拒否される（FR2）
- [ ] TS-9: ディレクトリが無いとき、改名に関係しない verification_index のキーの ID は従来どおり受理される（FR2）
- [ ] TS-10: entries が空の append_rework で implement を completed にする entry が拒否される（FR3）
- [ ] TS-11: entries が空の append_rework で step_patches が空だと拒否される（FR3）
- [ ] TS-12: entries が空の append_rework で step_patches が 2 件以上（起点以外の step が混ざる）だと拒否される（FR3）
- [ ] TS-13: entries が空の append_rework で起点ステップの set.status が pending 以外（例 completed）だと拒否される（FR3）
- [ ] TS-14: envelope の rework_source.type が verify なのに step_id が review（またはその逆）だと拒否される（FR3）
- [ ] TS-15: envelope が無いとき、step_id が verify または review の 1 件で set.status が pending なら受理され、それ以外の step_id は拒否される（FR3）
- [ ] TS-16: FR3 の拒否が `--dry-run-apply` の有無、`--kind worker-result` / `workflow-patch` のどちらでも起きる（FR3）
- [ ] TS-17: tests_replace の連鎖（TS-1→TS-2, TS-2→TS-3）が requirements_patch で拒否される（FR4）
- [ ] TS-18: tests_replace の入れ替え（TS-1→TS-2, TS-2→TS-1）が requirements_patch で拒否される（FR4）
- [ ] TS-19: from と to が重ならない複数 pair（valid-docs-only-round の TS1→TS-1, TS2→TS-2）は受理される（FR4, FR7）
- [ ] TS-20: 既存の valid- fixture がすべて終了コード 0 で受理される（FR7）
- [ ] TS-21: 形の崩れた rework_source / step_patches / tests_replace / VERIFICATION.md が例外にならず終了コード 1 で報告される（NFR1）
- [ ] TS-22: SSOT 3 文書が FR1〜FR4 の規則を述べている（FR5）

### Integration Tests
該当なし

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-4 / TS-5: 差分が取れないときは fail-closed で拒否する
- [ ] TS-21: 形の崩れた入力は例外にならず終了コード 1 で報告される

### Performance Tests
該当なし

## Security Considerations

- **Input Validation:** NFR1 に従い、形の崩れた入力は例外を出さずエラーとして報告し、CLI は終了コード 1 と JSON のエラー詳細を返す。
- 上記以外の項目は該当なし。

## Error Handling

### Error Codes

| Code | Description |
|------|-------------|
| rework-index | 改名による受理（FR1）と covered_by_existing（FR2）の拒否 |
| requirements_patch | tests_replace の from と to の重なり（FR4） |
| docs-only-implement-reset | 文書のみの回で implement を対象にする entry（FR3、既存コード） |
| docs-only-implement-reset と区別できるコード | 文書のみの回の step_patches の件数・起点・status の違反（FR3） |

報告コードが増える既存の invalid- fixture（例: invalid-docs-only-round-resets-implement、step_patches が implement と review の 2 件）は、tests 側の期待コードを更新してよい。AC-2 が守るのは valid- fixture だけ。

### Error Flow

```
不正な入力 → エラーとして報告 → 終了コード 1 と JSON のエラー詳細（2 にならない）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete（FR5）
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` がリポジトリルートから通る（NFR3）

## Constraints

- 完了済み feature の文書（`feature-docs/rework-docs-only-task-routing/` の THREAT-MODEL の TM-5、SPEC.md、reviews/round1.yaml）は変更しない。TM-5 の更新は残件として扱う。
- em-workflow の version は手で上げない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- Requirements: `feature-docs/rework-docs-only-medium-fixes/REQUIREMENTS.md`
- `em-workflow/references/rework-task-synthesis.md`: Section 12
- `em-workflow/references/contracts/rework-planner-contract.md`: check 2
- `em-workflow/references/workflow-patch.md`: Tests replacement 節
- `feature-docs/rework-docs-only-task-routing/reviews/round1.yaml`: medium 指摘 4 件の出典
