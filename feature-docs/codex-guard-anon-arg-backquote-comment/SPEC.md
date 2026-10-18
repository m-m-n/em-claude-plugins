# Feature: codex-guard-anon-arg-backquote-comment

## Overview

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）で、zsh 匿名関数の引数中の `(`〜`)` 範囲がバッククォートで群の読みに戻ったとき、その群が最も内側の開いた群であるあいだは、語の頭にある引用されていない `#` をコメントにせず語の文字として読む。これにより、範囲の空白の後に `#` があっても本体の明示的な `python3 -i` を deny する。codex-guard-anon-arg-backquote が持ち込んだ後退（review round1 の ab990994bd365064）を直す。

要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- zsh 匿名関数の引数中の `(`〜`)` 範囲がバッククォートで群の読みに戻り、その範囲の空白の後に `#` があっても、本体の明示的な `python3 -i` を deny する（codex-guard-anon-arg-backquote が持ち込んだ後退、review round1 の ab990994bd365064 を直す）
- 再発を `CASES` で検出できるようにする

## User Stories

### US1: 引数の範囲に空白と `#` を含む匿名関数の `python3 -i` を拒否する

em-workflow / em-review の利用者として、匿名関数の引数中の `(`〜`)` 範囲がバッククォートで群の読みに戻り、その範囲の空白の後に `#` があるコマンドでも、本体の明示的な `python3 -i` が deny されてほしい。

**Acceptance Criteria:**
- [ ] AC-1（FR1, FR2, FR6）: 再現コマンドの JSON を両コピーの標準入力に渡すと deny を出力する
- [ ] AC-2（FR2, FR7）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)<改行>python3 -i'`` が両コピーで deny になる
- [ ] AC-3（FR3, FR7）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` (a #))'`` が両コピーで deny になる
- [ ] AC-4（FR4, FR7）: ``zsh -c 'setopt nonomatch nobareglobqual nobadpattern; function { python3 -i; } foo(`case x in x) echo x;; esac`; # '"'"' ignored<改行>python3 -i'`` が両コピーで deny になる
- [ ] AC-5（FR5, NFR3）: 既存の `CASES` が変更なしで通る。対象には、`#)` を含む救済のケース（585-629 行、644 行）、バッククォートのケース（563-584 行。閉じないバッククォートの 576・577 行を含む）、群の外のコメントのケース（101・102・196・197 行）が含まれる

### US2: 2 つのコピーと docstring とテストを揃える

保守する開発者として、2 つのコピーがバイト単位で同一で、docstring が FR2〜FR4 の規則を述べ、テストが両コピーで通ってほしい。

**Acceptance Criteria:**
- [ ] AC-6（FR6）: `TestCopies.test_the_two_copies_are_byte_identical` が通る
- [ ] AC-7（FR8）: docstring テストが両コピーで通る（既存のマーカーと、FR2〜FR4 の新しいマーカー）
- [ ] AC-8（NFR1, NFR2）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

## Technical Requirements

### Functional Requirements

- **FR1:** 再現コマンドの deny。``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)'`` を両コピーに渡すと `permissionDecision: deny` を出力する。
- **FR2:** バッククォート契機の群では `#` を語の文字として読む。`_read_argument_parens` が開く仮の群のうち、`_scan_parens` が `end` を返し（対応する `)` がある）、`separated` が false で `backquoted` が true だったために開いた群を、例外の効いた群とする。例外の効いた群が最も内側の開いた群であるあいだ、語の頭にある引用されていない `#` はコメントの始まりにせず、語の文字として読む。
- **FR3:** 入れ子の群への継承。例外の効いた群の中で開いた群（`(` 群、`{` 群、仮の群）は、開いた時点で親の例外が効いていれば例外を引き継ぐ。群が閉じた後は、親の状態がそのまま効く。自分で開く条件（FR2）を満たさず、例外の効いた親からも引き継がない群では、今までどおり `#` をコメントとして読む。
- **FR4:** 直接の区切りで例外を外す。例外の効いた群が最も内側の開いた群であるあいだに、パーサ自身の `;`、`&`（単独）、`&&`、`|&`、改行を読んだら、その群の例外を外す。それ以後その群では `#` を今までどおりコメントとして読む。``zsh -c 'setopt nonomatch nobareglobqual nobadpattern; function { python3 -i; } foo(`case x in x) echo x;; esac`; # '"'"' ignored<改行>python3 -i'`` は deny になる（`;` で例外が外れて `#` 以降はコメントになり、仮の群は `;` で救済され、改行の後の `python3 -i` が判定される）。
- **FR5:** 変えないもの。`_scan_parens` の終端判定と返り値、`_read_argument_parens` の `paren_budget` への課金、`_skip_parens` と `_skip_substitution`（`$(` の中のコメントの読みを含む）は変えない。前の SPEC の FR5 が定める入力の終わりの扱い・救済の条件（`_rescue_separator`、`_rescue_argument_groups`、`_closes_after_rescue`）・接続の規則も変えない。`first_sep` の記録も変えない。群の外のコメント、`;` `&` 改行を契機に開いた仮の群、`)` が見つからずに開いた仮の群は、今までどおり `#` をコメントとして読む。閉じないバッククォートは、今までどおり判定不能（出力なし）にする。前の SPEC の仮定 A2（群の読みに新しい読みを足さない）には、FR2〜FR4 のこの 1 つの例外だけを足す。
- **FR6:** 両コピーの同時修正。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR7:** 再発を検出する CASES。`tests/test_codex_hook_interactive_guard.py` の `CASES` に deny の行を足す。対象は、再現コマンド、再現コマンドの後に改行と `python3 -i` が続く形、範囲の中に入れ子の括弧がある形、FR4 の走査がバッククォートの中の `)` で早く止まる形。表は両コピーに流す。既存の行は期待値を変えず、消さない。
- **FR8:** docstring の更新。両コピーのモジュール docstring の手順 4、`_Parser` の docstring、`_read_argument_parens` の docstring、例外の状態を持たせる `_Group` の属性の説明に、FR2〜FR4 の規則を書く。docstring テストに、この規則のマーカーを足す。既存のマーカーは残す（`a backquote and a comment get no special reading`、`BACKQUOTE_MODULE/PARSER/SCAN/READER_MARKER`、`ANONYMOUS_ARGUMENT_MARKERS`、`RESCUE_PROVISIONAL_MARKER`）。`STALE_DOCSTRING_SENTENCES` と `STALE_GROUP_SENTENCES` の文は docstring に戻さない。

### Non-Functional Requirements

- **NFR1 - Performance:** 解析全体を文字列長に対して線形時間に保つ。例外の状態は群を開くときに親から 1 回だけ決め、区切りを読むときと `#` を読むときは最も内側の群だけを見る（定数時間）。再帰は使わない。既存の性能テスト（バッククォートを含む範囲の入れ子、TS-16 の救済の形）と再帰検査テストを両コピーで通す。
- **NFR2 - Security:** 標準ライブラリのみを使い、ファイル・ネットワーク・子プロセスに触れない。判定はコマンド文字列だけで決まる。`TestStaticConstraints` を通す。既存の deny ケースを silent に変えない。
- **NFR3 - Compatibility:** 既存の `CASES` と他のテストの判定を変えない。`plugin.json` と `marketplace.json` の version は変えない。

## Implementation Approach

### Architecture

変更は `codex-hook-interactive-guard.py` の群の読みと `#` の読みに閉じる。

- `_read_argument_parens`: 仮の群を開くとき、`_scan_parens` が `end` を返し、`separated` が false で `backquoted` が true なら、その群を例外の効いた群にする（FR2）。`paren_budget` への課金は変えない（FR5）。
- 群を開く処理（`(` 群、`{` 群、仮の群）: 開いた時点で親の例外が効いていれば、例外を引き継ぐ（FR3、仮定 A2）。
- `#` の読み: 最も内側の開いた群が例外の効いた群なら、語の頭の引用されていない `#` を語の文字として読む。そうでなければ今までどおりコメントとして読む（FR2、FR3）。
- 区切りの読み: 最も内側の開いた群が例外の効いた群で、パーサ自身が `;`、単独の `&`、`&&`、`|&`、改行を読んだら、その群の例外を外す（FR4、仮定 A1、A2）。
- `_scan_parens`、`_skip_parens`、`_skip_substitution`、救済（`_rescue_separator`、`_rescue_argument_groups`、`_closes_after_rescue`）、接続の規則、`first_sep` の記録は変えない（FR5）。
- 例外の状態を `_Group` の新しい属性に持たせるか、別の形で持たせるかは計画に委ねる（仮定 A6）。

### `#` の読み

| 状況 | `#` の読み | 根拠 |
|---|---|---|
| 最も内側の開いた群が、FR2 の条件で開いた群 | 語の頭の引用されていない `#` は語の文字 | FR2 |
| 最も内側の開いた群が、例外の効いた親から引き継いだ群 | 語の頭の引用されていない `#` は語の文字 | FR3 |
| 例外の効いた群で、直接の区切り（`;`、単独の `&`、`&&`、`\|&`、改行）を読んだ後 | コメント | FR4 |
| 例外の効いた群で、`\|` または `\|\|` を読んだ後 | 語の文字（例外は外れない） | 仮定 A1 |
| 群の外 | コメント | FR5 |
| `;` `&` 改行を契機に開いた仮の群 | コメント | FR5 |
| `)` が見つからずに開いた仮の群 | コメント | FR5 |
| `$(` の中 | `_skip_substitution` の規則のまま | FR5、仮定 A5 |
| 語の途中の `#` | 語の文字（今までどおり） | Edge Cases |

- 入れ子の群の中で読んだ区切りは、外側の群の例外を変えない（仮定 A2）。
- リダイレクトの `&>` と `>&`、引用符で囲んだ区切り、バックスラッシュで打ち消した区切りは例外を外さない（仮定 A1）。

### Data Flow

```
tool_input.command → _read_argument_parens → _scan_parens（変えない）
  end あり・separated false・backquoted true → 例外の効いた仮の群を開く
    入れ子の群 → 開いた時点の親の例外を引き継ぐ
    語の頭の引用されていない # → 語の文字として読む
    直接の区切り（; & && |& 改行）→ その群の例外を外す → 以後 # はコメント
  それ以外 → 今までどおりの読み（# はコメント）
  → 既存の救済・接続の規則 → permissionDecision: deny / 出力なし
```

### API Design

該当なし（フックの入出力は変えない）。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`: バイト単位で同一に保つ（FR6）
- `tests/test_codex_hook_interactive_guard.py`: `CASES`・docstring テスト・性能テスト・再帰検査テスト・バイト同一テストを両コピーに流す（FR7、FR8、NFR1）

**External Dependencies:**
- なし（標準ライブラリのみ、NFR2）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # 群の例外の状態・# の読み・区切りの読みと docstring
em-review/scripts/codex-hook-interactive-guard.py     # 同一内容のコピー
tests/test_codex_hook_interactive_guard.py            # CASES / docstring テストのマーカー
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-anon-arg-backquote-comment/**`
- `test-docs/codex-guard-anon-arg-backquote-comment/**`

`feature-docs/codex-guard-anon-arg-backquote-comment/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-anon-arg-backquote-comment/**` covers `test-docs/codex-guard-anon-arg-backquote-comment/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-anon-arg-backquote-comment/` directory at all; the declared
`test-docs/codex-guard-anon-arg-backquote-comment/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

`CASES` は `(期待する判定, ラベル, コマンド)` の形で、表は両コピーに流す。

### Unit Tests

- [ ] TS1（AC-1）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)'`` - deny（再現コマンド）
- [ ] TS2（AC-2）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)<改行>python3 -i'`` - deny（今の実装では改行が最初の直接の区切りになり、silent になる）
- [ ] TS3（AC-3）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` (a #))'`` - deny（内側の `(` 群が例外を引き継ぐ）
- [ ] TS4（AC-4）: ``zsh -c 'setopt nonomatch nobareglobqual nobadpattern; function { python3 -i; } foo(`case x in x) echo x;; esac`; # '"'"' ignored<改行>python3 -i'`` - deny（例外を外す規則が無いと、`#` の後の `'` が閉じない引用符になり silent になる。今の実装は deny）
- [ ] TS5（AC-5）: 既存の `CASES` のすべての行 - 変更なしで通る
- [ ] TS6（AC-6, AC-7）: `TestCopies` と `TestGuardDocumentation`（新しいマーカーを足したもの）- pass

### Integration Tests

- [ ] IT1（AC-8）: `python3 -m unittest tests.test_codex_hook_interactive_guard && python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` - pass

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 区切りを契機にした群で `)` がコメントの中にある形（`foo(a; python3 -i #)`）: 今までどおりコメントとして読んで救済する（既存のケース）
- [ ] 範囲に `;` とバッククォートの両方がある形: `separated` が true なので例外は効かず、今までどおり読む
- [ ] 語の途中の `#`（`` foo(`x`#) ``）: 語が始まっているので、今もコメントではない
- [ ] 閉じないバッククォート（`` foo(`echo x) ``）: 今までどおり判定不能（silent）
- [ ] 例外の効いた群の中の `|` と `||`: FR4 の区切りに含まれないので、例外は外れない
- [ ] ``function { python3; } foo(`echo x` #) < /dev/null``: 群は `)` で閉じるが、入力リダイレクトは本体を接続しないので deny（前の SPEC の既知の誤拒否 572 行と同じ扱い）

### Performance Tests

- [ ] TS7（AC-8）: 既存の性能テスト（``"function { :; } x(`:` " * depth + ")" * depth`` と TS-16 の形）が両コピーで制限時間内に応答する

## Security Considerations

- **Input Validation:** 引数中の `(`〜`)` 範囲がバッククォートで群の読みに戻り、その範囲の空白の後に `#` があっても、本体の明示的な `python3 -i` を deny する（FR1〜FR4）。既存の deny ケースを silent に変えない（NFR2）。
- **Constraints:** 標準ライブラリのみ、ファイル・ネットワーク・子プロセスに触れない、判定はコマンド文字列だけで決まる。`TestStaticConstraints` を通す（NFR2）。
- Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF: 該当なし。

## Error Handling

- 閉じないバッククォートは、今までどおり判定不能とし、何も出力しない（FR5）。

## Performance Optimization

### Performance Goals

- 解析全体を文字列長に対して線形時間に保つ。例外の状態は群を開くときに親から 1 回だけ決め、区切りを読むときと `#` を読むときは最も内側の群だけを見る（定数時間）。再帰は使わない（NFR1）。

## Assumptions

- A1: FR4 で例外を外す区切りは、回答で挙がった `;`、単独の `&`、`&&`、`|&`、改行に限る。`|` と `||` は外さない。リダイレクトの `&>` と `>&`、引用符で囲んだ区切り、バックスラッシュで打ち消した区切りも外さない（これらは `_separator` に届かない）。
- A2: 例外を外すのは、その群が最も内側の開いた群であるあいだに読んだ区切りだけにする。入れ子の群の中で読んだ区切りは、外側の群の例外を変えない。入れ子の群が引き継ぐのは、開いた時点での親の状態とする。
- A3: 前の SPEC の仮定 A2（群の読みに新しい読みを足さない）には、FR2〜FR4 の 1 つの例外だけを足す。前の SPEC の FR5（救済の規則）は変えない。前の feature の SPEC ファイルそのものは書き換えず、この feature の SPEC で例外を述べる。
- A4: zsh では、語の途中の `(`〜`)` の中にある空白と `#` は語の一部で、コメントにならない（zsh では検証していない）。
- A5: `$(` の中の `#` は今までどおり `_skip_substitution` の規則で読み、この例外の対象にしない。
- A6: 例外の状態を `_Group` の新しい属性に持たせるか、別の形で持たせるかは計画に委ねる。どちらにしても、消したり名前を変えたりする記号は無い。
- A7: LICENSE ファイルは無く、ライセンスは未検出として扱う。
- A8: version は変えない。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] 2 つのコピーがバイト単位で同一

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/codex-guard-anon-arg-backquote-comment/REQUIREMENTS.md`
- 前の SPEC: `feature-docs/codex-guard-anon-arg-backquote/SPEC.md`
- 対象コード: `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`
- テスト: `tests/test_codex_hook_interactive_guard.py`
