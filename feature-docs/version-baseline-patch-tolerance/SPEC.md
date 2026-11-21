# Feature: version-baseline-patch-tolerance

## Overview

`tests/test_review_perspective_model_effort_version_bump.py` の版の検査を、ベースラインに対する下限の判定に変える。
4 件の現行版テストが、プラグインの現在の版に対して通るようにする。
以後の GitHub Actions による patch の引き上げや minor の引き上げでも、これらのテストが失敗しないようにする。

## Objectives

- `tests/test_review_perspective_model_effort_version_bump.py` の 4 件の現行版テストが、プラグインの現在の版に対して通る。
- 以後の GitHub Actions による patch の引き上げ、および以後の minor の引き上げで、これらのテストが失敗しない。
- テストを通すためにプラグインの版を手で編集しない。

## User Stories

該当なし。

## Technical Requirements

### Functional Requirements
- **FR1:** 下限による版の検査。`_assert_minor_bump_over_baseline` は、major がベースラインの major と等しく、かつ整数タプル (major, minor, patch) が (ベースライン major, ベースライン minor + 1, 0) 以上である版を受け入れる。patch の値は検査しない。minor に上限を設けない。
- **FR2:** 拒否。`_assert_minor_bump_over_baseline` は、major がベースラインの major と異なる版と、整数タプルが (ベースライン major, ベースライン minor + 1, 0) 未満の版を拒否する。版が無い、または形式が不正な場合は、引き続き `_version_tuple` が拒否する。
- **FR3:** patch が 0 でない場合のテストの反転。`test_rejects_minor_bump_with_nonzero_patch` を、minor を上げて patch が 0 でない値が受け入れられることを確かめるテストに置き換える。
- **FR4:** minor を 2 上げた場合のテストの反転。`test_rejects_minor_raised_by_two` を、ベースラインより minor を 2 上げた値が受け入れられることを確かめるテストに置き換える。
- **FR5:** モジュールの説明文を規則に合わせる。モジュールの docstring（AC-1 の説明と、matcher -> negative-proof の一覧）と `_assert_minor_bump_over_baseline` の docstring は、下限の規則を記述し、置き換えたテストの名前を載せる。
- **FR6:** 複合代入のサブテストは対象外。`[@]` 複合代入のサブテストは対象外とする。`tests/test_destructive_guard_args_json.py` は変更しない。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみ:** モジュールは引き続き標準ライブラリだけを import する。`test_only_standard_library_imports` は引き続き通る。
- **NFR2 - 数値による比較:** 版は整数の要素として比較し、文字列として比較しない。文字列の並び順の罠を扱う 2 件のテストは、変更せずに引き続き通る。
- **NFR3 - 版の編集をせず、具体的な版の値を書かない:** `em-workflow/.claude-plugin/plugin.json`、`em-review/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json` の version 欄は変更しない。SPEC・計画・受け入れ条件には、プラグインの具体的な版の値を書かない。
- **NFR4 - 参照されているテスト名の維持:** `test-docs/review-perspective-model-effort/task0006.tests.yaml` が参照する、このモジュール内のテスト名はすべて名前を変えない。4 件の現行版テストと、その他の manifest および marketplace のテストが対象となる。

## Implementation Approach

### Architecture

**System Architecture:**
```
tests/test_review_perspective_model_effort_version_bump.py
├── EM_WORKFLOW_BASELINE / EM_REVIEW_BASELINE   (ベースライン定数)
├── _version_tuple                               (版を整数タプルにする。版が無い・形式不正は拒否)
└── _assert_minor_bump_over_baseline             (下限による受け入れ・拒否の判定)
```

**Component Diagram:**
```
現行版テスト (4 件)             ─┐
偽のベースラインを使うテスト      ─┼─→ _assert_minor_bump_over_baseline ─→ _version_tuple
                                 ─┘
```

### Data Flow

```
plugin.json / marketplace.json の version
  → _version_tuple → (major, minor, patch)
  → _assert_minor_bump_over_baseline
      major == ベースライン major かつ
      (major, minor, patch) >= (ベースライン major, ベースライン minor + 1, 0) → 受け入れ
      それ以外 → AssertionError
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `test-docs/review-perspective-model-effort/task0006.tests.yaml`: このモジュールのテスト名を参照している。

**External Dependencies:**
- なし（標準ライブラリのみ）。

### File Structure

```
tests/
└── test_review_perspective_model_effort_version_bump.py   # 変更対象
```

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を述べる。上記の機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、既定で、上記の機能固有のパスに加えて次の 2 つのワークフロー生成エントリを宣言する。

- `feature-docs/version-baseline-patch-tolerance/**`
- `test-docs/version-baseline-patch-tolerance/**`

`feature-docs/version-baseline-patch-tolerance/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する設計成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを引用するだけで、その規則を再記述しない。

`test-docs/version-baseline-patch-tolerance/**` はタスクごとのテスト記録 `test-docs/version-baseline-patch-tolerance/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを引用するだけで、その規則を再記述しない。

この 2 つの既定エントリは、SPEC の作成者が明示的に外さない限り宣言に含まれる。記述が無いことをもって外したとはみなさない。外すことは、意図した明示的な絞り込みとして行う。

この宣言は上位集合としての主張である。検証時に観測した実際の変更集合は、宣言した集合に含まれていればよく、一致している必要はない。implement タスクを生まない機能では `test-docs/version-baseline-patch-tolerance/` ディレクトリ自体が生成されない。その場合も、宣言した `test-docs/version-baseline-patch-tolerance/**` は正しく、宣言したパスが実在しないことは違反ではない。

## Test Scenarios

### Unit Tests
- [ ] TS-1: 偽のベースラインに対し、値 (ベースライン major, ベースライン minor + 1, 0) を与える - 受け入れられる（既存の `test_accepts_the_correct_bump`）。
- [ ] TS-2: 偽のベースラインに対し、値 (ベースライン major, ベースライン minor + 1, 0 でない patch) を与える - 受け入れられる。
- [ ] TS-3: 偽のベースラインに対し、値 (ベースライン major, ベースライン minor + 2, 0) を与える - 受け入れられる。
- [ ] TS-4: 偽のベースラインに対し、patch だけを上げた版、変更していない版、minor を下げた版を与える - それぞれ拒否される。
- [ ] TS-5: 偽のベースラインに対し、major が異なり minor がベースライン + 1 の版を与える - 拒否される。
- [ ] TS-6: 文字列の並び順の罠 - 文字列としては小さく並ぶ数値上の引き上げは受け入れられ、文字列としては大きく並ぶ数値上の小さい値は拒否される。

### Integration Tests
- [ ] TS-7: 4 件の現行版テストを、実際の manifest と marketplace のエントリに対して実行する - 通る。

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 未検出

### Edge Cases

該当なし。

### Performance Tests

該当なし。

## Security Considerations

該当なし。

## Error Handling

### Error Codes

該当なし。

### Error Flow

```
版が無い・形式不正 → _version_tuple が拒否
major の不一致、または下限未満 → _assert_minor_bump_over_baseline が AssertionError を送出
```

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC1 (FR1, FR2): `TestEmWorkflowManifest` と `TestEmReviewManifest` の `test_version_is_a_minor_bump_over_baseline`、および `test_em_workflow_entry_version_is_a_minor_bump_over_baseline` と `test_em_review_entry_version_is_a_minor_bump_over_baseline` が、現在のリポジトリのファイルに対して通る。
- [ ] AC2 (FR2): `test_rejects_patch_only_bump`、`test_rejects_unchanged_version`、`test_rejects_major_change`、`test_rejects_lowered_minor`、`test_string_ordering_trap_rejects_a_numerically_lower_version`、`test_entry_without_a_version_fails_the_bump_check` が引き続き通る。いずれも偽の入力に対して引き続き AssertionError を送出する。
- [ ] AC3 (FR3): 偽のベースラインに対し、minor を上げて patch が 0 でない値が受け入れられることで通るテストがモジュールにある。`test_rejects_minor_bump_with_nonzero_patch` は存在しない。
- [ ] AC4 (FR4): 偽のベースラインに対し、minor を 2 上げた値が受け入れられることで通るテストがモジュールにある。`test_rejects_minor_raised_by_two` は存在しない。
- [ ] AC5 (FR2): major がベースラインの major と異なり、数値としては下限を上回る値が拒否される（`test_rejects_major_change`）。
- [ ] AC6 (FR5): モジュールの docstring と `_assert_minor_bump_over_baseline` の docstring が下限の規則を述べ、negative-proof の一覧には存在するテストだけが載っている。
- [ ] AC7 (FR6, NFR3): ベースとの `git diff` に、`tests/test_destructive_guard_args_json.py` の変更と、version 欄の変更が無い。
- [ ] AC8 (NFR1, NFR4): `python3 -m unittest discover -s tests` がこのモジュールについて通り、`test-docs/review-perspective-model-effort/task0006.tests.yaml` が参照するテスト名がすべてモジュール内に存在する。

## Assumptions

- A1: ヘルパー名 `_assert_minor_bump_over_baseline` は維持する。変えるのは規則と docstring だけ。
- A2: `EM_WORKFLOW_BASELINE` と `EM_REVIEW_BASELINE` は現在の値を維持する。
- A3: 置き換える 2 件のテストの新しい名前は実装に委ねる（例: `test_accepts_minor_bump_with_nonzero_patch`、`test_accepts_minor_raised_by_two`）。どちらも `task0006.tests.yaml` からは参照されない。
- A4: `[@]` 複合代入のサブテストは、未マージの args-json-deferred-eval-bypass の integration ブランチにだけ存在し、そこではコミット 854fbb33b が既に `A=([0]=1 [12]=2)` に置き換えている。main を基点とするこの機能はそれに触れない。
- A5: プラグインの版は main への push 時に GitHub Actions が上げ、手で編集しない（`.claude/rules/core-plugin-version-bump.md`）。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## Implementation Phases (if applicable)

該当なし。

## References

- バージョン引き上げの規則: `.claude/rules/core-plugin-version-bump.md`
- 参照されているテスト記録: `test-docs/review-perspective-model-effort/task0006.tests.yaml`
