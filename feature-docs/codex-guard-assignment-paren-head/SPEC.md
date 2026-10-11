# Feature: codex-guard-assignment-paren-head

## Overview

codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）が、配列代入（`a=()` / `a+=()` / `export a=()` など）の後に改行を挟んで続くグループを関数本体とみなさず、その中の対話起動を deny するようにする。
bash の関数定義（`foo()` + 改行 + 本体、`f() (本体)`、`function f() { 本体; }`）の本体は、これまでどおり判定しない。

## Objectives

- codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）が、配列代入（`a=()` / `a+=()` / `export a=()` など）の後に改行を挟んで続くグループを関数本体とみなさず、その中の対話起動を deny する
- bash の関数定義（`foo()` + 改行 + 本体、`f() (本体)`、`function f() { 本体; }`）の本体は、これまでどおり判定しない

## Acceptance Criteria

- [ ] AC-1: `{"tool_input": {"command": "a=()\n(python3 -i)"}}` を両コピーの標準入力に渡すと deny が出力される（FR1, FR2, FR5）
- [ ] AC-2: FR2 の全コマンドで両コピーが deny を出力する（FR1, FR2）
- [ ] AC-3: FR3 の全コマンドで両コピーが何も出力しない（FR1, FR3）
- [ ] AC-4: `a=() ; (python3 -i)` で両コピーが deny を出力する（FR4）
- [ ] AC-5: `CASES` に `a=()` / `a+=()` + 改行 + `(python3 -i)` が deny として含まれ、`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る（FR6）
- [ ] AC-6: `TestCopies.test_the_two_copies_are_byte_identical` が通る（FR5）
- [ ] AC-7: `python3 -m unittest discover -s tests` が修正前と同じく通る（既存ケースの判定が変わらない）（NFR1, NFR2）

## Technical Requirements

### Functional Requirements

- **FR1:** 関数名の判定条件を絞る。`(` を開いたときに関数名ありとみなす（`_Group.head` を立てる）のは、`(` の直前の単純コマンドが次のどちらかのときだけとする。
    - (a) 動的でない語 1 つだけで、その語が `=` を含まない。
    - (b) 語 2 つで、1 つ目が `function`、2 つ目が動的でなく `=` を含まない。
    - それ以外（`a=` / `a+=` / `export a=` / 動的な語 / 3 語以上）のときは関数名ありとしない。
- **FR2:** 配列代入の後のグループを判定する。次のコマンドで、グループの中の起動を判定し deny を出力する。
    - `a=()` + 改行 + `(python3 -i)`
    - `a+=()` + 改行 + `(python3 -i)`
    - `export a=()` + 改行 + `(python3 -i)`
    - `a=()` + 空行 + `(python3)`
    - `a=()` + 改行 + コメント行 + 改行 + `(python3 -i)`
    - `a=()` + 改行 + `{ python3 -i; }`
- **FR3:** 関数定義の本体は判定しない。次のコマンドは何も出力しない。関数名の後の改行で関数本体の待ち状態（`fn_head`）を消さない現在の振る舞いは保つ。
    - `foo()` + 改行 + `(python3 -i)`
    - `f() (python3 -i)`
    - `f() { python3; }`
    - `function f() { python3; }`
- **FR4:** `;` 区切りの判定を保つ。`a=() ; (python3 -i)` は deny のまま保つ。
- **FR5:** 両コピーを同時に直す。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更で直し、バイト単位で同一に保つ。
- **FR6:** テーブルにケースを追加する。`tests/test_codex_hook_interactive_guard.py` の `CASES` に、次を `(期待する判定, ラベル, コマンド)` の形で追加する。既存のケースは消さない。
    - FR2 のコマンドを deny
    - FR3 のうち未登録のコマンド（`foo()` + 改行 + `(python3 -i)`、`f() (python3 -i)`、`function f() { python3; }`）を silent
    - `a=() ; (python3 -i)` を deny

### Non-Functional Requirements

- **NFR1 - 判定できないものは通す方針を保つ:** モジュール docstring にある「判定できないものは何も出力しない」方針、標準ライブラリだけを使うこと、ファイル・ネットワーク・子プロセスに触れないことを保つ（既存の `TestStaticConstraints` / `TestFailOpen` が通る）。
- **NFR2 - docstring を実装に合わせる:** モジュール docstring の手順 4 の関数定義の記述と `_Group` の `head` の説明を、FR1 の条件に合わせる。`TestGuardDocumentation` の既存マーカーは残す。

## Assumptions

- **A1:** FR1 の「有効な関数名」は「動的でなく `=` を含まない語」とし、識別子の文字種までは絞らない。`my-func() { python3; }` のような bash で有効な非識別子の関数名は今と同じく silent のまま。
- **A2:** `a=()` + 改行 + `{ python3 -i; }`（基準版でも通っていた既存の見落とし）も FR1 の修正で deny になるため、対象に含めて deny ケースとして固定する。
- **A3:** 関数名の後の改行で `fn_head` を消さない振る舞い（`_separator` の 325 行目）は変えない。
- **A4:** バグ修正なので plugin.json / marketplace.json の version は手で変えない（patch は main への push 時に Actions が上げる）。

## Implementation Approach

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1–FR5, NFR1, NFR2
em-review/scripts/codex-hook-interactive-guard.py     # FR5（em-workflow 側とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR6（CASES への追加）
```

### Design Step

UI を持たない Python フックの判定ロジックの修正で、画面設計の対象が無いため、design ステップは行わない。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-assignment-paren-head/**`
- `test-docs/codex-guard-assignment-paren-head/**`

`feature-docs/codex-guard-assignment-paren-head/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-assignment-paren-head/**` covers `test-docs/codex-guard-assignment-paren-head/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-assignment-paren-head/` directory at all; the declared
`test-docs/codex-guard-assignment-paren-head/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

コマンドは Python の文字列リテラルで表す（`\n` は改行）。判定は両コピーに対して行う。

| ID | コマンド | 期待する判定 | 要件 |
|----|----------|--------------|------|
| TS-1 | `"a=()\n(python3 -i)"` | deny | FR1, FR2, FR6 |
| TS-2 | `"a+=()\n(python3 -i)"` | deny | FR1, FR2, FR6 |
| TS-3 | `"export a=()\n(python3 -i)"` | deny | FR1, FR2, FR6 |
| TS-4 | `"a=()\n\n(python3)"` | deny | FR1, FR2, FR6 |
| TS-5 | `"a=()\n# c\n(python3 -i)"` | deny | FR1, FR2, FR6 |
| TS-6 | `"a=()\n{ python3 -i; }"` | deny | FR1, FR2, FR6 |
| TS-7 | `"a=() ; (python3 -i)"` | deny | FR4, FR6 |
| TS-8 | `"foo()\n(python3 -i)"` | silent | FR1, FR3, FR6 |
| TS-9 | `"f() (python3 -i)"` | silent | FR1, FR3, FR6 |
| TS-10 | `"function f() { python3; }"` | silent | FR1, FR3, FR6 |
| TS-11 | `"f() { python3; }"` | silent | FR1, FR3 |

TS-11 は既存ケース（関数定義の本体は実行しない）。

### Integration Tests

- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る
- [ ] `python3 -m unittest discover -s tests` が修正前と同じく通る

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Open Questions

なし

## References

- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
