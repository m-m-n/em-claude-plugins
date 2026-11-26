# Feature: dbracket-regex-settled

## Overview

`[[ ]]` の中に `=~`（正規表現）や拡張パターン（`?(` `*(` `+(` `@(` `!(`）があるだけで、チャンクが不確定と判定され、後続の notion 呼び出しが検査対象（KIND_INSPECTED）になる誤爆をなくす。
括弧の対応から閉じ括弧 `]]` を決められる形は確定と読み、決められない形だけを不確定のまま残す。
確定と読んだパターンの括弧は、`_args_json_nameref_scan()` と `_args_json_shadow_scan()` の両方で単純コマンドの区切りにしない。

## Objectives

- `[[ ]]` の中に `=~` や拡張パターンがあるだけで、チャンクが不確定と判定され、後続の notion 呼び出しが KIND_INSPECTED になる誤爆をなくす。
- 括弧の対応から閉じ括弧 `]]` を決められる形は確定と読み、決められない形だけを不確定のまま残す。
- 確定と読んだパターンの括弧は、`_args_json_nameref_scan()` と `_args_json_shadow_scan()` の両方で単純コマンドの区切りにしない。これにより `^(ab)$` のような `$` で終わる正規表現でも、フック全体の判定が allow になる。
- 既存の検知力（deny / ask ケース）は削らない。

## Technical Requirements

### Functional Requirements

- **FR1:** =~ / 拡張パターンの存在だけでは不確定にしない — `_args_json_conditional_step()` で、書かれたとおり `=~` の語（引用・エスケープなし）や、`?*+@!` のいずれかで終わる語の直後に `(` が続く拡張パターンの接頭語があっても、それだけでは文を不確定にしない。現行の `if src == "=~": return True`（destructive-guard.py:8778）と、開き文側の `evaluates = True`（8822-8823）、継続文側の `return True, True`（8791-8792）によるこの 2 形の扱いを、FR2 の閉じ括弧判定に置き換える。
- **FR2:** 閉じ括弧は括弧の深さで決める — 条件式の範囲内（開き文では opener の直後から、継続文では文頭から）で `=~` の語、または拡張パターンの接頭語を読んだ後は、引用されていない括弧の演算子トークンの深さを数える。
    - 数えるのは除外前のトークン列 `words`（`flat` は演算子を落とすため使わない）で、`((` `))` `)(` `()` のような連結トークンも括弧 1 文字ずつ数える。
    - 深さ 1 以上の `]]` は閉じ括弧にしない。深さ 0 の最初の `]]`（書かれたとおり `]]`、末尾 CR なし）が閉じ括弧。
    - 括弧がひとつも無ければ最初の `]]` で閉じ、文を不確定にしない。
    - 文の終わりで深さが 1 以上残っていれば、その文は不確定（現行どおり）。
    - 字句解析器が `|` で文を分けるため、パターン内に `|` がある形（`[[ x =~ (a|b) ]]`）は分割点で深さが残り不確定のままでよい。
    - パターンの開始（`=~` の語、または拡張パターンの接頭語）の後で、`)` の直後または `(` の直前に空白を挟まず接している `]]`（`(x)]]`、`]](x)`）は閉じ括弧にせず、その文を不確定にする（review round 1 の finding 53cbfed1094b58a6 で入った読み。destructive-guard.py 8834-8844）。
- **FR3:** 開き文と継続文に同じ規則 — FR1 / FR2 の規則を、opener を含む文と、`&&` / `||` の後の継続文（was_open 側）の両方に同じように適用する。継続文の閉じ判定（現行は `flat` のどこかに `]]` があれば閉じる、8795-8800）も、深さ 0 の最初の `]]` に改める。
- **FR4:** 確定と読んだパターンの断片をコマンド名として判定しない — `_args_json_nameref_scan()` は、FR2 で閉じたと読んだパターンの括弧（深さを数えた括弧トークン）を単純コマンドの区切り（`_args_json_command_boundary()`）として扱わない。これにより `@(x)` の `x`、`^(ab)$` の `ab` と `$`、その後ろの `]]` が独立したコマンド名として許可リストで判定されず、`[[` のコマンドの語として読まれる。条件式の範囲外の括弧、深さを数えていない括弧（`=~` / 接頭語の前のグループ化の括弧）は現行どおり区切りとして扱う。
- **FR5:** 既存の読み方を保つ — 次の扱いは変えない。
    - 引用・エスケープ・行継続で書かれた `]]` は閉じ括弧にしない。
    - 末尾 CR を落とした語は閉じ括弧にしない。
    - 条件式が開いたまま `;` か単独の `&` に達した文は不確定。
    - チャンク末尾で開いたままなら不確定。
    - 引用・エスケープされた opener は不確定。
    - 条件式内の `-eq` `-ne` `-lt` `-le` `-gt` `-ge` `-v`（`_ARGS_JSON_DOUBLE_BRACKET_WORDS`）は不確定。
    - 引用された `"=~"` や `"("`、エスケープされた `\(` は `=~` の語・括弧として数えない。
- **FR6:** ケース表と単体テスト — `em-workflow/hooks/tests/destructive-guard-cases.json` に、ラベルが `dbracket-regex-settled` で始まるケースを、先行機能と同じ形（`A=(json --mcp desktop-commander --tool start_process); ` + 形 + `; ` + `--session "$SID"` 付き notion 呼び出し）で追加する。deny は 4 要素目 `{"rule": "git-branch-force-delete"}`、allow は 3 要素。`tests/test_destructive_guard_args_json.py` に、この機能の単体テストのクラスを追加する。
    - 次のエントリを、ラベル `dbracket-regex-settled` で始まるケース表のエントリとして先行と同じ形で追加する。
        - allow（3 要素）: `[[ x =~ ^(ab)$ ]]` と `[[ a == b && true =~ ^(ab)$ ]]`
        - deny（4 要素目 `{"rule": "git-branch-force-delete"}`）: FR2 で加えた `)` に接する `]]` の形（`[[ x =~ (x)]] || true -eq 0 ]]` と、拡張パターン・継続文の同じ形）
    - 既存の `^(ab)c` の 2 エントリは残す。
- **FR7:** _args_json_shadow_scan() の項目 3 も数えた括弧を区切りにしない — `_args_json_shadow_scan()` の項目 3（`_args_json_runs_string_as_code()` に渡す単純コマンドの分割）は、`_args_json_nameref_scan()` と同じ条件式の読み（`_args_json_conditional_step()`。`&&` / `||` で分かれた文をまたいで開いているかの状態を含む）で文ごとに数えた括弧を、単純コマンドの区切りにしない。
    - 数えた括弧は、`_args_json_shadow_scan()` が自分で字句解析した文のトークンから求める（トークンはオブジェクトの同一性で照合するため、`_args_json_nameref_scan()` の結果を流用しない）。
    - 条件式の読みがその文を不確定と判定したとき、または数えた括弧が無いときは、その文を現行どおりすべての括弧で分割する。
    - `_args_json_shadow_scan()` の項目 1・2・4・5 と、項目 3 の判定内容（`_args_json_runs_string_as_code()`）は変えない。

### Non-Functional Requirements

- **NFR1 - 既存の検知力と既存テストの保持:** 既存の deny / ask ケースを消さない。既存テストはそのまま通る: TS-16 / TS-17 のラベルの件数 30（tests/test_destructive_guard_args_json.py:4233）、`dbracket-opener-arith-scan` ラベルの所属（4448-4464）。新しいケースはこの 2 つのラベル接頭語を使わない。例外は呼び出し元の制限を確かめる既存テスト `test_the_readings_are_called_only_from_the_scan`（4170-4179）だけで、NFR2 に合わせて `_args_json_conditional_step` の期待する参照元を `_args_json_nameref_scan` と `_args_json_shadow_scan` の 2 つに改める（`_args_json_fd_variable_deferred` は `_args_json_nameref_scan` だけのまま）。
- **NFR2 - 呼び出し元と責務の制限:** `_args_json_conditional_step()` と、この機能で足す補助関数（`_args_json_simple_commands()` を含む）は、`_args_json_nameref_scan()` と `_args_json_shadow_scan()` からだけ呼ぶ。`_args_json_fd_variable_deferred()` は現行どおり `_args_json_nameref_scan()` からだけ呼ぶ。これらは判定を組み立てず、理由 ID（`destructive-guard/`）も `permissionDecision` も持たない（4181-4194、4483-4488）。
- **NFR3 - 静的解析だけで動く:** `_args_json_conditional_step()` はプロセス起動・文字列の評価・ファイルやネットワークへのアクセスをしない（AST 上の禁止名 4468-4481）。静的解析だけで、コマンドを実行しない。
- **NFR4 - docstring の更新と version の据え置き:** `_args_json_conditional_step()` と `_args_json_nameref_scan()` の docstring を新しい規則に合わせる（8760-8766 の「`=~` があれば不確定」の記述など）。`_args_json_nameref_scan()` の docstring はコマンド名（echo, printf 等）を含まない（4150-4168）。plugin の version は触らない。加えて次を行う。
    - `_args_json_shadow_scan()` の docstring の項目 3 に、数えた括弧を区切りにしないことを書く。このとき既存テストが固定している語句（"Fail safe"、"Only the chunk's own text is read"、"the static-run match"、"_args_json_static_runs()"）は残す。
    - `_args_json_conditional_step()` の docstring（8785）、`_args_json_simple_commands()` の docstring（9003-9004）、8587 行のコメントにある「`_args_json_nameref_scan()` からだけ呼ぶ」の記述を、NFR2 の呼び出し元に合わせて改める。

## Acceptance Criteria

- [ ] AC-1: 括弧の無い `=~`（`[[ x =~ a ]]`）、括弧のある正規表現（`[[ x =~ ^(ab)$ ]]`。`$` で終わる形を含む）、拡張パターン（`[[ a == @(x) ]]`、`[[ a == ?(x) ]]` など 5 つの接頭語）について、`_args_json_nameref_scan()` と `_args_json_shadow_scan()` がどちらも false を返し、後続の notion 呼び出しが KIND_NOTHING、フック全体の判定が allow になる。`[[ x =~ ^(ab)$ ]]` は、ケース表・KIND_NOTHING の確認・フック全体の allow の確認のすべてに含まれる。
- [ ] AC-2: パターン内の `]]` は閉じ括弧にならない: `[[ x =~ (]]) || true -eq 0 ]]` と `[[ a == @(]]) || true -eq 0 ]]` の後の notion 呼び出しは KIND_INSPECTED、判定は deny（git-branch-force-delete）になる。`)` に空白なしで接した `]]`（`[[ x =~ (x)]] || true -eq 0 ]]`、`[[ a == @(x)]] || true -eq 0 ]]`、および継続文の同じ形）も、KIND_INSPECTED で deny（git-branch-force-delete）になる。
- [ ] AC-3: 文末で深さが残る形は不確定: `[[ x =~ (a|b) ]]`、`[[ x =~ (a ]]` の後の notion 呼び出しは KIND_INSPECTED になる。
- [ ] AC-4: 継続文にも同じ規則: `[[ a == b && true =~ ^(ab)$ ]]` は、`_args_json_nameref_scan()` と `_args_json_shadow_scan()` がどちらも false、notion 呼び出しが KIND_NOTHING、フック全体の判定が allow になる。この形は、ケース表・KIND_NOTHING の確認・フック全体の allow の確認のすべてに含まれる。`[[ a == b && true == @(]]) || true -eq 0 ]]` は deny になる。
- [ ] AC-5: 既存の読み方は変わらない: `[[ x == =~ ]]` と `[[ a =~ "(" ]]` は allow、`=~` を行継続で書いた形は不確定のまま、既存の CONDITIONAL_DENY / CONDITIONAL_ALLOW / dbracket-opener-arith-scan の各形は従来の判定のまま。
- [ ] AC-6: ケース表に `dbracket-regex-settled` ラベルの追加ケースがあり（`$` で終わる 2 つの形と、`)` に接する `]]` の形を含む）、コマンド文字列が他のケースと重複しない。`python3 em-workflow/hooks/tests/run-destructive-guard.py`、`python3 -m unittest tests.test_destructive_guard_args_json`、`python3 -m unittest discover -s tests` がすべて通る。
- [ ] AC-7: 呼び出し元と責務: `_args_json_conditional_step()` と `_args_json_simple_commands()`（およびこの機能で足す補助関数）の参照元は `_args_json_nameref_scan()` と `_args_json_shadow_scan()` だけで、`_args_json_fd_variable_deferred()` の参照元は `_args_json_nameref_scan()` だけ。どの関数のソースにも `destructive-guard/`、`permissionDecision`、禁止名（NFR3）が無い。docstring は NFR4 のとおりになっている。
- [ ] AC-8: 数えた括弧の外の区切りは変わらない: 条件式の読みが不確定と判定した文、または数えた括弧が無い文では、`_args_json_shadow_scan()` の項目 3 が現行どおりすべての括弧で分割する。例: `[[ ( $y == b ) ]]`（パターン開始より前のグループ化の括弧）と `[[ x =~ (a) ]] && ( eval x )`（閉じ括弧より後の括弧）では、`_args_json_shadow_scan()` が true のまま。

## Assumptions

いずれも後から変更できる前提として置く。

- A1: 字句解析器は `@(x)` を `@` `(` `x` `)` に、`^(ab)$` を `^` `(` `ab` `)` `$` に分ける（`_args_json_conditional_step()` の接頭語判定が語の span の直後の `(` を見ていることから）。
- A2: `=~` の語の後、または接頭語の後で `)` が深さを 0 未満にする形（`[[ ( x =~ a ) ]]` のようにグループ化の括弧の中に `=~` がある形）は、その文を不確定にする。現行もこの形は不確定なので、判定は変わらない。
- A3: 行継続をまたいで書いた `=~`、および接頭語と `(` の間に行継続がある拡張パターンは、現行どおり不確定のままにする（緩めない）。
- A4: `=~` がオペランド位置にあっても（`[[ x == =~ ... ]]`）深さを数え始める。括弧が無ければ最初の `]]` で閉じるので `[[ x == =~ ]]` は確定になり、括弧がある場合は数えすぎの側（不確定寄り）に倒れる。
- A5: パターン内の `-eq` などの語（`_ARGS_JSON_DOUBLE_BRACKET_WORDS`）は、パターンの一部であっても現行どおり不確定とする。
- A6: 継続文の先頭語は現行どおりコマンド名として許可リストで判定する（`[[ a == b && c == d ]]` の `c` は不確定）。FR4 が変えるのはパターンの括弧による区切りだけ。
- A7: 確定と読んだパターンの括弧の中の語（例: `[[ a == @(eval) ]]` の `eval`）は、`_args_json_shadow_scan()` の項目 3 でもコマンド名として読まない。これは FR4 で `_args_json_nameref_scan()` がすでにそう読んでいることと揃えるためで、Bash もその語をパターンとして扱う。
- A8: `_args_json_shadow_scan()` の他の項目（1・2・4・5）と、`_args_json_notion_lifted()` によるキャッシュは変えない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
_args_json_nameref_scan()
  ├─ _args_json_conditional_step()   … 条件式の開閉と不確定の判定（FR1-FR3, FR5）
  │    └─ この機能で足す補助関数      … 括弧の深さによる閉じ括弧判定（FR2）
  ├─ _args_json_fd_variable_deferred()
  └─ _args_json_command_boundary()  … 単純コマンドの区切り（FR4 で、深さを数えた括弧を除く）

_args_json_shadow_scan()
  ├─ 項目 1・2・4・5                  … 変えない（A8）
  └─ 項目 3: 単純コマンドの分割（_args_json_simple_commands() など）
       ├─ _args_json_conditional_step() … 文ごとに数えた括弧を求める（FR7）
       └─ _args_json_runs_string_as_code() … 判定内容は変えない（FR7）
```

- `_args_json_conditional_step()` と、この機能で足す補助関数（`_args_json_simple_commands()` を含む）は `_args_json_nameref_scan()` と `_args_json_shadow_scan()` からだけ呼ぶ。`_args_json_fd_variable_deferred()` は `_args_json_nameref_scan()` からだけ呼ぶ（NFR2）。
- 判定（`permissionDecision`）と理由 ID は組み立てない（NFR2）。

### Data Flow

```
チャンクのトークン列 words
  → _args_json_conditional_step()
      開き文: opener の直後から / 継続文: 文頭から
      `=~` の語・拡張パターンの接頭語を読んだ後、引用されていない括弧の深さを数える
      `)` / `(` に空白なしで接した `]]` → 不確定
      深さ 0 の最初の `]]` → 閉じる（確定）
      文末で深さ 1 以上 → 不確定
  → _args_json_nameref_scan()
      深さを数えた括弧は単純コマンドの区切りにしない
      不確定なら後続の notion 呼び出しは KIND_INSPECTED、確定なら KIND_NOTHING
  → _args_json_shadow_scan() 項目 3
      自分で字句解析した文のトークンから、同じ条件式の読みで数えた括弧を求める
      数えた括弧は単純コマンドの区切りにしない
      不確定の文・数えた括弧が無い文は、現行どおりすべての括弧で分割する
```

### Edge Cases

- `(x)]]` / `]](x)`: Bash は 1 語のパターンとして読むので閉じ括弧にせず、不確定にする（FR2 に追加した項目）。これまでケース表にも単体テストにも、この形を確かめるものが無かった。
- 条件式の読みが不確定と判定した文では、`_args_json_shadow_scan()` は数えた括弧を使わず、すべての括弧で分割する（FR7、フェイルセーフ）。
- `_args_json_shadow_scan()` は `_lex_layout(marked, True)` で、`_args_json_nameref_scan()` は `lex_segments()` で、それぞれ別に字句解析する。トークンのオブジェクトは 2 つの走査で別物になるため、数えた括弧は走査ごとに求める（FR7）。
- `[[ x =~ (a) ]] && ( eval x )`: 閉じ括弧より後の括弧は区切りのままにし、`eval` を検出する（AC-8）。

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: `_args_json_nameref_scan()`、`_args_json_shadow_scan()`、`_args_json_conditional_step()`、`_args_json_simple_commands()`、`_args_json_runs_string_as_code()`、`_args_json_fd_variable_deferred()`、`_args_json_command_boundary()`、`_ARGS_JSON_DOUBLE_BRACKET_WORDS`
- `em-workflow/hooks/tests/destructive-guard-cases.json`: ケース表（FR6）
- `tests/test_destructive_guard_args_json.py`: 単体テスト（FR6、NFR1-NFR4）

**External Dependencies:**
- なし

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/dbracket-regex-settled/**`
- `test-docs/dbracket-regex-settled/**`

`feature-docs/dbracket-regex-settled/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/dbracket-regex-settled/**` covers `test-docs/dbracket-regex-settled/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/dbracket-regex-settled/` directory at all; the declared
`test-docs/dbracket-regex-settled/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: `=~` / 拡張パターンの形ごとに、2 つの走査の戻り値・notion の kind・フックの判定を確かめる - AC-1 のとおり、`$` で終わる形を含めて両方の走査が false、KIND_NOTHING、allow になる（FR1, FR2, FR4, FR7）
- [ ] TS-2: パターン内の `]]` と `)` に接した `]]` の後に `|| true -eq 0 ]]` を置き、閉じたと誤読すると allow になる形が deny になることを確かめる - AC-2 のとおり KIND_INSPECTED、deny（git-branch-force-delete）になる（FR2）
- [ ] TS-3: `|` を含む正規表現と閉じない括弧で不確定になることを確かめる - AC-3 のとおり KIND_INSPECTED になる（FR2）
- [ ] TS-4: 継続文で同じ規則が働くことを確かめる - AC-4 のとおり、`$` で終わる確定の形は両方の走査が false・KIND_NOTHING・allow、パターン内に `]]` がある形は deny になる（FR3, FR7）
- [ ] TS-5: 引用・行継続・オペランド位置の `=~` と既存表の形が回帰しないことを確かめる - AC-5 のとおり従来の判定のままになる（FR5）
- [ ] TS-6: ケース表の所属と一意性、呼び出し元の制限、禁止名をテストで固定する - AC-6、AC-7 と NFR1-NFR3 を満たす（FR6, NFR1, NFR2, NFR3）
- [ ] TS-7: docstring の規約をテストで固定する - `_args_json_conditional_step()`、`_args_json_nameref_scan()`、`_args_json_shadow_scan()` の docstring が NFR4 のとおりで、既存テストが固定している語句が残る（NFR4）
- [ ] TS-8: `_args_json_shadow_scan()` の項目 3 が数えた括弧を共有することと、数えた括弧の外の区切りが変わらないことを確かめる - `$` で終わる 2 つの形で false、AC-8 の形で true になる（FR7）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

- **Input Validation:** 判定はコマンド文字列の静的解析だけで行い、コマンドを実行しない（NFR3）。
- **Data Protection:** `_args_json_conditional_step()` はプロセス起動・文字列の評価・ファイルやネットワークへのアクセスをしない（NFR3）。
- 既存の deny / ask ケースを消さない（NFR1）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` が通る
- [ ] `python3 -m unittest tests.test_destructive_guard_args_json` が通る
- [ ] `python3 -m unittest discover -s tests` が通る
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（すべての要件が resolved）

## References

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `tests/test_destructive_guard_args_json.py`
