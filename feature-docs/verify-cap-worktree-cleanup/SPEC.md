# Feature: verify-cap-worktree-cleanup

要件定義書: `feature-docs/verify-cap-worktree-cleanup/REQUIREMENTS.md`

## Overview

verify が cap 到達で failed のまま Step C（完了処理）に入る batch 走行で、failed-run-cleanup-guard の判定を develop の Step C の規定に揃える。除外状態の feature を対象とする `git worktree remove`（S1）と `gh pr create`（S3）に、フックは判定を出さない。`git branch -d` / `--delete`（S2）と、除外状態にあたらない failed の扱いは変えない。

## Objectives

- verify が cap 到達で failed のまま Step C に入る batch 走行で、develop の Step C の規定と failed-run-cleanup-guard の判定を一致させる。Step C が completion_aborted で止まらず、worktree の削除を人が手で行わなくてよい状態にする。
- 同じ食い違いの再発を検出するテストを用意する。

## User Stories

### US1: cap 到達走行の Step C での worktree 削除と PR 作成
batch 走行として、除外状態の feature の Step C で S1 と S3 をフックに止められずに実行したい。Step C が completion_aborted で止まらないようにするため。

**Acceptance Criteria:**
- [ ] AC1: 除外状態の workflow.yaml を持つ integration worktree の絶対パスを対象とした `git worktree remove` に対し、フックは何も出力せず終了コード 0 で終わる。CLAUDE_BATCH を設定した場合も同じ。（FR1, FR2）
- [ ] AC2: 除外状態の integration worktree を cwd とする `gh pr create` に対し、フックは判定を出さない。（FR1, FR2）
- [ ] AC5: 系譜 cap だけ（failed_id_counts のある値が 2、rounds が 1）と hard cap だけ（rounds が 3、failed_id_counts の全値が 1）の両方で、除外が成り立つ。（FR2, FR3）
- [ ] AC6: S1 の対象を静的に解決できない（変数展開）場合、到達できる integration worktree が除外状態の 1 つだけなら判定を出さない。S2 の対象を静的に解決できない場合は、同じ配置で ask（CLAUDE_BATCH 下では deny）を出す。（FR5）

### US2: 除外状態以外の保護の維持
ガードとして、除外状態にあたらない failed と S2 には従来どおりの判定を出したい。

**Acceptance Criteria:**
- [ ] AC3: 除外状態の feature の `git branch -d em-workflow/{feature}/integration` に対し、フックは deny を出し、理由に feature と step verify を含む。（FR4）
- [ ] AC4: 次のいずれかの場合、S1 は deny される: retrospect が completed でない、verify 以外の step も failed、failed が verify 以外の step だけ、batch ブロックが無い、rounds < 3 かつ failed_id_counts の全値 < 2、cap 記録の型が不正。（FR2, FR3, FR6）
- [ ] AC8: 既存のテスト（`tests/test_failed_run_cleanup_guard.py`, `tests/test_guard_deferral_parity.py`, `tests/test_verify_cap_run_continuation.py`, `tests/test_step_c_verify_failed_default.py`, `tests/test_hooks_registration.py`, `tests/test_guardrail_hooks_migration.py`）と `python3 -m unittest discover -s tests` が通る。（FR6, FR8, NFR1, NFR2, NFR4）

### US3: 文書
フックの利用者として、除外状態と S2 の扱いを docstring と README で読めるようにしたい。

**Acceptance Criteria:**
- [ ] AC7: フックの docstring と README のフック一覧の行が、除外状態と S2 の扱いを記述している。（FR7）

## Technical Requirements

### Functional Requirements
- **FR1:** 揃える方向。failed-run-cleanup-guard 側で揃える。除外状態（FR2）の feature を対象とする S1（`git worktree remove`）と S3（`gh pr create`）には、フックは判定を出さない。`em-workflow/skills/develop/SKILL.md` の Step C 2. の worktree 削除規定と、cap 到達走行の detail 文言（「Step C まで到達し、worktree 掃除と終了報告は完了した」）は変えない。
- **FR2:** 除外状態の判定。対象 feature の workflow.yaml が次をすべて満たすときを除外状態とする。
    - (a) status が failed のトップレベル step は id が verify の step だけ
    - (b) id が retrospect の step があり、その status が completed
    - (c) それ以外のトップレベル step の status はすべて completed か skipped
    - (d) batch.verify_rework が系譜 cap（failed_id_counts のいずれかの値が 2 以上）か hard cap（rounds が 3 以上）の到達を示す
- **FR3:** cap 記録の読み方。
    - batch または batch.verify_rework が無い場合、または mapping でない場合は除外しない。
    - verify_rework の rounds / failed_id_counts のうち欠けているメンバーは未設定（rounds: 0、failed_id_counts: {}）として読む。
    - 存在するメンバーの型が不正な場合は、cap 記録全体を不正として除外しない。型が不正とは、rounds が整数でない（bool を含む）、failed_id_counts が mapping でない、failed_id_counts の値に整数でない（bool を含む）ものがある、のいずれか。
    - 廃止キー verify_rework_count は無視する。
    - batch ブロックがあることだけを batch 実行の根拠にはしない。
- **FR4:** S2 は従来どおり。S2（`git branch -d` / `--delete`）は除外しない。除外状態の feature を対象とする S2 は従来どおり deny する。
- **FR5:** 静的に解決できない対象での扱い。対象を静的に解決できない場合の判定（any_failed_worktree）はコマンド形ごとに行う。
    - S1 では、除外状態の worktree を健全なものとして数える。
    - S2 では、除外状態の worktree も従来どおり failed として数える。
    - 判定結果のメモ化は、コマンド形の違いで結果が混ざらないようにする。
    - worktree を 1 つも列挙できない場合に ask を残す挙動は変えない。
- **FR6:** 除外状態以外の deny の維持。除外状態にあたらない failed では、S1/S2/S3 に対する deny と、静的に解決できない対象への ask（CLAUDE_BATCH 下では deny）、deny 理由の文言を今のまま保つ。除外状態にあたらない failed とは、implement / review などの failed、verify と他の step が同時に failed、verify だけが failed で retrospect が completed でない、cap 記録が cap 到達を示さない・欠落・不正、のいずれか。
- **FR7:** 文書の更新。`em-workflow/hooks/failed-run-cleanup-guard.py` のモジュール docstring の判定モデルと、`em-workflow/README.md` のフック一覧にある failed-run-cleanup-guard.py の行を、除外状態と S2 の扱いを含めて更新する。
- **FR8:** 再発検出テスト。`tests/test_failed_run_cleanup_guard.py` に、除外状態の workflow.yaml フィクスチャで S1/S3 に判定が出ないこと、S2 が deny されること、除外の各条件が欠けたときに deny されることを確認するケースを追加する。

### Non-Functional Requirements
- **NFR1 - allow を出さない:** ガードは allow を出さない。除外は「判定なし」で表す。
- **NFR2 - 静的解析のみ:** subprocess を起動せず、ファイルを書かない。workflow.yaml の読み込みは対象 1 件につき 1 回までとする。
- **NFR3 - 信頼できない入力:** workflow.yaml は信頼できない入力として扱う。判定に使うのはトップレベル step の id / status と batch.verify_rework の数値だけで、goal などの自由記述は判定に使わない。
- **NFR4 - fail-open の維持:** workflow.yaml の欠落・パース失敗・PyYAML が使えない・内部エラーのときに判定を出さない挙動を変えない。
- **NFR5 - cap 値の一致:** フックが持つ cap の閾値（failed_id_counts の値 2、rounds 3）は、`skills/develop/SKILL.md`「batch 自動 rework の系譜 cap」の定義と一致する。
- **NFR6 - テスト規約:** テストは標準ライブラリの unittest だけを使い、tempfile のフィクスチャで動かす。実際の worktree や ~/.claude には触れない。
- **NFR7 - version:** プラグインの version は変更しない。

## Implementation Approach

### Architecture

コマンド形ごとの判定:

| コマンド形 | 除外状態の feature | 除外状態にあたらない failed の feature |
|---|---|---|
| S1 `git worktree remove` | 判定なし | deny（従来どおり） |
| S2 `git branch -d` / `--delete` | deny（従来どおり） | deny（従来どおり） |
| S3 `gh pr create` | 判定なし | deny（従来どおり） |

対象を静的に解決できない場合（any_failed_worktree）:

| コマンド形 | 除外状態の worktree の数え方 |
|---|---|
| S1 | 健全なものとして数える |
| S2 | failed として数える（従来どおり） |

worktree を 1 つも列挙できない場合の ask は変えない。CLAUDE_BATCH 下での ask から deny への降格も変えない。

### Data Flow

```
workflow.yaml → トップレベル step の id / status と batch.verify_rework の数値だけを読む
             → 除外状態の判定（FR2, FR3）
             → コマンド形（S1 / S2 / S3）ごとの判定
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/skills/develop/SKILL.md`: Step C 2. の worktree 削除規定と「batch 自動 rework の系譜 cap」の定義（NFR5）。変更しない。
- `em-workflow/hooks/destructive-guard.py`: `matches_target_shape()` による blanket allow の保留は変えない（A4）。

**External Dependencies:**
- PyYAML: 使えない場合は判定を出さない（NFR4）。

### File Structure

```
em-workflow/
├── hooks/
│   └── failed-run-cleanup-guard.py   # 除外状態の判定、docstring の更新
└── README.md                         # フック一覧の failed-run-cleanup-guard.py の行
tests/
└── test_failed_run_cleanup_guard.py  # ケース追加
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/verify-cap-worktree-cleanup/**`
- `test-docs/verify-cap-worktree-cleanup/**`

`feature-docs/verify-cap-worktree-cleanup/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/verify-cap-worktree-cleanup/**` covers `test-docs/verify-cap-worktree-cleanup/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/verify-cap-worktree-cleanup/` directory at all; the declared
`test-docs/verify-cap-worktree-cleanup/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 除外状態での S1 - step（create-spec / design skipped / create-plan / implement / review completed、verify failed、retrospect completed）と batch.verify_rework（rounds: 1, failed_id_counts: {V1: 2}）を持つフィクスチャを作り、`git worktree remove <絶対パス>` のペイロードをフックに渡す。CLAUDE_BATCH ありとなしの両方で実行する。期待: stdout が空で、終了コード 0（AC1, AC5）
- [ ] TS-2: hard cap だけでの S1 - TS-1 と同じ step で、batch.verify_rework を rounds: 3, failed_id_counts: {V1: 1} にする。期待: stdout が空（AC5）
- [ ] TS-3: 除外状態での S3 - TS-1 のフィクスチャの integration worktree を cwd にして `gh pr create` を渡す。期待: stdout が空（AC2）
- [ ] TS-4: 除外状態での S2 - TS-1 のフィクスチャのルートを cwd にして `git branch -d em-workflow/{feature}/integration` を渡す。期待: deny。理由に feature と verify を含む（AC3）
- [ ] TS-5: 除外条件の欠落 - TS-1 から 1 条件ずつ崩したフィクスチャで S1 を渡す: retrospect pending、implement も failed、batch ブロック無し、rounds: 2 で failed_id_counts の全値 1、rounds が文字列、failed_id_counts がリスト、failed_id_counts の値が true。期待: いずれも deny（AC4）
- [ ] TS-6: 静的に解決できない対象 - 除外状態の worktree だけを置いたルートを cwd にして、`git worktree remove "$WT"` と `git branch -d "$BR"` をそれぞれ渡す。期待: S1 は stdout が空。S2 は ask（CLAUDE_BATCH ありでは deny）（AC6）

### Integration Tests
- [ ] TS-7: 既存挙動の回帰 - 既存の `tests/test_failed_run_cleanup_guard.py`, `tests/test_guard_deferral_parity.py` ほか AC8 に挙げたテストを実行する。期待: 全件 pass（AC8）
- [ ] TS-8: 文書 - フックの docstring と `em-workflow/README.md` の failed-run-cleanup-guard.py の行を確認する。期待: 除外状態の条件と、S2 が除外されないことが書かれている（AC7）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 系譜 cap だけ / hard cap だけでの成立（TS-1, TS-2）
- [ ] rounds: 2 かつ failed_id_counts の全値 1 で不成立（TS-5）
- [ ] rounds が文字列、failed_id_counts がリスト、failed_id_counts の値が bool の場合は不成立（TS-5）

### Performance Tests

該当なし。

## Security Considerations

- **Input Validation:** workflow.yaml は信頼できない入力として扱う。判定に使うのはトップレベル step の id / status と batch.verify_rework の数値だけで、goal などの自由記述は判定に使わない（NFR3）。cap 記録の型が不正な場合は除外しない（FR3）。
- ガードは allow を出さない（NFR1）。subprocess を起動せず、ファイルを書かない（NFR2）。

## Error Handling

| 状況 | 挙動 |
|---|---|
| workflow.yaml の欠落・パース失敗・PyYAML が使えない・内部エラー | 判定を出さない（NFR4、従来どおり） |
| batch / batch.verify_rework が無い、または mapping でない | 除外しない（FR3） |
| cap 記録のメンバーの型が不正 | 除外しない（FR3） |
| 静的に解決できない対象で worktree を 1 つも列挙できない | ask（従来どおり、FR5） |

## Performance Optimization

- workflow.yaml の読み込みは対象 1 件につき 1 回までとする（NFR2）。
- any_failed_worktree の判定結果のメモ化は、コマンド形の違いで結果が混ざらないようにする（FR5）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

なし。

## Assumptions

- A1: 除外状態にあたらない failed に対する S1/S2/S3 の deny と、その理由文言は変えない。
- A2: ガードが allow を出さない不変条件と、subprocess を使わない不変条件は保つ。
- A3: cap 記録のメンバーが欠けている場合は workflow-schema.md の未設定の読み方（rounds: 0、failed_id_counts: {}）に従い、存在するメンバーの型が不正な場合は記録全体を不正として除外しない。
- A4: destructive-guard.py の matches_target_shape() による blanket allow の保留は変えない。除外状態の S1/S3 は、健全な worktree に対する S1/S3 と同じ扱いになる。
- A5: SKILL.md の Step C 2. の --force を使わない規定と、remove が失敗したら worktree とブランチを残して中断する規定は変えない。
- A6: プラグインの version は変更しない。

## References

- 要件定義書: `feature-docs/verify-cap-worktree-cleanup/REQUIREMENTS.md`
- `em-workflow/skills/develop/SKILL.md`: Step C、「batch 自動 rework の系譜 cap」
- `em-workflow/hooks/failed-run-cleanup-guard.py`
- `em-workflow/README.md`
- `tests/test_failed_run_cleanup_guard.py`
