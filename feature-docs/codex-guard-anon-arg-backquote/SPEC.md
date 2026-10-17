# Feature: codex-guard-anon-arg-backquote

## Overview

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）で、zsh 匿名関数の引数中の `(`〜`)` 範囲に契機となるバッククォートがあるときは、`;` `&` 改行を含む場合と同じく範囲を語として読まず、`(` で群を開く読み（仮に開いた群）に戻す。これにより、範囲の終端をバッククォート内の `)` と誤認して `-c` 文字列全体が判定不能になり、本体の明示的な `python3 -i` の deny が外れる後退を直す。

要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- 匿名関数の引数中の `(`〜`)` 範囲にバッククォートがあっても、本体の明示的な `python3 -i` を deny する（TB-1/TM-2 の回帰を直す）
- 再発を `CASES` で検出できるようにする

## User Stories

### US1: 引数にバッククォートを含む匿名関数の `python3 -i` を拒否する

em-workflow / em-review の利用者として、匿名関数の引数中の `(`〜`)` 範囲にバッククォートを含むコマンドでも、本体の明示的な `python3 -i` が deny されてほしい。

**Acceptance Criteria:**
- [ ] AC-1（FR1, FR9）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'`` を両コピーに渡すと deny を出力する
- [ ] AC-2（FR2, FR9）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo "x)"`")'`` を両コピーに渡すと deny を出力する
- [ ] AC-3（FR3, FR9）: 単一引用符内・バックスラッシュの後のバッククォートだけを含む範囲の後に `< /dev/null` がある形（本体 `python3`）は何も出力しない
- [ ] AC-4（FR4, FR9）: ``function { python3; } foo(`echo x`) < /dev/null`` と ``function { python3; } foo("`echo x`") < /dev/null`` は deny を出力し、SPEC に既知の誤拒否として記載されている（本書「Known False Deny」）
- [ ] AC-5（FR6, FR9）: ``function { python3 -i; } foo(`echo x)`` と ``function { python3 -i; } foo("`echo x")`` は何も出力しない
- [ ] AC-6（FR5）: 既存の `CASES`（`foo(x) < /dev/null` の silent、`;` `&` 改行の deny、救済のケース、`$(` を含むケースを含む）が変更なしで通る

### US2: 2 つのコピーと docstring とテストを揃える

保守する開発者として、2 つのコピーがバイト単位で同一で、docstring がバッククォートの規則を述べ、テストが両コピーで通ってほしい。

**Acceptance Criteria:**
- [ ] AC-7（FR7）: 両コピーの docstring がバッククォートの規則を述べ、docstring テストが通る
- [ ] AC-8（FR8）: 2 つのコピーがバイト単位で同一であることを確かめる既存テストが通る
- [ ] AC-9（NFR1）: 性能テスト・再帰検査テストが両コピーで通る
- [ ] AC-10（FR9, NFR2）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

## Technical Requirements

### Functional Requirements

- **FR1:** 引用されていないバッククォートで群の読みに戻す。`_read_argument_parens` が読む匿名関数の引数中の `(`（語中 `foo(` と語頭 `(` の両方）について、`_scan_parens` が `(` から終端の `)` までの間で引用されていないバッククォートを読んだときは、`;` `&` 改行を含む場合と同じく範囲を語として読まず、`(` で群を開く（仮に開いた群）。``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'`` は deny になる。
- **FR2:** 二重引用符内のバッククォートも契機にする。範囲の走査が二重引用符の中で（バックスラッシュの後でない）バッククォートを読んだときも FR1 と同じく群の読みに戻す。``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo "x)"`")'`` は deny になる。
- **FR3:** 単一引用符内とバックスラッシュの後のバッククォートは契機にしない。単一引用符内のバッククォート、引用符の外のバックスラッシュの後のバッククォート、二重引用符内のバックスラッシュの後のバッククォートは契機にせず、範囲は従来どおり 1 語として読む。``function { python3; } foo("\`x\`") < /dev/null``、``function { python3; } foo(\`x\`) < /dev/null``、``function { python3; } foo('`x`') < /dev/null`` は silent のまま。
- **FR4:** 平衡したバッククォートも契機にする（既知の誤拒否）。範囲内のバッククォートが平衡しているか（`` foo(`echo x`) ``）を問わず、FR1・FR2 の契機があれば群の読みに戻す。その結果 ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(`echo x`) < /dev/null'`` は deny になる。``function { python3; } foo("`echo x`") < /dev/null`` も同じく deny になる。これは既知の誤拒否である（「Known False Deny」を参照）。
- **FR5:** 終端判定・作業上限・既存の契機と救済を変えない。`_scan_parens` の `)` の終端判定（バックスラッシュの組・単一引用符・二重引用符だけを読み飛ばす）と、`_read_argument_parens` の `paren_budget` への課金は変えない。`_skip_parens`（`$(` とプロセス置換）の戻り値と挙動は変えない。`;` `&` 改行の契機、仮に開いた群の救済の規則、群の接続の確定は既存のまま適用する。
- **FR6:** 閉じないバッククォートは判定不能。群の読みに戻った後にバッククォートが閉じない形（`` foo(`echo x) ``、`` foo("`echo x") ``）は、既存の引用符の不平衡の規則どおり判定不能（出力なし）とする。
- **FR7:** docstring の更新。両コピーのモジュール docstring 手順 4（``The matching `)` is found by ...`` の段落）、`_Parser` の docstring、`_scan_parens` の docstring（返り値の意味）、`_read_argument_parens` の docstring に、範囲内の引用されていないバッククォートと二重引用符内のバッククォートで群の読みに戻ることを書く。既存の docstring テストのマーカー（``holds an unquoted `;`, `&` or newline, the `(` opens a group``、`a backquote and a comment get no special reading`）は残すか、文言を変える場合はテストのマーカーを同じ変更で揃える。バッククォートの規則のマーカーを docstring テストに足す。
- **FR8:** 2 つのコピーを同時に直す。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR9:** 再発を検出するテスト。`tests/test_codex_hook_interactive_guard.py` の `CASES` に再現手順のコマンドを deny として追加し、FR2〜FR6 を固定するケースを足す。既存の deny ケースは消さない。表は両コピーに流す。

### Non-Functional Requirements

- **NFR1 - Performance:** 線形時間。解析全体を文字列長に対して線形時間に保つ。契機の判定は走査 1 文字あたり定数の追加作業とし、再帰は使わない（既存の性能テスト・再帰検査テストを通す）。
- **NFR2 - Security:** 既存の制約の維持。標準ライブラリのみ、ファイル・ネットワーク・子プロセスに触れない、判定はコマンド文字列だけで決まる、という既存の制約とその検査テストを保つ。
- **NFR3 - Compatibility:** version を変えない。plugin.json と marketplace.json の version は変えない。

## Known False Deny

FR4 の結果、次の形は deny になる。zsh ではこの形の本体の標準入力は /dev/null になり、実際には対話にならない。これは既知の誤拒否（fail-closed 側）として受け入れる（仮定 A6）。

```
zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(`echo x`) < /dev/null'
```

平衡したバッククォートの範囲を読み飛ばして未平衡のときだけ群の読みに戻す扱いは採らない。範囲内に契機となるバッククォートがあれば、平衡の有無を問わず群の読みに戻す。

## Implementation Approach

### Architecture

変更は `codex-hook-interactive-guard.py` の引数中の `(` の読みに閉じる。

- `_scan_parens`: `(` から終端の `)` までを走査する。終端判定（バックスラッシュの組・単一引用符・二重引用符だけを読み飛ばす）は変えず、走査中に契機となるバッククォートを読んだことを返り値で示す（FR1、FR2、FR3、FR5）。
- `_read_argument_parens`: `_scan_parens` の返り値で契機があれば、`;` `&` 改行のときと同じく範囲を語として読まず `(` で群を開く（FR1）。`paren_budget` への課金は変えない（FR5）。
- `_skip_parens`（`$(` とプロセス置換）の戻り値と挙動は変えない（FR5）。

### 契機となるバッククォートの判定

| 範囲内のバッククォートの位置 | 契機 | 根拠 |
|---|---|---|
| 引用符の外、バックスラッシュの後でない | する | FR1 |
| 二重引用符内、バックスラッシュの後でない | する | FR2 |
| 単一引用符内 | しない | FR3 |
| 引用符の外、バックスラッシュの後 | しない | FR3 |
| 二重引用符内、バックスラッシュの後 | しない | FR3 |
| 範囲内の `$(` の中、引用されていない | する | 仮定 A3 |
| 終端の `)` より後 | 対象外 | 仮定 A1 |

- 平衡の有無は問わない（FR4）。
- 群の読みに戻った後は、既存の仮の群・救済・接続の規則をそのまま適用し、新しい読みは足さない（FR5、仮定 A2）。
- 群の読みに戻った後にバッククォートが閉じない形は、既存の引用符の不平衡の規則どおり判定不能（出力なし）とする（FR6）。
- 契機を既存の `separated` に含めるか別の返り値にするかは計画に委ねる（仮定 A5）。

### Data Flow

```
tool_input.command → _read_argument_parens → _scan_parens（範囲の走査・契機の判定）
  契機なし → 範囲を 1 語として読む（従来どおり）
  契機あり（; & 改行 / バッククォート） → ( で群を開く（仮に開いた群）→ 既存の救済・接続の規則
  → permissionDecision: deny / 出力なし
```

### API Design

該当なし（フックの入出力は変えない）。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`: バイト単位で同一に保つ（FR8）
- `tests/test_codex_hook_interactive_guard.py`: `CASES`・docstring テスト・性能テスト・再帰検査テスト・バイト同一テストを両コピーに流す（FR9）

**External Dependencies:**
- なし（標準ライブラリのみ、NFR2）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # _scan_parens / _read_argument_parens と docstring
em-review/scripts/codex-hook-interactive-guard.py     # 同一内容のコピー
tests/test_codex_hook_interactive_guard.py            # CASES / docstring テスト / 性能テスト
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-anon-arg-backquote/**`
- `test-docs/codex-guard-anon-arg-backquote/**`

`feature-docs/codex-guard-anon-arg-backquote/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-anon-arg-backquote/**` covers `test-docs/codex-guard-anon-arg-backquote/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-anon-arg-backquote/` directory at all; the declared
`test-docs/codex-guard-anon-arg-backquote/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

`CASES` は `(期待する判定, ラベル, コマンド)` の形で、表は両コピーに流す。

### Unit Tests

- [ ] TS1（AC-1）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'`` - deny（再現手順）
- [ ] TS2（AC-2）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo "x)"`")'`` - deny
- [ ] TS3（AC-4）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo("`echo x`") < /dev/null'`` - deny
- [ ] TS4（AC-4）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(`echo x`) < /dev/null'`` - deny（既知の誤拒否）
- [ ] TS5（AC-3）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo("\`x\`") < /dev/null'`` - silent（二重引用符内のバックスラッシュの後）
- [ ] TS6（AC-3）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(\`x\`) < /dev/null'`` - silent（引用符の外のバックスラッシュの後）
- [ ] TS7（AC-3）: zsh が受け取る `-c` 文字列が ``setopt nonomatch nobareglobqual; function { python3; } foo('`x`') < /dev/null`` になる形 - silent（単一引用符内）
- [ ] TS8（AC-5）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x)'`` - silent（閉じないバッククォート）
- [ ] TS9（AC-5）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo x")'`` - silent（閉じないバッククォート）
- [ ] TS10（AC-6）: 既存の `CASES` は変更なしで通る
- [ ] TS11（AC-7, AC-8）: `TestGuardDocumentation` にバッククォートの規則のマーカーを足して通す。バイト同一テストを通す

### Integration Tests

- [ ] IT1（AC-10）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 平衡したバッククォートの範囲の後の入力リダイレクト（TS4）- deny（既知の誤拒否）
- [ ] 閉じないバッククォート（TS8, TS9）- silent
- [ ] エスケープまたは単一引用符内のバッククォート（TS5〜TS7）- silent のまま
- [ ] 終端の `)` より後のバッククォートは契機にならない

### Performance Tests

- [ ] TS12（AC-9）: 性能テストに ``"function { :; } x(`:` " * depth + ")" * depth`` の形を足し、既存の形とあわせて両コピーが制限時間内に応答することを確かめる

## Security Considerations

- **Input Validation:** 本体の明示的な `python3 -i` は、引数中の `(`〜`)` 範囲にバッククォートがあっても deny する（FR1、FR2、FR4）。判定の誤りは fail-closed 側に寄せ、その代償は「Known False Deny」に記す。
- **Constraints:** 標準ライブラリのみ、ファイル・ネットワーク・子プロセスに触れない、判定はコマンド文字列だけで決まる（NFR2）。
- Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF: 該当なし。

## Error Handling

- 群の読みに戻った後にバッククォートが閉じない形は、既存の引用符の不平衡の規則どおり判定不能とし、何も出力しない（FR6）。

## Performance Optimization

### Performance Goals

- 解析全体を文字列長に対して線形時間に保つ。契機の判定は走査 1 文字あたり定数の追加作業とし、再帰は使わない（NFR1）。

## Assumptions

- A1: 契機の判定対象は、`_scan_parens` が `(` から終端の `)` までに読んだ文字に限る。`)` より後のバッククォートは対象外とする。
- A2: 群の読みに戻った後は、既存の仮の群・救済・接続の規則をそのまま適用する（新しい読みは足さない）。
- A3: 範囲内の `$(` の中にある引用されていないバッククォートも契機とする（fail-closed 側）。
- A4: 閉じないバッククォートの形（TS8, TS9）の本体は、既存ケース「引数の閉じていない ( は判定不能」にならって `python3 -i` とする。zsh でも構文エラーで何も実行されないため、判定不能（silent）を期待値とする。
- A5: 契機を `separated` に含めるか別の返り値にするかは計画に委ねる。`_skip_parens` の戻り値は変えない。
- A6: ``function { python3; } foo(`echo x`) < /dev/null`` の deny は、決定済みの既知の誤拒否として受け入れる。
- A7: LICENSE ファイルは無く、ライセンスは未検出として扱う。
- A8: version は変えない（core-plugin-version-bump ルール）。

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

- 要件定義書: `feature-docs/codex-guard-anon-arg-backquote/REQUIREMENTS.md`
- 対象コード: `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`
- テスト: `tests/test_codex_hook_interactive_guard.py`
