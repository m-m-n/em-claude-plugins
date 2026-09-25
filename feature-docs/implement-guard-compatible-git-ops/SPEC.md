# Feature: implement-guard-compatible-git-ops

## Overview

destructive-guard が有効な環境で、em-workflow の implement フェーズが規定する git 操作のうち範囲内のもの（全 refresh 箇所と I.2.b step 4）が拒否されずに完走するよう、プロトコル側を修正する。hook の判定ロジックは変更しない。プロトコル本文と hook の判定のずれは、ケース表と文書抽出テストで検出する。

要件の詳細は `feature-docs/implement-guard-compatible-git-ops/REQUIREMENTS.md` を参照する。

## Objectives

- destructive-guard が有効な環境で、em-workflow の implement フェーズが規定する git 操作のうち範囲内のもの（全 refresh 箇所と I.2.b step 4）が拒否されずに完走する。
- hook と両立させる方針をプロトコル側の修正に決め、hook の検知力は削らない。
- プロトコル本文と hook の判定がずれたことを、テストで検出できるようにする。

## User Stories

### US1: 範囲内の git 操作が hook に拒否されない
As a em-workflow の利用者, I want to destructive-guard が有効な環境で implement フェーズの範囲内の git 操作（全 refresh 箇所と I.2.b step 4）を実行する, so that それらが拒否されずに完走する.

**Acceptance Criteria:**
- [ ] AC-1: implement-phase.md の I.2.b step 4 に `git branch -D` が無い。`git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` があり、それが `git worktree remove "$WT_ROOT/{T}"` より後に置かれている。
- [ ] AC-2: I.2.b step 4 に、-d が拒否されたときは強制削除せずにブランチを残して報告する、という規定がある。
- [ ] AC-3: 範囲内の全 refresh 箇所の文言が `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`（または同じ形の `"$WT_ROOT/integration"`）のまま残っている。Branch & Worktree Model に、対象をリテラルのブランチ名で書く規定がある。
- [ ] AC-4: Branch & Worktree Model の artifact 書き込みの項に、Write ツールで書くこと、`commit-docs.sh` と同じ Bash 呼び出しにヒアドキュメントを含めないこと、の規定がある。

### US2: プロトコルと hook のずれをテストで検出する
As a em-workflow の利用者, I want to プロトコル本文と hook の判定のずれをテストで検出する, so that ずれが再発したときに気づける.

**Acceptance Criteria:**
- [ ] AC-5: `destructive-guard-cases.json` に FR5 の allow ケースと deny の対照ケースがあり、`python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する。
- [ ] AC-6: 新しい文書抽出テストが、範囲内の各箇所から 1 件以上のコマンドを抽出し、そのどれもが deny/ask にならないことを確かめる。延期した 2 箇所は明示的な除外リストに載っている。
- [ ] AC-7: `python3 -m unittest discover -s tests` が全件 pass する。

### US3: 変更を配布し、範囲外を記録する
As a em-workflow の利用者, I want to 変更が新しい version として配布され、範囲外の既知の未対応が記録されている, so that インストール済みのプラグインに変更が反映され、残りの対応が追える.

**Acceptance Criteria:**
- [ ] AC-8: plugin.json と marketplace.json の em-workflow の version が、同じ新しい値になっている。
- [ ] AC-9: 延期した箇所（I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup）が SPEC に範囲外の既知の未対応として記録されている。

## Technical Requirements

### Functional Requirements
- **FR1:** マージ済み task ブランチを -d で削除する。`em-workflow/references/implement-phase.md` I.2.b step 4 のブランチ削除を `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` に書き換える。直前の `git worktree remove "$WT_ROOT/{T}"` はそのまま残し、順序も worktree 削除が先のまま変えない。`-D` を使う理由を述べた既存コメントは削除し、代わりに -d で通る理由を書く。integration worktree の HEAD は integration ブランチであり、そのブランチはマージ済みであることを `merge-base --is-ancestor` で確認済みのタスクブランチを含む、という理由。
- **FR2:** -d が拒否されたときも強制削除しない。I.2.b step 4 の `branch -d` が失敗したら、`-D` などの強制削除には切り替えない。ブランチは残し、wake phase の報告に対象のブランチ名を書く。
- **FR3:** refresh のリテラル形を維持し、対象の書き方を明記する。全 refresh 箇所（implement-phase.md の Branch & Worktree Model / I.1 / I.2.a step 2 / I.2.b step 2 / I.2.c、phase-state.md の Phase-state と Artifact-commit の exit-4 recovery、skills/develop/SKILL.md の Step A と exit-4 リカバリ、references/phases/create-spec-phase.md の stale handling）の `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration` はリテラル形のまま変えない。implement-phase.md の Branch & Worktree Model の refresh の項に、reset の対象はリテラルのブランチ名 `em-workflow/{feature}/integration` で書き、シェル変数・キャプチャした SHA・HEAD・`refs/heads/` 接頭辞・対象の省略は使わない、と 1 回だけ明記する。
- **FR4:** ドキュメントの書き込みとヒアドキュメント。implement-phase.md の Branch & Worktree Model で workflow artifact の書き込みを定めている項（"Every workflow artifact ..."）に、次を規定する。artifact は Write ツールで書く。Bash のヒアドキュメントで書かない。`commit-docs.sh` を実行する Bash 呼び出しにヒアドキュメントを含めない。
- **FR5:** hook ケース表にプロトコル形状を追加する。`em-workflow/hooks/tests/destructive-guard-cases.json` に `[期待する判定, ラベル, コマンド]` の形でケースを追加する。allow ケースは次の 3 つ。`git -C /home/sakura/.claude/worktrees/em-workflow/some-feature/integration reset --hard em-workflow/some-feature/integration`、`git -C /home/sakura/.claude/worktrees/em-workflow/some-feature/integration branch -d em-workflow/some-feature/task0001`、`git worktree remove /home/sakura/.claude/worktrees/em-workflow/some-feature/task0001`。対照として、リテラル以外の対象が deny のままであることを示すケースを追加する（例: `refs/heads/` 付き、`"$BRANCH"`）。既存ケースは削除も変更もしない。
- **FR6:** 文書抽出テスト。tests/ に unittest を新規に追加する。範囲内の各箇所（FR3 の全 refresh 箇所と、I.2.b step 4 の `git worktree remove` / `git branch -d`）から git コマンドのリテラルを抽出し、プレースホルダ（`{integration_worktree}`、`$WT_ROOT`、`{feature}`、`{T}`）を具体値に展開して `em-workflow/hooks/destructive-guard.py` に subprocess で渡す。判定が deny でも ask でもないことを確かめる。延期した箇所（I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup）は、テスト内の明示的な除外リストに箇所名つきで載せる。範囲内の各箇所からコマンドが少なくとも 1 件抽出されることも確かめる。これで抽出漏れによる素通りを防ぐ。
- **FR7:** 延期した箇所を記録する。I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup は、`git worktree remove --force` と未マージブランチへの `git branch -D` を使う。これらを今回の範囲外の既知の未対応として SPEC に記録し（本書の「Out of Scope (Known Unaddressed)」）、後続タスクに起票する。完了扱いにはしない。
- **FR8:** version を上げる。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの version を、同じ値のパッチ版（0.2.8 → 0.2.9）に上げる。中身の変更と同じ変更に含める。

### Non-Functional Requirements
- **NFR1 - hook ロジック不変:** `em-workflow/hooks/destructive-guard.py` と `/home/sakura/.claude/hooks/destructive-guard.py` の判定ロジックは変更しない。変更はリポジトリ内に限る。
- **NFR2 - 既存ケースの維持:** `destructive-guard-cases.json` の既存ケースは削除も期待値の変更もしない。`tests/test_destructive_guard_command_substitution.py` の `TestCaseTableDiscipline` が引き続き通ること。
- **NFR3 - テストの依存と隔離:** テストは Python 標準ライブラリの unittest だけを使う。実際の `~/.claude` の状態には触れない。`CLAUDE_BATCH` を外して hook を起動する。
- **NFR4 - 既存テストのアンカー保護:** FR3 で足す文と FR1 で書き換えるコメントに、既存テストが否定アンカーにしている綴りを含めない。対象は `reset --hard "$LAUNCH_TIP"`、`reset --hard "$COMPLETION_TIP"`、`reset --hard "${var}"` の各形。step ごとのセクション内に新たな `reset --hard` を足さない。`tests/test_tip_capture_idiom_uniformity.py` と `tests/test_exit4_tip_argument_consistency.py` が固定している出現位置と順序を崩さないため。
- **NFR5 - I.2.c の文言維持:** I.2.c セクション内の `git branch -D` の出現回数（1 回）と `git worktree remove --force` の文言は変えない（`tests/test_routeback_reset_scope_consistency.py`、`tests/test_implement_routeback_gate.py`、`tests/test_recycled_task_id_consistency.py`）。

## Out of Scope (Known Unaddressed)

次の箇所は今回の範囲外の既知の未対応とする（FR7、A-C2）。後続タスクに起票する。完了扱いにはしない。

| 箇所 | 使うコマンド |
|------|--------------|
| I.2.a の resume guard の clean re-attempt | `git worktree remove --force`、未マージブランチへの `git branch -D` |
| I.2.c の route-back cleanup | `git worktree remove --force`、未マージブランチへの `git branch -D` |

FR6 の文書抽出テストでは、この 2 箇所を明示的な除外リストに箇所名つきで載せる。

## Implementation Approach

### Architecture

**System Architecture:**
該当なし

**Component Diagram:**
```
プロトコル文書 (implement-phase.md / phase-state.md / SKILL.md / create-spec-phase.md)
        │ git コマンドのリテラルを抽出 (FR6)
        ▼
文書抽出テスト (tests/ の新規 unittest)
        │ subprocess
        ▼
em-workflow/hooks/destructive-guard.py (判定ロジックは変更しない: NFR1)
        ▲
        │ ケースを渡す
em-workflow/hooks/tests/run-destructive-guard.py ← destructive-guard-cases.json (FR5)
```

### Data Flow

```
範囲内の各箇所の git コマンドのリテラル
  → プレースホルダ展開 ({integration_worktree}、$WT_ROOT、{feature}、{T} → 具体値)
  → destructive-guard.py (subprocess、CLAUDE_BATCH を外す)
  → 判定が deny でも ask でもないことを確認
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: FR5 のケースと FR6 のテストの判定対象。判定ロジックは変更しない（NFR1）。
- 既存テスト（`tests/test_destructive_guard_command_substitution.py`、`tests/test_tip_capture_idiom_uniformity.py`、`tests/test_exit4_tip_argument_consistency.py`、`tests/test_routeback_reset_scope_consistency.py`、`tests/test_implement_routeback_gate.py`、`tests/test_recycled_task_id_consistency.py`）: 引き続き通ること（NFR2、NFR4、NFR5）。

**External Dependencies:**
- Python 標準ライブラリ unittest: テストに使う（NFR3）。

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json                  # version 0.2.8 → 0.2.9 (FR8)
├── references/implement-phase.md               # FR1, FR2, FR3, FR4
└── hooks/tests/destructive-guard-cases.json    # ケース追加 (FR5)
.claude-plugin/marketplace.json                 # em-workflow の version 0.2.8 → 0.2.9 (FR8)
tests/                                          # 文書抽出テストを新規追加 (FR6)
```

FR6 の抽出対象（FR3 の refresh 箇所）: implement-phase.md、phase-state.md、skills/develop/SKILL.md、references/phases/create-spec-phase.md。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/implement-guard-compatible-git-ops/**`
- `test-docs/implement-guard-compatible-git-ops/**`

`feature-docs/implement-guard-compatible-git-ops/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/implement-guard-compatible-git-ops/**` covers `test-docs/implement-guard-compatible-git-ops/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/implement-guard-compatible-git-ops/` directory at all; the declared
`test-docs/implement-guard-compatible-git-ops/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: `git -C <integration wt> reset --hard em-workflow/some-feature/integration` - destructive-guard が allow。
- [ ] TS-2: `git -C <integration wt> reset --hard refs/heads/em-workflow/some-feature/integration` と、対象が `"$BRANCH"` の形 - deny（対照）。
- [ ] TS-3: `git -C <integration wt> branch -d em-workflow/some-feature/task0001` - allow。
- [ ] TS-4: `git worktree remove <root>/.claude/worktrees/em-workflow/some-feature/task0001`（--force なし）- allow。
- [ ] TS-5: 既存ケース `git reset --hard HEAD~1` - deny のまま。

### Integration Tests
- [ ] TS-6: 文書抽出テストで、implement-phase.md / phase-state.md / SKILL.md / create-spec-phase.md の refresh コマンドと I.2.b step 4 のコマンドを展開 - どれも deny/ask にならない。
- [ ] TS-7: 文書抽出テストで、範囲内の各箇所の抽出件数が 0 のとき - fail する。
- [ ] TS-8: 除外リストの各箇所 - 抽出対象から外れ、テストの失敗理由にならない。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] I.2.b step 4 の `branch -d` が失敗した場合: `-D` などの強制削除に切り替えず、ブランチを残し、wake phase の報告に対象のブランチ名を書く（FR2）。
- [ ] 範囲内のある箇所から抽出件数が 0 件の場合: 文書抽出テストが fail する（TS-7）。

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 該当なし
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし
- **Destructive-command guard:** destructive-guard の判定ロジックは変更せず（NFR1）、検知力を削らない。リテラル以外の対象が deny のままであることを対照ケースで示す（FR5、TS-2）。

## Error Handling

### Error Codes

該当なし

### Error Flow

```
I.2.b step 4 の git branch -d が失敗 → 強制削除に切り替えない → ブランチを残す → wake phase の報告に対象のブランチ名を書く
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC-1: implement-phase.md の I.2.b step 4 に `git branch -D` が無い。`git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` があり、それが `git worktree remove "$WT_ROOT/{T}"` より後に置かれている。
- [ ] AC-2: I.2.b step 4 に、-d が拒否されたときは強制削除せずにブランチを残して報告する、という規定がある。
- [ ] AC-3: 範囲内の全 refresh 箇所の文言が `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`（または同じ形の `"$WT_ROOT/integration"`）のまま残っている。Branch & Worktree Model に、対象をリテラルのブランチ名で書く規定がある。
- [ ] AC-4: Branch & Worktree Model の artifact 書き込みの項に、Write ツールで書くこと、`commit-docs.sh` と同じ Bash 呼び出しにヒアドキュメントを含めないこと、の規定がある。
- [ ] AC-5: `destructive-guard-cases.json` に FR5 の allow ケースと deny の対照ケースがあり、`python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する。
- [ ] AC-6: 新しい文書抽出テストが、範囲内の各箇所から 1 件以上のコマンドを抽出し、そのどれもが deny/ask にならないことを確かめる。延期した 2 箇所は明示的な除外リストに載っている。
- [ ] AC-7: `python3 -m unittest discover -s tests` が全件 pass する。
- [ ] AC-8: plugin.json と marketplace.json の em-workflow の version が、同じ新しい値になっている。
- [ ] AC-9: 延期した箇所（I.2.a の resume guard の clean re-attempt と I.2.c の route-back cleanup）が SPEC に範囲外の既知の未対応として記録されている。

## Assumptions

- **A-C1:** 方針はプロトコル側の修正（protocol_side）。I.2.b step 4 を integration worktree 内の `git branch -d` に書き換え、hook の検知力は削らない。
- **A-C2:** 未マージの片付け（I.2.a の resume guard と I.2.c の route-back の `worktree remove --force` / `branch -D`）は範囲外とし、後続タスクに回す。完了扱いにはしない。
- **A-C3:** refresh は `reset --hard em-workflow/{feature}/integration` のリテラル形を維持し、対象はリテラルのブランチ名で書くと明記する。
- **A-C4:** ヒアドキュメントの誤爆は hook を直さず、プロトコルの規定で避ける（Write ツールで書き、`commit-docs.sh` と同じ Bash 呼び出しにヒアドキュメントを混ぜない）。worker の推奨（fix_hook_repo）とは違う選択。
- **A-C5:** 再発の検出は、ケース表への追加と、範囲を限定した文書抽出テスト（除外リストつき）の両方で行う。
- **A-C6:** 変更はリポジトリ内に限る。`~/.claude/hooks/destructive-guard.py` には触れない。今回の方針では hook のロジックを変えないため、利用者側のコピーに要る手作業は無い。
- **A1:** `git worktree add -b` で作った task ブランチには upstream が無い。そのため integration worktree 内の `git branch -d` は、その worktree の HEAD（integration ブランチ。merge-task.sh が update-ref で進めた ref）に対してマージ済みかを判定し、index が古いままでも通る。
- **A2:** failed-run-cleanup-guard.py は、integration 形状でない対象（task ブランチ）への `git branch -d` を判定しない。hook 本体は入力に含まれていなかった。
- **A3:** PR #19 の run で refresh が拒否された原因は、入力からは特定できない。現在の両方の hook のコピーはプロトコルのリテラルを allow する。対象を別の書き方にしたか、当時の hook のコピーが古かった可能性がある。FR3 の明記と FR5/FR6 のテストで、前者の再発を防ぐ。
- **A4:** I.2.b step 4 で -d が拒否されたときも強制削除に切り替えない（FR2）。強制削除の拒否を維持するという A-C1 の方針に従う。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/implement-guard-compatible-git-ops/REQUIREMENTS.md`
- implement フェーズのプロトコル: `em-workflow/references/implement-phase.md`
- destructive-guard: `em-workflow/hooks/destructive-guard.py`
- hook のケース表: `em-workflow/hooks/tests/destructive-guard-cases.json`
- hook のケース実行: `em-workflow/hooks/tests/run-destructive-guard.py`
