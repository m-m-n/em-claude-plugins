# Feature: consult-litellm-contributor-tier

## Overview

batch の Codex 相談が litellm エントリに移ったとき、同意を記録したリポジトリでは wrapper を `--litellm muse-spark-contributor` で、同意が無ければ `--litellm muse-spark` で呼ぶようにする。この判定は em-workflow/references/question-resolution.md の Codex consultation procedure の中に、review-phase.md Phase R0 と同じ手順として書く。同じ不具合が戻ってきたらテストで検出できるようにする。

この feature は tier `reduced` で進めるため REQUIREMENTS.md は作らず、要件はこの文書に直接書く。

## Objectives

- 同意を記録したリポジトリで batch の Codex 相談が litellm エントリに移ったとき、wrapper を `--litellm muse-spark-contributor` で呼ぶ。同意が無ければ `--litellm muse-spark` で呼ぶ
- この判定を、question-resolution.md の Codex consultation procedure の中に、review-phase.md Phase R0 と同じ手順として書く
- 同じ不具合が戻ってきたらテストで検出できるようにする

## User Stories

該当なし。受け入れ条件は「Acceptance Criteria」節に書く。

## Technical Requirements

### Functional Requirements

- **FR1: 可用性判定に contributor_consented 判定を足す** — em-workflow/references/question-resolution.md の Codex consultation procedure 手順 1（Availability probe）の `litellm` 項目に、`contributor_consented` 判定を加える。判定は litellm エントリが available と判定されたときだけ、最初のターンの前に `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/muse_guard.py" --list --project-dir "{project_root}"` を実行して行う。1 行出力されたら true、何も出力されないか失敗したら false とする。
- **FR2: 呼び出し例のモデル名を判定結果で決める** — 手順 2（Wrapper invocation）の litellm エントリの呼び出し例を、決め打ちの `--litellm muse-spark` から、判定結果で決まる形に書き換える。`contributor_consented` が true なら `--litellm muse-spark-contributor`（wrapper が `-p litellm -m muse-spark-contributor` に展開する）、false なら `--litellm muse-spark`（`-p litellm -m muse-spark` に展開する）とし、両方を書く。
- **FR3: チェーンのエントリと参照の記述を残す** — 手順 1 の `litellm` with the model `muse-spark` というチェーンの記述、`references/reviewers.yaml`'s contributor-tier pre-dispatch criteria (cited, not restated) の参照、"the model name written here is never edited to reach that tier" の一文は残す。チェーンのエントリは `muse-spark` のままにし、変えるのは読み替えだけとする。reviewers.yaml は変更しない。
- **FR4: 判定値は 1 回の相談を通して固定する** — 手順 1 で決めた `contributor_consented` の値を、その相談の litellm エントリの全ターンで使う。ターン途中で codex から litellm に移った場合も同じ値を使う。ターンごとに判定し直さない。
- **FR5: 再発を検出するテスト** — tests/test_consultation_harness_chain.py の TestConsultationProcedureChain にケースを足す。手順 1 の範囲（`1. **Availability probe.**` から `2. **Wrapper invocation.**` まで）に `contributor_consented` と muse_guard.py --list のコマンドが書かれていること、手順 2 の範囲（`2. **Wrapper invocation.**` から `3. **One turn per call.**` まで）に `contributor_consented`、`--litellm muse-spark-contributor`、`--litellm muse-spark` がすべて書かれていることを検査する。テストは標準ライブラリだけで書く。

### Non-Functional Requirements

- **NFR1:** テストは Python 標準ライブラリの unittest だけを使い、サードパーティのパッケージを import しない（test/README.md）。
- **NFR2:** プラグインの version は変えない（.claude/rules/core-plugin-version-bump.md）。今回はバグ修正なので minor / major も上げない。
- **NFR3:** 既存のテスト（tests/test_consultation_harness_chain.py、tests/test_contributor_tier_criteria.py ほか）を修正後も全部通す。
- **NFR4:** run_codex_exec.sh、muse_guard.py（em-workflow / em-review の両方）、reviewers.yaml（em-workflow / em-review の両方）、review-phase.md は変更しない。

## Acceptance Criteria

- [ ] **AC-1**（FR1）: question-resolution.md の手順 1 の litellm 項目に、`contributor_consented`、コマンド `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/muse_guard.py" --list --project-dir "{project_root}"`、true / false の決め方（1 行出力なら true、何も出ないか失敗なら false）、litellm エントリが available のときだけ実行することが書かれている。
- [ ] **AC-2**（FR2）: 手順 2 に、`contributor_consented` が true のとき `--litellm muse-spark-contributor`、false のとき `--litellm muse-spark` を使うことが両方書かれている。
- [ ] **AC-3**（FR4）: 手順 1 の判定値を相談の全ターンで使い、ターンごとに判定し直さないことが書かれている。
- [ ] **AC-4**（FR3）: FR3 で残すとした記述がすべて残っていて、reviewers.yaml の両方の registry のチェーンに `muse-spark-contributor` が出てこない（既存の tests/test_consultation_harness_chain.py AC-5 / AC-8 と tests/test_contributor_tier_criteria.py の AC-5 が通る）。
- [ ] **AC-5**（FR5）: FR5 で足したテストが、修正前の question-resolution.md（base revision）では失敗し、修正後は通る。
- [ ] **AC-6**（NFR1, NFR3）: `python3 -m unittest discover -s tests` が全部通る。

## Implementation Approach

### Architecture

変更対象は Markdown の手順書 1 つとユニットテストだけで、UI も視覚的な成果物も無い（design step は skipped）。

**変更するファイル:**

- `em-workflow/references/question-resolution.md` — Codex consultation procedure の手順 1（FR1, FR3, FR4）と手順 2（FR2）
- `tests/test_consultation_harness_chain.py` — TestConsultationProcedureChain へのケース追加（FR5）

**変更しないファイル（NFR4、FR3）:**

- run_codex_exec.sh
- muse_guard.py（em-workflow / em-review の両方）
- reviewers.yaml（em-workflow / em-review の両方）
- review-phase.md

### Data Flow

```
手順 1 Availability probe
  └─ litellm エントリが available
       └─ 最初のターンの前に muse_guard.py --list --project-dir "{project_root}" を実行
            ├─ 1 行出力                → contributor_consented = true
            └─ 出力なし / 失敗         → contributor_consented = false
手順 2 Wrapper invocation（litellm エントリ、相談の全ターンで同じ値を使う）
  ├─ true  → --litellm muse-spark-contributor（-p litellm -m muse-spark-contributor）
  └─ false → --litellm muse-spark（-p litellm -m muse-spark）
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**

- review-phase.md Phase R0: 判定手順をこれと同じにする
- tests/test_contributor_tier_criteria.py の CONSENT_CHECK_COMMAND: 判定コマンドの文字列をこれと同じにする（A-3）
- `references/reviewers.yaml` の contributor-tier pre-dispatch criteria: 手順 1 から引用で参照し続ける（FR3、A-8）

**External Dependencies:**

- なし（テストは Python 標準ライブラリの unittest だけを使う。NFR1）

### File Structure

```
em-workflow/
└── references/
    └── question-resolution.md        # Codex consultation procedure 手順 1 / 手順 2
tests/
└── test_consultation_harness_chain.py # TestConsultationProcedureChain にケースを追加
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/consult-litellm-contributor-tier/**`
- `test-docs/consult-litellm-contributor-tier/**`

`feature-docs/consult-litellm-contributor-tier/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/consult-litellm-contributor-tier/**` covers
`test-docs/consult-litellm-contributor-tier/{T}.tests.yaml`, the per-task
test record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/consult-litellm-contributor-tier/` directory at all; the declared
`test-docs/consult-litellm-contributor-tier/**` entry is still correct in
that case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1: 手順 1 に判定手順がある**（AC-1 / FR1）— Codex consultation procedure 節を切り出し、手順 1 と手順 2 の見出しで区切った範囲の空白を正規化してから、`contributor_consented` と muse_guard.py --list コマンドの文字列を assertIn で確かめる
- [ ] **TS-2: 手順 2 に両方のモデル名がある**（AC-2 / FR2）— 手順 2 から手順 3 の見出しまでの範囲で、`--litellm muse-spark-contributor`、`--litellm muse-spark`、`contributor_consented` を assertIn で確かめる
- [ ] **TS-3: 判定値の固定**（AC-3 / FR4）— 手順 1 か 2 に、判定値を相談の全ターンで使い、判定し直さないことを表す文があるかを assertIn で確かめる
- [ ] **TS-4: 残す記述と既存の固定値**（AC-4 / FR3）— 既存の test_contributor_read_mapping_is_cited_not_restated、test_probe_states_two_entries_in_order、test_wrapper_invocation_carries_the_litellm_flag、TestRegistriesAssignOnlyMuseSpark、TestAC5ChainImmutability が修正後も通ることを確かめる
- [ ] **TS-5: 再発の検出**（AC-5 / FR5）— base revision cca44706 の question-resolution.md に対して新しいケースが失敗することを確かめる（手順 2 に `--litellm muse-spark-contributor` が無く、手順 1 に `contributor_consented` も無いため）
- [ ] **TS-6: 全テスト**（AC-6 / NFR1, NFR3）— `python3 -m unittest discover -s tests`

### Integration Tests

該当なし。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] Existing E2E tests pass without regression

実際の batch 実行を再現する自動テストは作らない（A-1）。

### Edge Cases

- [ ] ターン途中で codex から litellm に移った場合: 手順 1 で決めた `contributor_consented` の値をそのまま使う（FR4）
- [ ] 判定値を出してから wrapper を呼ぶまでの間に同意が取り消され、muse_guard のフックが呼び出しを deny した場合: 専用の処理は足さない。判定は相談ごとに 1 回だけ行う（A-7）

### Performance Tests

該当なし。

## Security Considerations

該当なし。

## Error Handling

- 判定コマンドが失敗した場合は `contributor_consented` を false とする（FR1）。

## Performance Optimization

該当なし。

## Assumptions

- **A-1:** 完了の定義の「再現手順で現象が起きない」は、オーケストレーターが読む手順書（question-resolution.md）に判定手順と両方の呼び出し例が書かれていることで満たすとする。実際の batch 実行を再現する自動テストは作らない。
- **A-2:** 再発を検出するテストの置き場所は、check-plugin-invariants.py ではなく tests/test_consultation_harness_chain.py とする。同じ節をすでに検査しているファイルであり、check-plugin-invariants.py には question-resolution.md の litellm に関する検査が無いため。
- **A-3:** 判定コマンドは review-phase.md Phase R0 と同じ文字列（tests/test_contributor_tier_criteria.py の CONSENT_CHECK_COMMAND と同じ）にする。muse_guard.py --list は同意が無ければ何も出力せず exit 0 で、引数の誤りなら exit 2 なので、「1 行出力なら true、何も出ないか失敗なら false」で両方の場合を扱える。
- **A-4:** 直す対象は em-workflow の question-resolution.md だけとする。Codex consultation procedure は em-workflow にしかなく、batch-mode.md など他の batch の相談箇所はこの手順を参照しているだけなので、変更しなくても修正が効く。
- **A-5:** muse_guard.py の docstring に「The review phase invokes only the read-only --list」とあり、修正後は説明として足りなくなる。それでも em-workflow / em-review の 2 つのコピーを揃えたまま保つため、今回は変更しない。
- **A-6:** 課題に書かれた範囲外の観察（01:12:54 JST の相談で codex エントリを試さずに litellm エントリで呼んでいた件）は、この feature では扱わない。
- **A-7:** 判定値を出してから wrapper を呼ぶまでの間に同意が取り消され、muse_guard のフックが呼び出しを deny した場合について、専用の処理は足さない。Phase R0 と同じく、判定は相談ごとに 1 回だけ行う。
- **A-8:** 手順 1 の (cited, not restated) という表現は残す。contributor tier の規則（同意だけが条件であること）は今後も reviewers.yaml が持ち、question-resolution.md に足すのは判定の手順だけで、review-phase.md Phase R0 と同じ分け方になる。

## Success Criteria

- [ ] AC-1 から AC-6 をすべて満たす
- [ ] TS-1 から TS-6 がすべて通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件は無い）。

## References

- Codex consultation procedure: `em-workflow/references/question-resolution.md`
- Phase R0: `em-workflow/references/review-phase.md`
- contributor-tier pre-dispatch criteria: `em-workflow/references/reviewers.yaml`
- 既存テスト: `tests/test_consultation_harness_chain.py`、`tests/test_contributor_tier_criteria.py`
