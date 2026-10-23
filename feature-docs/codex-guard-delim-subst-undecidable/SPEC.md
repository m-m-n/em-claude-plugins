# Feature: codex-guard-delim-subst-undecidable

## Overview

`codex-hook-interactive-guard.py`（em-workflow / em-review の 2 つのコピー）の共有スキップ `_skip_substitution` の読みを直す。ヒアドキュメントの区切り語の `${ ... }` の中の `$( ... )` に、置換内の `<<`、コマンドの位置の算術の `<<`、引数の語の中の括弧のどれがあっても、区切り語の終わりを zsh と同じ位置に置き、終端行の後の `python3 -i` を deny に戻す。codex-guard-heredoc-delim-brace-case で入った fail-open の回帰の修正。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- ヒアドキュメントの区切り語の `${ ... }` の中の `$( ... )` に、置換内の `<<`、コマンドの位置の算術の `<<`、引数の語の中の括弧のどれがあっても、区切り語の終わりを zsh と同じ位置に置き、終端行の後の `python3 -i` を deny に戻す（codex-guard-heredoc-delim-brace-case で入った fail-open の回帰を直す）。

## User Stories

該当なし（UI の無いフックスクリプトの構文解析のバグ修正）

## Technical Requirements

### Functional Requirements

- **FR1:** 置換内の同じ行で閉じる `<<` の読み — 共有スキップ `_skip_substitution`（em-workflow / em-review の `scripts/codex-hook-interactive-guard.py`）は、case 文の外の `<<` のうち、置換を閉じる `)` までに引用されていない改行が無いものを判定不能にしない。閉じの位置を変えずに読み進め、本文は読まない。`<<` の後、置換が閉じる前に引用されていない改行が来る形と、case 文の中（subject・パターン・項目の本体）の `<<` は、今のとおり判定不能にする。`<<<` は今のとおり heredoc ではない。この読みは二重引用符の中の `$( )` と、区切り語の `${ }` の中の引用されていない `$( )` の両方に効く。改行が来るかどうかは `<<` ごとに先読みし直して確かめず、1 回の走査の中で判定して線形時間を保つ。
- **FR2:** コマンドの位置の `((` は算術、`))` で閉じなければサブシェル — `_skip_substitution` の中で、コマンドの位置の `((`（for の後の `((` を含む。空白を挟んだ `( (` は含まない）は、`))` で閉じれば算術の文脈として読む。中の `<<` は左シフトで、heredoc とみなさない。閉じた後は、包むリストがコマンドの位置になる（今の close_command の意味を保つ）。`((` に対応する閉じが `))` にならない場合は、その `((` から入れ子のサブシェル 2 段として読み直し、今の読みと同じ結果にする。読み直しは 1 つの `((` につき 1 回までにする。読み直しで読む文字の総量には上限を設け、明示スタックで処理して線形時間を保つ。上限を超えたら判定不能にする。
- **FR3:** 引数の語の中の括弧は語の文脈 — `_skip_substitution` の中で、コマンドの位置でない `(` は語の括弧の新しい文脈で開く。対象は語の途中の `(` と、引数の位置の語頭の `(` の両方。中の語はコマンドの位置にならず、case・閉じの語・head は効かない。`#` は語の文字として読み、注釈にしない（`(#q...)` などのグロブフラグのため）。`;`・`&`・`|` と改行も語の文字として読み、判定不能にしない。引用・`\` の組・`$( )`・`$(( ))`・`${ }`・バッククォートは、ほかの文脈と同じく追う。入れ子の `(` は同じ文脈の入れ子として開き、`)` は語の中で閉じる。閉じた後、包むリストは元の状態のまま語の中を読み続ける。コマンドの位置の `(`（サブシェル）、`<(`、`>(`、zsh の `=(`、関数 head の `name()`、`for name (words)` の語の並び（w 文脈）は、今の読みを保つ。既存の w 文脈は流用しない（w は `#` を注釈として読むため）。
- **FR4:** 両コピーの同一性 — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更で直し、バイト単位で同一に保つ。
- **FR5:** 回帰テスト — Test Scenarios の行を `tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で足し、両方のコピーに流す。既存の deny / silent の行は消さない。
- **FR6:** docstring の追従 — `_skip_substitution` の docstring（と、必要ならモジュールの docstring）を FR1〜FR3 の読みに合わせる。『a heredoc anywhere in the chunk (item bodies included)』の文言は case 文の中の heredoc について残す。heredoc を常に判定不能とする書き方は改める。テストが固定している文言（`TestSubstitutionSkipDocumentation` の `UNDECIDABLE_MARKERS` / `RULE_MARKERS` など）を変える場合は、テスト側の文言も同じ変更で直す。

### Non-Functional Requirements

- **NFR1 - Performance:** 線形時間を保つ。1 文字あたりの仕事は定数（読み直しは FR2 の上限の範囲内）で、明示スタックを使い再帰しない（`TestNoRecursion`、大規模入力の時間テスト）
- **NFR2 - Maintainability:** `_skip_substitution` の呼び出し構造の制約を保つ。`_skip_substitution` を呼ぶのは `_read_quoted_unit` だけで、`_skip_substitution` から到達できるメソッドに `_skip_substitution` / `_read_quoted_unit` / `parse` / `_remove_range_quotes` を含めない（`TestSharedQuotedUnitReader`、`TestSubstitutionSkipCallStructure`）
- **NFR3 - Security:** 今は判定できている形を新たに判定不能（出力なし）に変えない
- **NFR4 - Versioning:** plugin の version は変えない

## zsh 5.9 Measurements

zsh 5.9 の実測結果（`zsh -f`、`python3 -i` の代わりに無害な `echo`）:

1. `cat <<${v:-$(echo <<EOF)}` / 本文 / `${v:-$(echo <<EOF)}` / `echo AFTER` では本文が出力され AFTER が実行される。区切り語は同じ行の `)` で閉じた `${v:-$(echo <<EOF)}` 全体で、中の `<<EOF` は後続の行から本文を読まない。
2. 終端行を `EOF` にすると AFTER は本文に吸われる（区切り語は `EOF` ではない）。
3. 再現手順の形 `if false; then : <<${v:-$(echo <<EOF)} ... fi` のあとの `echo AFTER` は実行される。
4. `echo "$(cat <<EOF)"` のあとの `echo AFTER` では、空行が出て AFTER が実行される（同じ行で閉じ、本文は空）。
5. 区切り語の `$( ((1 << 2)) )` は全文が区切り語で、短い終端行 `2)) )}` では AFTER が吸われる。
6. 区切り語の `$(for ((i=0;i<1<<2;i++)) do :; done)` は全文が区切り語。
7. 区切り語の `$(echo foo(case x))` は全文が区切り語で、短い終端行 `x))}` では AFTER が吸われる。区切り語の `${v:-$(echo foo(a;b))}` も全文が区切り語として受理される。
8. `echo $( ((echo a) ) )` は `a` を出力し（算術でない `((` を入れ子のサブシェルとして読み直す）、`echo $( ((echo a); echo b) )` は `a b` を出力する。
9. `$( )` / `"$( )"` の中や case の項目の本体の中の複数行のヒアドキュメントは、置換の中で普通に本文が読まれる。グロブ修飾 `*(e:true<改行>:N)` も受理される。

## Implementation Approach

### Architecture

該当なし（既存スクリプト内の `_skip_substitution` の読みの変更）

### Data Flow

該当なし

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `_read_quoted_unit`: `_skip_substitution` を呼ぶ唯一のメソッド（NFR2）
- `tests/test_codex_hook_interactive_guard.py`: `CASES`、`TestNoRecursion`、`TestSharedQuotedUnitReader`、`TestSubstitutionSkipCallStructure`、`TestSubstitutionSkipDocumentation`

**External Dependencies:**
- 該当なし

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py
em-review/scripts/codex-hook-interactive-guard.py   # 上とバイト単位で同一（FR4）
tests/test_codex_hook_interactive_guard.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-delim-subst-undecidable/**`
- `test-docs/codex-guard-delim-subst-undecidable/**`

`feature-docs/codex-guard-delim-subst-undecidable/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-delim-subst-undecidable/**` covers
`test-docs/codex-guard-delim-subst-undecidable/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-delim-subst-undecidable/` directory at all; the
declared `test-docs/codex-guard-delim-subst-undecidable/**` entry is still
correct in that case — a declared path that never materializes is not a
violation.

## Test Scenarios

### Unit Tests

`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で足し、両方のコピーに流す（FR5）。コマンドは Python の式で表す。

- [ ] TS1 (deny, AC-1) [FR1, FR5]: `"\n".join(["zsh -c 'if false; then", ": <<${v:-$(echo <<EOF)}", "${v:-$(echo <<EOF)}", "fi", "python3 -i'"])`
- [ ] TS2 (deny) [FR1, FR5]: `"\n".join(["cat <<${v:-$(echo <<EOF)}", "${v:-$(echo <<EOF)}", "python3 -i"])`
- [ ] TS3 (silent) [FR1, FR5]: 終端行が EOF だけでは本文が閉じない。`"\n".join(["cat <<${v:-$(echo <<EOF)}", "EOF", "python3 -i"])`
- [ ] TS4 (deny, AC-2) [FR2, FR5]: `"\n".join(["cat <<${v:-$( ((1 << 2)) )}", "${v:-$( ((1 << 2)) )}", "python3 -i"])`
- [ ] TS5 (silent) [FR2, FR5]: 短い終端行では本文が閉じない。`"\n".join(["cat <<${v:-$( ((1 << 2)) )}", "2)) )}", "python3 -i"])`
- [ ] TS6 (deny, AC-2) [FR2, FR5]: `"\n".join(["cat <<${v:-$(for ((i=0;i<1<<2;i++)) do :; done)}", "${v:-$(for ((i=0;i<1<<2;i++)) do :; done)}", "python3 -i"])`
- [ ] TS7 (deny, AC-3) [FR3, FR5]: `"\n".join(["cat <<${v:-$(echo foo(case x))}", "${v:-$(echo foo(case x))}", "python3 -i"])`
- [ ] TS8 (silent) [FR3, FR5]: `"\n".join(["cat <<${v:-$(echo foo(case x))}", "x))}", "python3 -i"])`
- [ ] TS9 (deny, AC-3) [FR3, FR5]: `"\n".join(["cat <<${v:-$(echo foo(a;b))}", "${v:-$(echo foo(a;b))}", "python3 -i"])`
- [ ] TS10 (deny, AC-4 回帰) [FR3, FR5]: `'echo "$(echo foo(a;b))"; python3 -i'`
- [ ] TS11 (deny, AC-4 回帰) [FR2, FR5]: `'echo "$( ((echo a) ) )"; python3 -i'`
- [ ] TS12 (deny) [FR1, FR5]: 二重引用符の中の同じ行の heredoc は判定できる。`'echo "$(cat <<EOF)"; python3 -i'`
- [ ] TS13 (deny) [FR3, FR5]: 語の括弧の中の改行。`"\n".join(["cat <<${v:-$(echo *(e:true", ":N))}", "${v:-$(echo *(e:true", ":N))}", "python3 -i"])`。区切り語は 1 行で比べるため、行を分けたこの形の期待値は実装時に zsh の実測で確かめて確定する。合わない場合は、同じ行に収まる `*(#qN)` の形（`cat <<${v:-$(echo *(#qN))}` / `${v:-$(echo *(#qN))}` / `python3 -i` → deny）に置き換える
- [ ] TS14 (silent, 既存の行を保つ) [FR1, FR5]: `CASES` 967 行目の、case 文の項目の本体の中の heredoc は判定不能
- [ ] TS15 (silent) [FR1, FR5]: `<<` の後、置換の中で改行が来る形は判定不能。`'echo "$(cat <<EOF\nbody\nEOF\n)"; python3 -i'`

### Integration Tests

- [ ] AC-1: 再現手順の文字列 `zsh -c 'if false; then\n: <<${v:-$(echo <<EOF)}\n${v:-$(echo <<EOF)}\nfi\npython3 -i'` をフックの標準入力の `tool_input.command` に渡すと、両方のコピーが deny を返す
- [ ] AC-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] case 文の中（subject・パターン・項目の本体）の `<<` は判定不能のまま（FR1、TS14）
- [ ] `<<` の後、置換が閉じる前に引用されていない改行が来る形は判定不能のまま（FR1、TS15）
- [ ] `<<<` は heredoc ではない（FR1）
- [ ] 空白を挟んだ `( (` は算術の `((` に含まない（FR2）
- [ ] `((` に対応する閉じが `))` にならない場合は入れ子のサブシェル 2 段として読み直す。読み直しの上限を超えたら判定不能（FR2、TS11）
- [ ] 語の括弧の中の `#`・`;`・`&`・`|`・改行は語の文字（FR3、TS9、TS13）

### Performance Tests

- [ ] `TestNoRecursion` と大規模入力の時間テストが通る（NFR1）

## Security Considerations

- **Input Validation:** 今は判定できている形を新たに判定不能（出力なし）に変えない（NFR3）

## Error Handling

該当なし

## Performance Optimization

### Performance Goals
- 線形時間。1 文字あたりの仕事は定数（読み直しは FR2 の上限の範囲内）（NFR1）

### Optimization Strategies
- 明示スタックを使い再帰しない（NFR1）
- `<<` の後の改行の有無は 1 回の走査の中で判定する（FR1）

## Success Criteria

- [ ] AC-1: 再現手順の文字列をフックの標準入力の `tool_input.command` に渡すと、両方のコピーが deny を返す
- [ ] AC-2: 区切り語の `${ }` に `$( ((1 << 2)) )` を置いた同じ構成と、`$(for ((i=0;i<1<<2;i++)) do :; done)` を置いた同じ構成で、両方のコピーが deny を返す
- [ ] AC-3: 区切り語の `${ }` に `$(echo foo(case x))` を置いた同じ構成と、`$(echo foo(a;b))` を置いた同じ構成で、両方のコピーが deny を返す
- [ ] AC-4: 今 deny の `echo "$(echo foo(a;b))"; python3 -i` と `echo "$( ((echo a) ) )"; python3 -i` が、両方のコピーで deny のまま
- [ ] AC-5: 2 つのコピーがバイト単位で同一
- [ ] AC-6: SPEC に zsh 5.9 の実測結果が記録されている（本書「zsh 5.9 Measurements」）
- [ ] AC-7: Test Scenarios の行が `CASES` にあり、両方のコピーに流れる
- [ ] AC-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

## Assumptions

- A1: 2 つのコピーは同じ変更の中で一緒に直し、バイト単位で同一に保つ。`CASES` の新しい行は両方のコピーに流す。（`.claude/rules/hook-tests.md`）
- A2: 線形時間と呼び出し構造の制約を保つ（NFR1, NFR2）。（既存テストで固定されている）
- A3: plugin の version は変えない。（`.claude/rules/core-plugin-version-bump.md`）
- A4: 置換内の `<<` は shared_same_line で読む（FR1）。（batch の Codex 相談の回答。zsh 5.9 の実測 1〜4 と一致する）
- A5: コマンドの位置の `((` は arith_or_subshell で読む（FR2）。（batch の Codex 相談の回答。zsh 5.9 の実測 5・6・8 と一致する）
- A6: 語の括弧は word_ctx_all_chars で読む（FR3）。（batch の Codex 相談の回答。zsh 5.9 の実測 7 と、`${v:-$(echo foo(a;b))}`・`*(e:true<改行>:N)` が受理されることに一致する）
- A7: design ステップは飛ばす。（batch の決定表で推奨 skip を採用した）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（全要件 resolved）

## References

- 要件定義書: `feature-docs/codex-guard-delim-subst-undecidable/REQUIREMENTS.md`
- フックのテストのルール: `.claude/rules/hook-tests.md`
