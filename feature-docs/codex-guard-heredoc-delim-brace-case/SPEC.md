# Feature: codex-guard-heredoc-delim-brace-case

## Overview

codex-hook-interactive-guard（em-workflow / em-review の両コピー）で、ヒアドキュメントの区切り語の位置にある `${ ... }` の中の、引用されていない `$( ... )` に case 文が含まれていても、zsh と同じ区切り語を登録する。終端行の後の `python3 -i` を deny に戻す。

## Objectives

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）で、ヒアドキュメントの区切り語の位置にある `${ ... }` の中の、引用されていない `$( ... )` に case 文が含まれていても、zsh と同じ区切り語を登録する。終端行の後の `python3 -i` を deny に戻す（feature codex-guard-heredoc-delim-brace-quote の review round 1、stable_id 5b8947f11cc2c3b8 で見つかった回帰の修正）

## Acceptance Criteria

- [ ] AC1: 再現手順のコマンド（TS1）を 2 つのコピーのどちらに渡しても deny が出る。（FR1, FR2）
- [ ] AC2: TS1 から TS9 が `CASES` にあり、`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。（FR1, FR2, FR4）
- [ ] AC3: 既存の `CASES` の行（feature codex-guard-heredoc-delim-brace-quote の `${...}` の行と、括弧の範囲の行を含む）がすべて変わらず通る。（FR3, NFR3）
- [ ] AC4: 既存の構造テスト（TestSharedQuotedUnitReader、TestSubstitutionSkipCallStructure、TestNoRecursion）を変えずに通る。（FR2, NFR2）
- [ ] AC5: 2 つのコピーがバイト単位で同一（TestCopies が通る）。（FR5）

## Technical Requirements

### Functional Requirements

- **FR1:** 区切り語の ${ ... } の中の $( ... ) を case 文対応の読みで読み飛ばす — `<<` / `<<-` の区切り語の位置にある `${ ... }` の範囲（`_remove_range_quotes` の `braced=True`）で、引用されていない `$(`（`$((` を含む）から始まる置換は `_skip_substitution` で読み飛ばす。置換の文字は、中の引用符も含めて書かれたまま区切り語に入れる。case 文のパターンの `)` で置換を閉じない。
- **FR2:** 共有リーダー経由で読み飛ばす — `_read_quoted_unit` が受け付ける開始文字に、引用されていない `$(` を加える。`$(` で始まる場合は `_skip_substitution` で読み飛ばし、元の文字をそのまま返す（dynamic は真）。読み飛ばしの終わりが `limit` を越えたとき、または `_skip_substitution` が `_Undecidable` を投げたときは `_Undecidable` にする。`_remove_range_quotes` は `braced=True` のときの `$(` だけを `_read_quoted_unit` に渡す。`parse` は引用されていない `$` を `_dollar` に渡すので、`parse` からの呼び出しは変わらない。
- **FR3:** ほかの読みは変えない — 次の読みは変えない: 括弧の範囲（`braced=False`）の中の `$(`（`_skip_parens` のまま）、区切り語の語に直接書いた `$( ... )`（`_dollar` の `_skip_parens` のまま）、区切り語でない語の `${ ... }`、`${ ... }` の中のバッククォート（ふつうの文字のまま）、引用されていない `$'` / `$"` を判定不能にする規則、区切り語の二重引用符の中の置換。
- **FR4:** 再発を検出するテスト — `tests/test_codex_hook_interactive_guard.py` の `CASES` に、Test Scenarios の各行を `(期待する判定, ラベル, コマンド)` で加える。同じ表を 2 つのコピーの両方に流す。
- **FR5:** 説明文の更新と 2 コピーの一致 — モジュールの docstring、`_remove_range_quotes`・`_read_quoted_unit`・`_skip_substitution` の docstring を、FR1 から FR3 の読みに合わせて直す（`_read_quoted_unit` の「開始文字は backslash / single quote / double quote」という前提、`_skip_substitution` の「inside double quotes」の記述を含む）。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更の中で一緒に直し、バイト単位で同一に保つ。

### Non-Functional Requirements

- **NFR1:** 線形時間 — 区切り語の範囲の読みは範囲の長さに対して線形のまま。`$( ... )` 1 つは 1 回だけ読み飛ばし、読み直さない。
- **NFR2:** 呼び出し構造 — `_skip_substitution` を呼ぶメソッドは `_read_quoted_unit` 1 つだけのまま。`_skip_substitution` から辿れるメソッドに `_skip_substitution`・`_read_quoted_unit`・`parse`・`_remove_range_quotes` を含めない。再帰・循環を作らない。既存の構造テスト（TestSharedQuotedUnitReader、TestSubstitutionSkipCallStructure、TestNoRecursion）は変えずに通る。
- **NFR3:** 既存の制約 — 標準ライブラリだけを使う、fail-open（読めない入力は出力なし）を保つ。既存の deny / silent の行は消さない。

## Assumptions

- **A1:** 読み飛ばしの経路は共有リーダー経由: `_read_quoted_unit` の開始文字に引用外の `$(` を加え、`_skip_substitution` で読み飛ばして元の文字をそのまま返す。`_remove_range_quotes` は `braced=True` の `$(` だけを渡す。既存の構造テストは変えない。
- **A2:** 区切り語の語に直接書いた `$( ... )`（`${ ... }` の外、`_dollar` が `_skip_parens` で読む）と、括弧の範囲（`braced=False`）の中の `$( ... )` は、この feature の対象に含めず読みを変えない。
- **A3:** `_skip_substitution` を呼ぶメソッドは 1 つだけで、`_skip_substitution` から `_read_quoted_unit`・`parse`・`_remove_range_quotes` に辿れない（既存テストが固定している事実）。
- **A4:** 2 つのコピーはバイト単位で同一に保つ（既存テスト TestCopies と `.claude/rules/hook-tests.md` が固定している事実）。

## Implementation Approach

### Architecture

区切り語の `${ ... }` の範囲での読みの経路（FR1, FR2）:

```
_remove_range_quotes (braced=True)
  └─ 引用されていない `$(` ── _read_quoted_unit ── _skip_substitution
                                  │
                                  └─ 元の文字をそのまま返す（dynamic は真）
                                     読み飛ばしの終わりが limit を越えた / _Undecidable → _Undecidable
```

- `_remove_range_quotes` (`braced=False`) の `$(` は `_skip_parens` のまま（FR3）。
- `parse` は引用されていない `$` を `_dollar` に渡すので、`parse` からの `_read_quoted_unit` の呼び出しは変わらない（FR2）。
- `_skip_substitution` を呼ぶメソッドは `_read_quoted_unit` 1 つだけ（NFR2）。

### Dependencies

**External Dependencies:**
- 標準ライブラリのみ（NFR3）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1, FR2, FR3, FR5
em-review/scripts/codex-hook-interactive-guard.py     # FR5（em-workflow 側とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR4（CASES に TS1〜TS9 を加える）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-heredoc-delim-brace-case/**`
- `test-docs/codex-guard-heredoc-delim-brace-case/**`

`feature-docs/codex-guard-heredoc-delim-brace-case/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-heredoc-delim-brace-case/**` covers `test-docs/codex-guard-heredoc-delim-brace-case/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-heredoc-delim-brace-case/` directory at all; the declared
`test-docs/codex-guard-heredoc-delim-brace-case/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で加え、2 つのコピーの両方に流す（FR4）。コマンドは下のコードブロックの各行を改行でつないだ文字列。

実行コマンド:

```
python3 -m unittest tests.test_codex_hook_interactive_guard
```

#### TS1（FR1, FR2, FR4）

- 期待する判定: `deny`
- ラベル: `区切り語の ${...} の中の case 文を含む $( ) を書かれたまま区切り語にし、終端行の後の起動は deny (再現手順)`
- コマンド:

```
zsh -c 'cat <<${v:-$(case x in x) echo "x";; esac)}
${v:-$(case x in x) echo "x";; esac)}
python3 -i'
```

#### TS2（FR1, FR2, FR4）

- 期待する判定: `deny`
- ラベル: `最上位の ${...} の中の case 文を含む $( ) の引用を残す`
- コマンド:

```
cat <<${v:-$(case x in x) echo "x";; esac)}
${v:-$(case x in x) echo "x";; esac)}
python3 -i
```

#### TS3（FR1, FR2, FR4）

- 期待する判定: `silent`
- ラベル: `case 文を含む $( ) の引用を除いた行では本文が閉じない`
- コマンド:

```
cat <<${v:-$(case x in x) echo "x";; esac)}
${v:-$(case x in x) echo x;; esac)}
python3 -i
${v:-$(case x in x) echo "x";; esac)}
```

#### TS4（FR1, FR2, FR4）

- 期待する判定: `deny`
- ラベル: `case 文の本体の引用の中の } で ${...} を閉じない`
- コマンド:

```
cat <<${v:-$(case x in x) echo "}";; esac)}
${v:-$(case x in x) echo "}";; esac)}
python3 -i
```

#### TS5（FR1, FR2, FR4）

- 期待する判定: `deny`
- ラベル: `先頭の ( を持つパターンの case 文を読む`
- コマンド:

```
cat <<${v:-$(case x in (x) echo "x";; esac)}
${v:-$(case x in (x) echo "x";; esac)}
python3 -i
```

#### TS6（FR1, FR2, FR4）

- 期待する判定: `deny`
- ラベル: `${...} の中の $(( )) は書かれたまま区切り語になる`
- コマンド:

```
cat <<${v:-$((1+2))}
${v:-$((1+2))}
python3 -i
```

#### TS7（FR1, FR2, FR4）

- 期待する判定: `deny`
- ラベル: `<<- は先頭タブを除いて case 文を含む $( ) を残した区切り語と比べる`
- コマンド（2 行目の先頭はタブ文字 1 つ。Python の文字列では `\t`）:

```
cat <<-${v:-$(case x in x) echo "x";; esac)}
	${v:-$(case x in x) echo "x";; esac)}
python3 -i
```

#### TS8（FR2, FR4, NFR3）

- 期待する判定: `silent`
- ラベル: `${...} の中の esac で閉じない case 文は判定不能`
- コマンド:

```
cat <<${v:-$(case x in x) echo "x";;}
python3 -i
```

#### TS9（FR2, FR4）

- 期待する判定: `deny`
- ラベル: `判定不能な case 文を含む区切り語より前の行の起動は deny`
- コマンド:

```
python3 -i
cat <<${v:-$(case x in x) :;;}
x
```

### Integration Tests

- [ ] 既存の `CASES` の行（feature codex-guard-heredoc-delim-brace-quote の `${...}` の行と、括弧の範囲の行を含む）がすべて変わらず通る（AC3）
- [ ] 既存の構造テスト（TestSharedQuotedUnitReader、TestSubstitutionSkipCallStructure、TestNoRecursion）を変えずに通る（AC4）
- [ ] TestCopies が通る（AC5）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] AC1〜AC5 を満たす
- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る

## Open Questions

なし

## References

- `.claude/rules/hook-tests.md`
- `tests/test_codex_hook_interactive_guard.py`
- feature codex-guard-heredoc-delim-brace-quote の review round 1（stable_id 5b8947f11cc2c3b8）
