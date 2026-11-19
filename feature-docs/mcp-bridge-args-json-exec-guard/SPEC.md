# Feature: mcp-bridge-args-json-exec-guard

要件定義書: `feature-docs/mcp-bridge-args-json-exec-guard/REQUIREMENTS.md`

## Overview

notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープ（`$(` / ```）やシェルのエスケープ（二重引用符の `\$(`、ANSI-C の `\x24(`）で書いたコマンド置換を、destructive-guard が検出する。トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査する。notion の組（`notion-create-comment`）の既存の allow は保ち、静的に決まらない形と、`command` 以外のキーに平文で書く形は範囲外として記録する。

## Objectives

- notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープやシェルのエスケープで書いたコマンド置換を、destructive-guard が検出する。シェルを実行する MCP ツール経由の攻撃シナリオを成立させない。
- トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査する。
- notion の組（`notion-create-comment`）の既存の allow は保つ。静的に決まらない形と、`command` 以外のキーに平文で書く形は、範囲外として SPEC に記録する。

## Acceptance Criteria

- [ ] AC-1 (FR3, FR4): TS-1〜TS-4（JSON のエスケープとシェルのエスケープで書いた置換）が、変更後に deny になる。変更前は allow になる。
- [ ] AC-2 (FR5): TS-5（トップレベルの `command` に平文の破壊的コマンド）が、変更後に deny になる。変更前は allow になる。
- [ ] AC-3 (FR4): TS-6（`command` 以外の入れ子の文字列にエスケープした置換）が deny になる。
- [ ] AC-4 (FR1): TS-7、TS-8（ほかのコマンドと連ねた文、ラッパーの後ろ）が deny になる。TS-11（ほかのコマンドの引数に文字として現れるだけ）が allow になる。
- [ ] AC-5 (FR2): TS-9（notion の組とエスケープした置換）と、notion の組の既存の allow ケースが allow のまま。
- [ ] AC-6 (FR6, FR8): 範囲外の形の TS-10、TS-13、TS-14 は allow になる。ケースのラベルと SPEC の範囲外の記述が一致している。
- [ ] AC-7 (FR7): TS-15 が `scan-budget-exceeded` の ask になり、10 秒以内に終わる。
- [ ] AC-8 (NFR2): ほかの既存のケースが、期待する判定（理由 ID を固定しているケースはその理由 ID も）を保つ。ランナーが通り、既存のケースは 1 件も消されていない。
- [ ] AC-9 (FR10): FR10 に挙げた docstring とコメントが新しい判定を述べ、FR8 の範囲外の形を記録している。

## Technical Requirements

### Functional Requirements

- **FR1:** 対象の文 — `statements()` が返すすべての文を対象にする。トップレベルの文、`&&` / `;` / `|` で連なった文、ラッパーの後ろ、置換の本体、`-c` / `eval` / ヒアストリングのペイロードを含む。そのうち、既存の文の分割とラッパーの扱い（`head()` など）でコマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文に、FR2〜FR5 を適用する。ほかのコマンドの引数に `mcp-bridge run` が文字として現れるだけの文は対象にしない。
- **FR2:** notion の組は除外する — mcp-bridge-exec-tool-rescan FR1 の正規のフラグ並びで notion の組（`--mcp notion` / `--tool notion-create-comment`）を持つ文は、FR3〜FR5 の復号と検査の対象にしない。`_single_quote_skip_spans()` による生の文字列の引用内の候補の除外は、今の「トップレベルの静的な単一コマンドに限る」制限（W1〜W4、C1、S1、S2）をそのまま保つ。
- **FR3:** `--args-json` の値の再構成 — `run` より後ろの語を正規のフラグ並び（`--mcp` / `--tool` / `--args-json` / `--format` / `--session` は次の語を値として取り、`--dry-run` は値を取らない）として読み、`--args-json` がちょうど 1 回現れるときに、その値の語を対象にする。値の語が静的なときだけ、Bash の引用とエスケープの規則で引数の値を組み立てる。対象は、単一引用符、二重引用符（`\$`、`` \` ``、`\"`、`\\` と行継続）、ANSI-C 引用（既存の `_decode_ansi_c()`）、引用の外のバックスラッシュ、それらを連結した語。生の文字列の走査が引用内で候補として印を付けた `$(` やバッククォートは、Bash にとって文字どおりのテキストなので、印を外して文字として値に含める。
- **FR4:** JSON の復号と全文字列の置換の再走査 — FR3 の値を標準の JSON として復号する。入れ子のオブジェクトと配列をたどり、すべての文字列値から `$(` とバッククォートの置換の候補を、生の文字列のときと同じ規則で探す。候補の本体は、既存の置換の本体と同じように `pending` に積んで再走査する。重複したキーは、最後の値だけでなく、すべての組を対象にする。
- **FR5:** トップレベルの `command` のシェル入力としての再走査 — 復号した値のトップレベルがオブジェクトで、トップレベルの `command` キーの値が文字列のときは、その文字列を `-c` のペイロードと同じようにシェル入力として `pending` に積み、再走査する。重複したキーは、すべての組を対象にする。このペイロードは、入力全体で共有している既存の `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）の数に入れる。トップレベル以外の `command`、`command` 以外のキー、文字列でない値は、FR4 の置換の再走査だけを受ける。
- **FR6:** 静的に決まらない形は今の判定を保つ — 次の形は FR3〜FR5 を行わず、今の生の文字列による判定を保つ。値が置換や変数展開で決まる形、宛先が静的に決まらない形、JSON として読めない値、`--args-json` が無い・重複する・`=` で書かれている形、正規のフラグ並びとして読めない形、トップレベルがオブジェクトでない値。Bash が実際に実行する置換の本体は、これまでどおり再走査する。
- **FR7:** 走査量の上限 — JSON の復号、入れ子をたどる処理、復号した文字列の再走査を、`statements()` の全体の走査量の上限（`scan_budget`）に入れる。この上限は `MAX_SHELL_PAYLOAD_EXPANSIONS` の数とは別に数える。上限を超えたときは、既存の `scan-budget-exceeded` の ask にする（batch では deny）。
- **FR8:** 範囲外の記録 — このフィーチャーの SPEC の Security Considerations と、該当するコードの docstring に、範囲外の形を記録する。1 つめは、`command` 以外のキー（例: desktop-commander の `interact_with_process` の `input`）や、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド。2 つめは、FR6 の形（動的な値、静的に決まらない宛先、JSON として読めない値、`--args-json` の欠落・重複・`=` の形）。
- **FR9:** ケースの追加 — `em-workflow/hooks/tests/destructive-guard-cases.json` に、Test Scenarios の新しいケースを追加する。既存のケースは消さず、変えない。
- **FR10:** コード内の説明の更新 — mcp-bridge の `--args-json` の扱いを述べる docstring とコメントを、新しい判定に合わせて直す。対象は `_single_quote_skip_spans()`、`scan_structure()` のシングルクォート候補の段落、`statements()` の docstring とキュー投入ループのコメント、`extract_shell_payload_anchored()` の範囲外の宣言（FR7）。

### Non-Functional Requirements

- **NFR1 - Performance:** 1 回の判定を、`hooks.json` の destructive-guard のタイムアウト（10 秒）と、ランナーの `GUARD_TIMEOUT_SECONDS` に収める。巨大な JSON や深い入れ子でも、再帰や走査量が際限なく増えない（FR7）。
- **NFR2 - Fail-closed:** 既存の deny / ask の判定を allow に変えない。
- **NFR3 - Test procedure:** 同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を走らせる（`.claude/rules/hook-tests.md`）。新しい deny ケースは修正の前に追加し、変更前のフックがそれらを allow にすること（見逃しの再現）を確かめる。
- **NFR4 - Version:** `plugin.json` と `marketplace.json` の version は変えない。patch は GitHub Actions が上げる（`.claude/rules/core-plugin-version-bump.md`）。

## Implementation Approach

### Architecture

`em-workflow/hooks/destructive-guard.py` の `statements()` の走査に、`mcp-bridge run` の文に対する処理を加える。

```
statements() が返す文（FR1）
  └─ コマンドの位置が mcp-bridge、2 語目が run か
       ├─ いいえ → 今の判定
       └─ はい
            ├─ notion の組（FR2）→ 復号と検査をしない（今の判定）
            └─ それ以外
                 ├─ 正規のフラグ並びとして読み、--args-json がちょうど 1 回で、値の語が静的か（FR3）
                 │    └─ いいえ → 今の生の文字列による判定（FR6）
                 ├─ Bash の引用とエスケープの規則で値を組み立てる（FR3）
                 ├─ 標準の JSON として復号する（FR4）
                 │    └─ 読めない／トップレベルがオブジェクトでない → 今の判定（FR6）
                 ├─ すべての文字列値から置換の候補を探し、本体を pending に積む（FR4）
                 └─ トップレベルの command の文字列値を、シェル入力として pending に積む（FR5）
```

### Data Flow

```
--args-json の値の語 → 値の組み立て（FR3）→ JSON の復号（FR4）
  → 入れ子をたどる（FR4）→ 置換の本体 / トップレベルの command → pending → 再走査
  （復号・入れ子の走査・再走査は scan_budget に入れる。FR7）
```

### Dependencies

**Internal Dependencies:**
- `statements()`: 文の分割、`pending` による再走査、`scan_budget`
- `head()` などのラッパーの扱い: コマンドの位置の決定（FR1）
- `_decode_ansi_c()`: ANSI-C 引用の復号（FR3）
- `_single_quote_skip_spans()`: notion の組の引用内の候補の除外（FR2）
- `MAX_SHELL_PAYLOAD_EXPANSIONS`: シェル入力のペイロードの展開数の上限（FR5）
- mcp-bridge-exec-tool-rescan FR1: 正規のフラグ並びと notion の組（FR2）

**External Dependencies:**
- なし

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # FR1〜FR7、FR10
└── tests/
    └── destructive-guard-cases.json     # FR9
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/mcp-bridge-args-json-exec-guard/**`
- `test-docs/mcp-bridge-args-json-exec-guard/**`

`feature-docs/mcp-bridge-args-json-exec-guard/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/mcp-bridge-args-json-exec-guard/**` covers `test-docs/mcp-bridge-args-json-exec-guard/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/mcp-bridge-args-json-exec-guard/` directory at all; the declared
`test-docs/mcp-bridge-args-json-exec-guard/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

各シナリオは `em-workflow/hooks/tests/destructive-guard-cases.json` のケースとして追加する（FR9）。TS-15 を除いて `rule` の要素を付けない。

### Unit Tests

deny になるケース:

- [ ] TS-1: JSON の `$(` で書いた置換。変更前は allow - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'
  ```
- [ ] TS-2: JSON の ``` で書いたバッククォートの置換 - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo `git branch -D example`","shell":"bash"}'
  ```
- [ ] TS-3: 二重引用符の中の `\$(` で書いた置換 - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"echo \$(git branch -D example)\",\"shell\":\"bash\"}"
  ```
- [ ] TS-4: ANSI-C 引用の `\x24(` で書いた置換 - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json $'{"command":"echo \x24(git branch -D example)","shell":"bash"}'
  ```
- [ ] TS-5: トップレベルの `command` に平文の破壊的コマンド。変更前は allow - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-6: `command` 以外の入れ子の文字列に、エスケープした置換 - deny
  ```
  mcp-bridge run --mcp example-server --tool example-tool --args-json '{"msg":{"text":"$(git branch -D example)"}}'
  ```

allow になるケース:

- [ ] TS-9: notion の組は復号の対象にしない - allow
  ```
  mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"$(git branch -D example) と記載する"}'
  ```
- [ ] TS-12: 無害な `command` - allow
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"ls -la","shell":"bash"}'
  ```

### Integration Tests

- [ ] TS-7: `&&` で連ねた文 - deny
  ```
  cd /tmp && mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'
  ```
- [ ] TS-8: ラッパー `env` の後ろ - deny
  ```
  env mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-11: コマンドの位置ではない。ほかのコマンドの引数に文字として現れるだけ - allow
  ```
  echo "mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{\"command\":\"git branch -D example\"}'"
  ```
- [ ] TS-16: 既存のケースがすべて期待する判定を保つ（notion の組の allow、mcp-bridge-exec-tool-rescan の deny を含む） - 回帰なし

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases

範囲外の形（FR6、FR8）:

- [ ] TS-10: 範囲外: `command` 以外のキーに平文で書いたコマンド（FR8） - allow
  ```
  mcp-bridge run --mcp desktop-commander --tool interact_with_process --args-json '{"pid":1,"input":"git branch -D example"}'
  ```
- [ ] TS-13: 範囲外: 置換の出力が値になる形（FR6、FR8）。`cat` の本体は再走査される - allow
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json "$(cat args.json)"
  ```
- [ ] TS-14: 範囲外: JSON として読めない値は、今の生の文字列による判定を保つ（FR6、FR8） - allow
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)"'
  ```

### Performance Tests

- [ ] TS-15: 深い入れ子や大量の文字列で走査量の上限を超える JSON（FR7） - ask、`rule` は `scan-budget-exceeded`。10 秒以内に終わる。具体的な入力は create-plan で決める。

## Security Considerations

- **Input Validation:** `mcp-bridge run` の `--args-json` の値を、Bash の引用とエスケープの規則で組み立て、標準の JSON として復号し、すべての文字列値の置換の候補と、トップレベルの `command` の文字列値を再走査する（FR3〜FR5）。notion の組は復号と検査の対象にしない（FR2）。
- **Fail-closed:** 既存の deny / ask の判定を allow に変えない（NFR2）。走査量の上限を超えたときは `scan-budget-exceeded` の ask にする（batch では deny）（FR7）。

### 範囲外（FR8）

次の形は、このフィーチャーでは検出しない。

1. `command` 以外のキー（例: desktop-commander の `interact_with_process` の `input`）や、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド（TS-10）。
2. FR6 の形。今の生の文字列による判定を保つ。
    - 動的な値（値が置換や変数展開で決まる形。Bash が実際に実行する置換の本体は再走査する）（TS-13）
    - 静的に決まらない宛先
    - JSON として読めない値（TS-14）
    - `--args-json` の欠落・重複・`=` の形

### 前提

- A1: `notion-create-comment` は `--args-json` をデータとしてだけ使い、シェルのコマンドとして実行しない（mcp-bridge-exec-tool-rescan A1 と同じ）。
- A2: mcp-bridge は `--args-json` を標準の JSON として読む。重複したキーをどう扱うかは分からないので、すべての組を検査する。
- A3: シェルを実行する MCP ツールは、引数をトップレベルの `command` に取るのが一般的（desktop-commander の `start_process`）。ほかのキーで実行する形の平文は範囲外とする。
- A4: `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）を使い切った後に積まれるはずだったペイロードの扱いは、既存の `-c` / `eval` と同じにし、このフィーチャーでは変えない。
- A5: `--dry-run` 付きの `mcp-bridge run` も、ほかの形と同じように検査する。
- A6: 新しいケースには、TS-15 を除いて `rule` の要素を付けない。
- A7: version は変えない。

## Error Handling

| 状況 | 判定 |
|------|------|
| 走査量が `scan_budget` を超えた（FR7） | `scan-budget-exceeded` の ask（batch では deny） |
| JSON として読めない値、トップレベルがオブジェクトでない値、正規のフラグ並びとして読めない形など（FR6） | FR3〜FR5 を行わず、今の生の文字列による判定 |
| `MAX_SHELL_PAYLOAD_EXPANSIONS` を使い切った後のペイロード（A4） | 既存の `-c` / `eval` と同じ扱い |

## Performance Optimization

### Performance Goals

- 1 回の判定を、`hooks.json` の destructive-guard のタイムアウト（10 秒）と、ランナーの `GUARD_TIMEOUT_SECONDS` に収める（NFR1）。

### Optimization Strategies

- 走査量の上限: JSON の復号、入れ子をたどる処理、復号した文字列の再走査を `scan_budget` に入れる。`MAX_SHELL_PAYLOAD_EXPANSIONS` の数とは別に数える（FR7）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` が通り、既存のケースは 1 件も消されていない

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/mcp-bridge-args-json-exec-guard/REQUIREMENTS.md`
- フックのテスト: `.claude/rules/hook-tests.md`
- version の扱い: `.claude/rules/core-plugin-version-bump.md`
- mcp-bridge-exec-tool-rescan: FR1（正規のフラグ並び）、A1
