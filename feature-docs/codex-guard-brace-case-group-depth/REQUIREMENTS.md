---
title: "codex-guard-brace-case-group-depth"
created_date: 2026-10-24
status: draft
---

# codex-guard-brace-case-group-depth - 要件定義書

## 1. 概要

### 1.1 背景
codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）の置換の中の読み（`_Parser._skip_substitution`）で、zsh の波括弧形式の case（`case x { ... }`）の項目本体の `{ }` 群の深さが zsh の文法どおりに数えられていない。その結果、区切りを省略した `{ : }` の後ろの起動の拒否漏れ（fail-open）と、`always` 群と複数名の `function` の定義による誤拒否の回帰が起きている。

### 1.2 目的
- 波括弧形式の case の項目本体の `{ }` 群の深さを zsh の文法どおりに数える
- 区切りを省略した `{ : }` の後ろの起動の拒否漏れ（fail-open）をなくす
- `always` 群と複数名の `function` の定義による誤拒否の回帰をなくす

### 1.3 スコープ
- 対象: 置換の中の読み（`_skip_substitution` とその補助）、その docstring とコメント、`tests/test_codex_hook_interactive_guard.py`
- 対象外: 置換の外のコマンドの読み（最上位の `{ : }` を閉じない既存の挙動など）

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 の目的と同じ。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 区切りを省略した `{ : }` の後ろの起動が拒否される
- `always` 群と複数名の `function` の定義を含む入力が誤って拒否されない

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 |
|----|--------|
| FR1 | 引数の位置の単独の } をコマンド位置の } と同じに扱う |
| FR2 | always 群の { を数える |
| FR3 | 複数名の function 定義の { を数える |
| FR4 | 匿名関数の { の後は名前を続けない |
| FR5 | docstring とコメントを新しい読みに合わせる |
| FR6 | 再発を検出するテスト |

### 4.2 機能詳細

#### FR1: 引数の位置の単独の } をコマンド位置の } と同じに扱う

**説明**: 波括弧形式の case 文の項目本体のコマンド一覧そのもの（top が 8 で `braces[-1]` が None でない）で、単独で、引用もエスケープもされていない `}`（`_keyword_end(j, "}", " \t\n;&|()<>")` が一致する語の先頭）を、引数の位置で読んだときもコマンド位置の `}` と同じに扱う。

**ビジネスルール**:
- 深さが 1 以上なら 1 下げる
- 深さが 0 なら文を閉じ、文を保持する一覧をコマンド位置にする（esac と同じ）
- `{` は従来どおりコマンド位置でだけ深さを上げ、引数の位置の `{` は普通の語のまま

#### FR2: always 群の { を数える

**説明**: `{ }` 群を閉じた `}`（FR1 の引数の位置の `}` を含む。波括弧形式の文そのものを閉じた `}` は除く）の直後に、区切りを挟まず空白だけを置いて続く、単独で引用もエスケープもされていない `always`（行継続の対を除いた文字で判定）を zsh の予約語として読み、次の語をコマンド位置にする。

**ビジネスルール**:
- `always` の後の `{` は項目本体の深さを 1 上げる
- それ以外の位置の `always` は従来どおり普通の語

#### FR3: 複数名の function 定義の { を数える

**説明**: `function` の頭部で最初の名前を読んだ後、コマンド位置で普通の語になる語（`_read_command_word` が None を返す語）が続く場合は、それも名前として読み、頭部の状態（`HEAD_FUNCTION_NAME`）とコマンド位置を保つ。

**ビジネスルール**:
- 単独の `{`・`}`、予約語、頭部語、空の `()`、区切りは従来どおりに読む
- `function a b { :; }` の `{` はコマンド位置で読まれ、波括弧形式の項目本体では深さを 1 上げる

#### FR4: 匿名関数の { の後は名前を続けない

**説明**: `function` の直後の単独の `{`（zsh の匿名関数。名前の位置で読み、波括弧形式の項目本体では深さを上げる既存の特例）の後の普通の語は、FR3 の追加の名前にせず、従来どおり単純コマンドの最初の語として読む。

#### FR5: docstring とコメントを新しい読みに合わせる

**説明**: `_skip_substitution` の docstring とコメントを書き換える。

**ビジネスルール**:
- rule 2 の閉じ方 (c) と深さの文（`a standalone `}` read there lowers it ...`、`and so is a `}` at an argument position`）を、項目本体のコマンド一覧そのものでは単独の `}` が引数の位置でも閉じ波括弧として読まれる、という zsh の文法に合わせる
- rule 5 の「`fi`, `done` or `}` at an argument position are ordinary words」に波括弧形式の項目本体の例外を書く
- rule 6 の「Multi-name zsh definitions ... are not considered」を FR3 / FR4 の読みに書き換え、FR2 の `always` を書く
- 頭部の状態を増やす場合は rule 7 と HEAD_* 定数の前のコメントも更新する
- reserved 分岐のコメント（「A `{` or a `}` read at a command position of the item body list itself」）を合わせる
- 引数の位置の `}` の判定を `_read_command_word` に置く場合は、その docstring（「so a word at an argument position is never one of them」）も合わせる

#### FR6: 再発を検出するテスト

**説明**: `tests/test_codex_hook_interactive_guard.py` を更新する。

**ビジネスルール**:
- CASES に再現手順 2〜4 の入力と境界の行を `(期待する判定, ラベル, コマンド)` で追加し、両コピーに流す
- 既存の TS-16 行（「波括弧形式の case TS-16 引数の位置の } は閉じない」）とその前のコメントを新しい読みに合わせて見直す（期待する判定 deny は新しい読みでも変わらない）
- `TestSubstitutionSkipDocumentation` の `BRACE_FORM_MARKERS` / `RULE_MARKERS` を FR5 の文に合わせて更新する
- 既存の deny / silent の行は消さない

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1: 読みは 1 回の前向きの走査のまま線形時間に保つ。追加する状態は一覧ごとに定数サイズで、後ろの文字を見返さない。深い入れ子・長い名前の並び・多数の `}` でも時間内に終わることをテストで確かめる。

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更で一緒に直し、バイト単位で同一に保つ。
- NFR3: plugin.json / marketplace.json の version は触らない（patch は Actions が上げる）。
- NFR4: テストは標準ライブラリの unittest だけで書き、フックはサブプロセスとして JSON を標準入力に渡して呼ぶ。

### 5.5 互換性要件
- NFR5: 変更範囲は置換の中の読み（`_skip_substitution` とその補助）に限る。置換の外のコマンドの読み（最上位の `{ : }` を閉じない既存の挙動など）は変えない。

## 6. UI/UX要件

該当なし（UI や見た目の変更がなく、フックのスクリプトの解析ロジック・docstring・テストだけの変更）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- NFR1〜NFR5 に従う

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-brace-case-group-depth/**`
- `test-docs/codex-guard-brace-case-group-depth/**`

`feature-docs/codex-guard-brace-case-group-depth/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-brace-case-group-depth/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-brace-case-group-depth/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-brace-case-group-depth/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-brace-case-group-depth/**` は依然として正しい。

### 9.5 前提

- A-1: zsh の既定（IGNORE_BRACES / IGNORE_CLOSE_BRACES が無効）では単独の `}` は引数の位置でも閉じ波括弧になる。FR1 はこの既定に合わせ、オプションの設定は見ない。
- A-2: FR1 は波括弧形式の項目本体のコマンド一覧そのものに限る。それ以外の一覧（in 形式の本体、置換・サブシェルの中、置換の外の最上位）の引数の位置の `}` は従来どおり普通の語のまま。
- A-3: FR2 と FR3 は頭部と予約語の読み（rule 5 / rule 6）の一部として、波括弧形式の項目本体に限らずすべてのコマンド一覧（p と 8）に同じく適用する。深さを数えるのは従来どおり波括弧形式の項目本体だけ。bash では `{ :; } always` も `function a b` も構文エラーなので、bash の読みを損なわない。
- A-4: FR3 で追加の名前にするのは普通の語だけ。予約語・頭部語は従来どおりコマンド位置で読む（bash の `function f case ...` の読みを保つ）。zsh で予約語が名前になる形は扱わない。
- A-5: FR2 は閉じた `}` が普通の `{ }` 群か関数本体かを区別しない（深さの数だけを持つ）。関数本体の `}` の後の `always` は zsh では引数か構文エラーで、区別しない読みを受け入れる。
- A-6: `[[ ... ]]` の中やリダイレクトの対象の位置の単独の `}` も FR1 の引数の位置として扱う。zsh ではどちらも構文エラーで、コマンドは実行されない。
- A-7: `function` / `for` / `select` / `repeat` の名前の位置の `}` は従来どおり普通の語として読む。
- A-8: 先行 feature（codex-guard-escaped-hash-brace-case-heredoc）の SPEC の TS-16 / AC-5 は書き換えず、この feature の SPEC とテストで新しい読みを定める。

## 10. 想定される課題とリスク

### 10.1 技術的課題
エッジケース:
- 深さ 0 の引数の位置の `}`（`x) echo }`）は文を閉じる。後に続く `;;` は外側の一覧の区切りとして読む
- 区切りの後の `always`（`{ :; }; always { :; }`）は予約語にならない
- 波括弧形式の文を閉じた `}` の後の `always` は予約語にならない
- `always` と `}` の間の行継続の対は省いて判定する
- 引用・エスケープされた `always`、単独の語でない `always`（`alwaysx`）は予約語にならない
- `function a "b" {` の引用した名前も名前として読み、`{` はコマンド位置
- `function { echo ... }` の匿名関数の `{` の後の語は名前にしない（FR4）
- 群が開いたままの項目の終端は従来どおり判定不能（TS-22 系の既存行）
- 算術コマンドの読み直し（rule 9）では追加する状態も `((` の時点の値に戻す

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: `zsh -c 'echo "$(case x { x) { : };; })"; python3 -i'` が deny になる（再現手順 2）。`{ :; }` にした形も deny のまま。
- [ ] AC-2: `zsh -c` の本文 `echo "$(case x { x) { :; } always { :; };; y) echo '"; python3 -i; "';; })"` が無出力になる（再現手順 3）。
- [ ] AC-3: AC-2 と同じ形で項目本体に `function a b { :; }` を書いた入力が無出力になる（再現手順 4）。
- [ ] AC-4: 引用・エスケープされた `}`、単独の語でない `}`（`a}` / `}a`）、入れ子の一覧（サブシェル・置換）の中の `}`、in 形式の本体の `}` は深さを変えず、従来の判定のまま。
- [ ] AC-5: CASES に再現入力と境界の行があり、両コピーで通る。既存の行はすべて通る（TS-16 行はラベルと説明を新しい読みに合わせて更新）。
- [ ] AC-6: docstring が FR5 の内容を述べ、docstring のマーカーのテストが通る。
- [ ] AC-7: 両コピーがバイト単位で同一（`test_the_two_copies_are_byte_identical` が通る）。
- [ ] AC-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
テストシナリオ TS-1〜TS-18 の入力と期待する判定は SPEC.md の Test Scenarios に記載する。

- [ ] 正常系: 再現手順 2〜4 の入力（TS-1〜TS-4）
- [ ] 異常系: 引用・エスケープした `}`、単独の語でない `}`（TS-11〜TS-13）
- [ ] 境界値: 深さ 0 の引数の位置の `}`、入れ子の群、`always`、複数名の `function`、匿名関数（TS-5〜TS-10、TS-14、TS-15）
- [ ] パフォーマンス: 深い入れ子と長い名前の並び（TS-16、TS-17）
- [ ] docstring: FR5 の文の有無（TS-18）

## 13. 用語定義

該当なし

## 14. 確認事項

### 14.1 確認済み事項
該当なし

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- 先行 feature codex-guard-escaped-hash-brace-case-heredoc の SPEC（A-8）
