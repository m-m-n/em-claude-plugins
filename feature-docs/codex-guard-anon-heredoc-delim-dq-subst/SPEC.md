# Feature: codex-guard-anon-heredoc-delim-dq-subst

## Overview

codex-hook-interactive-guard の、匿名関数の引数位置にある heredoc の区切り語の範囲で、二重引用符の中の `$( )` / `$(( ))` を原文のまま残し、zsh と同じ区切り語を登録する。`\` の対、単引用符、二重引用符の引用除去を 1 つの共通関数にまとめ、語の読み取りと区切り語の範囲の両方から呼ぶ。要件は `REQUIREMENTS.md` を参照する。

## Objectives

- 匿名関数の引数位置にある heredoc の区切り語の範囲で、zsh と同じ区切り語を登録する。二重引用符の中の `$( )` / `$(( ))` の中の引用符を除去していることで起きる見逃し（fail-open）と誤 deny をなくす。
- `\` の対、単引用符、二重引用符の引用除去の規則を 1 つの共通関数にまとめ、語の読み取りと区切り語の範囲から呼ぶ。2 つの読みが再び食い違わないようにする。

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1: 引用の 1 単位を読む共通関数** — `\` の対、単引用符（`'...'`）、二重引用符（`"..."`）のどれか 1 単位を読む共通関数を作る。開始位置と、その位置を含まない上限を受け取り、除去後の文字列と次の位置を返す。上限の前で単位が閉じないときは判定不能（`_Undecidable`）にする。
- **FR2: 共通関数を両方から呼ぶ** — parse 本体の `\` / `'` / `"` の 3 分岐は、上限を入力の終わりとして共通関数を呼ぶ。`_remove_range_quotes` の同じ 3 分岐は、上限を範囲の終わりとして呼ぶ。今の `_double_quoted` が持つ二重引用符の読みは共通関数に移す。
- **FR3: 二重引用符の中の置換を原文のまま残す** — 共通関数は、二重引用符の中の `` ` `` / `$(` / `$((` を `_skip_substitution` で読み飛ばし、置換の原文を中の引用符も含めて残す。区切り語の範囲でも語の読み取りでも同じ。
- **FR4: 上限を越える読み飛ばしは判定不能** — `_skip_substitution` が返した位置が上限を越えたら判定不能にする。`_skip_substitution` が自分で出す判定不能（置換が閉じない、置換の中の heredoc や case）もそのまま伝える。
- **FR5: 語の読み取りの区別を保つ** — 語の読み取り側の挙動は変えない。次の 3 つ。
    - 二重引用符の中の置換と `$` で語を dynamic にすること。
    - 空の引用（`''` や `""`）が語を始めることと、`\` と改行の対が文字を足さず語も始めないことの区別。
    - 入力の終わりにある `\` を判定不能にすること。
- **FR6: 2 つのコピーの同一性** — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で一緒に直し、バイト単位で同一に保つ。
- **FR7: docstring の更新** — モジュールの docstring の区切り語の範囲の段落と、`_remove_range_quotes` の docstring を更新する。二重引用符の中の `$( )` / `$(( ))` が原文のまま残ること、読み飛ばしが範囲を越えると判定不能になること、引用除去は共通関数が担うことを書く。`DELIMITER_RANGE_MARKERS` の 4 文と、`DOCSTRING_MARKERS` の「inside double quotes」は残す。
- **FR8: 対象外** — 次は対象外とする。
    1. 区切り語の範囲の引用符の外にある `${ ... }` の読み。中の引用符を除去する今の処理のままにする。
    2. `$` の扱い全般（`_dollar`、範囲の中の `$'` / `$"` を判定不能にする規則、引用符の外の `$(` を `_skip_parens` で読む規則）。
    3. 通常の語の読み取り側（`_dollar`）の `${ ... }` の食い違い。これは別の課題として扱う。
    4. `_scan_parens` による範囲の見つけ方。

### Non-Functional Requirements
- **NFR1 - Performance:** 処理時間は入力の長さに対して線形を保つ。既存の `test_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied`（TS-17）が通ること。
- **NFR2 - Call structure:** 呼び出しは「読み取り側 → 共通関数 → 反復で読む `_skip_substitution`」に限る。再帰と循環呼び出しは持ち込まない（`TestNoRecursion`）。
- **NFR3 - Static constraints:** 標準ライブラリだけを使い、書き込みやプロセスの起動をしない（`TestStaticConstraints`）。
- **NFR4 - Version:** `plugin.json` と `marketplace.json` の version は変えない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
parse 本体の \ / ' / " の 3 分岐        （上限 = 入力の終わり）
_remove_range_quotes の \ / ' / " の 3 分岐（上限 = 範囲の終わり）
        │
        ▼
共通関数（引用の 1 単位を読む。除去後の文字列と次の位置を返す）
        │  二重引用符の中の ` / $( / $((
        ▼
_skip_substitution（反復で読む。返した位置が上限を越えたら判定不能）
```

### Data Flow

```
開始位置, 上限 → 共通関数 → (除去後の文字列, 次の位置)
                          → 判定不能（上限の前で単位が閉じない / 読み飛ばしが上限を越える /
                                      _skip_substitution 自身の判定不能）
```

### Dependencies

**Internal Dependencies:**
- `_skip_substitution`: 二重引用符の中の `` ` `` / `$(` / `$((` の読み飛ばしに使う（FR3、FR4）。
- `_double_quoted`: 二重引用符の読みを共通関数に移す（FR2）。

**External Dependencies:**
- なし（標準ライブラリのみ、NFR3）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # 変更（FR1〜FR5、FR7）
em-review/scripts/codex-hook-interactive-guard.py     # 上と同じ内容（FR6）
tests/test_codex_hook_interactive_guard.py            # CASES に追加（TS1〜TS6）
```

### Assumptions

- 範囲の中のバッククォートは共通関数に届かない。バッククォートを含む範囲は、`_read_argument_parens` がこれまでどおり群として開く（1246 行）ため。（影響度: 低、取り消し可能）
- 区切り語として登録される語では dynamic フラグは使われない（`_finish_word` が redirect の分岐で早く返る、741〜748 行）。共通関数が返す dynamic を範囲側で捨てても、判定は変わらない。（影響度: 低、取り消し可能）
- zsh 5.9 は heredoc の区切り語の `${ ... }` の中でも引用符を除去する。範囲側の今の `${ ... }` の処理は zsh と一致している（batch の Codex 相談での実測による）。（影響度: 低、取り消し可能）
- `_double_quoted` は共通関数に吸収するので、なくしてもよい。名前を残す必要はない。テストからは名前で参照されていない。（影響度: 低、取り消し可能）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-anon-heredoc-delim-dq-subst/**`
- `test-docs/codex-guard-anon-heredoc-delim-dq-subst/**`

`feature-docs/codex-guard-anon-heredoc-delim-dq-subst/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-anon-heredoc-delim-dq-subst/**` covers `test-docs/codex-guard-anon-heredoc-delim-dq-subst/{T}.tests.yaml`, the
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

テストは `tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` の形で追加する。期待する判定は `deny` か `silent`。

### Unit Tests
- [ ] TS1（deny、`CASES` に追加）: 見逃し側の再現入力（`zsh -c` + `shlex.quote` で包んだ 4 行）が deny になる。（FR1、FR2、FR3 / AC-1、AC-3）
    ```
    function { :; } << foo("$(echo "x")")
    foo("$(echo "x")")
    foo($(echo "x"))
    python3 -i
    ```
- [ ] TS2（silent、`CASES` に追加）: 誤 deny 側の再現入力（4 行）が silent になる。（FR1、FR2、FR3 / AC-2、AC-3）
    ```
    function { :; } << foo("$(echo "a")")
    foo($(echo a))
    python3 -i
    foo($(echo "a"))
    ```
- [ ] TS3（silent、`CASES` に追加）: 読み飛ばしが範囲の終わりを越える。例: `function { :; } << foo("$(echo ")")")` と本文の後ろの `python3 -i`。`_scan_parens` は範囲を `("$(echo ")` で閉じ、置換の読み飛ばしはその先で閉じる。（FR4 / AC-4）
- [ ] TS4（deny、`CASES` に追加）: 二重引用符の中の `$(( ))` を原文のまま残した区切り語の行で本文が閉じ、その後ろの `python3 -i` が deny になる。（FR3）
    ```
    function { :; } << foo("$((1+2))")
    foo($((1+2)))
    python3 -i
    ```
- [ ] TS5（deny、`CASES` に追加）: 二重引用符の中で置換が入れ子になり、中に引用符がある区切り語を原文のまま残す。（FR3）
    ```
    function { :; } << foo("$(a "$(b "c")")")
    foo($(a "$(b "c")"))
    python3 -i
    ```
- [ ] TS6（silent、`CASES` に追加）: 空の引用は語を始める。`python3 '' -i` と `python3 "" -i` は、空の語がオペランドになるので silent。既存の「行継続」（`python3 \<改行> -i` → deny、153 行）と対になる。実装の前に、変更前の判定が silent であることを確かめる。（FR5）
- [ ] TS7（既存）: 714〜752 行の区切り語の範囲のケース、TS-10（二重引用符の中の `$'` は契機にしない）、749 行（引用符の外の `$( )` の中の引用符を除去しない）が今のまま通る。（FR2、FR8）

### Integration Tests
- [ ] リポジトリルートで実行した `python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る。既存の `CASES`、`TestCopies`（バイト単位の同一性、FR6）、`TestNoRecursion`（NFR2）、TS-17（NFR1）、`TestGuardDocumentation`（FR7）を含む。（AC-6）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 上限の前で単位が閉じない: 判定不能（FR1）。
- [ ] `_skip_substitution` が返した位置が上限を越える: 判定不能（FR4、TS3）。
- [ ] `_skip_substitution` 自身の判定不能（置換が閉じない、置換の中の heredoc や case）: そのまま伝える（FR4）。
- [ ] 入力の終わりにある `\`: 判定不能（FR5）。

### Performance Tests
- [ ] 既存の TS-17（`test_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied`）が通る（NFR1）。

## Security Considerations

- **Input Validation:** 区切り語の範囲と語の読み取りの引用除去は共通関数を通る（FR1、FR2）。読めない入力は判定不能にする（FR1、FR4）。
- 書き込みやプロセスの起動をしない（NFR3）。

## Error Handling

### Error Flow

```
上限の前で単位が閉じない / 読み飛ばしが上限を越える / _skip_substitution 自身の判定不能
  → _Undecidable（判定不能） → silent
```

## Performance Optimization

### Performance Goals
- 処理時間は入力の長さに対して線形を保つ。既存の `test_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied`（TS-17）が通ること（NFR1）。

### Optimization Strategies
該当なし

### Caching Strategy
該当なし

## Success Criteria

- [ ] AC-1: 見逃し側の再現入力（TS1）が deny になる。
- [ ] AC-2: 誤 deny 側の再現入力（TS2）が silent になる。
- [ ] AC-3: AC-1 と AC-2 の 2 入力を、`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` の形で追加する。
- [ ] AC-4: 区切り語の範囲の二重引用符の中で、置換の読み飛ばしが範囲の終わりを越える入力が silent（判定不能）になる。
- [ ] AC-5: parse 本体の `\` / `'` / `"` の分岐と、`_remove_range_quotes` の同じ 3 分岐が、どちらも共通関数を呼んでいる。parse 本体にも `_remove_range_quotes` にも、二重引用符の中を読むループが残っていない。
- [ ] AC-6: リポジトリルートで実行した `python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る。既存の `CASES`、`TestCopies`（バイト単位の同一性）、`TestNoRecursion`、TS-17、`TestGuardDocumentation` を含む。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/codex-guard-anon-heredoc-delim-dq-subst/REQUIREMENTS.md`
