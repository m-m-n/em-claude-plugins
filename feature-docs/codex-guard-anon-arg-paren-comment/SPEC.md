# Feature: codex-guard-anon-arg-paren-comment

要件定義書: `feature-docs/codex-guard-anon-arg-paren-comment/REQUIREMENTS.md`

表記: コマンド例の `<改行>` は、コマンド文字列中の改行 1 文字を表す。

## Overview

codex-hook-interactive-guard（em-workflow / em-review の両コピー）で、zsh 匿名関数の引数中の `(` から仮に開いた群が閉じないとき、群の中の最初の実際の区切りが `;` または単独の `&` なら、その `(` を引数語の文字として読み、区切りの後のコマンドを判定する（救済）。改行の形と本物の未閉鎖群は従来どおり判定不能（出力なし）に保つ。

## Objectives

- 匿名関数の引数中の `(` から仮に開いた群が閉じないとき（閉じ括弧がコメントの中にある、または閉じ括弧が無い）に、実際の区切り `;` / `&` の後の対話起動を見逃さないようにする。
- zsh 5.9 が実行しない形（改行の形）と本物の未閉鎖群は従来どおり判定不能（出力なし）に保ち、誤爆を増やさない。

## User Stories

該当なし

## Technical Requirements

### Functional Requirements

- **FR1:** ; の形の救済 — 匿名関数の引数中の `(`（`_read_argument_parens` が読む `(`。語中 `foo(` と語頭 `(` の両方）から仮に開いた群が文字列の終わりまで閉じず、その群の中で直接読んだ最初の実際の区切りが `;` のとき、その `(` を引数語の文字として読み、`;` の後のコマンドを匿名関数の後に続くコマンドとして判定する。`zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` は deny になる。
- **FR2:** & の形の救済 — FR1 と同じ条件で、最初の実際の区切りが単独の `&`（バックグラウンド）のときも同じく救済する。`zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'` は deny になる。
- **FR3:** 改行の形は判定不能のまま — 仮に開いた群の中で直接読んだ最初の実際の区切りが改行のときは救済せず、従来どおり出力なしとする。`zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>python3 -i #)'` は silent のまま。
- **FR4:** 救済の契機は ; と単独の & に限る — 救済の契機になるのは、主の読み取りが区切りとして読む `;` と単独の `&` だけとする。`&&` `||` `|` `|&`、リダイレクトの `&>` `>&`、引用符内・バックスラッシュ後の `;` `&` は契機にならず、それらが最初の区切りの群は従来どおり出力なし。
- **FR5:** 本物の未閉鎖群は判定不能のまま — 匿名関数の引数から仮に開いた群でない群（コマンド位置の `(`、`{` 群、関数定義の本体など）が閉じないときは、救済の後に残る場合も含めて従来どおり出力なし（ガードの `if self.frames: raise _Undecidable("group")` の判定を保つ）。区切りを含まない閉じない引数の `(`（`function { python3 -i; } foo(`）も出力なしのまま。
- **FR6:** 入力接続と関数定義の除外を保つ — 救済の後のコマンドにも、既存の入力接続（入力リダイレクト・パイプ・接続された群からの継承）の確定と、関数定義の本体を判定しない規則（ガードの群の接続・skipped の確定ループ）をそのまま適用する。匿名関数の頭部のパイプ・入力リダイレクトの接続は、引数を終える区切りの後のコマンドには届かない。
- **FR7:** docstring の更新 — モジュール docstring の手順 4（`` so it does when no matching `)` is found, and a group that is never closed -> no output `` の段落）、`_Parser` の docstring、`_read_argument_parens` の docstring に、救済の規則（仮に開いた群、契機は `;` と単独の `&`、改行が最初なら救済しない、本物の未閉鎖群は出力なし）を書く。既存の docstring テストのマーカー（`` holds an unquoted `;`, `&` or newline, the `(` opens a group ``、`a backquote and a comment get no special reading` など）は残すか、文言を変える場合はテストのマーカーを同じ変更で揃える。
- **FR8:** 2 つのコピーを同時に直す — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR9:** 再発を検出するテスト — `tests/test_codex_hook_interactive_guard.py` の `CASES` で、既存の silent ケース「引数の ( ) の中に ; があり閉じ括弧がコメントの中なら従来どおり判定不能」を deny に変え（ラベルも改める）、& の形の deny、改行の形の silent、FR4〜FR6 を固定するケースを足す。既存の deny ケースは消さない。表は両コピーに流す。

### Non-Functional Requirements

- **NFR1 - 線形時間:** 救済を含めて解析全体を文字列長に対して線形時間に保つ。仮に開いた未閉鎖群が深く入れ子になった入力（既存の性能テストの `unclosed ranges` の形、救済が起きる形を含む）にも既存の制限時間内に応答する。再帰は使わない（既存の再帰検査テストを通す）。
- **NFR2 - 既存の制約の維持:** 標準ライブラリのみ、ファイル・ネットワーク・子プロセスに触れない、判定はコマンド文字列だけで決まる、という既存の制約とその検査テストを保つ。
- **NFR3 - version を変えない:** plugin.json と marketplace.json の version は変えない（patch は main への push 時に Actions が上げる）。

## Acceptance Criteria

- [ ] AC-1（FR1, FR9）: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` を両コピーに渡すと deny を 1 つ出力する
- [ ] AC-2（FR2, FR9）: `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'` を両コピーに渡すと deny を出力する
- [ ] AC-3（FR3, FR9）: `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>python3 -i #)'` を両コピーに渡すと何も出力しない
- [ ] AC-4（FR4, FR9）: 最初の区切りが `&&` の形（`foo(a && python3 -i #)`）は何も出力しない
- [ ] AC-5（FR5, FR9）: コマンド位置の閉じない `(`（`(python3 -i #)`、および外側にコマンド位置の閉じない `(` がある `(function { :; } foo(a; python3 -i #)`）と、区切りの無い閉じない引数の `(`（`function { python3 -i; } foo(`）は何も出力しない
- [ ] AC-6（FR6, FR9）: 救済の後のコマンドに入力リダイレクトがあれば何も出力せず、頭部がパイプの右側でも区切りの後のプログラム無し起動は deny、関数定義の本体の中で救済されたコマンドは判定しない
- [ ] AC-7（FR7）: 両コピーのモジュール docstring・`_Parser`・`_read_argument_parens` の docstring が救済の規則を述べ、docstring テストが通る
- [ ] AC-8（FR8）: 2 つのコピーがバイト単位で同一であることを確かめる既存テストが通る
- [ ] AC-9（NFR1）: 仮に開いた未閉鎖群を深く入れ子にした入力（救済が起きる形を含む）に、両コピーが既存の制限時間内に応答し、再帰検査テストが通る
- [ ] AC-10（FR9, NFR2）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通り、既存の deny ケース（引数の ( ) の中に ; / & / 改行があり閉じている形の deny を含む）が残っている

## Implementation Approach

### Architecture

対象はガードの判定ロジックのみ。

- `_read_argument_parens`: 匿名関数の引数中の `(` を読む。ここから開いた群が「仮に開いた群」となる（FR1, FR2）。
- `_Parser`: 救済の後のコマンドにも、既存の入力接続の確定と、関数定義の本体を判定しない規則（群の接続・skipped の確定ループ）を適用する（FR6）。
- `if self.frames: raise _Undecidable("group")`: 本物の未閉鎖群の判定として保つ（FR5）。

入れ子の仮の群は内側から順に救済し、救済の後にも本物の未閉鎖群が残れば出力なしとする。実現方法（再読み取りなど）は線形時間（NFR1）を保つ範囲で計画に委ねる。

### Dependencies

**Internal Dependencies:**
- `tests/test_codex_hook_interactive_guard.py`: `CASES` の表、docstring テスト（TestGuardDocumentation）、バイト同一テスト、性能テスト、再帰検査テスト、既存の制約の検査テスト

**External Dependencies:**
- なし（標準ライブラリのみ。NFR2）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # 修正（FR1〜FR8）
em-review/scripts/codex-hook-interactive-guard.py     # 修正（em-workflow 側とバイト単位で同一。FR8）
tests/test_codex_hook_interactive_guard.py            # ケースと性能テストの追加・変更（FR9, NFR1）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-anon-arg-paren-comment/**`
- `test-docs/codex-guard-anon-arg-paren-comment/**`

`feature-docs/codex-guard-anon-arg-paren-comment/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-anon-arg-paren-comment/**` covers `test-docs/codex-guard-anon-arg-paren-comment/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-anon-arg-paren-comment/` directory at all; the declared
`test-docs/codex-guard-anon-arg-paren-comment/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

`tests/test_codex_hook_interactive_guard.py` の `CASES` に置き、両コピーに流す。

- [ ] TS1（AC-1）: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` - deny
- [ ] TS2（AC-2）: `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'` - deny
- [ ] TS3（AC-3）: `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>python3 -i #)'` - silent
- [ ] TS4（AC-1）: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i'` - deny（閉じ括弧が無い形。zsh から見るとコメント除去後の TS1 と同じ）
- [ ] TS5（AC-1）: `zsh -c 'setopt nobadpattern; function { :; } (a; python3 -i #)'` - deny（語頭の ( の形）
- [ ] TS6（AC-3）: `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>b; python3 -i #)'` - silent（最初の区切りが改行）
- [ ] TS7（AC-1）: `zsh -c 'setopt nobadpattern; function { :; } foo(a; b<改行>python3 -i #)'` - deny（最初の区切りが ; なら後の改行の先も判定する）
- [ ] TS8（AC-4）: `zsh -c 'setopt nobadpattern; function { :; } foo(a && python3 -i #)'` - silent
- [ ] TS9（AC-5）: `zsh -c '(python3 -i #)'` - silent
- [ ] TS10（AC-5）: `zsh -c 'setopt nobadpattern; (function { :; } foo(a; python3 -i #)'` - silent
- [ ] TS11（AC-5）: `zsh -c 'function { python3 -i; } foo('` - silent（既存ケース。変えない）
- [ ] TS12（AC-6）: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 < /dev/null #)'` - silent
- [ ] TS13（AC-6）: `zsh -c 'setopt nobadpattern; echo x | function { :; } foo(a; python3 #)'` - deny
- [ ] TS14（AC-6）: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i #)<改行>}'` - silent
- [ ] TS15（AC-10）: 既存の 3 ケース `foo(a; python3 -i)` / `foo(a & python3 -i)` / `foo(a<改行>python3 -i)`（閉じている形）は変えずに deny のまま
- [ ] TS17（AC-7, AC-8）: TestGuardDocumentation に救済の規則のマーカーを足して通す。バイト同一テストを通す

### Integration Tests

- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通る（AC-10）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 最初の区切りが改行で、後に `;` がある（TS6）- silent
- [ ] 最初の区切りが `;` で、後に改行がある（TS7）- deny
- [ ] 外側にコマンド位置の閉じない `(` がある（TS10）- silent
- [ ] 関数定義の本体の中で救済される（TS14）- 判定しない

### Performance Tests

- [ ] TS16（AC-9）: 性能テストに `"function { :; } x(" * depth + "; python3 -i #"` の形を足し、既存の `unclosed ranges` の形とあわせて両コピーが制限時間内に応答することを確かめる。再帰検査テストを通す

## Security Considerations

- **Input Validation:** 判定はコマンド文字列だけで決まる。標準ライブラリのみを使い、ファイル・ネットワーク・子プロセスに触れない（NFR2）。

## Error Handling

判定不能の扱いは既存の規則に従う（出力なし）。FR3・FR4・FR5 の形は出力なしのままとする。

## Assumptions

次の仮定はいずれも可逆とする。

- 救済の対象は語中 `foo(` と語頭 `(` の両方（どちらも `_read_argument_parens` が読む「匿名関数の引数から仮に開いた群」）とする。Codex の zsh 5.9 実測は語中の形で、語頭の形（TS5）は実測していない。
- 救済の契機は `;` と単独の `&` に限り、`&&` `||` `|` `|&` は契機にしない（回答の「実際に区切りになる ; / &」を単独の演算子と読んだ）。
- 改行が最初の区切りの群は、後に `;` / `&` があっても救済しない（zsh 5.9 は改行の形を number expected で実行しないため）。
- 閉じている形の既存 deny ケース `foo(a<改行>python3 -i)` は、zsh で実行されるかどうかにかかわらず変えない（既存の deny ケースは消さないルール）。
- 入れ子の仮の群は内側から順に救済し、救済の後にも本物の未閉鎖群が残れば出力なしとする。実現方法（再読み取りなど）は線形時間を保つ範囲で計画に委ねる。
- LICENSE ファイルは無い。ライセンスは未検出として扱う。
- version は変えない（core-plugin-version-bump ルール）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/codex-guard-anon-arg-paren-comment/REQUIREMENTS.md`
