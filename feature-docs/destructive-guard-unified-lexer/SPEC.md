# Feature: destructive-guard-unified-lexer

## Overview

destructive-guard.py に、引用・コメント・展開の状態を 1 回のパスで追う字句解析を入れ、これを唯一の判定元にする。`$'...'`（ANSI-C 引用）と、`${...}`・`$((...))`・`((...))`・`$[...]` の中身を bash と同じ形で読む。要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- destructive-guard.py が `$'...'`（ANSI-C 引用）と、`${...}`・`$((...))`・`((...))`・`$[...]` の中身を bash と同じ形で読む。後ろに続く破壊的コマンドを、文の区切りごと隠したり、ヒアドキュメント本文として捨てたりしないようにする（4d76e1accb9e8fed、e812ca2e1c631029 とその別形 7357c6a8618d8556、09f237155908ac2f）。
- 引用・コメント・展開の状態を 1 回のパスで追う字句解析を作り、これを唯一の判定元にする。読み取りが複数箇所に分かれている問題（7e700e9f9906edc7）を合わせて解消する。
- 上流の修正版は無い（自前のコード）。完了の定義の「修正版に追随している」には、この修正そのものを対応とする（前提 A4）。

## User Stories

該当なし

## Technical Requirements

### Functional Requirements

- **FR1:** ANSI-C 引用を bash と同じ範囲で読む。引用の外（`${...}` の中を含む）の `$'` から ANSI-C 引用を開く。中ではバックスラッシュが次の 1 文字をエスケープし、エスケープされていない `'` で閉じる。二重引用符の中の `$'` は引用を開かない。`$$` などの特殊パラメータの直後の `'` は、普通の単一引用として読む。文の区切り・コメント・ヒアドキュメント演算子の判定は、すべてこの範囲に従う。（4d76e1accb9e8fed、7357c6a8618d8556）
- **FR2:** パラメータ展開の中の `<<` を演算子にしない。`${` は、対応する `}` で閉じる展開として読む。中の `<<` はヒアドキュメント演算子として扱わず、中の `#` はコメントを開始しない。中の引用は追い、引用の中の `}` では閉じない。中の `(` は括弧の入れ子に数えない。（e812ca2e1c631029）
- **FR3:** 算術式の中の `<<` を演算子にしない。`$((...))`、`$[...]`（入れ子の `[ ]` を含む）、コマンド位置の `((...))` の中の `<<` を、ヒアドキュメント演算子として扱わない。コマンド位置には、予約語の後ろと `for ((...))` を含む。算術式の中の `;` は文の区切りに数えない。（e812ca2e1c631029、09f237155908ac2f）
- **FR4:** 展開の中の置換の検査を保つ。`${...}` と算術式の中にある `$(...)` とバッククォートは、これまでどおり置換として取り出して検査する。
- **FR5:** 閉じない文脈は開かない。`${`・`$((`・`$[`・`((`・`$'` が入力の終わりまでに閉じないときは、その文脈を開かなかったものとして後ろを読む。
- **FR6:** 引用・コメント・展開の状態を 1 つの字句解析で決める。新しい字句解析が 1 回のパスで、引用・コメント・展開の範囲を決める唯一の場所になる。対象は `$'`・`$"`・`${}`・`$(( ))`・`(( ))`・`$[ ]`・コメント・`<<<`・`$( )`・バッククォート。_OperatorContext と _blank_comments() はこれに置き換える。scan_structure() は、引用・コメント・展開の判定をこの結果から取る。shlex（_TrackingLexer）は、字句解析が文字位置を保ったまま書き換えたテキストだけを受け取り、トークン化だけを続ける。パースに失敗したときの tokens() の shlex.split(comments=True) にも元の文字列を直接渡さず、この字句解析の結果を通す。これを 7e700e9f9906edc7 の解消の条件とする。
- **FR7:** 位置追跡用の書き換えと検査用の値を分ける。shlex に渡すための書き換えは、位置の追跡だけに使う。書き換えた文字（伏字）は、検査に渡す値に残さない。Tok の is_operator / quoted / unresolved は、元の入力での由来を保つ（例: `rm -rf /tmp/safe$'\t'` の対象を未解決の変数として扱わない）。
- **FR8:** ヒアドキュメント本文を状態追跡から外し、位置を対応させる。本物のヒアドキュメントの本文の行は、引用・コメント・展開の状態追跡から外す。位置は、元の入力・本文を除いた後・置換の印を入れた後の 3 つの間で対応させる。
- **FR9:** 置換を拾う 3 つの方針を保つ。置換を拾う既存の 3 つの方針は、それぞれ区別したまま保つ。shell モード、heredoc-body モード、単一引用の中の置換も拾う広い探索（honor_single_quotes=False）の 3 つ。
- **FR10:** 読み取りの一致を確かめるテスト。repo ルートの tests/ にテストを 1 ファイル置く。字句解析と shlex・scan_structure()・tokens() の結果について、引用の範囲・文の境界・演算子の位置・Tok の由来（is_operator / quoted / unresolved）・検査用の値が一致することを確かめる。対象のコマンドは、cases.json の既存ケース全件、AC-1 と AC-7 の攻撃形、無害な対照例。
- **FR11:** 修正より前にケースを足す。.claude/rules/hook-tests.md に従い、修正より前に destructive-guard-cases.json へ `[期待する判定, ラベル, コマンド]` 形式でケースを足す。足すのは、AC-1 と AC-7 の各形（deny）と、AC-2 の形（allow）。
- **FR12:** 既存ケースを保つ。既存の 574 件と、無人実行の降格ケース 1 件の期待する判定を変えない。既存の deny / ask ケースは 1 件も消さない。round 2 の loop 1 の退行を防ぐケース（cases.json 592〜596）は、期待する判定のまま通る。

### Non-Functional Requirements

- **NFR1 - 静的解析のみ:** 判定は決定的で、同じコマンドには常に同じ判定を返す。ファイルシステムにはアクセスせず、コマンドや置換は評価しない。
- **NFR2 - 依存を増やさない:** フックもテストも、Python 標準ライブラリだけで実装する。
- **NFR3 - 性能:** 字句解析は、入力長に対して線形の計算量にする。判定は hooks.json の timeout（10 秒）に十分収まる。既存の約 60KB の性能ケースも、10 秒以内に判定を返す。
- **NFR4 - 変更範囲:** 変更するのは em-workflow/hooks/destructive-guard.py、em-workflow/hooks/tests/destructive-guard-cases.json、repo ルート tests/ に足す一致検査のテスト 1 ファイルに限る。hooks.json と version は変えない。

## Implementation Approach

### Architecture

**System Architecture:**

該当なし（UI・アプリケーション層・データベースを持たない PreToolUse フック内の変更）

**Component Diagram:**
```
新しい字句解析（1 パス。引用・コメント・展開の範囲の唯一の判定元）  ... FR6
  ├─ 置き換え対象: _OperatorContext、_blank_comments()                 ... FR6
  ├─ scan_structure(): 引用・コメント・展開の判定をこの結果から取る    ... FR6
  ├─ shlex（_TrackingLexer）: 文字位置を保って書き換えたテキストだけを
  │                         受け取り、トークン化だけを行う            ... FR6, FR7
  └─ tokens() のパース失敗時の shlex.split(comments=True):
                            字句解析の結果を通して渡す                ... FR6
```

### Data Flow

```
元の入力
  → 本物のヒアドキュメント本文の行を状態追跡から外す                   ... FR8
  → 字句解析（引用・コメント・展開の範囲を決める）                    ... FR1〜FR6
  → 位置を保った書き換え（伏字）→ _TrackingLexer → Tok               ... FR6, FR7
       Tok の is_operator / quoted / unresolved は元の入力での由来を保つ
       検査に渡す値に伏字を残さない
位置の対応: 元の入力 ⇔ 本文を除いた後 ⇔ 置換の印を入れた後            ... FR8
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- 置換を拾う既存の 3 つの方針（shell モード、heredoc-body モード、honor_single_quotes=False の広い探索）: 区別したまま保つ（FR9）

**External Dependencies:**
- Python 標準ライブラリのみ（NFR2）

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py             # 字句解析の追加と置き換え（FR1〜FR9）
└── tests/
    └── destructive-guard-cases.json # ケースの追加（FR11）、既存ケースの維持（FR12）
tests/
└── test_*.py                        # 一致検査のテスト 1 ファイル（FR10）
```

## Declared Change Set

このフィーチャーで変更するパス（NFR4、前提 A5）:

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- repo ルート `tests/` に足す一致検査のテスト 1 ファイル（`tests/test_*.py`。test/README.md の命名規則に従う）

hooks.json と version は変更集合に含めない。

create-plan では、`workflow.yaml` の各タスクの `files` から変更集合を導出する（`references/phases/create-plan-phase.md`）。

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-unified-lexer/**`
- `test-docs/destructive-guard-unified-lexer/**`

`feature-docs/destructive-guard-unified-lexer/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/destructive-guard-unified-lexer/**` covers `test-docs/destructive-guard-unified-lexer/{T}.tests.yaml`, the
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

コマンド中の `\n` は改行を表す。

### Unit Tests

- [ ] TS-1（FR1, FR2, FR3, FR11, AC-1）: AC-1 の 11 形を deny ケースとして cases.json に足す - deny
- [ ] TS-2（FR3, FR11, AC-2）: AC-2 の形を allow ケースとして足す - allow
- [ ] TS-3（FR3, FR4, FR5, FR1, FR11, AC-7）: AC-7 の 5 形を deny ケースとして足す - deny
- [ ] TS-4（FR7, FR12, AC-3）: cases.json 592〜596 が期待する判定のまま通る
- [ ] TS-5（FR6, FR7, FR8, FR9, FR10, AC-6）: tests/ の一致検査のテストを実行する。対象は cases.json の全コマンド、AC-1 / AC-7 の攻撃形、無害な対照例（`rm -rf /tmp/safe$'\t'`、`echo "${x:-a(b}"; cat <<'EOF'\ngit reset --hard HEAD\nEOF`、`echo $((1<<2)); cat <<'EOF'\nrm -rf /tmp/zz\nEOF`、`for ((i=0; i<3; i++)); do echo $i; done`、`echo "$'x'"` など）。引用の範囲・文の境界・演算子の位置・Tok の由来・検査用の値が一致し、検査用の値に伏字が残らない - pass

### Integration Tests

- [ ] TS-6（FR12, AC-4, AC-5）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` を実行する - 全件 pass

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

該当なし

### Edge Cases

- [ ] TS-8（FR1, FR2, FR3, FR5, FR8）: TS-5 の一致検査で、次の形が bash と同じ範囲で読まれることを確かめる。
    - 二重引用符の中の `$'`
    - `$"..."`
    - `$$'...'`・`$?'...'`
    - `$'...'` の中の `\\` と `\'`
    - `${#x}`・`${x#pat}`・`$#`
    - `${x:-"}"}`
    - `${x:-${y}}`
    - `$((...))` と `$( (...) )`
    - `( (cmd) )`
    - 算術式の外の `a[1] <<EOF`
    - `<<<`
    - 置換の中の本物のヒアドキュメント
    - 1 行に複数の文脈が並ぶ形と行をまたぐ形

### Performance Tests

- [ ] TS-7（NFR3）: 既存の約 60KB の性能ケース（`echo ' + $(×30000 + ' ; rm -rf <対象>`）が、10 秒の制限時間内に deny を返す

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 静的解析のみで判定する。ファイルシステムにはアクセスせず、コマンドや置換は評価しない（NFR1）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

該当なし

## Performance Optimization

### Performance Goals

- 判定は hooks.json の timeout（10 秒）に十分収まる（NFR3）。
- 既存の約 60KB の性能ケースも、10 秒以内に判定を返す（NFR3）。

### Optimization Strategies

- 字句解析は、入力長に対して線形の計算量にする（NFR3）。

### Caching Strategy

該当なし

## Success Criteria

- [ ] AC-1: 次の各形が deny になり、deny ケースとして cases.json にある。
    1. `cat $'\'' ; bash -s \' <<EOF\ngit reset --hard HEAD\nEOF`
    2. `echo $'\'' ; rm -rf /home/sakura/valuable \'`
    3. `echo $'\'' ' #' ; rm -rf /home/sakura/valuable\necho \'`
    4. `echo ${x/<<EOF/}\nrm -rf /home/sakura/valuable\nEOF`
    5. `echo ${x:-<<EOF}\nrm -rf /home/sakura/valuable\nEOF`
    6. `x=${y/<<EOF/}; ls\ngit reset --hard HEAD~3\nEOF`
    7. `echo $((1<<2))\nrm -rf /home/sakura/valuable\n2`
    8. `((x=1<<2))\nrm -rf /home/sakura/valuable\n2`
    9. `echo $[1<<2]\nrm -rf /home/sakura/valuable\n2`
    10. `if ((1<<2)); then :; fi\nrm -rf /home/sakura/valuable\n2`
    11. `echo $[a[1]<<2]\nrm -rf /home/sakura/valuable\n2`
- [ ] AC-2: `echo $((1<<2)); cat <<'EOF'\nrm -rf /tmp/zz\nEOF` が allow になり、allow ケースとして cases.json にある。
- [ ] AC-3: cases.json の 592〜596（`$$'`、`${x:-a #}`、`$${`、`rm -rf /tmp/safe$'\t'`、`"${x:-a(b}"`）が、期待する判定のまま通る。
- [ ] AC-4: 既存の 574 件と無人実行の降格ケース 1 件が、期待する判定のまま通る。既存の deny / ask ケースは 1 件も消えていない。
- [ ] AC-5: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する（各ケース 10 秒以内）。`python3 -m unittest discover -s tests` も pass する。
- [ ] AC-6: FR10 の一致検査のテストが pass する。
- [ ] AC-7: 次の各形が deny になり、deny ケースとして cases.json にある。
    1. `for ((i=0; i<3; i++)); do rm -rf /home/sakura/valuable; done`
    2. `echo $(( $(rm -rf /home/sakura/valuable) + 1 ))`
    3. `echo ${x:-$(rm -rf /home/sakura/valuable)}`
    4. `echo "$'" ; rm -rf /home/sakura/valuable`
    5. `echo ${x\nrm -rf /home/sakura/valuable`

## Assumptions

- **A1**（影響: medium、可逆）: round2.yaml で unresolved の medium 5 件（0fb4a67c477e8034、54b0115faf5bc202、80dc2417b7e6670b、9f48c2f446a190b2、548598739d198748）は、この機能の範囲外とする。
- **A2**（影響: medium、可逆）: 既存の allow ケースも、期待する判定を変えない。
- **A3**（影響: high、可逆）: bash の読みを静的に確定できない形では、字句解析は後ろのテキストを検査から外さない読みを取る。閉じない `${`・`$((`・`$[`・`$'`、`))` で閉じない `((` などが該当する。外さない読みとは、ヒアドキュメント本文として取り込まない、コメントとして消さない、文の区切りを飲み込まない、の 3 つをいう。
- **A4**（影響: low、可逆）: 完了の定義の「修正版に追随している」は、自前のコードで上流の修正版が無いため、この修正そのものを対応として SPEC に記載する。
- **A5**（影響: low、可逆）: 変更するのは em-workflow/hooks/destructive-guard.py、em-workflow/hooks/tests/destructive-guard-cases.json、repo ルート tests/ に足す一致検査のテスト 1 ファイル（test/README.md の命名規則に従う test_*.py）に限る。hooks.json と version は変えない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件は無い）

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
- フックのテストのルール: `.claude/rules/hook-tests.md`
