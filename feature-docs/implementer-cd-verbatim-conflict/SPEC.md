# Feature: implementer-cd-verbatim-conflict

## Overview

implementer（サブエージェント）が、承認済みの workflow.yaml コマンドを、文字列を変えずに担当 worktree で、`cd "{worktree_path}" && <承認文字列>` の 1 回の Bash 呼び出しで実行できるようにする。bash_guard.py にこの形の許可を足し、implementer・スキル・参照文書の指示を合わせる。要件は `feature-docs/implementer-cd-verbatim-conflict/REQUIREMENTS.md` を参照する。

## Objectives

- implementer（サブエージェント）が、承認済みの workflow.yaml コマンドを、文字列を変えずに自分の担当 worktree で、1 回の Bash 呼び出しで実行できるようにする。
- 「承認文字列を一字一句そのまま実行する」規則と、「サブエージェントでは単独 `cd` が次の呼び出しに残らない」事実の食い違いをなくす。

## User Stories

### US1: 担当 worktree で承認済みコマンドを実行する
implementer として、承認済みの workflow.yaml コマンドを、文字列を変えずに担当 worktree で 1 回の Bash 呼び出しで実行したい。

**Acceptance Criteria:**
- [ ] AC-1: X が承認済みで、P がメイン作業ツリーの `.claude/worktrees/em-workflow/` より深いところにある既存ディレクトリのとき、`cd "P" && X` は allow になる。
- [ ] AC-2: 承認文字列が `CARGO_TARGET_DIR=src-tauri/target cargo test --manifest-path src-tauri/Cargo.toml --lib` のとき、`cd "<worktree>" && ` にこの文字列を続けたものは allow になる。
- [ ] AC-3: 承認文字列に `&&` を含むもの（例: `a && b`）について、`cd "<worktree>" && a && b` は allow になる。
- [ ] AC-4: hook の cwd が integration worktree やタスク worktree の中にあっても、AC-1 の判定は同じになる。

### US2: 許可範囲を FR1 の形に限る
hook の利用者として、FR1 の形以外の判定が変わらないことを確かめたい。

**Acceptance Criteria:**
- [ ] AC-5: 次の形は allow にならず、変更前と同じ判定になる。worktree の外への `cd`、別リポジトリの worktrees 配下への `cd`、`..` やシンボリックリンクで外へ出る `cd`、worktrees ディレクトリそのものへの `cd`、`cd` が 2 つ、`cd` と `&&` の間に `;` や `|` がある形、引用なしや一重引用のパス、パスに `$` やバッククォートを含む形、残りが承認文字列と一致しない形。
- [ ] AC-6: 残りが禁止パターンを含むなら、承認済みでも deny になる。
- [ ] AC-7: `cd` を前置しないコマンドの判定は、どれも変更前と同じ（承認済み → allow、宣言済みで未承認 → deny、それ以外 → 判定なし）。

### US3: 指示と文書を新しい規則に合わせる
implementer とオーケストレーターとして、役割ごとの実行方法が文書と deny 時の案内に書いてあってほしい。

**Acceptance Criteria:**
- [ ] AC-8: implementer.md と worktree-task-workflow/SKILL.md は、テスト・ビルド・フォーマット・merge_script を `cd "{worktree_path}" && <コマンド>` の 1 呼び出しで実行するよう指示し、「cwd は呼び出し間で残らない」と書いている。単独の `cd` 呼び出しを求める文と、`&&` で繋ぐことを禁じる文は残っていない。環境変数の前置禁止は残っている。
- [ ] AC-9: command-execution-protocol.md の Verbatim execution rule と判定表に implementer の例外がある。オーケストレーターの「単独 `cd` で移動し、実行後に単独 `cd` でルートへ戻る」規則も残っている。
- [ ] AC-10: bash_guard の deny 時 additionalContext は、オーケストレーター向けの単独 `cd` の案内と、implementer 向けの `cd "{worktree_path}" &&` の案内を分けて書いている。再試行せず notes で報告する指示も残っている。
- [ ] AC-11: README.md と workflow-schema.md の hook の説明に、cd 前置の例外が書いてある。
- [ ] AC-12: `python3 -m unittest discover -s tests` が通る。queue_launch_guard.py と merge-task.sh の hash 固定テスト、hook の分類テスト、hooks.json の登録テストもそのまま通る。

## Technical Requirements

### Functional Requirements
- **FR1:** bash_guard: worktree への cd 前置形の許可。`em-workflow/hooks/bash_guard.py` の hook は、次をすべて満たすコマンドに allow を返す。
    - (a) コマンドが `cd "<P>" && <残り>` の形になっている。
    - (b) `<P>` は二重引用符で囲んだ絶対パス 1 つで、中に `"`、`$`、バッククォート、バックスラッシュ、改行を含まない。
    - (c) `cd` は先頭の 1 つだけで、`cd` にオプション（`-P`、`--` など）は付かない。
    - (d) 閉じ引用符と最初の `&&` の間には空白しか無い。
    - (e) `realpath(<P>)` が存在するディレクトリで、メイン作業ツリー直下の `.claude/worktrees/em-workflow/` を realpath で解決した場所より深いところにある。その場所そのものは含めない。メイン作業ツリーは、hook の cwd から求めた git common dir の親とする。
    - (f) `<残り>` をトリムした文字列が、project_key(cwd) の承認済み文字列のどれかと完全一致する。
    - 分割には `cd` のパス引数の直後にある最初の `&&` を使い、その後ろ全体を `<残り>` とする。
- **FR2:** 禁止パターンの判定が先。FR1 の判定より先に、コマンド全体に禁止パターンの判定を当てる。一致したら、承認の有無に関係なく deny する。
- **FR3:** 条件を満たさない形は今の判定のまま。FR1 の条件を 1 つでも満たさないコマンドは、文字列全体に今の判定表を当てる。承認済みと完全一致なら allow、workflow.yaml にあって未承認なら deny、それ以外は判定なし。新しく deny を返す条件は足さない。`cd` を前置しないコマンドの判定は変えない。
- **FR4:** implementer.md の指示を連結形に戻す。`em-workflow/agents/implementer.md` の Step 3 と Step 6 で、テスト・ビルド・フォーマット・merge_script を `cd "{worktree_path}" && <コマンド>` の 1 回の Bash 呼び出しで実行するよう指示する。「cwd は Bash の呼び出し間で残らない」と書く。単独の `cd` 呼び出しと、`&&` で繋がない指示は削る。git の操作は今のまま `git -C "{worktree_path}"` を使う。
- **FR5:** worktree-task-workflow/SKILL.md の指示を連結形に戻す。`em-workflow/skills/worktree-task-workflow/SKILL.md` の merge-task.sh contract 節と Command execution gate 節を、FR4 と同じ形（`cd "{worktree_path}" && <コマンド>` の 1 呼び出し、cwd は呼び出し間で残らない）にする。環境変数の前置禁止と、コマンド文字列そのものを変えない規則は残す。gate 節で固定されている文「Never prefix `cd …` or environment assignments」は新しい規則に合わせて書き換え、`tests/test_worktree_skill_instruction_source.py` の期待文字列も同じ変更で合わせる。
- **FR6:** command-execution-protocol.md に例外を書き足す。`em-workflow/references/command-execution-protocol.md` の Verbatim execution rule と hook の判定表（Runtime enforcement）に、FR1 の形を implementer 用の例外として書き足す。オーケストレーターの規則（単独 `cd` で移動し、実行後に単独 `cd` でルートへ戻る）は変えない。
- **FR7:** bash_guard の deny 時 additionalContext を書き分ける。bash_guard.py が未承認コマンドを deny するときの additionalContext を書き分ける。オーケストレーターには、単独の `cd` で移動してから承認文字列をそのまま実行するよう案内する。implementer には、`cd "{worktree_path}" && <承認文字列>` の形を案内する。AskUserQuestion を持たないサブエージェントが、deny された後に再試行せず notes で報告する指示は残す。
- **FR8:** README.md と workflow-schema.md の説明。`em-workflow/README.md` の 118 行と `em-workflow/references/workflow-schema.md` の 305-306 行にある hook の説明（承認済み文字列と完全一致 → allow）に、FR1 の cd 前置の例外を書き足す。
- **FR9:** bash_guard のテストケース。bash_guard の hook テストに、許可ケース（FR1 の形）と、許可しないケースを足す。許可しないケースは、worktree の外への `cd`、`cd` が複数、`;` や `|` の混在、残りの不一致、引用なしや一重引用のパス、`..` やシンボリックリンクによる外への移動、worktrees ディレクトリそのものへの `cd`、禁止パターンを含む残り。テストは hook を subprocess で起動して JSON を渡し、`EM_WORKFLOW_APPROVALS` で承認ストアを分け、一時的な git リポジトリを使う。

### Non-Functional Requirements
- **NFR1 - 決定的な判定:** 判定は LLM を使わず、コードで決定的に行う。bash_guard.py は Python 標準ライブラリだけを使う。
- **NFR2 - 許可範囲を広げすぎない:** 新しく allow するのは FR1 の形だけ。workflow に無関係な Bash コマンドには、今までどおり判定を出さない。
- **NFR3 - hook 分類テストの前提を守る:** bash_guard.py のコメントと docstring を除く実行コードに、部分文字列 `"status"` を足さない（`tests/test_hook_classification_pin.py`）。
- **NFR4 - hash 固定ファイルを変えない:** `em-workflow/hooks/queue_launch_guard.py` と `em-workflow/scripts/merge-task.sh` はバイト単位で変えない。
- **NFR5 - hook の登録と順序を変えない:** `em-workflow/hooks/hooks.json` の登録内容と順序は変えない。
- **NFR6 - SKILL の gate 節の文言の制約:** worktree-task-workflow/SKILL.md の Command execution gate 節では、`(byte-for-byte)` をちょうど 1 回だけにし、ほかに `byte`、`identical to`、`equal to the line` を書かない。`tests/test_worktree_skill_instruction_source.py` の、承認規則とデコード値についての既存の固定は残す。
- **NFR7 - version を変えない:** プラグインの version は変えない。
- **NFR8 - テストの実行方法:** テストは標準ライブラリの unittest だけを使い、`python3 -m unittest discover -s tests` がすべて通る。

## Implementation Approach

### Architecture

bash_guard.py（PreToolUse(Bash) hook）の判定順:

```
コマンド全体
  → 禁止パターンの判定（FR2）: 一致 → deny
  → FR1 の条件 (a)〜(f) をすべて満たす → allow
  → それ以外は文字列全体に今の判定表（FR3）
       承認済みと完全一致 → allow
       workflow.yaml にあって未承認 → deny（additionalContext は FR7）
       それ以外 → 判定なし
```

### Data Flow

```
hook 入力 JSON（command, cwd）
  → cwd から git common dir を求め、その親をメイン作業ツリーとする
  → cd "<P>" と <残り> に分割（cd のパス引数の直後にある最初の &&）
  → realpath(<P>) が <メイン作業ツリー>/.claude/worktrees/em-workflow/ の realpath より深いか判定
  → <残り> をトリムして project_key(cwd) の承認済み文字列と完全一致を判定
  → permissionDecision を出力
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- project_key(cwd) の承認ストア: FR1 (f) と FR3 の完全一致判定に使う。
- 禁止パターンの判定: FR2 で FR1 より先に当てる。

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）。

### File Structure

```
em-workflow/
├── hooks/
│   └── bash_guard.py                      # FR1, FR2, FR3, FR7
├── agents/
│   └── implementer.md                     # FR4
├── skills/
│   └── worktree-task-workflow/
│       └── SKILL.md                       # FR5
├── references/
│   ├── command-execution-protocol.md      # FR6
│   └── workflow-schema.md                 # FR8
└── README.md                              # FR8
tests/
└── test_worktree_skill_instruction_source.py  # FR5
```

FR9 の bash_guard の hook テストも追加する。

変更しないファイル: `em-workflow/hooks/queue_launch_guard.py`、`em-workflow/scripts/merge-task.sh`（NFR4）、`em-workflow/hooks/hooks.json`（NFR5）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/implementer-cd-verbatim-conflict/**`
- `test-docs/implementer-cd-verbatim-conflict/**`

`feature-docs/implementer-cd-verbatim-conflict/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/implementer-cd-verbatim-conflict/**` covers `test-docs/implementer-cd-verbatim-conflict/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/implementer-cd-verbatim-conflict/` directory at all; the declared
`test-docs/implementer-cd-verbatim-conflict/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1（AC-1、AC-2、AC-3）: 一時 git リポジトリに `.claude/worktrees/em-workflow/f/t` を作り、承認ストアに X を記録する。`cd "<絶対パス>" && X` を hook に渡す。 - permissionDecision が allow
- [ ] TS-2（AC-4）: TS-1 と同じ内容で、hook 入力の cwd を worktree（`git worktree add` で作ったもの）にする。 - allow
- [ ] TS-3（AC-5）: AC-5 に挙げた形を 1 ケースずつ hook に渡す。 - allow にならない。判定は変更前の判定表と同じ（多くは出力なし）。
- [ ] TS-4（AC-6）: 禁止パターンを含む文字列を承認ストアに直接書いた状態で、`cd "<worktree>" && <その文字列>` を渡す。 - deny
- [ ] TS-5（AC-7）: `cd` を前置しない承認済みコマンド、宣言済みで未承認のコマンド、無関係なコマンドを渡す。 - それぞれ allow / deny / 出力なし
- [ ] TS-6（AC-8、AC-9、AC-10、AC-11）: 対象の文書と bash_guard.py の文言を読み、必要な文があり、消すべき文が無いことを確かめる文書契約テスト。 - すべて合格

### Integration Tests
- [ ] TS-7（AC-12）: `python3 -m unittest discover -s tests` を実行する。 - 失敗 0

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 承認文字列に `&&` を含む: `cd` のパス引数の直後にある最初の `&&` で分割し、後ろ全体を `<残り>` として完全一致させる（AC-3）。
- [ ] 承認文字列が環境変数の代入から始まる: `<残り>` としてそのまま一致する（AC-2）。
- [ ] worktrees ディレクトリそのものへの `cd`: allow にしない（AC-5）。
- [ ] `..` やシンボリックリンクで外へ出る `cd`: realpath で判定し、allow にしない（AC-5）。
- [ ] hook の cwd が worktree の中: メイン作業ツリーは git common dir の親から求め、判定は同じ（AC-4）。

### Performance Tests

該当なし。

## Security Considerations

- **Authentication:** 該当なし。
- **Authorization:** 新しく allow するのは FR1 の形だけ（NFR2）。禁止パターンは FR1 より先に判定し、承認の有無に関係なく deny する（FR2）。
- **Input Validation:** `<P>` は二重引用符で囲んだ絶対パス 1 つで、`"`、`$`、バッククォート、バックスラッシュ、改行を含まない。`cd` は先頭の 1 つだけでオプションなし。閉じ引用符と最初の `&&` の間は空白のみ（FR1 (b)〜(d)）。
- **Data Protection:** 該当なし。
- **XSS Prevention:** 該当なし。
- **SQL Injection Prevention:** 該当なし。
- **CSRF Protection:** 該当なし。

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| deny（禁止パターン） | コマンド全体が禁止パターンに一致（FR2） | - | - |
| deny（未承認） | workflow.yaml にあって未承認（FR3） | - | オーケストレーター向けと implementer 向けに書き分けた additionalContext（FR7） |

### Error Flow

```
未承認で deny → additionalContext
  オーケストレーター: 単独の cd で移動してから承認文字列をそのまま実行する
  implementer: cd "{worktree_path}" && <承認文字列> の形で実行する
  AskUserQuestion を持たないサブエージェント: 再試行せず notes で報告する
```

## Performance Optimization

該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし。

## References

- 要件定義書: `feature-docs/implementer-cd-verbatim-conflict/REQUIREMENTS.md`
- コマンド実行プロトコル: `em-workflow/references/command-execution-protocol.md`
