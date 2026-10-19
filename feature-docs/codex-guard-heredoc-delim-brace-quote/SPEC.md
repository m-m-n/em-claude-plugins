# Feature: codex-guard-heredoc-delim-brace-quote

## Overview

codex-hook-interactive-guard が、`<<` / `<<-` の区切り語に書かれた `${ ... }` の範囲に `_remove_range_quotes` と同じ引用除去を当て、zsh と同じ区切り語を登録するようにする。区切り語の位置で zsh の読みを再現できない形（引用されていない `$'` / `$"`、閉じを確定できない `${`）は判定不能にする。要件は `feature-docs/codex-guard-heredoc-delim-brace-quote/REQUIREMENTS.md` を参照する。

## Objectives

- `<<` / `<<-` の区切り語に書かれた `${ ... }` を zsh と同じ区切り語として登録し、heredoc の終端行の後にある `python3 -i` などの対話起動を見逃さないようにする。
- 区切り語の位置で zsh の読みを再現できない形（引用されていない `$'` / `$"`）は、誤った区切り語を登録せず判定不能にする。

## User Stories

該当なし（UI の無いフックの判定ロジックの修正）。

## Technical Requirements

### Functional Requirements

- **FR1:** 区切り語の位置の `${ ... }` の引用除去 — `<<` または `<<-` の区切り語として読んでいる語の中で、引用の外にある `${` から閉じの `}` まで（FR2）の範囲に `_remove_range_quotes` と同じ規則を当てて、区切り語を登録する。範囲の外の部分の読みは変えない。
    - 引用の外のバックスラッシュは除いて次の文字を残す（バックスラッシュと改行は両方除く）。
    - `'` と `"` は除く。
    - 単引用符の中はそのまま残す。
    - 二重引用符の中のバックスラッシュは `$`、バッククォート、`"`、`\`、改行の前でだけ除く。
    - `$( ... )` と `$(( ... ))` は、中の引用も含めて書かれたまま残す。
    - それ以外の文字（入れ子の `${`、`#`、`:-` など）は書かれたまま残す。
    - 例: `${v:-"x"}`、`${v:-'x'}`、`${v:-\x}` → `${v:-x}`。`${v:-"x"y}` → `${v:-xy}`。`${v#"x"}` → `${v#x}`。`foo${v:-"x"}bar` → `foo${v:-x}bar`。`${v:-$(echo "x")}` → 書かれたまま。
- **FR2:** 区切り語の位置の `${ ... }` の閉じの探し方 — 区切り語の位置に限り、`${` の閉じの `}` は次のどれにも当たらない最初の `}` とする: 単引用符・二重引用符の中の `}`、バックスラッシュで逃がした `}`、入れ子の `${ ... }` の閉じ（深さで数える）、`$( ... )` / `$(( ... ))` の中の `}`。
    - 例: `${v:-"a}b"}` → `${v:-a}b}`、`${a:-${b:-"x"}}` → `${a:-${b:-x}}`。
    - 入力が終わるまで閉じが見つからないとき、閉じる前に入力が終わる引用があるとき、`$(` が閉じないときは判定不能にする。
    - 区切り語の位置にない `}` の探し方（`_dollar` が最初の `}` で閉じる今の読み）は変えない。
- **FR3:** 区切り語の位置の `${ ... }` の中の引用されていない `$'` / `$"` — 区切り語の位置の `${ ... }` の範囲の中に、引用の外の `$'` または `$"` があるときは判定不能にする。二重引用符の中の `$'` / `$"` と、バックスラッシュで逃がした `$` は判定不能の理由にしない（`_remove_range_quotes` と同じ）。
- **FR4:** 区切り語の位置の `${ ... }` の外の引用されていない `$'` / `$"` — `<<` / `<<-` の区切り語として読んでいる語で、`${ ... }` の外にある引用されていない `$'` または `$"` は判定不能にする。語の途中にあるもの（例: `foo$'x'`）も同じ。二重引用符の中の `$'` / `$"` と、バックスラッシュで逃がした `$` は判定不能の理由にしない。今の読み（`$'x'` を書かれたまま登録する、`$"` の `$` を落とす）は区切り語の位置では使わない。
- **FR5:** 区切り語の位置にない読みは変えない — 次の読みは変えない: 区切り語の位置にない `${ ... }`（最初の `}` で閉じて、書かれたままの文字を dynamic な語にする）。区切り語の位置にない `$'` / `$"`。`<<<` と `<` のリダイレクト先。区切り語の中の二重引用符の中にある `${ ... }`（今の引用付き単位の読み手で読む）。匿名関数の引数の `(`...`)` の範囲の引用除去（`_remove_range_quotes`）。区切り語の位置の `$( ... )`。
- **FR6:** 判定不能はチェックポイントの規則に従う — FR2 から FR4 で判定不能になった文字列は、今の `_Undecidable` の規則で扱う。最後のチェックポイントまでのコマンドは判定し、チェックポイントの無い文字列は出力しない。たとえば、区切り語の行より前の行にある `python3 -i` は、改行がチェックポイントになっていれば deny する。判定不能な区切り語と同じ行にある `python3 -i` は判定しない（silent）。
- **FR7:** 回帰テスト — `tests/test_codex_hook_interactive_guard.py` の `CASES` に、Test Scenarios の各行を `(期待する判定, ラベル, コマンド)` の形で足す。期待する判定は `deny` か `silent`。`CASES` は今のテストで 2 つのコピーの両方に流す。

### Non-Functional Requirements

- **NFR1 - 2 つのコピーの同一性:** `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更の中で一緒に直し、バイト単位で同一に保つ。
- **NFR2 - 線形時間:** 閉じの探索と引用除去は、`${ ... }` の範囲の長さに対して線形時間で行う。入れ子の `$( ... )` は 1 回だけ読み飛ばし、読み直さない。長さ上限や時間に関する今のテストは通る。
- **NFR3 - docstring の整合:** モジュール docstring の判定手順の説明を、FR1 から FR6 の読みと合わせる。docstring の marker を確かめる今のテスト（`DELIMITER_RANGE_MARKERS`、`CHECKPOINT_MARKERS`、`CHECKPOINT_PASSAGES` など）は変えずに通る。新しく書く `-> no output` の記述は、チェックポイントの規則を述べている節の中に置く。
- **NFR4 - 既存ケースの保持:** `CASES` の今の deny / silent の行は消さず、期待する判定も変えない。
- **NFR5 - 標準ライブラリのみ:** フックとテストは Python 標準ライブラリだけを使う。
- **NFR6 - version:** プラグインの version は変えない。

## Implementation Approach

### Architecture

区切り語の位置（`<<` / `<<-` の区切り語として読んでいる語）の読みだけを変える。

| 区切り語の中の形 | 読み | 要件 |
|------------------|------|------|
| 引用の外の `${ ... }` | FR2 で閉じを探し、範囲に `_remove_range_quotes` と同じ規則を当てて登録する | FR1、FR2 |
| 閉じを確定できない `${` | 判定不能 | FR2 |
| `${ ... }` の中の引用の外の `$'` / `$"` | 判定不能 | FR3 |
| `${ ... }` の外の引用されていない `$'` / `$"`（語の途中を含む） | 判定不能 | FR4 |
| 二重引用符の中の `$'` / `$"`、逃がした `$` | 判定不能の理由にしない | FR3、FR4 |
| 二重引用符の中の `${ ... }` | 今の引用付き単位の読み手で読む（変えない） | FR5 |
| `$( ... )` | 変えない | FR5 |

区切り語の位置にない `${ ... }` / `$'` / `$"`、`<<<` と `<` のリダイレクト先、匿名関数の引数の `(`...`)` の範囲の引用除去は変えない（FR5）。判定不能は今の `_Undecidable` の規則で扱う（FR6）。

### Data Flow

```
区切り語の語 → ${ の閉じを探す（FR2） → 範囲の引用除去（FR1） → 区切り語を登録
                └→ 閉じを確定できない / 引用されていない $' / $"（FR2〜FR4） → 判定不能（FR6）
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `_remove_range_quotes`: FR1 の引用除去の規則と、FR3 の判定不能の理由にしない形の基準
- `_dollar`: 区切り語の位置にない `}` の探し方（変えない）
- `_Undecidable`: 判定不能の扱い（FR6）

**External Dependencies:**
- なし（Python 標準ライブラリのみ、NFR5）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # 判定ロジックとモジュール docstring
em-review/scripts/codex-hook-interactive-guard.py     # 上とバイト単位で同一
tests/test_codex_hook_interactive_guard.py            # CASES に Test Scenarios を足す
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

各 SPEC は、フィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つをデフォルトで宣言する。

- `feature-docs/codex-guard-heredoc-delim-brace-quote/**`
- `test-docs/codex-guard-heredoc-delim-brace-quote/**`

`feature-docs/codex-guard-heredoc-delim-brace-quote/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照する（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-heredoc-delim-brace-quote/**` に含まれるもの: タスクごとのテスト記録 `test-docs/codex-guard-heredoc-delim-brace-quote/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照する（引用のみ、ルールは再掲しない）。

この 2 つのデフォルトのメンバーは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。

この宣言はスーパーセット（superset）の主張であり、verify 時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。等しい必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/codex-guard-heredoc-delim-brace-quote/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-heredoc-delim-brace-quote/**` は依然として正しい。実際には生成されないパスが宣言されていても違反にはならない。

## Test Scenarios

### Unit Tests

各シナリオを `tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で足す（FR7）。

記法: 行の並びは、フックが受け取る `tool_input.command` を改行で区切った行の並び。各行は JSON 文字列として書いており、JSON の escape を解いた文字がそのままコマンドの文字になる（`"\\"` は 1 個のバックスラッシュ、`"\t"` はタブ）。「修正前」は今のコードでの判定。

#### TS1: deny（修正前 silent）

ラベル: 区切り語の ${...} の二重引用符を除いた終端行の後の起動は deny (再現手順)
要件: FR1

```json
["zsh -c 'cat <<${v:-\"x\"}","body","${v:-x}","python3 -i'"]
```

#### TS2: silent（修正前 deny）

ラベル: 引用を除く前の ${...} の行では本文が閉じない
要件: FR1

```json
["cat <<${v:-\"x\"}","${v:-\"x\"}","python3 -i","${v:-x}"]
```

#### TS3: deny（修正前 silent）

ラベル: ${...} の単引用符を除く
要件: FR1

```json
["cat <<${v:-'x'}","${v:-x}","python3 -i"]
```

#### TS4: deny（修正前 silent）

ラベル: ${...} のバックスラッシュを除く
要件: FR1

```json
["cat <<${v:-\\x}","${v:-x}","python3 -i"]
```

#### TS5: deny（修正前 silent）

ラベル: ${...} の引用の後ろの文字はつなぐ
要件: FR1

```json
["cat <<${v:-\"x\"y}","${v:-xy}","python3 -i"]
```

#### TS6: deny（修正前 silent）

ラベル: ${v#...} の引用を除く
要件: FR1

```json
["cat <<${v#\"x\"}","${v#x}","python3 -i"]
```

#### TS7: deny（修正前 silent）

ラベル: ${...} の前後の部分はそのままつなぐ
要件: FR1

```json
["cat <<foo${v:-\"x\"}bar","foo${v:-x}bar","python3 -i"]
```

#### TS8: deny（修正前 silent）

ラベル: <<- は先頭タブを除いて ${...} の引用を除いた区切り語と比べる
要件: FR1

```json
["cat <<-${v:-\"x\"}","\t${v:-x}","python3 -i"]
```

#### TS9: deny（修正前 silent）

ラベル: ${...} の二重引用符の中の } で閉じない
要件: FR1、FR2

```json
["cat <<${v:-\"a}b\"}","${v:-a}b}","python3 -i"]
```

#### TS10: deny（修正前 silent）

ラベル: ${...} の単引用符の中の } で閉じない
要件: FR1、FR2

```json
["cat <<${v:-'a}b'}","${v:-a}b}","python3 -i"]
```

#### TS11: deny（修正前 silent）

ラベル: ${...} の逃がした } で閉じない
要件: FR1、FR2

```json
["cat <<${v:-\\}}","${v:-}}","python3 -i"]
```

#### TS12: deny（修正前 silent）

ラベル: 入れ子の ${...} の閉じで外側を閉じない
要件: FR1、FR2

```json
["cat <<${a:-${b:-\"x\"}}","${a:-${b:-x}}","python3 -i"]
```

#### TS13: deny（修正前 deny）

ラベル: ${...} の中の $( ) は引用を含め書かれたまま区切り語になる
要件: FR1、FR2

```json
["cat <<${v:-$(echo \"x\")}","${v:-$(echo \"x\")}","python3 -i"]
```

#### TS14: silent（修正前 silent）

ラベル: ${...} の中の $( ) の引用を除いた行では本文が閉じない
要件: FR1、FR2

```json
["cat <<${v:-$(echo \"x\")}","${v:-$(echo x)}","python3 -i","${v:-$(echo \"x\")}"]
```

#### TS15: deny（修正前 silent）

ラベル: ${...} の中の $( ) の } で閉じない
要件: FR1、FR2

```json
["cat <<${v:-$(echo \"}\")}","${v:-$(echo \"}\")}","python3 -i"]
```

#### TS16: deny（修正前 silent）

ラベル: ${...} の二重引用符の中の $' は判定不能にしない
要件: FR2、FR3

```json
["cat <<${v:-\"$'\"}","${v:-$'}","python3 -i"]
```

#### TS17: deny（修正前 silent）

ラベル: ${...} の逃がした $ は判定不能にしない
要件: FR2、FR3

```json
["cat <<${v:-\\$'x'}","${v:-$x}","python3 -i"]
```

#### TS18: silent（修正前 deny）

ラベル: ${...} の中の引用されていない $' は判定不能
要件: FR2、FR3

```json
["cat <<${v:-$'x'}","${v:-$'x'}","python3 -i","${v:-x}"]
```

#### TS19: silent（修正前 deny）

ラベル: ${...} の中の引用されていない $" は判定不能
要件: FR2、FR3

```json
["cat <<${v:-$\"x\"}","${v:-$\"x\"}","python3 -i"]
```

#### TS20: silent（修正前 silent）

ラベル: ${...} の閉じを確定できなければ判定不能
要件: FR2、FR3

```json
["cat <<${v:-\"a}","python3 -i"]
```

#### TS21: silent（修正前 deny）

ラベル: 区切り語の引用されていない $' は判定不能
要件: FR4

```json
["cat <<$'x'","$'x'","python3 -i","x"]
```

#### TS22: silent（修正前 deny）

ラベル: 区切り語の引用されていない $" は判定不能
要件: FR4

```json
["cat <<$\"x\"","x","python3 -i","$x"]
```

#### TS23: silent（修正前 deny）

ラベル: 区切り語の途中の引用されていない $' は判定不能
要件: FR4

```json
["cat <<foo$'x'","foo$'x'","python3 -i","foox"]
```

#### TS24: deny（修正前 deny）

ラベル: 区切り語の二重引用符の中の $' は判定不能にしない
要件: FR4

```json
["cat <<\"$'x'\"","$'x'","python3 -i"]
```

#### TS25: deny（修正前 deny）

ラベル: 区切り語の逃がした $ は判定不能にしない
要件: FR4

```json
["cat <<\\$'x'","$x","python3 -i"]
```

#### TS26: deny（修正前 deny）

ラベル: 判定不能な ${...} の区切り語より前の行の起動は deny
要件: FR6

```json
["python3 -i","cat <<${v:-$'x'}","${v:-x}","python3 -i"]
```

#### TS27: deny（修正前 deny）

ラベル: 判定不能な $" の区切り語より前の行の起動は deny
要件: FR6

```json
["python3 -i","cat <<$\"x\"","x"]
```

#### TS28: silent（修正前 silent）

ラベル: 判定不能な区切り語と同じ行の起動は判定しない
要件: FR6

```json
["python3 -i; cat <<$'x'","x"]
```

#### TS29: deny（修正前 deny）

ラベル: 区切り語でない ${...} の読みは変えない
要件: FR5

```json
["echo ${v:-\"x\"}; python3 -i"]
```

#### TS30: deny（修正前 deny）

ラベル: <<< の目標の ${...} の $' は判定不能にしない
要件: FR5

```json
["cat <<< ${v:-$'x'}; python3 -i"]
```

#### TS31: deny（修正前 deny）

ラベル: <<< の目標の $' は判定不能にしない
要件: FR5

```json
["cat <<< $'x'; python3 -i"]
```

#### TS32: deny（修正前 deny）

ラベル: 区切り語でない $" は判定不能にしない
要件: FR5

```json
["echo $\"x\"; python3 -i"]
```

#### TS33: deny（修正前 deny）

ラベル: 区切り語の二重引用符の中の ${...} の読みは変えない
要件: FR5

```json
["cat <<\"${v:-x}\"","${v:-x}","python3 -i"]
```

#### TS34: deny（修正前 deny）

ラベル: ${...} の中のバッククォートは文字のまま残す
要件: FR1、FR2

```json
["cat <<${v:-`echo x`}","${v:-`echo x`}","python3 -i"]
```

### Integration Tests

- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が成功する（AC8）
- [ ] `python3 -m unittest discover -s tests` が成功する（AC8）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases

- [ ] 閉じる前に入力が終わる `${`（TS20）: 判定不能
- [ ] 判定不能な区切り語と同じ行の起動（TS28）: silent
- [ ] `<<-` の先頭タブ（TS8）: タブを除いてから比べる

### Performance Tests

- [ ] 長さ上限や時間に関する今のテストが通る（NFR2）

## Security Considerations

- **Input Validation:** 区切り語の位置で zsh の読みを再現できない形は、誤った区切り語を登録せず判定不能にする（FR2〜FR4、FR6）。
- 上記以外: 該当なし。

## Error Handling

### Error Codes

該当なし。

### Error Flow

```
閉じを確定できない ${ / 引用されていない $' / $" → 判定不能 → 最後のチェックポイントまでを判定（FR6）
```

## Performance Optimization

### Performance Goals

- 閉じの探索と引用除去は `${ ... }` の範囲の長さに対して線形時間（NFR2）

### Optimization Strategies

- 入れ子の `$( ... )` は 1 回だけ読み飛ばし、読み直さない（NFR2）

### Caching Strategy

- 該当なし

## Success Criteria

- [ ] AC1: 再現手順 TS1 が deny になる。（FR1）
- [ ] AC2: 区切り語の位置の `${ ... }` で引用（`"`、`'`、`\`）を除いた区切り語で heredoc の本文が閉じ、終端行の後の起動が deny になる。引用を除く前の文字のままの行では本文が閉じない。`<<-` では先頭のタブを除いてから比べる。範囲の外の部分はそのままつなぐ。（FR1、TS2〜TS8）
- [ ] AC3: 区切り語の位置の `${ ... }` は、引用の中の `}`、逃がした `}`、入れ子の `${ ... }`、`$( ... )` の中の `}` では閉じない。`$( ... )` は中の引用も含めて書かれたまま区切り語になる。（FR1、FR2、TS9〜TS15、TS34）
- [ ] AC4: 区切り語の位置の `${ ... }` の中の引用されていない `$'` / `$"` と、閉じを確定できない `${` は判定不能になる（チェックポイントが無ければ silent）。二重引用符の中の `$'` と逃がした `$` は判定不能の理由にならない。（FR2、FR3、TS16〜TS20）
- [ ] AC5: 区切り語の位置の `${ ... }` の外の引用されていない `$'` / `$"` は、語の途中にあるものも含めて判定不能になる。二重引用符の中と逃がした `$` は今の読みのまま区切り語になる。（FR4、TS21〜TS25）
- [ ] AC6: 判定不能な区切り語より前のチェックポイントまでの起動は deny になり、同じ行の起動は silent になる。（FR6、TS26〜TS28）
- [ ] AC7: 区切り語の位置にない `${ ... }` と `$'` / `$"`、`<<<` のリダイレクト先、区切り語の二重引用符の中の `${ ... }` の読みは変わらない。（FR5、TS29〜TS33）
- [ ] AC8: 2 つのコピーがバイト単位で同一で、`python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` がどちらも成功する。（FR7、NFR1、NFR2、NFR3、NFR4）

## Assumptions

- A-1: 区切り語の位置の `${ ... }` の中の引用されていないバッククォートは、`_remove_range_quotes` と同じく普通の文字として扱う。閉じの探索でも特別に読まない（FR2 の列挙に入っていない）。TS34 の今の deny は変わらない。
- A-2（確認済み）: TS11 と TS15 の終端は zsh 5.9 で実測して確かめた。`${v:-\}}` は `${v:-}}` で終わり、`${v:-$(echo "}")}` は書かれたままで終わる。あわせて `${v:-"$'"}` は `${v:-$'}`、`${v:-\$'x'}` は `${v:-$x}` で終わる。
- A-3: zsh は `${v:-$'x'}` と外側の `$'x'` を `x` として読むが、回答に従って判定不能にする（これらの形は見逃しとして受け入れる）。
- A-4: 区切り語の位置にない `${v:-"a}b"}` が最初の `}` で閉じる今の読みは、このフィーチャーの範囲外として残す。
- A-5: 判定不能はチェックポイントまでを判定する。これは今の `CASES` とモジュール docstring の marker テストで固定されている。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- REQUIREMENTS.md: `feature-docs/codex-guard-heredoc-delim-brace-quote/REQUIREMENTS.md`
