# Feature: codex-guard-subst-reading-regressions

## Overview

codex-hook-interactive-guard（em-workflow / em-review の両コピー）の `_skip_substitution` から、codex-guard-case-reading-fixes で生じた 3 種類の後退（拒否漏れ）をなくす。3 種類とも、基準コミットでは deny だった入力が、置換の読み違いで `_Undecidable` になる。要件定義は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）の `_skip_substitution` から、codex-guard-case-reading-fixes で生じた 3 種類の後退（拒否漏れ）をなくす。
- 3 種類とも、基準コミットでは deny だった入力が、置換の読み違いで `_Undecidable` になる。これらの入力で、後ろの `python3 -i` を再び deny にする。
- 直した後の読み方で、新たな誤拒否を生まない。

## User Stories

該当なし（受け入れ基準は Success Criteria に記載）

## Technical Requirements

### Functional Requirements

- **FR1:** for の語一覧は専用の文脈で読む — zsh の `for name (words)` の語一覧は、算術展開の文脈 `a` を流用せず、語一覧用の文脈として積む。語一覧の中の語は、今と同じくコマンドの位置で読まない。`#` のコメントは `p` と同じ条件で始まる（直前の文字が空白・タブ・改行・`;` `&` `|` `(` のいずれか）。始まったコメントは改行まで読み飛ばす。コメントの中の引用符・`)`・置換は、何も開かず何も閉じない。改行は語を区切るが、次の語をコマンドの位置にはしない。語一覧の中でさらに開く `(`（`*(N)` のような glob 修飾子）も、中の語をコマンドの位置で読まない。その `)` の後は語の続きとして読む。語一覧を閉じる `)` の後は、今と同じくコマンドの位置にする。`$((` の算術展開の読み方は変えない。
- **FR2:** 空の () の判定で行継続の対を読み飛ばす — `_empty_parens_end` は、括弧の間にある空白とタブに加えて、バックスラッシュと改行の対も読み飛ばす。中がそれらだけのときに空の `()` とする。対象は `name()`、`function name()`、`function ()` のすべて（例: `f(\<NL>)`、`f (\<NL>)`、`f( \<NL>\<NL> )`）。入力が対のバックスラッシュで終わり、`)` が来ないものは空の `()` ではない。
- **FR3:** シェルの種類を読み取りに渡す — シェルの `-c` 文字列は、それを直接保持するシェルコマンドのベース名から決めたシェルの種類で読む。種類は bash / zsh / 不明 の 3 つ。照合は `_family_of` と同じで、名前そのものか、名前の後ろに数字と `.` が続くものを一致とみなす。`env` などのラッパーやパス（`/usr/bin/zsh`）を経由しても、照合はベース名で行う。sh / dash / ksh の `-c` 文字列と、フックが受け取ったコマンドそのものは、種類を『不明』とする。文字列の中の `$( )` も、その文字列と同じ種類で読む。より深い段の文字列は、自分を直接保持するシェルで決める。
- **FR4:** coproc をシェルごとに読む — bash では今の読み方（前のフィーチャー codex-guard-case-reading-fixes の SPEC の要件 11）のとおりに読む。coproc の直後の語をコマンドの位置にし、それが普通の語（NAME）なら、その次の語もコマンドの位置にする（`coproc c {`）。zsh の coproc は NAME を取らない。直後の語はコマンドの位置にする（`coproc {`、`coproc while`）。それが普通の語なら、その語は単純コマンドの最初の語として読み、後ろの語は引数とする（`coproc echo case x in x` の case は文を開かない）。
- **FR5:** repeat をシェルごとに読む — zsh では今の読み方（前のフィーチャー codex-guard-case-reading-fixes の SPEC の要件 11）のとおりに読む。repeat の直後の 1 語（回数）は普通の語で、その次の語をコマンドの位置にする（`repeat 1 {`）。bash では repeat は予約語ではなく、普通のコマンド名として読む。後ろの語は引数とする（`repeat x case y in y` の case は文を開かない）。
- **FR6:** シェルが分からない文字列は、読めなければ 1 回だけ読み直す — 種類が『不明』の文字列は、まず今の読み方で読む。今の読み方とは、bash の coproc NAME の規則と zsh の repeat の規則の両方を使う読み方。それで最後まで読めたら、その結果を使う（codex-guard-case-reading-fixes の TS47 / TS50 は今のまま deny）。判定不能（`_Undecidable`）になったときだけ、どちらの規則も使わない読み方で 1 回だけ読み直す。どちらの規則も使わない読み方では、coproc の直後の語をコマンドの位置にし、それが普通の語なら後ろの語を引数とする（FR4 の zsh の読み方と同じ）。repeat は普通のコマンド名として読む（FR5 の bash の読み方と同じ）。読み直しで最後まで読めたときだけ、その結果を採用する。読み直しも失敗したら、例外の種類にかかわらず、初回の `_Undecidable` とそれが持つ確定済みのコマンド（最後のチェックポイントまで）を使う。bash / zsh と分かっている文字列は読み直さない。読み直しは `parse` の中で扱う。`find_deny(command)` の引数と、`_scan` の中で `parse` を囲む 1 つの try は保つ。
- **FR7:** 両コピーを同時に直す — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR8:** docstring を更新する — 次の docstring とコメントを、FR1〜FR6 に合わせて書き直す。`_skip_substitution` の docstring（rule 6 の、空の `()` の判定・coproc・repeat の文と、Contexts on the stack の `a` の説明）、`_empty_parens_end` の docstring、`HEAD_*` と `HEAD_AFTER_WORD` のコメント、シェルの種類と読み直しにかかわる関数（`parse` / `_Parser` / `_judge` / `_scan`）の docstring、モジュールの docstring の手順 7 と手順 9。`TestSubstitutionSkipDocumentation` と `TestGuardDocumentation` が固定している文言のうち、本フィーチャーで意味が変わるもの（`RULE_MARKERS` の `loop and coproc head rule` など）は、docstring と同じ変更の中で書き換えてよい。それ以外の固定された文言は残す。
- **FR9:** CASES に再現と派生の行を足す — `tests/test_codex_hook_interactive_guard.py` の `CASES` に、TS1〜TS24 を `(期待する判定, ラベル, コマンド)` の形で足し、両コピーに流す。線形時間のシナリオ（TS25〜TS27）は `TestCaseStatementsInASubstitution` に置く。

### Non-Functional Requirements

- **NFR1 - 線形時間:** 読み取りは、入力の長さに対して線形の時間で終わる。1 つの文字列を読む回数は最大 2 回。空の `()` の判定で、行継続の対を含めて読み直す回数は定数に収める。語一覧の文脈とシェルの種類は、定数サイズの状態として持つ。
- **NFR2 - 再帰を使わない:** `TestNoRecursion` と `TestSubstitutionSkipCallStructure` を通す。`_skip_substitution` から到達できるメソッドに、`_skip_substitution` / `_read_quoted_unit` / `parse` / `_remove_range_quotes` を含めない。
- **NFR3 - 標準ライブラリだけを使う:** `TestStaticConstraints` を通す。
- **NFR4 - version を変えない:** プラグインの version は変えない。
- **NFR5 - 構造の制約を保つ:** `find_deny(command)` の引数を変えない。`_scan` は `_judge` と `parse` を呼ぶ。`_scan` の中で `parse` の呼び出しを囲む try はちょうど 1 つで、`_Undecidable` と `Exception` を捕まえる。`Exception` の節では return も raise もしない。

## Implementation Approach

### Architecture

該当なし（既存の `codex-hook-interactive-guard.py` の読み取り処理の変更）

### Data Flow

該当なし

### API Design

該当なし。`find_deny(command)` の引数は変えない（NFR5）。

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`: バイト単位で同一に保つ（FR7）。

**External Dependencies:**
- なし（標準ライブラリだけを使う。NFR3）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1〜FR8
em-review/scripts/codex-hook-interactive-guard.py     # FR1〜FR8（上とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR9
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

デフォルトで、次の 2 つのワークフロー生成エントリを宣言に含める。

- `feature-docs/codex-guard-subst-reading-regressions/**`
- `test-docs/codex-guard-subst-reading-regressions/**`

`feature-docs/codex-guard-subst-reading-regressions/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-subst-reading-regressions/**` に含まれるもの: `test-docs/codex-guard-subst-reading-regressions/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

この 2 つのデフォルトエントリは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。

この宣言はスーパーセット（superset）の主張であり、検証時に観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。実際には生成されないパスが宣言されていても違反にはならない。

## Test Scenarios

表記: `<NL>` は改行、`\<NL>` はバックスラッシュの直後に改行が続く対を表す。`wrap_bash(s)` は `'bash -c ' + shlex.quote(s)`、`wrap_zsh(s)` は `'zsh -c ' + shlex.quote(s)` を表す。TS44〜TS59（TS46 / TS47 / TS50 / TS53 を含む）は、前のフィーチャー（codex-guard-case-reading-fixes）の CASES の行のコマンドを指す。

### Unit Tests

`tests/test_codex_hook_interactive_guard.py` の `CASES` に足し、両コピーに流す（FR9）。

- [ ] TS1（deny）: 欠陥 1 の再現 — `echo "$(for x (a # "<NL>) { :; })"; python3 -i` — FR1, FR9
- [ ] TS2（deny）: 欠陥 2 の再現（内側の文字列はタスクの再現手順 3 のとおり） — `wrap_bash('echo "$(f(\\<NL>) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')` — FR2, FR9
- [ ] TS3（deny）: 欠陥 3 の再現（zsh の coproc） — `zsh -c 'echo "$(coproc echo case x in x)"; python3 -i'` — FR3, FR4, FR9
- [ ] TS4（deny）: 欠陥 3（bash の repeat） — `bash -c 'echo "$(repeat x case y in y)"; python3 -i'` — FR3, FR5, FR9
- [ ] TS5（deny）: 語一覧のコメントの中の `)` は語一覧を閉じない — `echo "$(for x (a # )<NL>) { case x in x) printf '%s' '"';; esac; })"; python3 -i` — FR1, FR9
- [ ] TS6（silent）: コメントを含む語一覧の後の case 文の本体の、引用符の中の `python3 -i` を拒否しない — `echo "$(for x (a # '<NL>) { case x in x) echo "; python3 -i;";; esac; })"` — FR1, FR9
- [ ] TS7（deny）: 語一覧の改行の後の case は文を開かない — `echo "$(for x (a<NL>case) { :; }; echo case x in x)"; python3 -i` — FR1, FR9
- [ ] TS8（deny）: 語一覧の `(` の直後のコメント — `echo "$(for x (# c<NL>a) { case x in x) printf '%s' '"';; esac; })"; python3 -i` — FR1, FR9
- [ ] TS9（deny）: 空白を挟んだ `(` の後の対 — `wrap_bash('echo "$(f (\\<NL>) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')` — FR2, FR9
- [ ] TS10（deny）: `function name(` の後の対 — `wrap_bash('echo "$(function f(\\<NL>) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')` — FR2, FR9
- [ ] TS11（deny）: 空白と複数の対が混ざった空の `()` — `wrap_bash('echo "$(f( \\<NL>\\<NL> ) { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')` — FR2, FR9
- [ ] TS12（silent）: 対を挟んだ関数の本体の、引用符の中の `python3 -i` を拒否しない — `wrap_bash('echo "$(f(\\<NL>) { case x in x) echo "; python3 -i;";; esac; }; f)"')` — FR2, FR9
- [ ] TS13（deny）: bash の coproc NAME の後の `{` — `wrap_bash(TS47 のコマンド)`（codex-guard-case-reading-fixes の TS47） — FR3, FR4, FR9
- [ ] TS14（deny）: bash では coproc WORD の後の case が文を開く — `wrap_bash('echo "$(coproc echo case x in x) printf \'%s\' \'"\';; esac)"; python3 -i')` — FR3, FR4, FR9
- [ ] TS15（deny）: zsh の repeat word の後の `{` — `wrap_zsh(TS50 のコマンド)`（codex-guard-case-reading-fixes の TS50） — FR3, FR5, FR9
- [ ] TS16（deny）: zsh の coproc の後の `{` — `wrap_zsh(TS46 のコマンド)`（codex-guard-case-reading-fixes の TS46） — FR3, FR4, FR9
- [ ] TS17（silent）: zsh の `coproc {` の case 文の本体の、引用符の中の `python3 -i` を拒否しない — `wrap_zsh(TS53 のコマンド)`（codex-guard-case-reading-fixes の TS53） — FR3, FR4, FR9
- [ ] TS18（deny）: bash の repeat は普通のコマンドで、`{` と case は引数 — `bash -c 'echo "$(repeat 1 { case x in x)"; python3 -i'` — FR3, FR5, FR9
- [ ] TS19（deny）: 最上位（シェルが分からない場合）の coproc の形。初回は判定不能で、読み直しで deny になる — `echo "$(coproc echo case x in x)"; python3 -i` — FR6, FR9
- [ ] TS20（deny）: 最上位（シェルが分からない場合）の repeat の形。初回は判定不能で、読み直しで deny になる — `echo "$(repeat x case y in y)"; python3 -i` — FR6, FR9
- [ ] TS21（deny）: sh の `-c` 文字列はシェルが分からない場合として読み直す — `sh -c 'echo "$(coproc echo case x in x)"; python3 -i'` — FR3, FR6, FR9
- [ ] TS22（deny）: 読み直しも失敗したら、初回の確定済みのコマンド（チェックポイントまで）を判定する — `python3 -i<NL>echo "$(repeat x case y in y` — FR6, FR9
- [ ] TS23（silent）: bash と分かっている文字列は読み直さない（bash では case が文を開き、閉じない） — `bash -c 'echo "$(coproc echo case x in x)"; python3 -i'` — FR3, FR4, FR6, FR9
- [ ] TS24（deny）: 外側が bash でも、内側の zsh -c の文字列は zsh として読む（直接保持するシェルで決める） — `wrap_bash(TS3 のコマンド)`（本フィーチャーの TS3） — FR3, FR9

### Integration Tests

- [ ] 既存の CASES の行が、すべて元の判定のまま通る（AC4）。
- [ ] `TestCopies`・`TestNoRecursion`・`TestSubstitutionSkipCallStructure`・`TestNestedParseErrorContainment`・`TestStaticConstraints`・`TestSubstitutionSkipDocumentation` が通る（AC5、AC7）。
- [ ] `python3 -m unittest discover -s tests` が通る（AC8）。

### E2E Tests

**Existing E2E tests**: なし
**Run command**: 検出なし

### Edge Cases

Unit Tests の TS22（読み直しも失敗した場合）と TS23（bash と分かっている文字列は読み直さない）を参照。

### Performance Tests

`TestCaseStatementsInASubstitution` に置く（FR9）。`DEPTH` と `TIMEOUT` の中で答えを返し、deny になる（AC6、NFR1）。

- [ ] TS25（deny）: `wrap_bash('echo "$(f(' + '\\<NL>' * DEPTH + ') { case x in x) printf \'%s\' \'"\';; esac; }; f)"; python3 -i')` — NFR1, FR2
- [ ] TS26（deny）: `'echo "$(for x (a' + ' # "<NL>' * DEPTH + ') { :; })"; python3 -i'` — NFR1, FR1
- [ ] TS27（deny）: `'echo "$(coproc echo case x in x)' + ' :' * DEPTH + '"; python3 -i'`（最上位。初回は長い本体を読み切ってから判定不能になり、読み直しで deny になる） — NFR1, FR6

## Security Considerations

該当なし

## Error Handling

FR6 のとおり。読み直しも失敗したら、例外の種類にかかわらず、初回の `_Undecidable` とそれが持つ確定済みのコマンド（最後のチェックポイントまで）を使う。`_scan` の中で `parse` の呼び出しを囲む try はちょうど 1 つで、`_Undecidable` と `Exception` を捕まえる。`Exception` の節では return も raise もしない（NFR5）。

## Performance Optimization

### Performance Goals

- NFR1 のとおり。1 つの文字列を読む回数は最大 2 回。

### Optimization Strategies

該当なし

### Caching Strategy

該当なし

## Success Criteria

- [ ] AC1: 再現手順の 3 入力（TS1〜TS3）と、bash の repeat の形（TS4）が、両コピーで deny になる。
- [ ] AC2: 最上位（シェルが分からない場合）の欠陥 3 の 2 つの形（TS19 / TS20）と、sh -c の形（TS21）が、両コピーで deny になる。
- [ ] AC3: 派生の行（TS5〜TS18、TS22〜TS24）が CASES に入り、両コピーで期待どおりの判定になる。
- [ ] AC4: 既存の CASES の行が、すべて元の判定のまま通る。codex-guard-case-reading-fixes の TS44〜TS59 のうち TS47 / TS50 も含む。
- [ ] AC5: `TestCopies` により、両コピーがバイト単位で同一であることが確かめられる。
- [ ] AC6: TS25〜TS27 が、`TestCaseStatementsInASubstitution` の `DEPTH` と `TIMEOUT` の中で答えを返し、deny になる（NFR1）。
- [ ] AC7: `TestNoRecursion`・`TestSubstitutionSkipCallStructure`・`TestNestedParseErrorContainment`・`TestStaticConstraints`・`TestSubstitutionSkipDocumentation` が通る。
- [ ] AC8: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る。

## Assumptions

- A1: sh / dash / ksh の `-c` 文字列は、フックのコマンドそのものと同じく、種類を『不明』として扱う（FR6 の読み直しの対象になる）。
- A2: zsh の `for name (words)` の読み方、select、function、算術の for は、シェルの種類で変えない。シェルによって読み分けるのは、coproc の NAME と repeat だけ。
- A3: `NESTED_READ_LIMIT` は、読み直しがあっても 1 つの文字列をその長さで 1 回だけ数える。
- A4: 既存の CASES の行は、削除も判定の変更もしない（codex-guard-case-reading-fixes の TS44〜TS59 を含む）。
- A5: 前のフィーチャーの SPEC（要件 10 の『中は空白だけ』と、要件 11 の coproc / repeat の文）は履歴として残し、編集しない。本フィーチャーの SPEC で置き換える。
- A6: プラグインの version は変えない。

## Open Questions

なし

## Implementation Phases (if applicable)

該当なし

## References

- [REQUIREMENTS.md](REQUIREMENTS.md)
- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
