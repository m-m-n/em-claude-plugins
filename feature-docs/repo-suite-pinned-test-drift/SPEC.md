# Feature: repo-suite-pinned-test-drift

## Overview

リポジトリスイート（`python3 -m unittest discover -s tests`）で現 HEAD に残っている 16 件の失敗を解消する。ピン留めテストの期待値を現行のドキュメント・マニフェスト・`review-rules.yaml` に追随させ、version の特定値ピン留めは下限・一致・形式の検証に置き換える。develop SKILL.md の 1 箇所を言い換え、em-workflow の version を 0.2.4 に上げる。

要件定義書: `feature-docs/repo-suite-pinned-test-drift/REQUIREMENTS.md`

## Objectives

- `python3 -m unittest discover -s tests` がリポジトリルートで終了コード 0 になる。
- verify フェーズで既存失敗と新規回帰を base commit 比較で切り分ける作業を不要にする。

## User Stories

### US1: リポジトリスイートの全件成功
em-workflow の verify フェーズとして、リポジトリスイートを終了コード 0 で通したい。既存失敗と新規回帰を base commit 比較で切り分けずに済むように。

**Acceptance Criteria:**
- [ ] AC1: FR11 の version bump 適用後の integration worktree で `python3 -m unittest discover -s tests` が終了コード 0 で終わる。
- [ ] AC2: Orchestrator が観測した 16 件がすべて pass する（test_abort_terminal_commit_precedence 2 件、test_batch_structured_result_output_version_bump 1 件、test_codex_wrapper_fallback_removal_version_bump 2 件、test_develop_once_option 1 件、test_muse_consent_no_new_questions 1 件、test_muse_consent_version_bump 1 件、test_reviewers_primary_chains 4 件、test_step_c_verify_failed_default 2 件、test_stop_reason_coverage_version_bump 2 件。FR6 / FR7 で改名したものは改名後の名前）。

### US2: version が上がっても失敗しない version 検査
em-workflow の verify フェーズとして、プラグインの version が上がってもピン留めテストが失敗しないようにしたい。

**Acceptance Criteria:**
- [ ] AC3: FR6〜FR9 の version matcher は、偽造した上位 version（例: 99.0.0、両レジストリ一致）を受理し、下限未満の version・形式不正の version・レジストリ不一致を拒否する。
- [ ] AC5: em-workflow の `plugin.json` とマーケットプレイスエントリの version がともに 0.2.4、em-review はともに 0.5.13 のまま。

### US3: ドキュメント・定義側の維持
em-workflow の verify フェーズとして、テスト側の追随のためにドキュメント・選定規則・マニフェストの内容が変わらないようにしたい。

**Acceptance Criteria:**
- [ ] AC4: `em-workflow/skills/develop/SKILL.md` の `AskUserQuestion` 出現数が 7 以下で、`BASELINE_COUNTS` の値は変更されていない。
- [ ] AC6: SKILL.md の argument-hint 行、Step C の文面、`review-rules.yaml` の選定規則、`plugin.json` の description は変更されていない（FR4 の 1 箇所の言い換えを除く）。

## Technical Requirements

### Functional Requirements
- **FR1:** argument-hint 期待値の追随。`tests/test_develop_once_option.py` の `ARGUMENT_HINT_LINE` を、`em-workflow/skills/develop/SKILL.md` 4 行目の現行 argument-hint 行に更新する。`test_argument_hint_line_includes_once_and_retains_existing_tokens` のトークン検査に `--pr` を加える。SKILL.md の argument-hint 行は変更しない。
  ```
  argument-hint: "[feature-path] [--report-only] [--batch] [--once] [--pr] [task-description]"
  ```
- **FR2:** Step C batch 自動選択文面の追随。`tests/test_step_c_verify_failed_default.py` の `BATCH_AUTO_SELECT_PHRASE` を、SKILL.md Step C 1. の現行文面に更新する。比較は既存の `_strip_ws` による空白除去比較のまま。
  ```
  batch: `--pr` 未指定なら質問せず自動で「ブランチを残す」を選ぶ。マージ・push・PR 作成のいずれも行わない
  ```
- **FR3:** Non-packet gates 参照検査の空白正規化。`tests/test_step_c_verify_failed_default.py` の `test_batch_non_packet_gates_reference_present` で、「`batch-mode.md` の Non-packet gates 表」の検査を `_strip_ws` 適用後の部分文字列比較にする（本文 918-919 行で改行をまたいでいるため）。`develop.completion` の検査は維持する。SKILL.md は変更しない。
- **FR4:** develop SKILL.md の AskUserQuestion 出現数を上限内に戻す。`em-workflow/skills/develop/SKILL.md`「引数処理」の `--pr` 項目（106 行目）にある「AskUserQuestion を出さない」を、ツール名 `AskUserQuestion` を含まない表現（例:「質問を出さない」）に言い換え、ファイル内の出現数を 7 以下にする。`tests/test_muse_consent_no_new_questions.py` の `BASELINE_COUNTS` は変更しない。`--pr` の挙動の記述内容は変えない。
- **FR5:** em-workflow マニフェスト非 version ダイジェストの追随。`tests/test_muse_consent_version_bump.py` の `EM_WORKFLOW_MANIFEST_NONVERSION_SHA256` を、現行 `em-workflow/.claude-plugin/plugin.json` の非 version 内容のダイジェスト `bf70d7104511c338b6f076c3d9ab08b6a19b757b59d45397324242f11008ebf0`（`tests/test_batch_structured_result_output_version_bump.py` の `PLUGIN_MANIFEST_NONVERSION_SHA256` と同値）に更新し、基準時点を説明するコメントを更新する。`plugin.json` の description は変更しない。
- **FR6:** abort-terminal-commit-precedence の version リテラル固定の撤去。`tests/test_abort_terminal_commit_precedence.py` の `TestVersionBump` の 2 テストを、`0.2.2` との文字列一致から、`plugin.json` とマーケットプレイスの em-workflow エントリの version が X.Y.Z 形式で、数値比較で 0.2.2 以上、かつ両者が一致する検証に置き換える。テストメソッド名・docstring・`EXPECTED_VERSION` 定数をこの内容に合わせて改める。
- **FR7:** stop-reason-coverage の version リテラル固定の撤去。`tests/test_stop_reason_coverage_version_bump.py` の `test_version_is_the_literal_bump_target` と `test_entry_version_is_the_literal_bump_target` を、`0.2.2` との文字列一致から、数値比較で 0.2.1 以上の検証に置き換える。メソッド名・docstring・モジュール docstring の該当記述を合わせて改める。
- **FR8:** codex-wrapper-fallback-removal の version リテラル固定の撤去。`tests/test_codex_wrapper_fallback_removal_version_bump.py` の `TestSpecificVersionValues` の 2 テストを、`PLUGIN_SPECS[*]["expected"]` との一致から、マニフェストとマーケットプレイスエントリの version が一致し、かつ数値比較で各プラグインの記録済み下限以上である検証に置き換える。`PLUGIN_SPECS` の `"expected"` キーと「later features update this literal」系のコメントを撤去する。
- **FR9:** batch-structured-result-output の em-review version 固定の撤去。`tests/test_batch_structured_result_output_version_bump.py` の `_assert_em_review_entry_unchanged` を、name / author / category / source の完全一致と、version の形式検査（X.Y.Z）に変える。`EM_REVIEW_VERSION` 定数の用途を合わせて改め、`test_em_review_matcher_rejects_altered_identity_field` の `("version", "99.0.0")` ケースは形式不正 version を拒否するケースに置き換える。
- **FR10:** review-rules.yaml 期待値の追随。`tests/test_reviewers_primary_chains.py` の `review-rules.yaml` 検査 4 件を現行定義に更新する。モジュール・クラス docstring の該当記述を合わせて改める。`review-rules.yaml` は変更しない。
  - `test_baseline_unchanged`: `baseline: [comprehensive, security]`
  - `test_rules_block_unchanged`: 現行の 4 規則（data-persistence→performance / concurrency, external-io→performance / api-contract→architecture / if_complexity: high→architecture, comprehensive）
  - `test_cross_validation_data_block_unchanged`: when_any は `- complexity: high` のみ
  - `test_computation_semantics_preserved_in_prose`: 「re-evaluates it after Layer 2」を「Layer 1 settles the value and Layer 2 cannot change it」に置き換える
- **FR11:** em-workflow の version bump。FR4 で em-workflow 配下を変更するため、em-workflow の version を 0.2.3 から 0.2.4 に上げる。変更箇所は `em-workflow/.claude-plugin/plugin.json` の version と `.claude-plugin/marketplace.json` の em-workflow エントリの version の 2 箇所で、同じ値にする。em-review の version は変更しない。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみ:** 変更するテストモジュールは Python 標準ライブラリのみを import する。
- **NFR2 - 現行 version リテラルとの非比較:** FR6〜FR9 で変更した version 検査は、どのプラグインの現行 version のリテラルとも一致比較しない。
- **NFR3 - 否定証明テスト:** 変更・新設した各 matcher は、偽造データに対する否定証明テストを持つ（既存の否定証明が検査対象の変化で無効になる場合は置き換える）。
- **NFR4 - マニフェストの version 以外不変:** `plugin.json` と `marketplace.json` の version 以外のフィールドは変更しない。

## Implementation Approach

### Architecture

該当なし（テストの期待値・検証ロジック、ドキュメント 1 箇所、マニフェスト version の変更のみ）。

### Data Flow

該当なし

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/skills/develop/SKILL.md`: FR1 / FR2 / FR3 / FR4 の検査対象
- `em-workflow/.claude-plugin/plugin.json`: FR5 / FR6 / FR7 / FR8 / FR11 の検査・変更対象
- `.claude-plugin/marketplace.json`: FR6 / FR7 / FR8 / FR9 / FR11 の検査・変更対象
- `review-rules.yaml`: FR10 の検査対象

**External Dependencies:**
- なし（Python 標準ライブラリのみ。NFR1）

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json                              # FR11: version 0.2.4
└── skills/develop/SKILL.md                                  # FR4: 106 行目の言い換え
.claude-plugin/marketplace.json                              # FR11: em-workflow エントリの version 0.2.4
tests/
├── test_develop_once_option.py                              # FR1
├── test_step_c_verify_failed_default.py                     # FR2, FR3
├── test_muse_consent_version_bump.py                        # FR5
├── test_abort_terminal_commit_precedence.py                 # FR6
├── test_stop_reason_coverage_version_bump.py                # FR7
├── test_codex_wrapper_fallback_removal_version_bump.py      # FR8
├── test_batch_structured_result_output_version_bump.py      # FR9
└── test_reviewers_primary_chains.py                         # FR10
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/repo-suite-pinned-test-drift/**`
- `test-docs/repo-suite-pinned-test-drift/**`

`feature-docs/repo-suite-pinned-test-drift/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/repo-suite-pinned-test-drift/**` covers `test-docs/repo-suite-pinned-test-drift/{T}.tests.yaml`, the
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
- [ ] TS2（AC3）: FR6〜FR9 で変更した各 matcher に対し、偽造上位 version（受理）、下限未満（拒否）、形式不正（拒否）、レジストリ不一致（拒否）の各ケースを hermetic なテストで確認する。
- [ ] TS3（AC4）: `test_no_develop_or_review_document_exceeds_its_pinned_budget` が `BASELINE_COUNTS` 無変更のまま pass することを確認する。

### Integration Tests
- [ ] TS1（AC1, AC2）: integration worktree で `python3 -m unittest discover -s tests` を実行し、失敗 0・終了コード 0 を確認する。
- [ ] TS4（AC5）: `tests/test_plugin_version_parity.py` を含む既存の version 一致テストが 0.2.4 で pass することを確認する。
- [ ] TS5（AC6）: 差分を確認し、em-workflow 配下の変更が SKILL.md 106 行付近の 1 箇所と `plugin.json` の version のみであることを確認する。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] 該当なし

### Edge Cases
- [ ] 調査対象外のテストが em-workflow の version リテラル `0.2.3`、または FR4 で言い換える「AskUserQuestion を出さない」の文面をピン留めしている場合、FR4 / FR11 の適用で新たに失敗する。その場合も同じ扱い（リテラル version は下限検証へ、文面は現行へ追随）の対象に含む。AC1 の全件実行で検出する。
- [ ] FR4 の言い換えは Step C 側（910 行目）の `AskUserQuestion` に触れない。`test_step_c_verify_failed_default` の `test_askuserquestion_and_three_way_wording_present` は Step C 節内の出現を要求している。
- [ ] 作業中に main が進み他 feature が version を上げた場合でも、FR6〜FR9 の検証は下限比較のため失敗しない。統合時は FR11 の値をその時点の現行値より大きい patch に合わせる。
- [ ] `plugin.json` の description が将来変わると、非 version ダイジェストを固定している 2 モジュール（`test_muse_consent_version_bump` / `test_batch_structured_result_output_version_bump`）が同時に失敗する。本 feature では description を変えない（NFR4）。

### Performance Tests
- 該当なし

## Security Considerations

- 該当なし

## Error Handling

該当なし

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1〜AC6 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- A1: fba3d7e（`--pr` 追加）と 6c4971e（security 常時選択）の変更は意図どおりであり、ドキュメント・選定規則は戻さずテスト側を追随させる。
- A2: version の特定値ピン留め（FR6〜FR9）は新しい値へ更新せず、下限＋レジストリ一致＋形式の検証に置き換える。version は変更のたびに上がる運用（`.claude/rules/core-plugin-version-bump.md`）で、本 feature 自身も FR11 で bump するため。
- A3: develop SKILL.md の AskUserQuestion 上限超過は、上限（7）を上げずに本文の言い換えで解消する。`test_muse_consent_no_new_questions.py` のモジュール docstring が「the baseline is never raised to make that pass」と定めているため。
- A4: em-workflow の bump は patch（0.2.3 → 0.2.4）とする。変更はドキュメント 1 箇所の言い換えで挙動を変えない。
- A5: タスク記述の `test_codex_wrapper_fallback_removal_version_bump.TestSpecificVersionValues.test_em_workflow_reads_0_1_78` は、現行の `test_em_workflow_manifest_and_entry_agree_on_the_current_version` に改名済みのものを指す。
- A6: 対象範囲はタスク記述の 6 件ではなく、Orchestrator が現 HEAD で観測した 16 件（同種のピン留め追随漏れ）とする。

## References

- 要件定義書: `feature-docs/repo-suite-pinned-test-drift/REQUIREMENTS.md`
- version bump の運用: `.claude/rules/core-plugin-version-bump.md`
