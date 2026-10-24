# Feature: codex-guard-funcname-anon-always

要件定義書: `feature-docs/codex-guard-funcname-anon-always/REQUIREMENTS.md`

## Overview

codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）の `$( )` の中の読み（`_skip_substitution`）で、feature codex-guard-brace-case-group-depth の FR3 / FR2 が生んだ 2 件の拒否漏れの回帰（判定不能による無出力）を解消する。再現手順 2〜5 を deny にする。

## Objectives

- `function` の頭部で 2 つ目以降の名前を読んだ後の語を名前として読み、再現手順 2 を deny にする
- 匿名関数の本体を閉じた `}` の後を引数として読み、再現手順 3〜5 を deny にする
- 既存の CASES の行と既存のテストクラスの判定を保つ

## User Stories

該当なし

## Technical Requirements

### Functional Requirements

- **FR1:** 2 つ目以降の関数名の後の語を名前として読む。`$( )` の中のどの一覧でも、`function` の頭部で 2 つ目以降の名前を読んだ後は、単独の `{`、単独の `}`、空の `()`、区切り（`;` `&` `|` 改行と一覧の閉じ）以外の語をすべて名前として読む。予約語、頭部語（`function` `for` `select` `coproc` `repeat`）、`case`、`esac`、`[[`、`always` もここでは名前になる。名前の状態とコマンド位置は保ち、後の `{` または空の `()` が頭部を終える。`function f g case { :; }` は 3 つの名前を持つ定義として読む。
- **FR2:** 最初の関数名の直後の扱いは変えない。最初の名前の直後の語の読み（codex-guard-brace-case-group-depth の SPEC A-4）は今のまま保つ。FR1 が変えるのは 2 つ目の名前を読んだ後の語だけ。語の始まりにならない文字（空でない `(`、`<` `>`、コメントの `#`）の読みも今のまま。
- **FR3:** 匿名関数の本体を閉じた `}` の後を引数として読む。匿名関数の 3 つの形（`function { ...; }`、`function () { ...; }`、`() { ...; }`）の本体を閉じた `}` では、どの一覧でも群を閉じた状態（HEAD_GROUP_CLOSED）を立てない。その後、次の区切り（`;` `&` `|` 改行）または一覧の閉じ（置換やサブシェルの `)`）までの語はすべて匿名関数の引数として読む。`always`、`{`、`case`、`esac`、予約語、頭部語はどれも普通の語で、何も開かず何も閉じない。コマンド位置にもならない。コマンド位置の `}` と、波括弧形式の項目の本体の引数の位置の `}` の両方が対象。
- **FR4:** 匿名関数の引数の位置の単独の `}` は最も内側の開いた `{` 群を閉じる。匿名関数の引数の位置にある、引用もエスケープもされていない単独の `}` は、その一覧で開いている最も内側の `{` 群をどの一覧でも閉じる。閉じた群が普通の `{` 群なら、その `}` は群を閉じた `}` で、直後の単独の `always` は予約語になる（HEAD_GROUP_CLOSED）。閉じた群が外側の匿名関数の本体なら、外側の匿名関数の引数として読み続ける（FR3）。引用した `"}"`、エスケープした `\}`、語の一部の `}`（`a}` `}a`）は引数のまま。
- **FR5:** 既存の always の予約語の読みを保つ。匿名関数の本体でない `{` 群を閉じた `}` の直後の単独の `always` は今どおり予約語で、次の語はコマンド位置になる。`{ :; } always { ... }` の既存の silent の行と、FR2（codex-guard-brace-case-group-depth）の always の行はすべて今の判定のまま。
- **FR6:** 両コピーの同一性。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更の中で一緒に直し、バイト単位で同一に保つ。
- **FR7:** docstring とコメントを読みに合わせる。`_skip_substitution` の docstring（rule 1 の一覧の状態、rule 5 の引数の位置の `}`、rule 6 の関数名と group-closing `}` と always、rule 7 の頭部の状態の集合、rule 9 の読み直しで戻す状態）と、モジュールの頭部の状態のコメント（HEAD_* 定数の前）を、FR1〜FR4 の読みに合わせて書き換える。docstring の文言を固定している TestSubstitutionSkipDocumentation の期待文字列も、同じ変更の中で新しい文言に合わせる。

### Non-Functional Requirements

- **NFR1 - 線形時間と再帰なし:** 読みは線形時間のまま。再帰を使わない（TestNoRecursion）。多数の匿名関数や多数の名前が並ぶ入力も、既存の DEPTH の行と同じ時間制限の中で読める。
- **NFR2 - 算術コマンドの読み直しで状態を戻す:** 算術コマンドの読み直し（rule 9）では、この変更で増える状態（2 つ目以降の名前の状態、匿名関数の本体の印、開いた `{` 群の情報）も `((` の時点の値に戻す。
- **NFR3 - 標準ライブラリだけを使う:** テストは標準ライブラリの unittest だけを使い、外部パッケージを使わない。ガードのランタイムも今の制約（TestStaticConstraints）を守る。
- **NFR4 - version を変えない:** プラグインの version は変えない（main への push 時に Actions が patch を上げる）。

### Assumptions

- **A1:** 匿名関数の引数の位置にある引用されていない単独の `}` は、どの一覧でも最も内側の開いた `{` 群を閉じる（zsh の既定の動作）。普通の群を閉じた場合は後の `always` が予約語になり、匿名関数の本体を閉じた場合は引数の読みが続く。引用した `"}"` は引数のまま。zsh で確認済み: `zsh -fc '{ function { echo "argc=$#"; } } always { echo ALWAYS; }'` は argc=0 の後に ALWAYS を出力し、`function () {…}` と `() {…}` も同じ。`function { echo "argc=$#:$*"; } always { case` は argc=3:always { case を出力する。（answer requirement.anon-args-close-brace、batch policy record_as_assumption）
- **A2:** 匿名関数の引数の位置の単独の `}` で、その一覧に開いた `{` 群が無いときは今の読みのまま。波括弧形式の項目の本体ではない一覧では普通の語、波括弧形式の項目の本体の深さ 0 では今どおり文を閉じる。
- **A3:** `() { ...; }` の形は、単純コマンドの語をまだ読んでいないコマンド位置（頭部の状態が無い位置）で読んだ空の `()` を匿名関数の頭部とする。空の `()` と `{` の間に空白・行継続の対・改行があってもよい（モジュール docstring の step 4 の読みと同じ）。
- **A4:** 匿名関数の引数の中の `(` は、今の引数の位置の `(` と同じく語の括弧（rule 10）として読む。リダイレクトとヒアドキュメント（rule 8）の読みも変えない。
- **A5:** 名前付きの関数定義（`name()`、`function name`）の本体を閉じた `}` と、トップレベルの読み（`_skip_substitution` の外）は変えない。

## Implementation Approach

### Architecture

対象は `_skip_substitution`（`$( )` の中の読み）、その docstring、モジュールの頭部の状態のコメント（HEAD_* 定数の前）。トップレベルの読みは変えない（A5）。

### Data Flow

該当なし

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- feature codex-guard-brace-case-group-depth: その SPEC の A-4（最初の名前の直後の読み、FR2 で保つ）と FR2（always の行、FR5 で保つ）

**External Dependencies:**
- なし（NFR3）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1〜FR5, FR7
em-review/scripts/codex-hook-interactive-guard.py     # em-workflow のコピーとバイト単位で同一（FR6）
tests/test_codex_hook_interactive_guard.py            # CASES の追加、TestSubstitutionSkipDocumentation の期待文字列（FR7）
```

## Declared Change Set

フィーチャー固有のパスは手で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリを既定で宣言する。

- `feature-docs/codex-guard-funcname-anon-always/**`
- `test-docs/codex-guard-funcname-anon-always/**`

`feature-docs/codex-guard-funcname-anon-always/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、デザインステップが生成するデザイン成果物を含む。生成と所有は各フェーズドキュメントと `references/phase-state.md` にあり、この節は引用だけで、それらのルールを再掲しない。

`test-docs/codex-guard-funcname-anon-always/**` はタスクごとのテスト記録 `test-docs/codex-guard-funcname-anon-always/{T}.tests.yaml` を含む。生成と所有は `implement-phase.md` にあり、この節は引用だけで、そのルールを再掲しない。

この 2 つの既定のエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込み。

この宣言はスーパーセットの主張で、検証時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要があり、等しい必要は無い。implement タスクを生成しないフィーチャーは `test-docs/codex-guard-funcname-anon-always/` を作らないが、宣言した `test-docs/codex-guard-funcname-anon-always/**` はその場合も正しい。宣言したパスが生成されなくても違反ではない。

## Test Scenarios

### Unit Tests

`tests/test_codex_hook_interactive_guard.py` の CASES に `(期待する判定, ラベル, コマンド)` で追加し、両コピーに流す。

- [ ] TS1: `zsh -c 'echo "$(function f g case { :; })"; python3 -i'` - deny（FR1, AC1）
- [ ] TS2: 2 つ目以降の名前の後の予約語・頭部語・`[[`・`esac`・`always`（例: `function f g if {`、`function f g for {`、`function f g [[ {`、`function f g always {`）を置いた `$( )` の後の `python3 -i` - deny（FR1）
- [ ] TS3: 最初の名前の直後の `case`（SPEC A-4 の読み）の既存の行、`function a b { ... }`・`function a b () { ... }`・`function a b ((echo a) ) { ... }` の既存の行 - 既存の判定のまま（FR2, FR5）
- [ ] TS4: 再現手順 3〜5 の 3 入力 - deny（FR3, AC2, AC3, AC4）
- [ ] TS5: 再現手順 3〜5 の `function { :; }` を `function () { :; }` と `() { :; }` に置き換えた入力 - deny（FR3, AC5）
- [ ] TS6: 波括弧形式の case の項目の本体で、匿名関数の本体を閉じた `}` の後の `always` が深さを上げない形（quoted_launch_in_a_later_item 系で、always 群として読むと閉じを誤る形） - deny（FR3）
- [ ] TS7: `quoted_launch_in_a_later_case("{ function { :; } }" + " always")` の形: 匿名関数の引数の位置の `}` が外側の普通の `{` 群を閉じ、その直後の `always` は予約語で、次の `{` はコマンド位置 - silent（FR4）
- [ ] TS8: `echo "$(function { function { :; } } always { case y in y) echo '"; python3 -i; "';; esac; })"` の形: 引数の位置の `}` が外側の匿名関数の本体を閉じ、`always` 以降も外側の引数として読む - deny（FR4）
- [ ] TS9: 匿名関数の引数の位置の引用した `"}"`、エスケープした `\}`、`a}`、`}a` - 引数のまま（閉じの位置が変わらない）（FR4）
- [ ] TS10: 匿名関数の引数の後の区切りの後の `always` は予約語にならない（`function { :; } x; always ...`） - deny（FR3, FR5）
- [ ] TS12: 匿名関数や 2 つ目以降の名前の後に算術コマンドの読み直しが起きる形（`function a b ((echo a) ) case ...`、`function { :; } ((echo a) ) always ...`） - 既存の判定のまま（NFR2）

### Integration Tests

- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る（AC9）
- [ ] `python3 -m unittest discover -s tests` が通る（AC9）
- [ ] CASES の既存の行（`{ :; } always { ... }` の silent の行を含む）と既存のテストクラスがすべて今の判定のまま通る（AC7）
- [ ] 両コピーがバイト単位で同一（TestCopies が通る）（AC8）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS9 の引用・エスケープ・語の一部の `}`
- [ ] A2: 匿名関数の引数の位置の単独の `}` で、その一覧に開いた `{` 群が無いとき - 今の読みのまま

### Performance Tests

- [ ] TS11: DEPTH 個の匿名関数を並べた形と、DEPTH 個の名前の後に `case` を置いた形 - 既存の DEPTH の行と同じ時間制限の中で deny（NFR1）

## Security Considerations

- **Input Validation:** 再現手順 2〜5 の拒否漏れの回帰を解消し、deny にする（FR1, FR3, FR4）。

## Error Handling

該当なし

## Performance Optimization

### Performance Goals

- 読みは線形時間のまま、再帰なし（NFR1）

## Success Criteria

- [ ] AC1: 再現手順 2 `zsh -c 'echo "$(function f g case { :; })"; python3 -i'` が deny になる
- [ ] AC2: 再現手順 3 `zsh -c 'echo "$(function { :; } always case x)"; python3 -i'` が deny になる
- [ ] AC3: 再現手順 4（`zsh -c` の本文が `echo "$(function { :; } always case x in x)"; python3 -i; ";; esac)"`）が deny になる
- [ ] AC4: 再現手順 5（`zsh -c` の本文が `echo "$(function { :; } always { case y in y) echo '"; python3 -i; "';; esac; })"`）が deny になる
- [ ] AC5: 再現手順 3〜5 と同じ形を `function () { :; }` と `() { :; }` で書いた入力も deny になる
- [ ] AC6: 再現入力と FR1〜FR5 の行を `tests/test_codex_hook_interactive_guard.py` の CASES に `(期待する判定, ラベル, コマンド)` で追加し、両コピーに流して通る
- [ ] AC7: CASES の既存の行（`{ :; } always { ... }` の silent の行を含む）と既存のテストクラスはすべて今の判定のまま通る
- [ ] AC8: 両コピーがバイト単位で同一（TestCopies が通る）
- [ ] AC9: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/codex-guard-funcname-anon-always/REQUIREMENTS.md`
- feature codex-guard-brace-case-group-depth の SPEC（A-4、FR2、FR3）
