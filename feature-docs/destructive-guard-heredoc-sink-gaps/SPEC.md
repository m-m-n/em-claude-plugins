# Feature: destructive-guard-heredoc-sink-gaps

## Overview

`destructive-guard.py` が、シェルシンクに渡るヒアドキュメント本文の破壊的コマンドと、ヒアドキュメントと誤認されて隠れていた実コマンド行を ask / deny にする。単一引用符内に `$(` を大量に含む大きな入力でも、hooks.json の timeout（10 秒）内に判定を返す。要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- `destructive-guard.py` が、シェルシンクに渡るヒアドキュメント本文の破壊的コマンドを ask / deny にする。ヒアドキュメントと誤認されて隠れていた実コマンド行も同じく ask / deny にする。round2 で deferred にした critical 1 件・high 4 件の検知漏れを塞ぐ。
- 単一引用符内に `$(` を大量に含む大きな入力でも、hooks.json の timeout（10 秒）内に判定を返す。

## User Stories

該当なし。受け入れ基準は REQUIREMENTS.md 11.1（AC-1〜AC-9）を参照する。

## Technical Requirements

### Functional Requirements
- **FR1:** ホスト文の特定を lex_segments() の文の区切りに合わせる — ヒアドキュメントのホスト文（宛先を判定する文）は、`lex_segments()` と同じ区切りで特定する。`2>&1`・`>&2`・`&>`・`&>>`・`>|` はリダイレクトであり、文の区切りに数えない。`\;`・`\&`・行継続（`\` + 改行）はエスケープであり、これも区切りに数えない。（cdb8382d4bbb0b1d）
- **FR2:** ホスト文が確定できないときは判定不能にする — ホスト文として選んだ文に、そのヒアドキュメント自身の `<<` / `<<-` 演算子が無いことがある。その場合は宛先を判定不能にし、既存のフォールバックに回す。フォールバックは、チャンクに `SHELL_SINK` が現れたら本文を再走査する。data としては確定させない。（cdb8382d4bbb0b1d、73a1d7b31734dd22）
- **FR3:** エスケープされた引用符を引用の開始として扱わない — `scan_structure()` は、バックスラッシュでエスケープされた `'` と `"` を引用の開始として扱わない。`case` / `esac` を見分けるための語の読み取りでも同じにする（例: `echo it\'s`、`echo a\"b`）。（73a1d7b31734dd22）
- **FR4:** 単一引用符内 `$(` の対応探索を線形にする — `honor_single_quotes=False` の走査では、単一引用符内の `$(` に対応する `)` を探す。この探索を入力長に対して線形の計算量にする。見つける範囲は現行と変えない。対応が取れるのは、引用の終わりより前で釣り合ったときだけとする。（26ab9a3d83649eff）
- **FR5:** 偽のヒアドキュメント演算子は本文を取り込まない — 引用符の中やコメントの中にある `<<WORD` は、ヒアドキュメントの演算子として扱わない。置換の中にある本物の演算子（例: `"$(cat <<'EOF' … EOF)"`）は除く。偽の演算子は後続の行を本文として取り込まない。後続の行は元の位置に残し、実際の構文どおりに字句解析する。引用の続きであれば引用として、そうでなければコマンドとして読む。引用とコメントの判定は行をまたいで追跡する。本物のヒアドキュメントの本文の行は、この追跡の対象から外す。（18b99bd71e74c8dc）
- **FR6:** 読み飛ばした語に sink がある文は data にしない — コマンド語より前で読み飛ばした語のどれかに `SHELL_SINK` が一致したら、ホストのコマンド語を data と判定せず、判定不能にする。読み飛ばした語とは、`VAR=value` の代入、ラッパーのオプションとその値、git / gh のグローバルオプションの値をいう。一致の判定には、引用符を除去した後の一致も含める。`env` が `-S` または `--split-string` を持つ文も判定不能にする。つづり方（分けて書く、続けて書く、`=` 付き）は問わない。`GIT_EDITOR=bash git commit -e -F -` と `git -c core.editor=sh commit -e -F -` もこの要件で扱う。（511cd470522973d8）
- **FR7:** コマンド名を差し替える構文があれば、コマンド全体の data 判定を判定不能にする — コマンド名の実体を差し替える構文が、hook に渡されたコマンド文字列の中に 1 つでもあれば、そのコマンドの中のヒアドキュメントの data 判定をすべて判定不能にする。対象の構文は、関数定義（`NAME()` と `function NAME`。本体が `( )` のものも含む）、コマンド位置の `alias`・`hash`・`enable`、PATH への代入（コマンドの前に置く代入、単独の代入、`export`）。判定不能になった本文は、既存のフォールバックで扱う。（b8fd289ca7750a04）
- **FR8:** 修正より前にケースを足す — `.claude/rules/hook-tests.md` に従い、修正より前に `destructive-guard-cases.json` へケースを `[期待する判定, ラベル, コマンド]` 形式で足す。足すのは、6 件それぞれの再現形（deny）と、FR1 の逆向きの誤検知（allow）と、FR5 の引用の続きの形（allow）。
- **FR9:** 既存ケースを保つ — 既存の deny / ask ケースは 1 件も削除せず、期待する判定も変えない。既存の allow ケースも期待する判定を変えない。
- **FR10:** テストランナーに制限時間を入れる — `run-destructive-guard.py` は各ケース（無人実行の降格ケースも含む）の実行に、hooks.json の `destructive-guard.py` と同じ 10 秒の制限時間を設ける。制限時間を超えたケースは FAIL として数え、ランナー自体は異常終了させずに残りのケースを続ける。cases.json には約 60KB の再現入力（`echo ' + $(×30000 + ' ; rm -rf <対象>`）を deny ケースとして足す。（26ab9a3d83649eff）

### Non-Functional Requirements
- **NFR1 - 静的解析のみ:** 判定は決定的にし、同じコマンドには常に同じ判定を返す。ファイルシステムにはアクセスしない。コマンドや置換は評価しない。
- **NFR2 - 依存を増やさない:** Python 標準ライブラリだけで実装する。
- **NFR3 - 性能:** 判定は hooks.json の timeout（10 秒）に十分収まる。FR1〜FR7 で追加・変更する処理は、どれも入力長に対して線形の計算量にする。
- **NFR4 - 変更範囲:** 変更するのは `em-workflow/hooks/destructive-guard.py`、`em-workflow/hooks/tests/destructive-guard-cases.json`、`em-workflow/hooks/tests/run-destructive-guard.py` の 3 ファイルに限る。hooks.json と version は変えない。

## Implementation Approach

### Architecture

**System Architecture:**

該当なし（既存の PreToolUse フック `destructive-guard.py` の修正）。

**Component Diagram:**
```
em-workflow/hooks/destructive-guard.py
  - ホスト文の特定            : FR1, FR2（lex_segments() と同じ区切り）
  - scan_structure()          : FR3, FR5
  - honor_single_quotes=False の走査 : FR4
  - 読み飛ばした語の sink 照合 : FR6
  - コマンド名の差し替え構文の検出 : FR7
  - 既存のフォールバック（チャンクに SHELL_SINK が現れたら本文を再走査）: FR2, FR6, FR7 の判定不能の受け先

em-workflow/hooks/tests/run-destructive-guard.py
  - ケースごとの 10 秒の制限時間 : FR10

em-workflow/hooks/tests/destructive-guard-cases.json
  - 追加ケース : FR8, FR10
  - 既存ケース : FR9
```

### Data Flow

```
cases.json のケース → run-destructive-guard.py（ケースごとに 10 秒の制限時間）→ destructive-guard.py → 判定（allow / ask / deny）
                    ← PASS / FAIL（制限時間超過は FAIL）                       ←
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `lex_segments()`: FR1 のホスト文の特定は、これと同じ文の区切りを使う。
- 既存のフォールバック: FR2・FR6・FR7 で判定不能になった本文を扱う。
- `.claude/rules/hook-tests.md`: FR8 のケース追加の手順。

**External Dependencies:**
- Python 標準ライブラリのみ（NFR2）。

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py
└── tests/
    ├── destructive-guard-cases.json
    └── run-destructive-guard.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-heredoc-sink-gaps/**`
- `test-docs/destructive-guard-heredoc-sink-gaps/**`

`feature-docs/destructive-guard-heredoc-sink-gaps/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/destructive-guard-heredoc-sink-gaps/**` covers `test-docs/destructive-guard-heredoc-sink-gaps/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/destructive-guard-heredoc-sink-gaps/` directory at all; the declared
`test-docs/destructive-guard-heredoc-sink-gaps/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

各ケースのコマンド文字列は REQUIREMENTS.md 11.1 と 12.1 に記載する。ケースは `destructive-guard-cases.json` に `[期待する判定, ラベル, コマンド]` 形式で足す。

### Unit Tests
- [ ] TS-1（FR1、FR2、FR8 / AC-1）: AC-1 の 11 形を、それぞれ deny ケースとして cases.json に足す - deny
- [ ] TS-2（FR1、FR8 / AC-2）: AC-2 の形を allow ケースとして足す - allow
- [ ] TS-3（FR2、FR3、FR8 / AC-3）: AC-3 の 3 形を deny ケースとして足す - deny
- [ ] TS-4（FR4、FR10、NFR3 / AC-4）: `echo ' + $(×30000 + ' ; rm -rf <対象>` を deny ケースとして足す - deny、10 秒の制限時間内に判定を返す
- [ ] TS-5（FR5、FR8 / AC-5）: AC-5 の 4 形を deny ケースとして足す - deny
- [ ] TS-6（FR5、FR8 / AC-6）: AC-6 の形を allow ケースとして足す - allow
- [ ] TS-7（FR6、FR8 / AC-7）: AC-7 の 5 形を deny ケースとして足す - deny
- [ ] TS-8（FR7、FR8 / AC-8）: AC-8 の 5 形を deny ケースとして足す - deny
- [ ] TS-9（FR4、FR9）: round2 の 46923ffe262f20b1 の 3 形を deny ケースとして足す。FR4 の変更後も、単一引用符内の閉じないバッククォートや `$(` の後ろにある置換・文が検査されることを確かめる - deny
    1. ``tr -d '`' < a > b; echo "$(rm -rf <対象>)"``
    2. ``echo 'don`t'; echo "$(rm -rf <対象>)"``
    3. `echo 'a $(' ; rm -rf <対象> ; f "(" ; echo ')'`

### Integration Tests
- [ ] TS-10（FR9、FR10 / AC-9）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行する - 全件 pass する

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- 該当なし

### Edge Cases
- [ ] ヒアドキュメントの区切り語を囲む引用符（`<<'EOF'` / `<<"EOF"`）は演算子の一部である。FR5 の行をまたぐ引用追跡で、引用の開始と読まない。
- [ ] 置換の中にある本物の演算子（`"$(cat <<'EOF' … EOF)"`、既存ケース 428・434・435・456・457 の形）は、FR5 の変更後もヒアドキュメントとして扱う。
- [ ] コメント内の 2 つ目の演算子（既存ケース 455: `cat <<'A' # <<'B'`）は、これまでどおり本文を取り込まない。
- [ ] FR6 の sink 照合は `user.name=x` のような値には一致しない。既存の allow ケース 468・469 は allow のまま。
- [ ] FR2 の判定不能化と FR7 の判定不能化は、チャンクに sink 語が無ければ本文を再走査しない。既存の allow ケース 4・36・416〜419 は allow のまま。

### Performance Tests
- [ ] TS-4: 約 60KB の再現入力が 10 秒の制限時間内に deny を返す（AC-4）。
- [ ] ランナーは 10 秒を超えたケースを FAIL として数え、残りのケースを続ける（FR10）。

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 判定は静的解析のみで行い、ファイルシステムにはアクセスせず、コマンドや置換を評価しない（NFR1）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし
- **Accepted residual risk:** 判定不能にしても、チャンクに sink 語が無ければフォールバックは本文を再走査しない。このため、差し替え先が sink 名を含まないパスの場合（例: `hash -p /tmp/evil cat`）は検知漏れが残る。これは受け入れた残存リスクとする（A6）。

## Error Handling

### Error Codes

該当なし

### Error Flow

```
ホスト文が確定できない（FR2）／ 読み飛ばした語に sink がある（FR6）／ コマンド名の差し替え構文がある（FR7）
  → 判定不能 → 既存のフォールバック（チャンクに SHELL_SINK が現れたら本文を再走査）

ランナーでケースが 10 秒を超える（FR10）
  → そのケースを FAIL として数える → ランナーは異常終了せず残りのケースを続ける
```

## Performance Optimization

### Performance Goals
- 判定は hooks.json の timeout（10 秒）に十分収まる（NFR3）。
- 約 60KB の再現入力（`echo ' + $(×30000 + ' ; rm -rf <対象>`）を 10 秒の制限時間内に判定する（AC-4）。

### Optimization Strategies
- 単一引用符内 `$(` の対応探索: 入力長に対して線形の計算量にする（FR4）。
- FR1〜FR7 で追加・変更する処理: どれも入力長に対して線形の計算量にする（NFR3）。

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] REQUIREMENTS.md 11.1 の AC-1〜AC-9 をすべて満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
- フックのテストのルール: `.claude/rules/hook-tests.md`
