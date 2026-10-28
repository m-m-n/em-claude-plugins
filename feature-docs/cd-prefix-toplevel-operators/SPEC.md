# Feature: cd-prefix-toplevel-operators

## Overview

`em-workflow/hooks/bash_guard.py` が allow する cd 前置形 `cd "{worktree_path}" && <承認文字列>` の条件に、`<残り>` のトップレベルに単独の `&`、`;`、`||`、改行が無いことと、安全側の追加除外条件に当たらないことを加える。対象外になった形は今の判定表で判定し、新しい deny は足さない。文書と試験を同じ変更で揃える。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- bash_guard.py が allow する cd 前置形では、承認文字列の全部が cd 先の worktree で動く。元の cwd（メイン作業ツリー）で動く部分を残さない。
- hook・文書・試験を同じ変更で揃え、再発を試験で検出する。

## User Stories

### US1: cd 前置形で allow される承認文字列を、全部 cd 先で動くものに限る

implementer として、cd 前置形で allow された承認文字列が全部 cd 先の worktree で動くようにしたい。

**Acceptance Criteria:**
- [ ] AC1: `A & B` を承認済みにしたとき、`cd "<worktree 領域の下>" && A & B` に hook は allow を返さず、判定なしになる。
- [ ] AC2: `A ; B`、`A || B`、および内部に改行を含む承認文字列でも、cd 前置形は判定なしになる。
- [ ] AC3: 既存の allow ケース（`make test`、環境変数の代入で始まる文字列、`a && b`、パス条件の各 allow ケース）と、`make test 2>&1`、`a |& b`、`a | b`、`a &> log`、`a &>> log`、`a <&0`、引用の中の `;` や `&`（例: `echo "a;b"`、`echo 'a&b'`）、エスケープした `\;` を承認したときの cd 前置形は allow のまま。
- [ ] AC4: FR3 の各条件に当たる承認文字列の cd 前置形は判定なしになる。対象は、閉じていない引用、末尾のバックスラッシュ、`$'…'`、`$"…"`、`#`、引用の外の `(` `)` `{` `}`、`$(...)`、`${...}`、バッククォート、二重引用の中の `$(` / `${` / バッククォート。
- [ ] AC5: cd を前置しない `A & B` の完全一致は allow のまま。workflow.yaml にあって未承認の文字列は deny のまま。
- [ ] AC6: 禁止パターンを含む承認文字列の cd 前置形は、トップレベル演算子の有無に関係なく deny され、理由に禁止パターンが示される。

### US2: 文書と試験を hook に揃える

implementer として、対象外になる承認文字列の扱いを手順書から読み取りたい。

**Acceptance Criteria:**
- [ ] AC7: command-execution-protocol.md の Verbatim execution rule、implementer.md の Step 3、worktree-task-workflow SKILL.md の Command execution gate 節、README.md の実行時強制の項、workflow-schema.md の Command approval store 節、bash_guard.py の docstring が、対象外の条件と implementer の扱いを、それぞれ FR6〜FR9 の範囲で書いている。文書試験がそれを確かめる。
- [ ] AC8: `python3 -m unittest discover -s tests` がすべて通る。NFR2〜NFR6 の制約を満たす。

## Technical Requirements

### Functional Requirements

- **FR1:** トップレベル演算子を含む承認文字列を cd 前置形の対象外にする。`em-workflow/hooks/bash_guard.py` の cd 前置形の allow 条件に、次の条件を加える。`<残り>`（最初の `&&` より後ろをトリムした文字列）に、FR2 の規則で数えた単独の `&`、`;`、`||`、改行が無い。さらに FR3 の除外条件にも当たらない。`cd "{worktree_path}" && <承認文字列>` という実行形は変えない。
- **FR2:** 演算子の検出規則（引用と転送を区別する）。`<残り>` を左から走査する。単一引用・二重引用・バックスラッシュエスケープの中の文字は数えない。単一引用の中のバックスラッシュは通常の文字として扱い、二重引用の中のエスケープは Bash の規則に従う。引用の外では、`&&`、`|&`、`>&`、`<&`、`&>`、`&>>`、`||` を最長一致で 1 つのまとまりとして認識する。`&&`、`|&`、`>&`、`<&`、`&>`、`&>>` に含まれる `&` は数えない。それ以外の単独の `&`、`;`、`||`、改行があれば対象外にする。
- **FR3:** 安全側の追加除外条件。`<残り>` が次のどれかに当たる場合も対象外にする。入れ子は解析しない。閉じていない引用、末尾のバックスラッシュ、文字列の内部の改行。`$'` または `$"`。`#`（位置を問わない。引用の中も含む）。引用の外にある `(` `)` `{` `}`。`$(...)`、`${...}`、バッククォート。二重引用の中の置換構文（`$(`、`${`、バッククォート）。
- **FR4:** 対象外にした形は今の判定表で判定する。FR1〜FR3 で対象外になった cd 前置形は、文字列全体を今の判定表で判定する。承認済みと完全一致なら allow、workflow.yaml にあって未承認なら deny、それ以外は判定なし。新しい deny は足さない。cd を前置しないコマンド（承認済みの `A & B` との完全一致を含む）の判定も変えない。
- **FR5:** 禁止パターンの判定を先に当てる順序を保つ。禁止パターンは今までどおり、cd 前置部分を含むコマンド全体に FR1 より先に当てる。一致したら、承認の有無に関係なく deny する。
- **FR6:** command-execution-protocol.md に対象外の条件を書く。`em-workflow/references/command-execution-protocol.md` の Verbatim execution rule にある、hook が cd 前置形を allow する条件の箇条書きに、FR1〜FR3 の条件を書き足す。トップレベルに単独の `&`、`;`、`||`、改行を含む承認文字列などは対象外になる。あわせて、該当する承認文字列は implementer が実行せず notes で報告することを書く。
- **FR7:** implementer の手順書に、該当する承認文字列の扱いを書く。`em-workflow/agents/implementer.md` の Step 3 と、`em-workflow/skills/worktree-task-workflow/SKILL.md` の Command execution gate 節に、cd 前置形の対象外になる承認文字列は実行せず notes で報告することを書く。
- **FR8:** README.md と workflow-schema.md の説明に対象外の条件を書き足す。`em-workflow/README.md` の実行時強制の項と、`em-workflow/references/workflow-schema.md` の Command approval store 節にある cd 前置形の allow 条件の説明に、トップレベルに `&` / `;` / `||` を含む承認文字列は対象外になることを書き足す。詳細は `references/command-execution-protocol.md` に任せる。
- **FR9:** bash_guard.py の docstring を合わせる。bash_guard.py の module docstring にある cd prefix の条件の箇条書きに、FR1〜FR3 の条件を書き足す。
- **FR10:** 再発を検出する試験。`tests/` の hook 試験に、FR1〜FR4 を確かめるケースを足す。方式は `tests/test_bash_guard_cd_prefix.py` と同じ（hook を subprocess で起動して JSON を渡す、`EM_WORKFLOW_APPROVALS` で承認ストアを分ける、一時的な git リポジトリを使う）。FR6〜FR8 の文書の記述を確かめる文書試験も足す。

### Non-Functional Requirements

- **NFR1 - 決定的な判定:** 判定は LLM を使わず、コードで決定的に行う。bash_guard.py は Python 標準ライブラリだけを使う。
- **NFR2 - hook 分類試験の前提を守る:** bash_guard.py の実行コード（コメントと docstring を除く）に部分文字列 `"status"` を足さない（`tests/test_hook_classification_pin.py`、`tests/test_bash_guard_cd_prefix.py` の AC-7）。
- **NFR3 - hash 固定ファイルと hook 登録を変えない:** `em-workflow/hooks/queue_launch_guard.py` と `em-workflow/scripts/merge-task.sh` はバイト単位で変えない。`em-workflow/hooks/hooks.json` の登録内容と順序は変えない。
- **NFR4 - version を変えない:** プラグインの version は変えない。
- **NFR5 - SKILL の gate 節の文言の制約:** `worktree-task-workflow/SKILL.md` の Command execution gate 節では、`(byte-for-byte)` をちょうど 1 回だけにし、ほかに `byte`、`identical to`、`equal to the line` を書かない。implementer.md と SKILL.md には、`separate` と `cd` を同じ文に含む文、`chain` と `&&` と禁止語を同じ文に含む文、`may reset` / `may have reset` を含む文を書かない（`tests/test_implementer_cd_chain_docs.py` の AC-3、AC-5）。
- **NFR6 - 既存の文書試験の固定を保つ:** `tests/test_cd_prefix_exception_docs.py` と `tests/test_implementer_cd_chain_docs.py` が固定している文言（`cd "{worktree_path}" &&`、everything after the first `&&` … approved string、判定表の行の順序、only one `cd` と主張しないこと など）を保つ。
- **NFR7 - 試験の実行方法:** 試験は標準ライブラリの unittest だけを使い、`python3 -m unittest discover -s tests` がすべて通る。

## Implementation Approach

### Architecture

**判定の順序（bash_guard.py）:**
```
コマンド全体（strip 済み）
  │
  ├─ 禁止パターンに一致 ─────────────→ deny（FR5）
  │
  ├─ cd 前置形で、<残り> が FR1〜FR3 の対象外の条件に当たらず、承認済み
  │                         ─────────→ allow（cd 前置形）
  │
  └─ それ以外（FR1〜FR3 で対象外になった cd 前置形を含む）
        文字列全体を今の判定表で判定（FR4）
          ├─ 承認済みと完全一致 ──────→ allow
          ├─ workflow.yaml にあって未承認 → deny
          └─ それ以外 ────────────────→ 判定なし
```

**Component Diagram:**
```
em-workflow/hooks/bash_guard.py          cd 前置形の allow 条件（FR1〜FR5）、module docstring（FR9）
em-workflow/references/command-execution-protocol.md   Verbatim execution rule（FR6）
em-workflow/agents/implementer.md        Step 3（FR7）
em-workflow/skills/worktree-task-workflow/SKILL.md     Command execution gate 節（FR7）
em-workflow/README.md                    実行時強制の項（FR8）
em-workflow/references/workflow-schema.md              Command approval store 節（FR8）
tests/                                   hook 試験と文書試験（FR10）
```

### Data Flow

```
implementer → cd "{worktree_path}" && <承認文字列> → bash_guard.py → allow / deny / 判定なし
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- 承認ストア（`EM_WORKFLOW_APPROVALS`）: 承認文字列の完全一致の判定に使う。
- workflow.yaml: 宣言済みで未承認の文字列の deny に使う。

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1、NFR7）。

### File Structure

```
em-workflow/
├── hooks/
│   └── bash_guard.py                       # FR1〜FR5、FR9
├── references/
│   ├── command-execution-protocol.md       # FR6
│   └── workflow-schema.md                  # FR8
├── agents/
│   └── implementer.md                      # FR7
├── skills/
│   └── worktree-task-workflow/
│       └── SKILL.md                        # FR7
└── README.md                               # FR8
tests/                                      # FR10
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/cd-prefix-toplevel-operators/**`
- `test-docs/cd-prefix-toplevel-operators/**`

`feature-docs/cd-prefix-toplevel-operators/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/cd-prefix-toplevel-operators/**` covers `test-docs/cd-prefix-toplevel-operators/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/cd-prefix-toplevel-operators/` directory at all; the declared
`test-docs/cd-prefix-toplevel-operators/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

hook 試験の方式は `tests/test_bash_guard_cd_prefix.py` と同じ（hook を subprocess で起動して JSON を渡す、`EM_WORKFLOW_APPROVALS` で承認ストアを分ける、一時的な git リポジトリを使う）。

- [ ] TS1: `A & B`、`A ; B`、`A || B`、`A &`、`A;` を承認する - cd 前置形が判定なしになる（AC1、AC2）
- [ ] TS2: `make test 2>&1`、`a |& b`、`a | b`、`a &> log`、`a &>> log`、`a <&0`、`a && b`、`echo "a;b"`、`echo 'a&b'`、`echo a\;b` を承認する - cd 前置形が allow のまま（AC3）
- [ ] TS3: FR3 の各条件（閉じていない引用、末尾のバックスラッシュ、`$'x'`、`$"x"`、`#` の位置違い（引用の中を含む）、引用の外の `(` `)` `{` `}`、`$(true)`、`${HOME}`、バッククォート、二重引用の中の `$(` / `${` / バッククォート）を承認する - cd 前置形が判定なしになる（AC4）
- [ ] TS4: cd を前置しない `A & B` の完全一致と、宣言済みで未承認の文字列 - それぞれ allow、deny のまま（AC5）
- [ ] TS5: 禁止パターンを含み `&` も含む承認文字列（承認ストアに直接書く）の cd 前置形 - deny になる（AC6）
- [ ] TS6: `tests/test_bash_guard_cd_prefix.py` の既存ケース - すべて通る（AC3、AC8）

### Integration Tests

- [ ] TS7: 文書試験 - 見出しで節を切り出し、空白を正規化して、FR6〜FR9 の記述（対象外の条件、implementer が実行せず notes で報告すること）が各文書にあることを確かめる。不在を確かめる assertion には、照合器が反応することを示す偽の文のケースを組にする（AC7）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

該当なし

### Edge Cases

- [ ] `&&&` のように `&&` の直後に `&` が続く場合: `&&` を認識した後の単独の `&` を数えて対象外にする。
- [ ] `||` と `|&` の区別: 引用の外で最長一致で認識する。
- [ ] 単一引用の中のバックスラッシュ（`'a\'`）: 通常の文字として扱い、引用はそこで閉じる。
- [ ] 二重引用の中のエスケープした引用符（`"a\"b"`）: 引用は閉じない。
- [ ] 二重引用の中の素の `$VAR`: FR3 の除外対象ではない。
- [ ] `<残り>` の前後の空白・末尾の改行: トリムしたあとに判定する（hook は入力全体も先に strip している）。
- [ ] path 部分に `&&` や空白を含む場合: 走査するのは `<残り>` だけで、path は対象外（既存ケース `x && y` ディレクトリ）。

### Performance Tests

該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** cd 前置形の allow は、`<残り>` が FR1〜FR3 の対象外の条件に当たらない承認済みの文字列に限る。禁止パターンは FR1 より先にコマンド全体へ当て、一致したら deny する（FR5）。
- **Input Validation:** `<残り>` を FR2 の規則で走査し、FR3 の安全側の追加除外条件を当てる。判定は LLM を使わず、コードで決定的に行う（NFR1）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

```
<残り> が FR1〜FR3 の対象外の条件に当たる → 文字列全体を今の判定表で判定（FR4）→ allow / deny / 判定なし
```

bash_guard.py の未承認 deny の additionalContext（`UNAPPROVED_GUIDANCE`）は変えない（前提 A6）。

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` がすべて通る（AC8）

## Assumptions

- A1: 修正方針は exclude_toplevel_operators とする。`cd "{worktree_path}" && <承認文字列>` という実行形は変えない（回答 requirement.fix-approach）。
- A2: 検出の精度は quote_and_redirect_aware とする。FR2 の走査規則と FR3 の安全側の追加除外条件は、回答で示された詳細化（単一引用の中のバックスラッシュ、二重引用の中のエスケープ、最長一致での認識、`$'` / `$"` / `#`、括弧・波括弧、置換構文）に従う（回答 requirement.operator-detection-precision）。
- A3: 対象外になった cd 前置形は判定なしに落ちる。新しい deny は足さない。
- A4: 既存の allow ケースと、cd を前置しないコマンドの判定は変えない。
- A5: 設計ステップは省略する（回答 design-step.decision）。
- A6: bash_guard.py の未承認 deny の additionalContext（`UNAPPROVED_GUIDANCE`）は変えない。対象外になった形は判定なしに落ち、deny にならないため、この案内は出ない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/cd-prefix-toplevel-operators/REQUIREMENTS.md`
- コマンド実行プロトコル: `em-workflow/references/command-execution-protocol.md`
- 既存の hook 試験: `tests/test_bash_guard_cd_prefix.py`
