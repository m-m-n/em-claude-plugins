# Feature: env-route-unreadable-heredoc-ask

## Overview

destructive-guard の env 経路で、区切り語を読めないヒアドキュメントより後ろに置かれた mcp-bridge の notion ペアが検査を逃れる穴を塞ぐ。
読めない末尾（TAIL）に `mcp-bridge` の語か `$'` か `$"` があるとき、その読み取りを `unrestorable` にし、`args-json-unrestorable` の ask にする。
env-route-lex-flag-isolation で決めた挙動は保つ。

## Objectives

- destructive-guard の env 経路の穴を塞ぐ。区切り語を読めないヒアドキュメントの後ろに mcp-bridge の notion ペアがあっても、検査を逃れないようにする。攻撃シナリオが通らないようにする。
- env-route-lex-flag-isolation の挙動を保つ。読めないヒアドキュメントだけを含む無害な env 経路の本文で、無人実行を止めない。

## Acceptance Criteria

- [ ] AC-1: `/usr/bin/env 'BASH_FUNC_mcp-bridge%%=() { :; }' bash -c '<body>'` の形のコマンドを取る。静的な本文には、区切り語が `${tag}` の cat ヒアドキュメントがあり、その後ろに `mcp-bridge run --mcp notion --tool notion-create-comment --args-json ...` の呼び出しがある。その command は `git branch -D example`。このコマンドは rule `args-json-unrestorable` の ask になる。batch では同じ rule の deny になる。(TS-1, TS-2)
- [ ] AC-2: 同じ本文を `env - ... bash -c` の形で渡しても同じ判定になる。(TS-3)
- [ ] AC-3: TAIL の中の回避形も rule `args-json-unrestorable` の ask になる。引用符で分けた mcp-bridge、行継続で分けた mcp-bridge、`$'` を含む TAIL、`$"` を含む TAIL、`$` と `"` の間に行継続を挟んだ TAIL、`$` と `'` の間に行継続を挟んだ TAIL の 6 つ。(TS-4)
- [ ] AC-4: env-route-lex-flag-isolation の TS-1/TS-2 は batch で allow のまま。その本文は `${tag}` のヒアドキュメントだけで、行継続を除いても mcp-bridge の語も `$'` も `$"` も含まない。(TS-5)
- [ ] AC-5: mcp-bridge の語が読めない `<<` より前の読める範囲にだけあるとき、修正前の判定が変わらず、新しい `args-json-unrestorable` の ask は出ない。(TS-6)
- [ ] AC-6: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` の両方が通る。(TS-8)

## Technical Requirements

### Functional Requirements

- **FR1:** mcp-bridge の語を含む読めない末尾を unrestorable にする
    - env 経路が `bash -c` のペイロードを読む処理（`_args_json_env_body_reading()` / `_args_json_payload_chunk()`）で、`lex_shell(payload, "shell")` の map を取る。
    - その `unreadable` が立っているとき、map の `tail_start` からペイロード末尾までの生テキストを TAIL とする。
    - 次のどちらかを満たすとき、その読み取りの `unrestorable`（`_EnvBodyReading.unrestorable`）を立てる。
        - (a) TAIL からバックスラッシュと改行の組（行継続）をすべて除き、残りから `'`、`"`、`\` の文字をすべて除いた結果が、部分文字列 `mcp-bridge` を含む。
        - (b) TAIL からバックスラッシュと改行の組（行継続）をすべて除いた文字列が `$'` または `$"` を含む。
    - 除く順序は固定する。先に行継続を除き、次に引用符とバックスラッシュを除く。
    - `unrestorable` が立つと、既存の経路で `args-json-unrestorable` の ask（`ARGS_JSON_UNRESTORABLE_ASK`）になる。
    - TAIL がどちらの条件も満たさない本文には、新しい ask を出さない。
    - 展開して初めて `mcp-bridge` になる名前（例: `${a}cp-bridge`、`$(printf ...)`）は TAIL で照合しない。読める範囲でも対象外とする。
- **FR2:** 2 つの extglob の読み方の結合
    - どちらかの extglob の読み方で FR1 が `unrestorable` を立てたら、結合した結果は `unrestorable` になる。既存の `_args_json_env_combine()` の OR を使う。
- **FR3:** フラグの退避と復元は変えない
    - `_args_json_env_body_readings()` が `_lex_unreadable_met`、`_lex_extglob_met`、`_lex_extglob` を退避・復元するやり方（env-route-lex-flag-isolation FR1/FR2）を変えない。
    - 読めない末尾が FR1 のどちらの条件も満たさない本文は、新しい ask を出さない。
- **FR4:** 退行を捕まえるケース
    - 攻撃シナリオ、FR1 が扱う回避形、誤検知の対照ケースを `em-workflow/hooks/tests/destructive-guard-cases.json` に足す。
    - ask か deny を固定するケースには `rule` を付ける。batch の判定を固定するケースには `{"batch": true}` を付ける。

### Non-Functional Requirements

- **NFR1:** env 経路の外の判定は変えない。対象はトップレベル、素の `bash -c`、`run()` の読めないヒアドキュメント区切り語と extglob 切り替えの扱い。
- **NFR2:** 優先順位は変えない。deny は `args-json-unrestorable` の ask に勝ち、scan-budget の ask はその上に来る。
- **NFR3:** 既存の deny / ask ケースを消さず、既存のケースはすべて通る。
- **NFR4:** plugin.json と marketplace.json の version は変えない。patch は Actions のワークフローが上げる。

## Implementation Approach

### Architecture

変更は destructive-guard の env 経路の判定ロジックと、テストケースのファイルに限る。UI は無い。

### Data Flow

```
bash -c のペイロード
  → lex_shell(payload, "shell") の map
  → unreadable が立っている？
      いいえ → 既存の判定のまま
      はい   → TAIL = payload[tail_start:]
               → JOINED = TAIL から行継続を除いた文字列
               → (a) JOINED から ' " \ を除く → "mcp-bridge" を含む？
               → (b) JOINED が $' または $" を含む？
               → どちらかを満たす → _EnvBodyReading.unrestorable = True
  → _args_json_env_combine() で 2 つの extglob の読み方を OR で結合
  → unrestorable → ARGS_JSON_UNRESTORABLE_ASK（rule: args-json-unrestorable）
```

### Assumptions

- **A1:** TAIL は生テキストとして照合する。TAIL の中でヒアドキュメント本文としてだけ現れる mcp-bridge の語でも ask にする。
- **A2:** TAIL の mcp-bridge の語は、ペアの種類（notion か desktop-commander か）にも、BASH_FUNC_ の持ち上げの有無にも関係なく ask にする。
- **A3:** 展開して初めて mcp-bridge になる名前（`${a}cp-bridge`、`$(printf ...)`）は TAIL で照合しない。
- **A4:** `LexMap.unreadable` が立っているときは、`LexMap.tail_start` は None でなく、読めない `<<` と同じ位置かそれより前にある。
- **A5:** `_args_json_env_body_readings()` の 3 つの lexer フラグの退避と復元は、不変条件として保つ。

### Dependencies

**Internal Dependencies:**
- env-route-lex-flag-isolation: 3 つの lexer フラグの退避と復元（同 FR1/FR2）と、その TS-1〜TS-4 のケースを前提にする。

### File Structure

```
em-workflow/hooks/
└── tests/
    └── destructive-guard-cases.json   # FR4 のケースを足す
```

判定ロジックの変更は destructive-guard の env 経路（`_args_json_env_body_reading()` / `_args_json_payload_chunk()`）に入れる。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/env-route-unreadable-heredoc-ask/**`
- `test-docs/env-route-unreadable-heredoc-ask/**`

`feature-docs/env-route-unreadable-heredoc-ask/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/env-route-unreadable-heredoc-ask/**` covers `test-docs/env-route-unreadable-heredoc-ask/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/env-route-unreadable-heredoc-ask/` directory at all; the declared
`test-docs/env-route-unreadable-heredoc-ask/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

ケースは `em-workflow/hooks/tests/destructive-guard-cases.json` に置く。

- [ ] TS-1: `["ask", ..., "/usr/bin/env 'BASH_FUNC_mcp-bridge%%=() { :; }' bash -c '<body>'", {"rule": "args-json-unrestorable"}]`。本文は `cat <<${tag}` で始まり、無害な行と `${tag}` の行が続く。その後ろに notion ペアの `mcp-bridge run --mcp notion --tool notion-create-comment --args-json` の呼び出しがあり、JSON の command は `git branch -D example`。JSON は外側の単一引用符のペイロードに収まるように引用する。修正前は allow になる（red）。 - rule `args-json-unrestorable` の ask
- [ ] TS-2: TS-1 のコマンドに `{"batch": true, "rule": "args-json-unrestorable"}` を付ける。 - deny
- [ ] TS-3: TS-1 の本文を `env - 'BASH_FUNC_mcp-bridge%%=() { :; }' bash -c '<body>'` で渡す。 - batch で rule `args-json-unrestorable` の deny
- [ ] TS-4: 読めない `${tag}` ヒアドキュメントの後ろの回避形。それぞれ batch で rule `args-json-unrestorable` の deny になる。
    - (a) コマンド語を引用符で分ける。例: `"mcp-"bridge`
    - (b) コマンド語を行継続で分ける。例: `mcp-br\<改行>idge`
    - (c) コマンド語を ANSI-C クォートで書き、ペイロードのテキストに `$'` を含める。例: `$'\x6dcp-bridge'`（外側の引用に収まるように書く）
    - (d) コマンド語をロケール引用で分け、ペイロードのテキストに `$"` を含める。例: `mcp-$"bridge"`
    - (e) (d) の `$` と `"` の間に行継続を挟む。例: `mcp-$\<改行>"bridge"`
    - (f) (c) の `$` と `'` の間に行継続を挟む。例: `$\<改行>'\x6dcp-bridge'`（外側の引用に収まるように書く）
- [ ] TS-5: 既存の env-route-lex-flag-isolation の TS-1/TS-2 のケース（ケースファイルの 1678〜1679 行）を編集しない。 - batch で allow のまま
- [ ] TS-6: 対照ケース。本文が `mcp-bridge` に触れるのは読めないヒアドキュメントより前だけ。例: `echo mcp-bridge; cat <<${tag}` の後に無害な行と `${tag}` の行。 - batch で修正前と同じ判定のまま（allow の見込み。修正前に確かめる）。`args-json-unrestorable` は出ない
- [ ] TS-7: `mcp-bridge` の語が TAIL の中でヒアドキュメント本文としてだけ現れる。例: `cat <<${tag}`、`mcp-bridge` の行、`${tag}` の行。 - batch で rule `args-json-unrestorable` の deny。A1 の安全側の広さを固定する

### Integration Tests

- [ ] TS-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` を実行する。 - 両方が通る

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] Existing E2E tests pass without regression

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] 既存の deny / ask ケースを消していない

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/hooks/tests/run-destructive-guard.py`
- env-route-lex-flag-isolation（FR1/FR2、TS-1〜TS-4）
