# Feature: rework-docs-only-task-routing

## Overview

rework で `feature-docs/**` だけを直せば解消する修正を、implementer 向けのタスクにせず、rework-planner が文書を直す経路で処理する。文書のみの回は implement を pending に戻さず、発生元の step だけを pending に戻す。要件は `feature-docs/rework-docs-only-task-routing/REQUIREMENTS.md` に従う。

## Objectives

- rework で `feature-docs/**` だけを直せば解消する修正を implementer 向けのタスクにせず、rework-planner が文書を直す経路で処理する
- 無人実行（`--batch`）が、文書だけの修正で implement の failed（`failed_kind: decision`）に止まらず先へ進む

## User Stories

### US1: 文書だけで解消する修正を rework-planner が直す
As a em-workflow の利用者, I want to 文書だけで解消する rework の修正を rework-planner に直させる, so that その修正が implementer 向けのタスクにならない.

**Acceptance Criteria:**
- [ ] AC1
- [ ] AC2
- [ ] AC5
- [ ] AC6
- [ ] AC7

### US2: 無人実行が文書だけの修正で止まらない
As a em-workflow の利用者, I want to 無人実行（`--batch`）を文書だけの修正で止めずに進めたい, so that implement の failed（`failed_kind: decision`）で止まらない.

**Acceptance Criteria:**
- [ ] AC1
- [ ] AC3
- [ ] AC4
- [ ] AC8

## Technical Requirements

### Functional Requirements
- **FR1:** 文書のみ修正経路を rework-task-synthesis.md 第 9 節に追加 — `rework-task-synthesis.md` の第 9 節に、文書だけの修正のための小節を追加する。対象は、Wording-correction route の適格条件を満たさず、`feature-docs/{feature}/` の VERIFICATION.md・IMPLEMENTATION.md・既存の `tasks/*.md` と、`workflow.yaml` の要件の tests 参照だけを変えれば解消する修正。判定の順序は「Wording-correction route → 文書のみ修正経路 → rework タスク合成 / SPEC-change 遷移」とし、Wording-correction route の Guard と Ordering の記述をこの順序に合わせる。Wording-correction route の対象・3 つの適格条件・適格時の結果は変えない。SPEC.md / REQUIREMENTS.md の変更が要る修正は、これまでどおり SPEC-change 遷移に回す。
- **FR2:** rework-planner が既存の feature-docs 文書を直接修正 — 文書のみ修正経路では rework-planner がタスクを作らず、VERIFICATION.md・IMPLEMENTATION.md・既存の `tasks/*.md` を自分で書き換える。`agents/rework-planner.md` と `contracts/rework-planner-contract.md` の文書更新範囲の表を改める。既存の `tasks/*.md` を書き換える回では、そのパスを `write_policy.targets` に `action: replace_own` で列挙する。これは VERIFICATION.md / IMPLEMENTATION.md を `replace_own` で扱っている既存の前例（`rework-planner-contract.md:129-140`）と同じ扱いで、`contracts/spec-writer-contract.md` の `replace_own` の定義とどう整合するかを契約の中で明記する。書き換えない回には列挙しない。
- **FR3:** 合成タスクの files に feature-docs/** を含めない — rework-planner が合成するタスクの `files` に、先頭のパス要素が `feature-docs` のパスを 1 つも含めない。この規則を `rework-task-synthesis.md` と `agents/rework-planner.md` に書く。`em-workflow/scripts/validate-worker-output.py` は、append_rework の `tasks_patch.entries` のうち `files` にそのパスを 1 つでも含むものを拒否する。
- **FR4:** 要件の tests 参照を期待値付きで置き換える操作 — workflow patch の `requirements_patch` に、要件の tests 参照を置き換える操作を追加する。置き換え前の ID が現在の tests に含まれることを `expected` で確かめ、旧 ID を除いて新 ID を入れる。現状の `_append` 系の追加と status 等の直接代入はそのまま残す。`references/workflow-patch.md`、`validate-worker-output.py` の構造検証（`REQUIREMENTS_PATCH_SET_KEYS`）・`--dry-run-apply` の `expected` 検証・`apply_patch` にこの操作を入れる。
- **FR5:** 文書のみの回は発生元の step だけを pending に戻す — 文書のみの回（`tasks_patch.entries` が空）の append_rework patch では、発生元の step だけを pending に戻す（verify 由来なら verify、review 由来なら review）。implement は completed のまま残す。Invariant 1 と `implement-phase.md` の Step I.0 の文言は緩めず、新しい小節で「この経路は implement を pending に戻さない」と明記する。`validate-worker-output.py` は、`tasks_patch.entries` が空なのに `step_patches` が implement を pending に戻す append_rework patch を拒否する。
- **FR6:** コード修正と文書修正が混在する回の分割 — 同じ回の失敗項目・指摘にコード修正と文書だけの修正が混ざる場合、同じ dispatch の中で分ける。文書の部分は rework-planner が直接直し、コードの部分だけを既存のグループ化規則（第 4 節）でタスクにする。タスクが 1 件以上ある回は、これまでどおり implement（と発生元の step）を pending に戻す。発生元の step だけを戻す規則は文書のみの回に限る。
- **FR7:** 文書修正の宣言と、改名したシナリオ ID のカバレッジ判定 — rework-planner の completed の結果で、文書だけで直した項目ごとに、変えた文書と発生元（`origin_kind` / `origin_id`）を宣言する。シナリオ ID の改名（例: `TS<N>` → `TS-<N>`）では、改名前と改名後の ID の対応も宣言する。混在する回の `rework_index` の `covered_by_existing` が改名後の ID を挙げる場合、`validate-worker-output.py` は、宣言された対応を通じて入力の `verification_index` の改名前 ID に当たるかで判定する。宣言のフィールド名と形は計画段階で決める。
- **FR8:** develop の verify 失敗分岐と --once の再開先を更新 — `skills/develop/SKILL.md` の verify 失敗時の対話分岐と batch 分岐に、文書のみの回の結果を書く。implement を戻さず、verify を pending に戻してコミットする。タスクが 1 件以上ある回の既存の記述（'新しい rework task が 1 件以上 workflow.yaml へ登録されるまで戻さない'）は残す。'--once のフェーズ境界' の表には、文書のみの回の再開先が verify になる行（または注記）を足す。batch の系譜 cap / hard cap の数え方は変えない。
- **FR9:** 再発検出テスト — `tests/test_validate_worker_output.py` の既存の fixture 実行の仕組みで、rework-planner の fixture を追加する。拒否される例は 2 つ: `files` が `feature-docs/**` だけのタスク、コードと `feature-docs/**` が混ざったタスク。通る例は 2 つ: コードだけのタスク、文書のみの回。文書のみの回は、`TS<N>` → `TS-<N>` の改名と既存の `tasks/task0001.md`・`tasks/task0003.md` の書き換えを想定し、新しいタスクが無い・旧 tests 参照が除かれている・implement が completed のまま・verify だけが pending に戻ることを確かめる。改名後の ID を `covered_by_existing` に挙げる混在の例も足す。文書テスト（unittest）では、対話・batch の両方の新経路と、タスクがある場合の既存の前提（`test_develop_skill_rewiring.py:276-333` が固定している内容）が残ることを固定する。

### Non-Functional Requirements
- **NFR1 - 4 経路の同一性:** review/verify × interactive/batch の 4 経路で同じ規則にする（`rework-task-synthesis.md` Invariant 7）
- **NFR2 - 固定済み構造の維持:** `rework-task-synthesis.md` の 13 節の構成と順序、'## 14.' が無いこと、Invariant が 11 件、Wording-correction route の 3 条件・'conjunctive'・Guard 内の 'rework-task synthesis' / 'SPEC-change transition' / 'concrete' / 'artefact' を壊さない。既存テストを変えずに通す
- **NFR3 - implementer の制約は不変:** `agents/implementer.md` の 'Never modify `feature-docs/**`' を変えない
- **NFR4 - SSOT の参照規律:** 規則は所有文書に一度だけ書き、他の文書からはパスで参照し、言い直さない（既存文書の書き方に合わせる）
- **NFR5 - テスト依存:** テストは Python 標準ライブラリの unittest だけを使う（`test/README.md`）
- **NFR6 - version:** plugin version は変えない（`.claude/rules/core-plugin-version-bump.md`）

## Implementation Approach

### Architecture

**System Architecture:**
```
verify / review の失敗
        │
        ▼
rework-planner の判定（rework-task-synthesis.md 第 9 節）
  1. Wording-correction route
  2. 文書のみ修正経路
  3. rework タスク合成 / SPEC-change 遷移
```

**Component Diagram:**
```
rework-task-synthesis.md 第 9 節 ── 判定の順序と文書のみ修正経路の規則を所有（FR1, FR3, FR5）
agents/rework-planner.md ───────── 文書更新範囲と files 規則（FR2, FR3）
contracts/rework-planner-contract.md ─ 文書更新範囲、write_policy の replace_own 列挙（FR2）、文書修正の宣言（FR7）
references/workflow-patch.md ───── requirements_patch の tests 置き換え操作（FR4）
validate-worker-output.py ──────── files 規則・implement の戻し・tests 置き換え・改名対応の検証（FR3, FR4, FR5, FR7）
skills/develop/SKILL.md ────────── verify 失敗分岐と --once の再開先（FR8）
```

### Data Flow

```
文書のみの回:
rework-planner → VERIFICATION.md / IMPLEMENTATION.md / 既存の tasks/*.md を書き換え
              → append_rework patch（tasks_patch.entries が空、
                 requirements_patch で tests 参照を置き換え、
                 発生元の step だけを pending）
              → validate-worker-output.py --dry-run-apply
              → develop: implement は completed のまま、発生元の step を pending に戻してコミット

混在する回:
rework-planner → 文書の部分を直接修正 + コードの部分だけをタスク化（第 4 節）
              → append_rework patch（implement と発生元の step を pending）
```

### API Design

#### requirements_patch の tests 参照の置き換え（FR4）

- 置き換え前の ID が現在の tests に含まれることを `expected` で確かめ、旧 ID を除いて新 ID を入れる
- `expected` の旧 ID が現在の tests に無いとき expected-mismatch で拒否する（AC4）
- 現状の `_append` 系の追加と status 等の直接代入はそのまま残す

#### rework-planner の completed の結果の宣言（FR7）

- 文書だけで直した項目ごとに、変えた文書と発生元（`origin_kind` / `origin_id`）を宣言する
- シナリオ ID の改名では、改名前と改名後の ID の対応も宣言する
- フィールド名と形は計画段階で決める

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `rework-task-synthesis.md`: 第 9 節の Wording-correction route、第 4 節のグループ化規則、Invariant 1 / Invariant 7
- `implement-phase.md`: Step I.0
- `contracts/spec-writer-contract.md`: `replace_own` の定義
- `test_develop_skill_rewiring.py:276-333`: タスクがある回の既存の前提

**External Dependencies:**
- Python 標準ライブラリ unittest: テスト（NFR5）

### File Structure

```
rework-task-synthesis.md                         # 第 9 節に小節を追加（FR1, FR3, FR5）
agents/rework-planner.md                         # 文書更新範囲と files 規則（FR2, FR3）
contracts/rework-planner-contract.md             # 文書更新範囲と replace_own の列挙（FR2）
references/workflow-patch.md                     # tests 置き換え操作（FR4）
em-workflow/scripts/validate-worker-output.py    # 検証の追加（FR3, FR4, FR5, FR7）
skills/develop/SKILL.md                          # verify 失敗分岐と --once の表（FR8）
tests/test_validate_worker_output.py             # fixture の追加（FR9）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/rework-docs-only-task-routing/**`
- `test-docs/rework-docs-only-task-routing/**`

`feature-docs/rework-docs-only-task-routing/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/rework-docs-only-task-routing/**` covers `test-docs/rework-docs-only-task-routing/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/rework-docs-only-task-routing/` directory at all; the declared
`test-docs/rework-docs-only-task-routing/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 文書のみの回の fixture（`TS<N>`→`TS-<N>` の改名、既存の `tasks/task0001.md`・`task0003.md` の書き換え）が `--dry-run-apply` で通る - 適用後は implement が completed、verify が pending で、旧 tests 参照が除かれ新 ID が入っている（FR1, FR2, FR4, FR5, FR9）
- [ ] TS-2: `files` が `feature-docs/**` だけのタスクを含む fixture - 拒否される（FR3, FR9）
- [ ] TS-3: `files` がコードと `feature-docs/**` の混在するタスクを含む fixture - 拒否される（FR3, FR9）
- [ ] TS-4: `files` がコードだけのタスクの fixture - 通る（既存の挙動を回帰確認）（FR3, FR9）
- [ ] TS-5: entries が空で implement を pending に戻す patch の fixture - 拒否される（FR5, FR9）
- [ ] TS-6: tests 置き換えの `expected` が満たされない fixture - expected-mismatch で拒否される（FR4, FR9）
- [ ] TS-7: 改名後の ID を `covered_by_existing` に挙げる混在の fixture - 対応の宣言ありで通り、宣言なしで拒否される（FR6, FR7, FR9）

### Integration Tests
- [ ] TS-8: `rework-task-synthesis.md` の新しい小節と判定順序を固定する文書テスト - 13 節・Invariant 11 件・Wording-correction route の固定内容は変えない（FR1, FR5, NFR2）
- [ ] TS-9: `rework-planner.md` / `rework-planner-contract.md` の文書更新範囲と `files` 規則を固定する文書テスト（FR2, FR3）
- [ ] TS-10: `develop/SKILL.md` の対話・batch の verify 失敗分岐と --once の表の新しい記述を固定する文書テスト - タスクがある回の既存の文言が残る（FR8, FR9）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] `python3 -m unittest discover -s tests` が全件通る（AC9）

### Edge Cases
- [ ] SPEC.md / REQUIREMENTS.md の変更が要る修正: これまでどおり SPEC-change 遷移に回す（FR1）
- [ ] review 由来の文書のみの回: review を pending に戻す（FR5）
- [ ] 混在する回: 文書の部分は rework-planner が直接直し、コードの部分だけをタスクにする。implement と発生元の step を pending に戻す（FR6）
- [ ] 文書のみの回の batch の数え方: verify rework の `rounds` / `failed_id_counts` に通常どおり数える

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** `validate-worker-output.py` が、`files` に `feature-docs/**` を含むタスク（FR3）、`tasks_patch.entries` が空なのに implement を pending に戻す patch（FR5）、`expected` が満たされない tests 置き換え（FR4）、改名対応の宣言の無い `covered_by_existing`（FR7）を拒否する
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | Requirement |
|------|-------------|-------------|
| expected-mismatch | `requirements_patch` の tests 置き換えで、`expected` の旧 ID が現在の tests に無い | FR4 |
| — | append_rework の `tasks_patch.entries` のうち、`files` に先頭のパス要素が `feature-docs` のパスを 1 つでも含むもの | FR3 |
| — | `tasks_patch.entries` が空なのに `step_patches` が implement を pending に戻す append_rework patch | FR5 |
| — | 混在する回で、改名後の ID を `covered_by_existing` に挙げ、改名の対応の宣言が無い結果 | FR7 |

### Error Flow

```
rework-planner の結果 → validate-worker-output.py → 上の条件に当たれば拒否
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1: タスクの再現手順（feature-docs 配下の文書だけで解消し、要件の tests 参照が変わるため Wording-correction route の対象外になる verify 失敗）に当たる rework-planner の結果が、タスクを含まない append_rework patch として `validate-worker-output.py --dry-run-apply` を通る。適用後は implement が completed、verify が pending で、旧 tests 参照が除かれ新 ID が入っている
- [ ] AC2: `files` に `feature-docs/**` のパスを含むタスク（文書だけでも、コードと混在でも）を持つ rework-planner の結果を、`validate-worker-output.py` が拒否する
- [ ] AC3: `tasks_patch.entries` が空なのに implement を pending に戻す append_rework patch を、`validate-worker-output.py` が拒否する
- [ ] AC4: `requirements_patch` の tests 置き換えは、`expected` の旧 ID が現在の tests に無いとき expected-mismatch で拒否される
- [ ] AC5: 混在する回で、改名後の ID を `covered_by_existing` に挙げ、改名の対応を宣言した結果が通り、対応の宣言が無い結果は拒否される
- [ ] AC6: `rework-task-synthesis.md` 第 9 節に文書のみ修正経路の小節があり、判定順序（Wording-correction route → 文書のみ修正経路 → タスク合成 / SPEC-change）と、implement を pending に戻さないことが書かれている
- [ ] AC7: `agents/rework-planner.md` と `contracts/rework-planner-contract.md` が、既存の `tasks/*.md`・VERIFICATION.md の直接修正、`write_policy` の `replace_own` による列挙、タスクの `files` に `feature-docs/**` を含めない規則を書いている
- [ ] AC8: `skills/develop/SKILL.md` の verify 失敗分岐（対話・batch）と '--once のフェーズ境界' の表が、文書のみの回の遷移と再開先（verify）を書いている
- [ ] AC9: `python3 -m unittest discover -s tests` が全件通る（既存テストの変更なし、または意図した更新だけ）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（`status: tbd` の要件は無い）

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/rework-docs-only-task-routing/REQUIREMENTS.md`
