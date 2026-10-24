---
title: "codex-guard-funcname-anon-always"
created_date: 2026-10-24
status: draft
---

# codex-guard-funcname-anon-always - 要件定義書

## 1. 概要

### 1.1 背景
codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）の `$( )` の中の読み（`_skip_substitution`）で、feature codex-guard-brace-case-group-depth の FR3 / FR2 が 2 件の拒否漏れの回帰（判定不能による無出力）を生んだ。

### 1.2 目的
この 2 件の回帰を解消し、再現手順 2〜5 を deny にする。

### 1.3 スコープ
- 対象: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` の `_skip_substitution` の読み、その docstring とモジュールの頭部の状態のコメント、`tests/test_codex_hook_interactive_guard.py`
- 対象外: 名前付きの関数定義（`name()`、`function name`）の本体を閉じた `}` の読みと、トップレベルの読み（`_skip_substitution` の外）（A5）

## 2. ビジネス要件

### 2.1 ビジネス目標
- codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）の `$( )` の中の読み（`_skip_substitution`）で、feature codex-guard-brace-case-group-depth の FR3 / FR2 が生んだ 2 件の拒否漏れの回帰（判定不能による無出力）を解消し、再現手順 2〜5 を deny にする

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 再現手順 2〜5 が deny になる

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | 2 つ目以降の関数名の後の語を名前として読む | `function` の頭部で 2 つ目以降の名前を読んだ後の語を名前として読む |
| FR2 | 最初の関数名の直後の扱いは変えない | 最初の名前の直後の語の読みを今のまま保つ |
| FR3 | 匿名関数の本体を閉じた } の後を引数として読む | 匿名関数の本体を閉じた `}` の後の語を引数として読む |
| FR4 | 匿名関数の引数の位置の単独の } は最も内側の開いた { 群を閉じる | 引数の位置の単独の `}` で最も内側の `{` 群を閉じる |
| FR5 | 既存の always の予約語の読みを保つ | 匿名関数の本体でない `{` 群の後の `always` は今どおり予約語 |
| FR6 | 両コピーの同一性 | 両コピーを一緒に直し、バイト単位で同一に保つ |
| FR7 | docstring とコメントを読みに合わせる | docstring・コメント・TestSubstitutionSkipDocumentation の期待文字列を書き換える |

### 4.2 機能詳細

#### FR1: 2 つ目以降の関数名の後の語を名前として読む

**説明**: `$( )` の中のどの一覧でも、`function` の頭部で 2 つ目以降の名前を読んだ後は、単独の `{`、単独の `}`、空の `()`、区切り（`;` `&` `|` 改行と一覧の閉じ）以外の語をすべて名前として読む。予約語、頭部語（`function` `for` `select` `coproc` `repeat`）、`case`、`esac`、`[[`、`always` もここでは名前になる。名前の状態とコマンド位置は保ち、後の `{` または空の `()` が頭部を終える。`function f g case { :; }` は 3 つの名前を持つ定義として読む。

#### FR2: 最初の関数名の直後の扱いは変えない

**説明**: 最初の名前の直後の語の読み（codex-guard-brace-case-group-depth の SPEC A-4）は今のまま保つ。FR1 が変えるのは 2 つ目の名前を読んだ後の語だけ。語の始まりにならない文字（空でない `(`、`<` `>`、コメントの `#`）の読みも今のまま。

#### FR3: 匿名関数の本体を閉じた } の後を引数として読む

**説明**: 匿名関数の 3 つの形（`function { ...; }`、`function () { ...; }`、`() { ...; }`）の本体を閉じた `}` では、どの一覧でも群を閉じた状態（HEAD_GROUP_CLOSED）を立てない。その後、次の区切り（`;` `&` `|` 改行）または一覧の閉じ（置換やサブシェルの `)`）までの語はすべて匿名関数の引数として読む。`always`、`{`、`case`、`esac`、予約語、頭部語はどれも普通の語で、何も開かず何も閉じない。コマンド位置にもならない。コマンド位置の `}` と、波括弧形式の項目の本体の引数の位置の `}` の両方が対象。

#### FR4: 匿名関数の引数の位置の単独の } は最も内側の開いた { 群を閉じる

**説明**: 匿名関数の引数の位置にある、引用もエスケープもされていない単独の `}` は、その一覧で開いている最も内側の `{` 群をどの一覧でも閉じる。閉じた群が普通の `{` 群なら、その `}` は群を閉じた `}` で、直後の単独の `always` は予約語になる（HEAD_GROUP_CLOSED）。閉じた群が外側の匿名関数の本体なら、外側の匿名関数の引数として読み続ける（FR3）。引用した `"}"`、エスケープした `\}`、語の一部の `}`（`a}` `}a`）は引数のまま。

#### FR5: 既存の always の予約語の読みを保つ

**説明**: 匿名関数の本体でない `{` 群を閉じた `}` の直後の単独の `always` は今どおり予約語で、次の語はコマンド位置になる。`{ :; } always { ... }` の既存の silent の行と、FR2（codex-guard-brace-case-group-depth）の always の行はすべて今の判定のまま。

#### FR6: 両コピーの同一性

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更の中で一緒に直し、バイト単位で同一に保つ。

#### FR7: docstring とコメントを読みに合わせる

**説明**: `_skip_substitution` の docstring（rule 1 の一覧の状態、rule 5 の引数の位置の `}`、rule 6 の関数名と group-closing `}` と always、rule 7 の頭部の状態の集合、rule 9 の読み直しで戻す状態）と、モジュールの頭部の状態のコメント（HEAD_* 定数の前）を、FR1〜FR4 の読みに合わせて書き換える。docstring の文言を固定している TestSubstitutionSkipDocumentation の期待文字列も、同じ変更の中で新しい文言に合わせる。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1: 読みは線形時間のまま。再帰を使わない（TestNoRecursion）。多数の匿名関数や多数の名前が並ぶ入力も、既存の DEPTH の行と同じ時間制限の中で読める。

### 5.2 正しさの要件
- NFR2: 算術コマンドの読み直し（rule 9）では、この変更で増える状態（2 つ目以降の名前の状態、匿名関数の本体の印、開いた `{` 群の情報）も `((` の時点の値に戻す。

### 5.3 依存の要件
- NFR3: テストは標準ライブラリの unittest だけを使い、外部パッケージを使わない。ガードのランタイムも今の制約（TestStaticConstraints）を守る。

### 5.4 リリースの要件
- NFR4: プラグインの version は変えない（main への push 時に Actions が patch を上げる）。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 読みは線形時間で、再帰を使わない（NFR1）
- 標準ライブラリだけを使う（NFR3）
- 両コピーはバイト単位で同一（FR6）

### 9.2 ビジネス上の制約
- プラグインの version は変えない（NFR4）

### 9.3 スケジュール制約
なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-funcname-anon-always/**`
- `test-docs/codex-guard-funcname-anon-always/**`

`feature-docs/codex-guard-funcname-anon-always/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-funcname-anon-always/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-funcname-anon-always/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-funcname-anon-always/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-funcname-anon-always/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 再現手順 2 `zsh -c 'echo "$(function f g case { :; })"; python3 -i'` が deny になる
- [ ] AC2: 再現手順 3 `zsh -c 'echo "$(function { :; } always case x)"; python3 -i'` が deny になる
- [ ] AC3: 再現手順 4（`zsh -c` の本文が `echo "$(function { :; } always case x in x)"; python3 -i; ";; esac)"`）が deny になる
- [ ] AC4: 再現手順 5（`zsh -c` の本文が `echo "$(function { :; } always { case y in y) echo '"; python3 -i; "';; esac; })"`）が deny になる
- [ ] AC5: 再現手順 3〜5 と同じ形を `function () { :; }` と `() { :; }` で書いた入力も deny になる
- [ ] AC6: 再現入力と FR1〜FR5 の行を `tests/test_codex_hook_interactive_guard.py` の CASES に `(期待する判定, ラベル, コマンド)` で追加し、両コピーに流して通る
- [ ] AC7: CASES の既存の行（`{ :; } always { ... }` の silent の行を含む）と既存のテストクラスはすべて今の判定のまま通る
- [ ] AC8: 両コピーがバイト単位で同一（TestCopies が通る）
- [ ] AC9: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通る

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
| ID | 入力 | 期待 | 対象 |
|----|------|------|------|
| TS1 | `zsh -c 'echo "$(function f g case { :; })"; python3 -i'` | deny | FR1, AC1 |
| TS2 | 2 つ目以降の名前の後の予約語・頭部語・`[[`・`esac`・`always`（例: `function f g if {`、`function f g for {`、`function f g [[ {`、`function f g always {`）を置いた `$( )` の後の `python3 -i` | deny | FR1 |
| TS3 | 最初の名前の直後の `case`（SPEC A-4 の読み）の既存の行、`function a b { ... }`・`function a b () { ... }`・`function a b ((echo a) ) { ... }` の既存の行 | 既存の判定のまま | FR2, FR5 |
| TS4 | 再現手順 3〜5 の 3 入力 | deny | FR3, AC2, AC3, AC4 |
| TS5 | 再現手順 3〜5 の `function { :; }` を `function () { :; }` と `() { :; }` に置き換えた入力 | deny | FR3, AC5 |
| TS6 | 波括弧形式の case の項目の本体で、匿名関数の本体を閉じた `}` の後の `always` が深さを上げない形（quoted_launch_in_a_later_item 系で、always 群として読むと閉じを誤る形） | deny | FR3 |
| TS7 | `quoted_launch_in_a_later_case("{ function { :; } }" + " always")` の形: 匿名関数の引数の位置の `}` が外側の普通の `{` 群を閉じ、その直後の `always` は予約語で、次の `{` はコマンド位置 | silent | FR4 |
| TS8 | `echo "$(function { function { :; } } always { case y in y) echo '"; python3 -i; "';; esac; })"` の形: 引数の位置の `}` が外側の匿名関数の本体を閉じ、`always` 以降も外側の引数として読む | deny | FR4 |
| TS9 | 匿名関数の引数の位置の引用した `"}"`、エスケープした `\}`、`a}`、`}a` | 引数のまま（閉じの位置が変わらない） | FR4 |
| TS10 | 匿名関数の引数の後の区切りの後の `always` は予約語にならない（`function { :; } x; always ...`） | deny | FR3, FR5 |
| TS11 | DEPTH 個の匿名関数を並べた形と、DEPTH 個の名前の後に `case` を置いた形 | deny（時間内） | NFR1 |
| TS12 | 匿名関数や 2 つ目以降の名前の後に算術コマンドの読み直しが起きる形（`function a b ((echo a) ) case ...`、`function { :; } ((echo a) ) always ...`） | 既存の判定のまま | NFR2 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 匿名関数 | `function { ...; }`、`function () { ...; }`、`() { ...; }` の 3 つの形 |
| HEAD_GROUP_CLOSED | 群を閉じた状態。直後の単独の `always` が予約語になる |
| 頭部語 | `function` `for` `select` `coproc` `repeat` |
| 区切り | `;` `&` `\|` 改行と一覧の閉じ |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 匿名関数の引数の位置の単独の `}`（answer requirement.anon-args-close-brace、batch policy record_as_assumption）: A1 として記録
- [x] デザインステップ（answer design-step.decision、decide_autonomously）: UI の変更が無いため省略

### 14.2 未確認・保留事項

以下は前提として置いた事項（いずれも reversible）。

- [ ] A1: 匿名関数の引数の位置にある引用されていない単独の `}` は、どの一覧でも最も内側の開いた `{` 群を閉じる（zsh の既定の動作）。普通の群を閉じた場合は後の `always` が予約語になり、匿名関数の本体を閉じた場合は引数の読みが続く。引用した `"}"` は引数のまま。zsh で確認済み: `zsh -fc '{ function { echo "argc=$#"; } } always { echo ALWAYS; }'` は argc=0 の後に ALWAYS を出力し、`function () {…}` と `() {…}` も同じ。`function { echo "argc=$#:$*"; } always { case` は argc=3:always { case を出力する。
- [ ] A2: 匿名関数の引数の位置の単独の `}` で、その一覧に開いた `{` 群が無いときは今の読みのまま。波括弧形式の項目の本体ではない一覧では普通の語、波括弧形式の項目の本体の深さ 0 では今どおり文を閉じる。
- [ ] A3: `() { ...; }` の形は、単純コマンドの語をまだ読んでいないコマンド位置（頭部の状態が無い位置）で読んだ空の `()` を匿名関数の頭部とする。空の `()` と `{` の間に空白・行継続の対・改行があってもよい（モジュール docstring の step 4 の読みと同じ）。
- [ ] A4: 匿名関数の引数の中の `(` は、今の引数の位置の `(` と同じく語の括弧（rule 10）として読む。リダイレクトとヒアドキュメント（rule 8）の読みも変えない。
- [ ] A5: 名前付きの関数定義（`name()`、`function name`）の本体を閉じた `}` と、トップレベルの読み（`_skip_substitution` の外）は変えない。

## 15. 参考資料

- feature codex-guard-brace-case-group-depth の SPEC（A-4、FR2、FR3）
