# Feature: codex-guard-brace-case-group-depth

## Overview

codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）の置換の中の読み（`_Parser._skip_substitution`）で、zsh の波括弧形式の case（`case x { ... }`）の項目本体の `{ }` 群の深さを zsh の文法どおりに数える。要件の詳細は `feature-docs/codex-guard-brace-case-group-depth/REQUIREMENTS.md` を参照する。

## Objectives

- 波括弧形式の case の項目本体の `{ }` 群の深さを zsh の文法どおりに数える
- 区切りを省略した `{ : }` の後ろの起動の拒否漏れ（fail-open）をなくす
- `always` 群と複数名の `function` の定義による誤拒否の回帰をなくす

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1:** 引数の位置の単独の } をコマンド位置の } と同じに扱う。波括弧形式の case 文の項目本体のコマンド一覧そのもの（top が 8 で `braces[-1]` が None でない）で、単独で、引用もエスケープもされていない `}`（`_keyword_end(j, "}", " \t\n;&|()<>")` が一致する語の先頭）を、引数の位置で読んだときもコマンド位置の `}` と同じに扱う。深さが 1 以上なら 1 下げ、深さが 0 なら文を閉じ、文を保持する一覧をコマンド位置にする（esac と同じ）。`{` は従来どおりコマンド位置でだけ深さを上げ、引数の位置の `{` は普通の語のまま。
- **FR2:** always 群の { を数える。`{ }` 群を閉じた `}`（FR1 の引数の位置の `}` を含む。波括弧形式の文そのものを閉じた `}` は除く）の直後に、区切りを挟まず空白だけを置いて続く、単独で引用もエスケープもされていない `always`（行継続の対を除いた文字で判定）を zsh の予約語として読み、次の語をコマンド位置にする。これにより `always` の後の `{` は項目本体の深さを 1 上げる。それ以外の位置の `always` は従来どおり普通の語。
- **FR3:** 複数名の function 定義の { を数える。`function` の頭部で最初の名前を読んだ後、コマンド位置で普通の語になる語（`_read_command_word` が None を返す語）が続く場合は、それも名前として読み、頭部の状態（`HEAD_FUNCTION_NAME`）とコマンド位置を保つ。単独の `{`・`}`、予約語、頭部語、空の `()`、区切りは従来どおりに読む。これにより `function a b { :; }` の `{` はコマンド位置で読まれ、波括弧形式の項目本体では深さを 1 上げる。
- **FR4:** 匿名関数の { の後は名前を続けない。`function` の直後の単独の `{`（zsh の匿名関数。名前の位置で読み、波括弧形式の項目本体では深さを上げる既存の特例）の後の普通の語は、FR3 の追加の名前にせず、従来どおり単純コマンドの最初の語として読む。
- **FR5:** docstring とコメントを新しい読みに合わせる。`_skip_substitution` の docstring を書き換える。rule 2 の閉じ方 (c) と深さの文（`a standalone `}` read there lowers it ...`、`and so is a `}` at an argument position`）を、項目本体のコマンド一覧そのものでは単独の `}` が引数の位置でも閉じ波括弧として読まれる、という zsh の文法に合わせる。rule 5 の「`fi`, `done` or `}` at an argument position are ordinary words」に波括弧形式の項目本体の例外を書く。rule 6 の「Multi-name zsh definitions ... are not considered」を FR3 / FR4 の読みに書き換え、FR2 の `always` を書く。頭部の状態を増やす場合は rule 7 と HEAD_* 定数の前のコメントも更新する。reserved 分岐のコメント（「A `{` or a `}` read at a command position of the item body list itself」）と、引数の位置の `}` の判定を `_read_command_word` に置く場合はその docstring（「so a word at an argument position is never one of them」）も合わせる。
- **FR6:** 再発を検出するテスト。`tests/test_codex_hook_interactive_guard.py` の CASES に再現手順 2〜4 の入力と境界の行を `(期待する判定, ラベル, コマンド)` で追加し、両コピーに流す。既存の TS-16 行（「波括弧形式の case TS-16 引数の位置の } は閉じない」）とその前のコメントを新しい読みに合わせて見直す（期待する判定 deny は新しい読みでも変わらない）。`TestSubstitutionSkipDocumentation` の `BRACE_FORM_MARKERS` / `RULE_MARKERS` を FR5 の文に合わせて更新する。既存の deny / silent の行は消さない。

### Non-Functional Requirements
- **NFR1 - 線形時間:** 読みは 1 回の前向きの走査のまま線形時間に保つ。追加する状態は一覧ごとに定数サイズで、後ろの文字を見返さない。深い入れ子・長い名前の並び・多数の `}` でも時間内に終わることをテストで確かめる。
- **NFR2 - 両コピーの同一性:** `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更で一緒に直し、バイト単位で同一に保つ。
- **NFR3 - version:** plugin.json / marketplace.json の version は触らない（patch は Actions が上げる）。
- **NFR4 - テストの書き方:** テストは標準ライブラリの unittest だけで書き、フックはサブプロセスとして JSON を標準入力に渡して呼ぶ。
- **NFR5 - 変更範囲:** 変更範囲は置換の中の読み（`_skip_substitution` とその補助）に限る。置換の外のコマンドの読み（最上位の `{ : }` を閉じない既存の挙動など）は変えない。

## Implementation Approach

### Architecture

変更対象:

- `em-workflow/scripts/codex-hook-interactive-guard.py` の `_Parser._skip_substitution` とその補助（FR1〜FR5）
- `em-review/scripts/codex-hook-interactive-guard.py`（同じ変更。NFR2）
- `tests/test_codex_hook_interactive_guard.py`（FR6）

### Dependencies

**Internal Dependencies:**
- 該当なし

**External Dependencies:**
- 標準ライブラリの unittest（NFR4）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-brace-case-group-depth/**`
- `test-docs/codex-guard-brace-case-group-depth/**`

`feature-docs/codex-guard-brace-case-group-depth/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-brace-case-group-depth/**` covers `test-docs/codex-guard-brace-case-group-depth/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-brace-case-group-depth/` directory at all; the declared
`test-docs/codex-guard-brace-case-group-depth/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

CASES の行（`(期待する判定, ラベル, コマンド)`）として両コピーに流す。TS-3 / TS-4 / TS-16 / TS-17 のコマンドは Python の式で書く。

- [ ] TS-1（FR1, AC-1）: deny
  ```
  zsh -c 'echo "$(case x { x) { : };; })"; python3 -i'
  ```
- [ ] TS-2（AC-1）: deny。対照。現状も deny
  ```
  zsh -c 'echo "$(case x { x) { :; };; })"; python3 -i'
  ```
- [ ] TS-3（FR2, AC-2）: silent
  ```
  "zsh -c " + shlex.quote('echo "$(case x { x) { :; } always { :; };; y) echo \'"; python3 -i; "\';; })"')
  ```
- [ ] TS-4（FR3, AC-3）: silent
  ```
  "zsh -c " + shlex.quote('echo "$(case x { x) function a b { :; };; y) echo \'"; python3 -i; "\';; })"')
  ```
- [ ] TS-5（FR2）: deny
  ```
  echo "$(case x { x) { :; } always { :; };; })"; python3 -i
  ```
- [ ] TS-6（FR1, FR2）: deny。引数の位置の } の直後の always
  ```
  echo "$(case x { x) { : } always { : };; })"; python3 -i
  ```
- [ ] TS-7（FR3）: deny
  ```
  echo "$(case x { x) function a b { :; };; })"; python3 -i
  ```
- [ ] TS-8（FR3）: deny
  ```
  echo "$(case x { x) function a b () { :; };; })"; python3 -i
  ```
- [ ] TS-9（FR1）: deny。深さ 0 の引数の位置の } が文を閉じ、置換は ) で閉じる
  ```
  echo "$(case x { x) echo }; :)"; python3 -i
  ```
- [ ] TS-10（FR1）: deny。入れ子の群を引数の位置の } で閉じる
  ```
  echo "$(case x { x) { { : }; : };; })"; python3 -i
  ```
- [ ] TS-11（AC-4）: silent。引用した } は数えず、群が開いたままの ;; で判定不能
  ```
  echo "$(case x { x) { : "}" ;; })"; python3 -i
  ```
- [ ] TS-12（AC-4）: silent。エスケープした }
  ```
  echo "$(case x { x) { : \} ;; })"; python3 -i
  ```
- [ ] TS-13（AC-4）: silent。単独の語でない }
  ```
  echo "$(case x { x) { : a} ;; })"; python3 -i
  ```
- [ ] TS-14（FR6）: deny。既存の TS-16 行（先行 feature の行）。判定は deny のまま、ラベルを「引数の位置の } も深さ 0 では文を閉じる」趣旨に更新
  ```
  echo "$(case x { x) echo };; })"; python3 -i
  ```
- [ ] TS-15（FR4）: deny。既存行。匿名関数の特例を維持
  ```
  echo "$(case x { x) function { :; };; y) echo '"';; })"; python3 -i
  ```

### Integration Tests

- [ ] TS-18（FR5, AC-6）: docstring。両コピーの `_skip_substitution` の docstring が FR5 の文を含み、古い文（「and so is a `}` at an argument position」「Multi-name zsh definitions and function-name validity are not considered」）を含まない

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 深さ 0 の引数の位置の `}`（`x) echo }`）は文を閉じる。後に続く `;;` は外側の一覧の区切りとして読む
- [ ] 区切りの後の `always`（`{ :; }; always { :; }`）は予約語にならない
- [ ] 波括弧形式の文を閉じた `}` の後の `always` は予約語にならない
- [ ] `always` と `}` の間の行継続の対は省いて判定する
- [ ] 引用・エスケープされた `always`、単独の語でない `always`（`alwaysx`）は予約語にならない
- [ ] `function a "b" {` の引用した名前も名前として読み、`{` はコマンド位置
- [ ] `function { echo ... }` の匿名関数の `{` の後の語は名前にしない（FR4）
- [ ] 群が開いたままの項目の終端は従来どおり判定不能（TS-22 系の既存行）
- [ ] 算術コマンドの読み直し（rule 9）では追加する状態も `((` の時点の値に戻す

### Performance Tests

時間内に終わることを確かめる（NFR1）。コマンドは Python の式で、`DEPTH` は繰り返しの数。

- [ ] TS-16（NFR1）: deny
  ```
  'echo "$(case x { x) ' + '{ ' * DEPTH + ':' + ' }' * DEPTH + ';; })"; python3 -i'
  ```
- [ ] TS-17（NFR1）: deny
  ```
  'echo "$(case x { x) function' + ' a' * DEPTH + ' { :; };; })"; python3 -i'
  ```

## Security Considerations

該当なし

## Error Handling

該当なし

## Performance Optimization

### Performance Goals
- NFR1 に従う

## Assumptions

- A-1: zsh の既定（IGNORE_BRACES / IGNORE_CLOSE_BRACES が無効）では単独の `}` は引数の位置でも閉じ波括弧になる。FR1 はこの既定に合わせ、オプションの設定は見ない。
- A-2: FR1 は波括弧形式の項目本体のコマンド一覧そのものに限る。それ以外の一覧（in 形式の本体、置換・サブシェルの中、置換の外の最上位）の引数の位置の `}` は従来どおり普通の語のまま。
- A-3: FR2 と FR3 は頭部と予約語の読み（rule 5 / rule 6）の一部として、波括弧形式の項目本体に限らずすべてのコマンド一覧（p と 8）に同じく適用する。深さを数えるのは従来どおり波括弧形式の項目本体だけ。bash では `{ :; } always` も `function a b` も構文エラーなので、bash の読みを損なわない。
- A-4: FR3 で追加の名前にするのは普通の語だけ。予約語・頭部語は従来どおりコマンド位置で読む（bash の `function f case ...` の読みを保つ）。zsh で予約語が名前になる形は扱わない。
- A-5: FR2 は閉じた `}` が普通の `{ }` 群か関数本体かを区別しない（深さの数だけを持つ）。関数本体の `}` の後の `always` は zsh では引数か構文エラーで、区別しない読みを受け入れる。
- A-6: `[[ ... ]]` の中やリダイレクトの対象の位置の単独の `}` も FR1 の引数の位置として扱う。zsh ではどちらも構文エラーで、コマンドは実行されない。
- A-7: `function` / `for` / `select` / `repeat` の名前の位置の `}` は従来どおり普通の語として読む。
- A-8: 先行 feature（codex-guard-escaped-hash-brace-case-heredoc）の SPEC の TS-16 / AC-5 は書き換えず、この feature の SPEC とテストで新しい読みを定める。

## Success Criteria

- [ ] AC-1: `zsh -c 'echo "$(case x { x) { : };; })"; python3 -i'` が deny になる（再現手順 2）。`{ :; }` にした形も deny のまま。
- [ ] AC-2: `zsh -c` の本文 `echo "$(case x { x) { :; } always { :; };; y) echo '"; python3 -i; "';; })"` が無出力になる（再現手順 3）。
- [ ] AC-3: AC-2 と同じ形で項目本体に `function a b { :; }` を書いた入力が無出力になる（再現手順 4）。
- [ ] AC-4: 引用・エスケープされた `}`、単独の語でない `}`（`a}` / `}a`）、入れ子の一覧（サブシェル・置換）の中の `}`、in 形式の本体の `}` は深さを変えず、従来の判定のまま。
- [ ] AC-5: CASES に再現入力と境界の行があり、両コピーで通る。既存の行はすべて通る（TS-16 行はラベルと説明を新しい読みに合わせて更新）。
- [ ] AC-6: docstring が FR5 の内容を述べ、docstring のマーカーのテストが通る。
- [ ] AC-7: 両コピーがバイト単位で同一（`test_the_two_copies_are_byte_identical` が通る）。
- [ ] AC-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/codex-guard-brace-case-group-depth/REQUIREMENTS.md`
- 先行 feature codex-guard-escaped-hash-brace-case-heredoc の SPEC（A-8）
