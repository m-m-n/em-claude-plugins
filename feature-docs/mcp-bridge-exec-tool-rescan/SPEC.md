# Feature: mcp-bridge-exec-tool-rescan

## Overview

destructive-guard の `_single_quote_skip_spans()` の `mcp-bridge` アーム（条件 S1）を、`--mcp notion` / `--tool notion-create-comment` の対があるときだけ働くように絞る。引数を実行する MCP ツールを呼ぶ `mcp-bridge run` コマンドは、`--args-json` のシングルクォート値も再走査される。Notion の進捗コメントは allow のまま保つ。

要件の詳細は同じディレクトリの `REQUIREMENTS.md` を参照する。

## Objectives

- destructive-guard で、静的な `mcp-bridge run` コマンドの `--args-json` のシングルクォート値に対する再走査スキップを、引数を実行する MCP ツールには適用しない。`mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'` のようなコマンドは allow にならない。
- Notion の進捗コメント（`mcp-bridge run --mcp notion --tool notion-create-comment --args-json '...'`）に対する既存の誤 deny 修正は、allow のまま保つ。

## User Stories

該当なし（フック内部の静的解析の変更）。

## Technical Requirements

### Functional Requirements

- **FR1:** mcp-bridge アームを notion / notion-create-comment の対に限定する。`_single_quote_skip_spans()`（`em-workflow/hooks/destructive-guard.py`）の `mcp-bridge` アーム（条件 S1）は、コマンドが `--mcp notion` / `--tool notion-create-comment` の対も持つときに限り、スキップするデータ語を返す。対があるのは次の両方が成り立つときだけ。
  - (a) クォートされていない `--mcp` とちょうど一致する語がちょうど 1 つあり、その直後の語が、クォートを含まない 1 つの連なりで `notion` とちょうど一致する。
  - (b) クォートされていない `--tool` とちょうど一致する語がちょうど 1 つあり、その直後の語が、クォートを含まない 1 つの連なりで `notion-create-comment` とちょうど一致する。

  どちらかが偽、または判定できないときは、アームは空集合を返し、すべての候補はこれまでどおり再走査される。S1 の既存部分は残す（2 語目はちょうど `run`、データ語は `--args-json` とちょうど一致する語の直後の語）。`run` より後ろの語の中での `--mcp`、`--tool`、`--args-json` の位置は制限しない。
- **FR2:** ほかのスキップ条件は変えない。条件 W1〜W4 と C1、トップレベルの塊だけに限る制限、ANSI-C クォートのデータ語の扱い、`printf '%s\n'` アーム（S2）は変えない。
- **FR3:** 候補の印付けは変えない。変えるのは `pending` へのキュー投入だけ。トップレベルの範囲の計算、`_mark_substitutions()` / `_mark_quoted_substitutions()` による印付け、`all_subs` の拡張とその印のインデックス、トークンごとの `.unresolved` / `.substitution_only` フラグはそのまま。
- **FR4:** ケースを追加する。`em-workflow/hooks/tests/destructive-guard-cases.json` に、タスクの desktop-commander / start_process のシナリオの deny ケース（TS-1）と、Test Scenarios に挙げる対の境界の deny ケース（TS-3〜TS-9）を追加する。notion の対が別の順序で現れる allow ケース（TS-2）を 1 件追加する。既存のケースは消さず、変えない。
- **FR5:** コード内の説明を更新する。mcp-bridge のスキップを、任意の静的な `mcp-bridge run --args-json` に適用されると説明している文言を、notion / notion-create-comment の対の条件を述べる文言に直す。対象は `_single_quote_skip_spans()` の docstring（S1）、`scan_structure()` の docstring のシングルクォート候補についての段落、`statements()` の docstring、`statements()` のキュー投入ループにある `FR2` コメント。
- **FR6:** 条件はこのフィーチャーの文書にだけ記録する。このフィーチャーの SPEC と THREAT-MODEL に、再走査のスキップが `notion` MCP サーバーの `notion-create-comment` が引数を実行しないことに依存すること、それ以外の `--mcp` / `--tool` の対はすべて再走査されることを記録する。`feature-docs/destructive-guard-false-deny`（THREAT-MODEL の TM-1 と SPEC）は編集しない。

### Non-Functional Requirements

- **NFR1 - Performance:** 1 回の判定は、hooks.json のタイムアウト（10 秒）と、ランナーの `GUARD_TIMEOUT_SECONDS`（10 秒）に収まる。`scan_budget` と `MAX_SHELL_PAYLOAD_EXPANSIONS` は変えない。
- **NFR2 - Fail-closed:** 対の判定ができない形は、すべて再走査する（deny 側）。この変更は、既存の deny / ask の判定を allow に変えない。
- **NFR3 - Test procedure:** 同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を走らせる（`.claude/rules/hook-tests.md`）。新しい deny ケースは修正の前に追加し、変更前のフックがシナリオのケース（TS-1）を allow にすること（見逃しの再現）を確かめる。
- **NFR4 - Version:** `plugin.json` と `marketplace.json` の version は変えない。patch の引き上げは GitHub Actions が行う（`.claude/rules/core-plugin-version-bump.md`）。

## Implementation Approach

### Architecture

変更するのは `em-workflow/hooks/destructive-guard.py` の `_single_quote_skip_spans()` の S1 アームだけ（FR1）。ほかのスキップ条件（FR2）と候補の印付け（FR3）は変えない。

### Data Flow

S1 アームの判定は次の順に進む。

```
2 語目がちょうど run（既存）
  → (a) --mcp notion の対の片側が成り立つか
  → (b) --tool notion-create-comment の対の片側が成り立つか
  → 両方成り立つ: --args-json とちょうど一致する語の直後の語をデータ語として返す
  → どちらかが偽 / 判定不能: 空集合を返す（すべての候補を pending に積んで再走査）
```

判定不能として扱う形（前提 A2）:

- `--mcp` / `--tool` の語の重複
- クォートされた値（例: `--mcp 'notion'`）
- `--opt=value` の形（例: `--mcp=notion`）

対の一致は語の順序に依存しない（前提 A2）。

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- 既存のスキップ条件（W1〜W4、C1、S1、S2）: S1 だけを変え、ほかは変えない（FR2）。
- destructive-guard-false-deny の前提 A6（フェイルクローズ）: 判定不能な形の扱いはこれに従う（前提 A2）。

**External Dependencies:**
- 該当なし。

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # S1 アームの絞り込み（FR1）、docstring とコメント（FR5）
└── tests/
    └── destructive-guard-cases.json     # ケースの追加（FR4）
feature-docs/mcp-bridge-exec-tool-rescan/
├── SPEC.md                              # 条件の記録（FR6）
└── THREAT-MODEL.md                      # 条件の記録（FR6）
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/mcp-bridge-exec-tool-rescan/**`
- `test-docs/mcp-bridge-exec-tool-rescan/**`

`feature-docs/mcp-bridge-exec-tool-rescan/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/mcp-bridge-exec-tool-rescan/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/mcp-bridge-exec-tool-rescan/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/mcp-bridge-exec-tool-rescan/` ディレクトリを生成しないが、宣言された `test-docs/mcp-bridge-exec-tool-rescan/**` は依然として正しい。

## Test Scenarios

ケースは `em-workflow/hooks/tests/destructive-guard-cases.json` に置き、`python3 em-workflow/hooks/tests/run-destructive-guard.py` で走らせる。

### Case Suite: 新しいケース

- [ ] TS-1: タスクのシナリオ（FR1, FR4） - 期待: deny。変更前のフックでは allow
  - `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'`
- [ ] TS-2: 対が別の順序で現れる（FR1, FR4） - 期待: allow
  - `mcp-bridge run --tool notion-create-comment --args-json '{"body":"$(git branch -D example) と記載する"}' --mcp notion`

### Edge Cases: 対の境界

- [ ] TS-3: notion サーバーのほかのツール（FR1, FR4） - 期待: deny
  - `mcp-bridge run --mcp notion --tool notion-update-page --args-json '{"body":"$(git branch -D example)"}'`
- [ ] TS-4: 許可するツール名がほかのサーバーの下にある（FR1, FR4） - 期待: deny
  - `mcp-bridge run --mcp desktop-commander --tool notion-create-comment --args-json '{"body":"$(git branch -D example)"}'`
- [ ] TS-5: `--mcp` / `--tool` なし（FR1, FR4） - 期待: deny
  - `mcp-bridge run --args-json '{"body":"$(git branch -D example)"}'`
- [ ] TS-6: `--mcp` が 2 回（FR1, FR4） - 期待: deny
  - `mcp-bridge run --mcp notion --tool notion-create-comment --mcp desktop-commander --args-json '{"body":"$(git branch -D example)"}'`
- [ ] TS-7: クォートされたサーバー値（FR1, FR4） - 期待: deny
  - `mcp-bridge run --mcp 'notion' --tool notion-create-comment --args-json '{"body":"$(git branch -D example)"}'`
- [ ] TS-8: `--opt=value` の形（FR1, FR4） - 期待: deny
  - `mcp-bridge run --mcp=notion --tool=notion-create-comment --args-json '{"body":"$(git branch -D example)"}'`
- [ ] TS-9: `--tool` なし（FR1, FR4） - 期待: deny
  - `mcp-bridge run --mcp notion --args-json '{"body":"$(git branch -D example)"}'`

### Regression

- [ ] TS-10: 既存ケース（destructive-guard-false-deny の TS-3、TS-4、TS-5、TS-22 の 2 行）（FR1, FR2） - 期待: allow のまま

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] Existing E2E tests pass without regression

### Performance Tests

個別のシナリオはない。NFR1 を満たす。

## Security Considerations

- **許可する対:** 再走査のスキップが働くのは、`notion` MCP サーバーの `notion-create-comment`（`--mcp notion` / `--tool notion-create-comment`）の対だけ。それ以外の `--mcp` / `--tool` の対はすべて再走査される（FR1, FR6）。
- **前提:** このスキップは、`notion` MCP サーバーの `notion-create-comment` が `--args-json` をデータとしてだけ使い、シェルのコマンドとして実行しないことに依存する（前提 A1、FR6）。
- **フェイルクローズ:** 対の判定ができない形はすべて再走査する（NFR2、前提 A2）。この変更は既存の deny / ask の判定を allow に変えない。
- **Input Validation:** 対の判定は FR1 の (a)、(b) に従う。
- **Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF:** 該当なし。

## Error Handling

### Error Codes

該当なし。

### Error Flow

```
対の判定が偽 / 判定不能 → S1 アームが空集合を返す → すべての候補を再走査
```

## Performance Optimization

### Performance Goals

- 1 回の判定は、hooks.json のタイムアウト（10 秒）と、ランナーの `GUARD_TIMEOUT_SECONDS`（10 秒）に収まる（NFR1）。

### Optimization Strategies

- `scan_budget` と `MAX_SHELL_PAYLOAD_EXPANSIONS` は変えない（NFR1）。

### Caching Strategy

該当なし。

## Success Criteria

- [ ] AC-1（FR1, FR4）: 変更後のフックで、TS-1 のコマンドが deny になる。変更前のフックでは同じケースが allow になる。
- [ ] AC-2（FR1, FR4）: TS-3〜TS-9 の境界の deny ケースが、変更後のフックですべて deny になる。
- [ ] AC-3（FR1, FR2）: 既存の allow ケース（destructive-guard-false-deny の TS-3、TS-4、TS-5、TS-22 の 2 行）が allow のまま。新しい順序違いの allow ケース（TS-2）が allow になる。
- [ ] AC-4（FR2, FR3, NFR2）: `destructive-guard-cases.json` のほかの既存ケースは、期待する判定（理由 ID を固定しているケースはその理由 ID も）を保つ。`python3 em-workflow/hooks/tests/run-destructive-guard.py` が通り、既存ケースは 1 件も消されていない。
- [ ] AC-5（FR5）: FR5 に挙げた docstring とコメントが notion / notion-create-comment の対の条件を述べ、どれも「任意の静的な `mcp-bridge run --args-json` にスキップが適用される」と述べていない。
- [ ] AC-6（FR6）: このフィーチャーの SPEC と THREAT-MODEL が、許可する対と、その対が引数を実行しないという前提を述べている。`feature-docs/destructive-guard-false-deny` は変わっていない。
- [ ] All test scenarios pass

## Assumptions

- A1: `notion` MCP サーバーの `notion-create-comment` は、`--args-json` をデータとしてだけ使い、シェルのコマンドとして実行しない。
- A2: destructive-guard-false-deny の A6（フェイルクローズ）に従い、`--mcp` / `--tool` の語の重複、クォートされた値、`--opt=value` の形は判定不能として扱い、再走査する。対の一致は語の順序に依存しない。
- A3: `printf '%s\n'` アームは対象外で、変えない。
- A4: 新しいケースに `rule` の要素は要らない。`.claude/rules/hook-tests.md` が `rule` を求めるのは、再帰削除とほかの check を組み合わせたケースだけ。

いずれも覆せる。

## Open Questions

なし。

## References

- `feature-docs/mcp-bridge-exec-tool-rescan/REQUIREMENTS.md`
- `feature-docs/destructive-guard-false-deny/SPEC.md`、`feature-docs/destructive-guard-false-deny/THREAT-MODEL.md`（編集しない）
- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
