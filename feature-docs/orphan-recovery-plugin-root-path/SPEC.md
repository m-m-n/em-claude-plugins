# Feature: orphan-recovery-plugin-root-path

## Overview

`em-workflow/references/implement-phase.md` の I.2.b で orchestrator がプラグイン同梱スクリプトを cwd 相対（`em-workflow/scripts/...`）で起動している 3 箇所を、`${CLAUDE_PLUGIN_ROOT}/scripts/...` を Step I.0 step 4 の解決規律で解決して起動する文に書き換える。あわせて recover-orphaned-task.py の起動時 cwd を `{project_root}` に固定し、解決失敗時の扱いを明記する。既存テストのピンを更新し、再発を検出するテストを追加する。

## Objectives

- マーケットプレイス経由でインストールした em-workflow（利用者の cwd に `em-workflow/` が無い構成）でも、I.2.b の孤児 launched 復旧が実際に発火する
- orchestrator が cwd 相対でプラグイン同梱スクリプトを起動している箇所を無くし、Step I.0 step 4 の解決規律に統一する
- recover-orphaned-task.py の D1 既定導出（default_transcripts_dir の os.getcwd()）を、起動時の cwd を固定することで決定的にする

## Acceptance Criteria

- [ ] **AC-1:** implement-phase.md I.2.b の orphan-recovery 起動文が `${CLAUDE_PLUGIN_ROOT}/scripts/recover-orphaned-task.py`（RECOVER_SCRIPT）を使い、Step I.0 step 4 を cite し、cwd が `{project_root}` であることを同じ文で述べる（covers: FR1, FR5, NFR1）
- [ ] **AC-2:** Same-session extension の再起動文が同じ RECOVER_SCRIPT と同じ cwd を使う（covers: FR2, FR5）
- [ ] **AC-3:** ancestor-check bullet の merge-unverified 起動文が `${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py` を使い、Step I.0 step 4 を cite する。`exactly once, with the task id and `--reason merge-unverified`, supplying no launch identity` の意味は保たれる（covers: FR3, NFR1）
- [ ] **AC-4:** 解決失敗時に recovery 2 箇所は Residual（journal 不変）、merge-unverified は Helper-failure residue になることが明記されている（covers: FR4）
- [ ] **AC-5:** implement-phase.md の orchestrator 起動位置に cwd 相対の `em-workflow/scripts/` 起動文が残っておらず、それを検出するテストがあり、更新した 2 つのピンを含め `python3 -m unittest discover -s tests` が通る（covers: FR6, NFR2, NFR3）
- [ ] **AC-6:** FR7 の対象外箇所と recover-orphaned-task.py が変更されていない（covers: FR7）

## Technical Requirements

### Functional Requirements

- **FR1: orphan-recovery の起動を ${CLAUDE_PLUGIN_ROOT} 経由にする** — em-workflow/references/implement-phase.md I.2.b step 1 の Orphan recovery 段落（現行 :605-606 「then invokes `em-workflow/scripts/recover-orphaned-task.py` for the candidate task」）を、`RECOVER_SCRIPT=${CLAUDE_PLUGIN_ROOT}/scripts/recover-orphaned-task.py` を解決して起動する文に書き換える。解決とフォールバック（信頼できるルート配下の探索、cwd は見ない、fail-closed）は Step I.0 step 4 を owning section として cite し、探索パスは再記述しない
- **FR2: Same-session extension の再起動も同じ解決経路にする** — 同じ段落の Same-session extension の Invocation contract（現行 :675-676 「the orchestrator re-invokes `em-workflow/scripts/recover-orphaned-task.py` for the same candidate task」）を、FR1 で解決した RECOVER_SCRIPT を使う文に書き換える
- **FR3: merge-unverified の journal-append-failed.py 起動を ${CLAUDE_PLUGIN_ROOT} 経由にする** — I.2.b step 1 の ancestor-check bullet（現行 :720-723 「the orchestrator invokes `em-workflow/scripts/journal-append-failed.py` exactly once, with the task id and `--reason merge-unverified`, supplying no launch identity」）を、`${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py` を Step I.0 step 4 の規律（cite のみ）で解決して起動する文に書き換える
- **FR4: 解決失敗時の扱いを明記する** — RECOVER_SCRIPT の解決に失敗した場合（FR1 / FR2）は、その候補を Residual（journal 不変）として扱うと明記する。FR3 の journal-append-failed.py の解決に失敗した場合は、既存の Helper-failure residue（journal 不変）として扱うと明記する
- **FR5: recover-orphaned-task.py の起動時 cwd を固定する** — FR1 / FR2 の起動文と同じ文で、recover-orphaned-task.py を `{project_root}`（main working tree）を cwd として起動すると明記する
- **FR6: 既存テストのピン更新と再発検出テスト** — tests/test_implement_routeback_gate.py の ORPHAN_RECOVER_SCRIPT_INVOCATION_PHRASE（:714-717）と tests/test_merge_unverified_exit_doc_contract.py の R2_HELPER_INVOCATION_PHRASE（:155-159）を新しい文言に更新する。あわせて、implement-phase.md の orchestrator 起動 3 箇所が `${CLAUDE_PLUGIN_ROOT}/scripts/...` で起動し、Step I.0 step 4 を cite し、FR5 の cwd を明記していること、および cwd 相対の起動文（`invokes `em-workflow/scripts/recover-orphaned-task.py``、`re-invokes `em-workflow/scripts/recover-orphaned-task.py``、`the orchestrator invokes `em-workflow/scripts/journal-append-failed.py``）が残っていないことを検出するテストを追加する
- **FR7: 対象外箇所を変更しない** — スクリプト内部からの呼び出しや書き手の同定である箇所は変更しない: implement-phase.md :629（recover-orphaned-task.py 内部からの journal-append-failed.py 呼び出し）、:694（同 extended chain の内部呼び出し）、:1115（Supporting cast Journal bullet）、:1262（Stale-`launched` caveat）、workflow-schema.md :407 / :443。em-workflow/scripts/recover-orphaned-task.py（_SCRIPT_DIR で兄弟ヘルパーを自力解決）も変更しない

### Non-Functional Requirements

- **NFR1 - SSOT 重複禁止（NFR7）:** フォールバック探索パス（`$HOME/.claude/plugins` / `$HOME/.claude/skills`、`*/em-workflow/*/scripts/*`）は implement-phase.md 内で Step I.0 step 4 にだけ書かれ、FR1-FR3 の起動文は Step I.0 step 4 を cite する
- **NFR2 - テストの慣習:** 追加・更新するテストは標準ライブラリのみを使い、モジュール自身の位置から求めたリポジトリルートから文書を読み、空白正規化したうえで照合する。新しい文言には forged sanity（フレーズを除去すると検出されることの確認）、置き換える文言には変更前サンプルに対する negative proof を付ける既存の書き方に従う
- **NFR3 - 既存の byte-identity ガードを保つ:** em-workflow/scripts/merge-task.sh と em-workflow/hooks/queue_launch_guard.py は変更しない（tests/test_merge_unverified_exit_doc_contract.py の sha256 ガードが通り続ける）
- **NFR4 - version を触らない:** em-workflow の plugin.json / marketplace.json の version は変更しない

## Implementation Approach

### 変更する箇所

| 対象 | 変更内容 | 要件 |
|---|---|---|
| `em-workflow/references/implement-phase.md` I.2.b Orphan recovery 段落（現行 :605-606） | RECOVER_SCRIPT の解決と起動、Step I.0 step 4 の cite、cwd `{project_root}`、解決失敗時は Residual | FR1, FR4, FR5 |
| `em-workflow/references/implement-phase.md` Same-session extension の Invocation contract（現行 :675-676） | FR1 で解決した RECOVER_SCRIPT で再起動、cwd `{project_root}`、解決失敗時は Residual | FR2, FR4, FR5 |
| `em-workflow/references/implement-phase.md` ancestor-check bullet（現行 :720-723） | `${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py` を Step I.0 step 4 の規律で解決して起動、解決失敗時は Helper-failure residue | FR3, FR4 |
| `tests/test_implement_routeback_gate.py` ORPHAN_RECOVER_SCRIPT_INVOCATION_PHRASE（:714-717） | 新しい文言に更新 | FR6 |
| `tests/test_merge_unverified_exit_doc_contract.py` R2_HELPER_INVOCATION_PHRASE（:155-159） | 新しい文言に更新 | FR6 |
| 再発検出テスト | 3 箇所の新しい起動文の存在と、cwd 相対の起動文の不在を検出 | FR6 |

### 変更しない箇所

- `em-workflow/references/implement-phase.md` :629 / :694 / :1115 / :1262（FR7）
- `em-workflow/references/workflow-schema.md` :407 / :443（FR7）
- `em-workflow/scripts/recover-orphaned-task.py`（FR7）
- `em-workflow/scripts/merge-task.sh`、`em-workflow/hooks/queue_launch_guard.py`（NFR3）
- tests/test_implement_routeback_gate.py の ORPHAN_JOURNAL_HELPER_INVOCATION_PHRASE（:718-721）、tests/test_merge_unverified_exit_doc_contract.py の R5_HELPER_NAMED_AS_EXCEPTION_PHRASE（:681-684）（A5）
- em-workflow の plugin.json / marketplace.json の version（NFR4）

### Design Step

設計ステップは skip する: 参照ドキュメントの起動文とテストの更新のみで、設計ステップの対象がない。

## Declared Change Set

この節は手書きの一覧ではなく create-plan での導出を述べる。上記の feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出される（`references/phases/create-plan-phase.md`）。

feature 固有のパスに加え、すべての SPEC は既定で次の 2 つのワークフロー生成エントリを宣言する。

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および設計ステップが生成する設計成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを cite するだけで、規則を再記述しない。

`test-docs/{feature}/**` はタスクごとのテスト記録 `test-docs/{feature}/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを cite するだけで、規則を再記述しない。

この 2 つの既定エントリは、SPEC 作成者が明示的に除かない限り宣言に含まれる。記載が無いことをもって不在とは見なさず、除外は意図的・明示的な絞り込みとして行う。

この宣言は SUPERSET の主張である。検証時に観測される実際の変更集合は、宣言集合と等しい必要はなく、宣言集合に含まれていればよい。implement タスクを生まない feature は `test-docs/{feature}/` ディレクトリを生成しないが、その場合も宣言した `test-docs/{feature}/**` は正しい。宣言したパスが実体化しないことは違反ではない。

## Test Scenarios

### Unit Tests

- [ ] **TS-1:** I.2.b 節を空白正規化して、3 つの起動文に `${CLAUDE_PLUGIN_ROOT}/scripts/recover-orphaned-task.py` / `${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py`、Step I.0 step 4 への cite、`{project_root}` の cwd 指定が含まれることを確認する（forged sanity 付き）（covers: AC-1, AC-2, AC-3）
- [ ] **TS-2:** 変更前の 3 つの起動文（`invokes `em-workflow/scripts/recover-orphaned-task.py` for the candidate task`、`re-invokes `em-workflow/scripts/recover-orphaned-task.py` for the same candidate task`、`the orchestrator invokes `em-workflow/scripts/journal-append-failed.py``）が現行文書に無いことを確認し、変更前サンプルには含まれることを negative proof として確認する（covers: AC-5）
- [ ] **TS-3:** `$HOME/.claude/plugins` が implement-phase.md 内で Step I.0 節にだけ現れることを確認する（covers: AC-1, NFR1）
- [ ] **TS-4:** 解決失敗時に Residual / Helper-failure residue となる旨の文言を確認する（covers: AC-4）
- [ ] **TS-5:** 既存の ORPHAN_JOURNAL_HELPER_INVOCATION_PHRASE（:629 の内部呼び出し）と R5_HELPER_NAMED_AS_EXCEPTION_PHRASE（:1115）が変更なしで通り、merge-task.sh / queue_launch_guard.py の sha256 ガードが通ることを確認する（covers: AC-5, AC-6）

実行コマンド: `python3 -m unittest discover -s tests`

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] RECOVER_SCRIPT の解決に失敗した場合（FR1 / FR2）: その候補を Residual（journal 不変）として扱う（FR4）
- [ ] journal-append-failed.py の解決に失敗した場合（FR3）: 既存の Helper-failure residue（journal 不変）として扱う（FR4, A3）

## Assumptions

- **A1:** recover-orphaned-task.py は `{project_root}`（main working tree）を cwd として起動する。integration worktree は選ばない。これと別の cwd で開始したセッションの transcript が見つかることは保証しない
- **A2:** 修正範囲は orchestrator が cwd 相対で直接起動している 3 箇所（:606 recover 起動、:676 same-session 再起動、:721 merge-unverified の journal-append-failed.py 起動）すべて。:629 / :670 / :694 はスクリプト内部からの呼び出しの記述なので対象外
- **A3:** merge-unverified 側で journal-append-failed.py の解決に失敗した場合は、既存の Helper-failure residue（invocation が非ゼロ終了または `appended` 以外を報告した場合と同じ扱い、journal 不変）に含める
- **A4:** 起動時 cwd の明記は recover-orphaned-task.py の起動（FR1 / FR2）に対して行う。journal-append-failed.py の起動（FR3）には cwd の明記を要求しない
- **A5:** tests/test_implement_routeback_gate.py :718-721 の ORPHAN_JOURNAL_HELPER_INVOCATION_PHRASE（:629 の内部呼び出しを固定）と tests/test_merge_unverified_exit_doc_contract.py :681-684 の R5_HELPER_NAMED_AS_EXCEPTION_PHRASE（:1115 の同定を固定）は変更しない

## Success Criteria

- [ ] AC-1 から AC-6 がすべて満たされている
- [ ] `python3 -m unittest discover -s tests` が通る

## Open Questions

なし

## References

- `em-workflow/references/implement-phase.md` Step I.0 step 4（プラグイン同梱スクリプトの解決規律。owning section）
