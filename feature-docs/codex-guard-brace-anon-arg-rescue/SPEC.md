# Feature: codex-guard-brace-anon-arg-rescue

## Overview

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）で、`{` 群（匿名関数の本体と関数定義の本体を含む）の中で救済した仮の群の後の単独の素の `}` が、外側の `{` 群を閉じるようにする。これにより、`{ ...; }` や匿名関数の本体で包んだ引数の `(` による救済のすり抜けを塞ぎ、`;` の後の対話起動を deny にする。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- 引数の `(` の救済（前回の TM-1 対策）は、`{ ...; }` や匿名関数の本体で包むだけですり抜けられる。この抜け道を塞ぎ、`;` の後の対話起動を deny にする。

## User Stories

### US1: 波括弧群で包んだ救済形を deny にする
codex-hook-interactive-guard として、`{` 群や匿名関数の本体で包んだ救済形の `;` の後の対話起動を判定したい。

**Acceptance Criteria:**
- [ ] AC1: 再現1 `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'` が、両方のコピーで deny を返す。
- [ ] AC2: 再現2 `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'` が、両方のコピーで deny を返す。
- [ ] AC3: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i; }'` は silent、`zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; :; }; python3 -i'` は deny を返す。

### US2: 救済できない形と既存の判定を保つ
codex-hook-interactive-guard として、救済できない形と既存の CASES の判定を変えずにおきたい。

**Acceptance Criteria:**
- [ ] AC4: 救済できない形は silent のまま。最初の区切りが改行・`&&` の形、閉じる `}` が無い既存ケース 601、`}` が引用符の中・語の一部・リダイレクトの対象の形、サブシェル版が該当する。
- [ ] AC5: 既存の CASES の判定がすべて変わらない（ケース 604 はラベルだけ変わり、判定は silent）。`python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通る。
- [ ] AC6: 深い仮の群の列（救済できない列を含む）の後に `}` を大量に並べた入力で、両方のコピーが TestMalformedAndDeepInput の TIMEOUT 内に答えを返す。
- [ ] AC7: 2つのコピーがバイト単位で同一である。
- [ ] AC8: 「救済した区切りの後の `}` が外側の `{` 群を閉じる」趣旨の目印の文が、両方のコピーのモジュール docstring と `_Parser` の docstring にある。TestGuardDocumentation がそれを検査する。

## Technical Requirements

### Functional Requirements
- **FR1:** 救済した仮の群の後の `}` が外側の `{` 群を閉じる。単独の素の `}` を読んだときの規則。
    - 一番内側から外側へ連続して開いている仮の群の列が、救済の条件を満たすか調べる。条件は既存の `_rescue_argument_groups` と同じで、最初の直接の区切りが `;` か単独の `&` であること。内側の区切りは外側に受け継ぐ。
    - 区切りは本体の読み手が実際に読んだもの（`_Group.first_sep`）で判定し、先読み（`_scan_parens`）の結果は使わない。
    - 条件を満たし、列のすぐ外側が `{` 群（匿名関数の本体と関数定義の本体を含む）なら、`}` を読んだ時点で列の仮の群を救済する（その `(` は引数語の文字として読む）。そのうえで、その `{` 群を閉じる。
    - 後に `)` が来たら、他の場所と同じく区切りとして読む（外側にサブシェルがあればそれを閉じる）。
    - 語が残っていない `}` は、どの `{` 群も閉じる。
    - 語が残っている `}` で閉じるのは、閉じる `{` 群が匿名関数の本体の中にある（in_anon）ときだけ。このとき、残っている語を群のコマンドとして確定してから閉じる。それ以外の `{` 群では、`}` を普通の語のままにする。
    - 次の `}` は対象外で、閉じる契機にならない。引用符で囲んだもの、展開の一部、他の文字と続いて語の一部になっているもの、リダイレクトの対象。
- **FR2:** 閉じた後の読み。FR1 で閉じた `{` 群は、`; }` で閉じた `{` 群と同じに扱う。
    - 閉じた後の入力リダイレクトとパイプはその群を接続する。その接続は、中の救済した区切りの後のコマンドにも届く。
    - 閉じた群が匿名関数の本体なら、後の語は引数になる。それ以外の波括弧群の後の語は判定不能になる。
    - 関数定義の本体なら、中のコマンドは判定しない（skipped）。本体の後に区切りを挟んで続く起動は判定する。
- **FR3:** 救済できない形は従来どおり。次の場合、`}` は従来どおり普通の語として読み、判定不能のまま（出力なし）にする。
    - 列の最初の直接の区切りが改行・`&&`・`||`・`|`・`|&` の場合。
    - 区切りが無い場合。
    - 列のすぐ外側が `{` 群でない（`(` 群、またはトップレベル）場合。
    - 救済に失敗した `}` は、開いている群の状態を変えない。
- **FR4:** 再現の2形を deny、関数定義の本体は silent。
    - `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'` と `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'` を deny にする。
    - 関数定義の本体の中で救済した形（例: `f() { function { :; } foo(a; python3 -i; }`）は、skipped の規則で silent のままにする。
- **FR5:** docstring の更新と目印テスト。
    - FR1〜FR3 の規則を次の箇所に書く。モジュール docstring の手順4、`_Parser`・`_Group.provisional`・`_rescue_argument_groups` の docstring、`_finish_word` の `}` まわりのコメント。
    - 仮の群を「入力の終わりまで閉じない場合だけ救済する」とする既存の記述は、`}` の時点の救済を反映して書き直す。対象はモジュール docstring の「When a provisional group is never closed (its `)` sits in a comment, or there is none)」と、`_Group.provisional` の「may be rescued when input ends, and no other group ever is」。
    - 既存の目印の文（RESCUE_PROVISIONAL_MARKER と RESCUE_MARKERS）は残す。STALE_DOCSTRING_SENTENCES に当たる文は戻さない。
    - モジュール docstring と `_Parser` の docstring に「救済した区切りの後の `}` が外側の `{` 群を閉じる」趣旨の文を書く。その文を目印として TestGuardDocumentation に加え、両方のコピーで検査する。
- **FR6:** 回帰テスト。
    - CASES に足すもの: 再現の2形（deny）、FR1〜FR3 の境界ケース（Test Scenarios の各形）。
    - ケース 604 はラベルを skipped の趣旨に改め、判定は silent のままにする。
    - 性能テストを足す。深い仮の群の列（救済できない列を含む）と大量の `}` を組み合わせた入力で、両方のコピーが制限時間内に答えを返すことを確かめる。
- **FR7:** サブシェル版は範囲外。今回扱うのは `{` 群（匿名関数の本体と関数定義の本体を含む）だけ。`( function { :; } foo(a; python3 -i; )` の扱いは変えない。この形では `)` が仮の群を閉じ、外側の `(` が開いたまま残るので silent のまま。

### Non-Functional Requirements
- **NFR1 - Performance:** 解析は入力の長さに対して線形時間に保ち、再帰を使わない（TestNoRecursion）。`}` ごとの救済判定で、開いている群をさかのぼって走査しない。群が開いた時点で決まる値を持たせるなどして、`}` 1個あたり償却定数時間にする。各仮の群が外されるのは1回だけ。救済に失敗する `}` が続く場合も線形を保つ。
- **NFR2 - Maintainability:** em-workflow と em-review の2つのコピーを同じ変更の中で直し、バイト単位で同一に保つ（TestCopies）。
- **NFR3 - Security:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（TestStaticConstraints）。
- **NFR4 - Release:** plugin の version は変更しない。

## Implementation Approach

### Architecture

**System Architecture:**
```
zsh -c の文字列
  → _Parser（本体の読み手）
      ├── _finish_word: 単独の素の `}` の扱い（FR1 / FR3）
      ├── _rescue_argument_groups: 仮の群の救済
      └── 未閉鎖の群が残れば _Undecidable("group")
  → 判定（deny / silent）
```

**Component Diagram:**
```
_Group.provisional  : 仮の群の目印
_Group.first_sep    : 本体の読み手が実際に読んだ最初の直接の区切り
_scan_parens        : 先読み（FR1 の判定には使わない）
```

### Data Flow

```
`}` を読む → 仮の群の列の救済条件を調べる（償却定数時間）
  ├─ 条件を満たし、外側が `{` 群 → 列を救済 → `{` 群を閉じる → 閉じた後の読み（FR2）
  └─ 満たさない → `}` は普通の語、群の状態は変えない（FR3）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`: バイト単位で同一に保つ（NFR2）
- `tests/test_codex_hook_interactive_guard.py`: CASES、TestGuardDocumentation、TestMalformedAndDeepInput、TestNoRecursion、TestCopies、TestStaticConstraints

**External Dependencies:**
- なし（標準ライブラリのみ、NFR3）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py
em-review/scripts/codex-hook-interactive-guard.py
tests/test_codex_hook_interactive_guard.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-brace-anon-arg-rescue/**`
- `test-docs/codex-guard-brace-anon-arg-rescue/**`

`feature-docs/codex-guard-brace-anon-arg-rescue/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-brace-anon-arg-rescue/**` covers `test-docs/codex-guard-brace-anon-arg-rescue/{T}.tests.yaml`, the
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

各コマンドは CASES に足し、両方のコピーで期待する判定を返す。`\n` は改行を表す。

### Unit Tests
- [ ] TS1 (FR1, FR4, FR6): 再現1 `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'` - deny
- [ ] TS2 (FR1, FR4, FR6): 再現2 `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'` - deny
- [ ] TS3 (FR1, FR6): 単独の `&` が区切り `zsh -c 'setopt nobadpattern; { function { :; } foo(a & python3 -i; }'` - deny
- [ ] TS4 (FR1, FR6): コメントの中の `)` は救済を妨げない（`}` の時点で確定） `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; } #)'` - deny
- [ ] TS5 (FR1, FR6): プログラムを渡さない起動 `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; }'` - deny
- [ ] TS6 (FR2, FR6): 閉じた `{` 群の入力リダイレクトが救済後のコマンドに届く `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; } < /dev/null'` - silent
- [ ] TS7 (FR2, FR6): 閉じた `{` 群のパイプ接続が救済後のコマンドに届く `zsh -c 'setopt nobadpattern; echo x | { function { :; } foo(a; python3; }'` - silent
- [ ] TS8 (FR1, FR6): 入れ子の仮の群を内側から救済 `zsh -c 'setopt nobadpattern; { function { :; } foo(function { :; } bar(a; python3 -i; }'` - deny
- [ ] TS9 (FR1, FR6): 仮の群の中で入れ子の `{` 群が普通に閉じる `zsh -c 'setopt nobadpattern; { function { :; } foo(a; { python3 -i; }; }'` - deny
- [ ] TS10 (FR1, FR6): 語が残っている `}` で、閉じる `{` 群が in_anon なので語を確定して閉じる `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i }'` - deny
- [ ] TS11 (FR1, FR6): 匿名でない `{` 群で語が残っている `}` は普通の語 `zsh -c 'setopt nobadpattern; { function { :; } foo(a; echo }'` - silent
- [ ] TS12 (FR2, FR6): 閉じた匿名本体の後は引数、区切りの先の起動を判定 `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; :; } arg; python3 -i'` - deny
- [ ] TS13 (FR2, FR6): 匿名でない波括弧群の後の語は判定不能 `zsh -c 'setopt nobadpattern; { function { :; } foo(a; :; } arg'` - silent
- [ ] TS14 (FR2, FR4, FR6): 関数定義の本体は skipped `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i; }'` - silent
- [ ] TS15 (FR2, FR4, FR6): 関数定義の本体の後の起動は判定 `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; :; }; python3 -i'` - deny

### Integration Tests
- [ ] TS23 (FR6): 既存の CASES の判定がすべて変わらない（ケース 604 はラベルを skipped の趣旨に改め、判定は silent）。`python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通る
- [ ] TS24 (NFR2): 2つのコピーがバイト単位で同一（TestCopies）
- [ ] TS25 (FR5): 「救済した区切りの後の `}` が外側の `{` 群を閉じる」趣旨の目印の文が、両方のコピーのモジュール docstring と `_Parser` の docstring にある（TestGuardDocumentation）
- [ ] TS26 (NFR1, NFR3): 再帰を使わない（TestNoRecursion）。標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（TestStaticConstraints）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS16 (FR3, FR6): 最初の区切りが改行 `zsh -c 'setopt nobadpattern; { function { :; } foo(a\npython3 -i; }'` - silent
- [ ] TS17 (FR3, FR6): 最初の区切りが `&&` `zsh -c 'setopt nobadpattern; { function { :; } foo(a && python3 -i; }'` - silent
- [ ] TS18 (FR1, FR3, FR6): 引用符の中の `}` は閉じない `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; "}"'` - silent
- [ ] TS19 (FR1, FR3, FR6): 語の一部の `}` は閉じない `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }x'` - silent
- [ ] TS20 (FR1, FR3, FR6): リダイレクトの対象の `}` は閉じない `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; echo > }'` - silent
- [ ] TS21 (FR3, FR7, FR6): サブシェル版は範囲外で従来どおり `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'` - silent

### Performance Tests
- [ ] TS22 (NFR1, FR6): 救済できない深い列に `}` を大量に並べる。入力は `"{ function { :; } x(a && " + "function { :; } x(" * D + "; }" * M`。両方のコピーが TestMalformedAndDeepInput の TIMEOUT 内に答えを返す。素直にさかのぼる実装だと O(D·M) になる。

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** FR1〜FR3 の規則で `}` を読む
- **Data Protection:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（NFR3）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

```
救済の条件を満たさない `}` → 普通の語として読む → 未閉鎖の群が残る → _Undecidable("group") → 出力なし（silent）
```

## Performance Optimization

### Performance Goals
- 入力の長さに対して線形時間（NFR1）
- TS22 の入力で TestMalformedAndDeepInput の TIMEOUT 内に答えを返す

### Optimization Strategies
- `}` ごとの救済判定で、開いている群をさかのぼって走査しない。群が開いた時点で決まる値を持たせるなどして、`}` 1個あたり償却定数時間にする。
- 各仮の群が外されるのは1回だけ。救済に失敗する `}` が続く場合も線形を保つ。

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1〜AC8 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

### Assumptions
- `{ function { :; } foo(a; python3 -i; } )` のように末尾に余分な `)` がある形は、zsh では構文エラーで実行されない。それでも deny になりうる誤拒否を許容する。
- 匿名関数の外の通常の `{` 群で語が残っている `}`（例: `{ function { :; } foo(a; printf REACHED }`）は、既存の規則どおり普通の語のままとする。この見逃しは残す。
- サブシェル版 `( function { :; } foo(a; python3 -i; )` の見逃しは残し、別の課題とする。
- 既存の CASES の判定は変えない。変わるのはケース 604 のラベルだけ。
- plugin の version は Actions が上げるため、実装では変更しない。

## References

- 要件定義書: `feature-docs/codex-guard-brace-anon-arg-rescue/REQUIREMENTS.md`
- 残件の記録: `feature-docs/codex-guard-anon-arg-paren-comment/reviews/round1.yaml`（stable_id `db007e0ea42e58d2`）
