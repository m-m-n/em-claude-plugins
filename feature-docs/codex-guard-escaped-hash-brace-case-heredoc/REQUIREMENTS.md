---
title: "codex-guard-escaped-hash-brace-case-heredoc"
created_date: 2026-10-24
status: draft
---

# codex-guard-escaped-hash-brace-case-heredoc - 要件定義書

## 1. 概要

### 1.1 背景

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）のコマンド列 p の読みでは、次の形が判定不能（`_Undecidable`）になり、後ろの対話コマンドを検査しない。feature `codex-guard-procsub-in-wordlist` で zsh の `for name (words)` の語一覧の語の先頭のプロセス置換を p として読むようにしたため、語一覧の中でもこの形が起きるようになった。素の `$(...)` では変更前から同じ。

- `#` のコメント判定が直前 1 文字（`s[j - 1]`）だけを見るため、エスケープした空白（`\ `）や継続行の後の `#` もコメントの始まりと読む。改行が無いと判定不能になる
- zsh の波括弧形式の `case x { ... }` は `case without in`、ヒアドキュメントは `heredoc in a substitution` として判定不能になる

あわせて、w 分岐のコメントと docstring の「The start of a word is a state kept while reading and never looked up backward」が、`#` の判定まで状態で決めているように読める（実際は直前 1 文字）。

### 1.2 目的

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）の置換の読み（`_skip_substitution`）で、エスケープした文字や継続行の後の `#` をコメントの始まりと読み違えて判定不能になり、後ろの対話コマンド（`python3 -i` など）を拒否しない漏れ（fail-open）を塞ぐ
- zsh の波括弧形式の `case x { ... }` を置換の中で読み、閉じ位置を確定して後ろの対話コマンドを検査できるようにする
- ヒアドキュメントの扱いは今の rule 8（case 文の中は判定不能で silent）のまま保つ
- docstring とコメントを実際の `#` の判定と波括弧形式の case の読みに合わせる

### 1.3 スコープ

対象:

- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` の `_skip_substitution` の `#` の判定、波括弧形式の case の読み、docstring とコメント
- `tests/test_codex_hook_interactive_guard.py` の `CASES` と docstring の文言を固定しているテスト

対象外（A7）:

- in 形式のパターン位置の `}` による閉じ（zsh 5.9 は受理するが今の読みのまま）
- メインの読みの `)` 救済 case 印（既存 870 行の既知の見逃し A9 は silent のまま）
- `)`・`<`・`>` の直後の `#` の読み

## 2. ビジネス要件

### 2.1 ビジネス目標

- 置換の読みで `#` を読み違えて判定不能になり、後ろの対話コマンドを拒否しない漏れ（fail-open）を塞ぐ
- zsh の波括弧形式の case を置換の中で読み、後ろの対話コマンドを検査できるようにする
- ヒアドキュメントの扱いは rule 8 のまま保つ
- docstring とコメントを実際の読みに合わせる

### 2.2 対象ユーザー

該当なし

### 2.3 期待される効果

- `$( )` の中のプロセス置換やコマンド列に、エスケープした空白の後の `#` や波括弧形式の case を書いた場合も、後ろの対話コマンドを拒否する
- 拒否漏れ（fail-open）で無人実行が入力待ちで止まることが、上の形では起きない

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧

- FR1: エスケープした文字と継続行の後の # の判定
- FR2: 波括弧形式の case の開始
- FR3: 波括弧形式の case の閉じ
- FR4: 波括弧形式の case の項目本体の { } 群の深さ
- FR5: 算術コマンドの読み直しでの状態の復元
- FR6: ヒアドキュメントは今のまま
- FR7: docstring とコメントの更新
- FR8: テストの追加と更新
- FR9: 両コピーの同一性

### 4.2 機能詳細

#### FR1: エスケープした文字と継続行の後の # の判定

**説明**: `_skip_substitution` の中で、`#` がコメントを始めるのは、直前の文字が空白・タブ・改行・`;`・`&`・`|`・`(` のどれかで、かつその文字がエスケープされていない（バックスラッシュの対の 2 文字目でない）ときだけとする。

**ビジネスルール**:
- 継続行（バックスラッシュの直後の改行）は判定の上で透明とし、継続行の前の文字で決める（`: a\<改行>#x` の `#` は語の文字、`: \<改行>#x` の `#` はコメントの始まり）
- エスケープした空白・タブ・`;`・`&`・`|`・`(` の後の `#` は語の文字とする
- 対象は `#` の判定をしている全箇所: コマンド列 p と項目本体 8 の語の始まりの判定（現 2701 行）と一般のコメント判定（現 3004 行）、パターン 6 と群 g（現 2903 行）、語一覧 w の最も外側の項目（現 2998 行）
- case 文の待ちの段（1・3・4・5・7、現 2771 行）も同じ条件に揃える
- `)` の直後（rule 3 を含む）・`<`・`>` の直後の `#` の読みは今のまま変えない

#### FR2: 波括弧形式の case の開始

**説明**: case 文の対象の後の in を待つ段（phase 3）で、継続行を除いた文字で単独の語の `{`（続く文字が空白・タブ・改行、または入力の終わり）を in の代わりとして受け付け、その case 文を波括弧形式としてパターン位置（phase 4）へ進める。

**ビジネスルール**:
- 引用・エスケープした `{` や、単独の語でない `{` は今のまま case without in で判定不能とする
- in 形式の読みは変えない

#### FR3: 波括弧形式の case の閉じ

**説明**: 波括弧形式の case 文は次で閉じる。

- (a) パターン位置で単独の語の `}`（引用・エスケープしていないもの）
- (b) パターン位置で単独の語の `esac`（zsh 5.9 の実測で受理）
- (c) 項目本体のコマンド位置の単独の `}` で、その項目本体の中で開いている `{ }` 群の深さが 0 のとき

**ビジネスルール**:
- 閉じた後は、esac で閉じたときと同じく case 文を持つリストがコマンド位置になる
- 引用・エスケープした `}` や `esac` はパターンを始める（パターン位置）か普通の語（本体）として読む

#### FR4: 波括弧形式の case の項目本体の { } 群の深さ

**説明**: 波括弧形式の case 文ごとに、項目本体のリストそのもので読んだコマンド位置の単独の `{` で深さを 1 上げ、コマンド位置の単独の `}` で深さが 1 以上なら 1 下げる。

**ビジネスルール**:
- 引用・エスケープした括弧、`${ }`・置換・算術・語の括弧の中の括弧、本体の中で開いた入れ子のリスト（サブシェル、置換、入れ子の case 文）の中の括弧は数えない
- 入れ子の case 文（in 形式・波括弧形式とも）は自分の状態を持ち、外側の case 文の深さと混ざらない

**エラーケース**:
- 深さが 1 以上のまま項目の終端（`;;` `;&` `;|` `;;&`）を読んだら判定不能とする
- 波括弧形式の項目本体のコマンド位置の `esac` は判定不能とする（zsh 5.9 の実測で parse error）

#### FR5: 算術コマンドの読み直しでの状態の復元

**説明**: 波括弧形式かどうかと `{ }` 群の深さ（FR2〜FR4 で足す状態）は、算術コマンド `((` の読み直し（rule 9）で `((` の時点の値に戻す。

#### FR6: ヒアドキュメントは今のまま

**説明**: ヒアドキュメントの読みは rule 8 のまま変えない。

**ビジネスルール**:
- case 文の中（波括弧形式を含む）の `<<` は判定不能で silent
- case 文の外の `<<` は改行が来るまで保留する
- 既存 CASES の 1050・1293・1298〜1300・1305 行は silent のまま

#### FR7: docstring とコメントの更新

**説明**: `_skip_substitution` の docstring（rule 2 の case 文の開閉、判定不能になる形の一覧、語一覧 w の `#` と語の始まりの説明）と、w の状態を進める箇所・w 分岐・`#` の判定箇所のコメントを、実際の `#` の判定（FR1）と波括弧形式の case の読み（FR2〜FR5）に合わせる。

**ビジネスルール**:
- 判定不能の一覧から「no `in` after the subject (zsh's brace form included)」の波括弧形式の部分を外し、波括弧形式で判定不能になる形（FR4 の 2 つ）を加える
- 「The start of a word is a state kept while reading and never looked up backward」は、`#` の判定を含めて実際と食い違わない文にする

#### FR8: テストの追加と更新

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に再現手順 2・3・4 の入力（deny）と、FR1〜FR6 の境界の入力を追加し、両コピーに流す。

**ビジネスルール**:
- 既存行 1051（zsh の `case x { x) :;; }` の形）を deny に変え、ラベルを読める形に合わせる
- docstring の文言を固定しているテスト（`UNDECIDABLE_MARKERS`、`WORD_LIST_PROCESS_SUBSTITUTION_MARKERS` など）を FR7 の文に合わせる

#### FR9: 両コピーの同一性

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更で直し、バイト単位で同一に保つ。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR1（線形の読み）: 置換の読みは 1 回の前向きの走査のまま、全体の仕事量を文字列の長さの定数倍に保つ。`#` の判定に後ろ向きの探索を足すときも、1 文字あたり定数の仕事に収める

### 5.2 セキュリティ要件

該当なし

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR4（version を触らない）: プラグインの version は変更しない（`.claude/rules/core-plugin-version-bump.md`）

### 5.5 互換性要件

- NFR2（既存の判定の維持）: CASES の既存行は 1051 行を除いて期待する判定を変えない。既存の deny / ask・silent の行を消さない
- NFR3（置換の中身は判定しない契約）: 置換の中身のコマンドは判定せず、閉じ位置だけを読む契約を保つ。閉じ位置が確定しないときは判定不能で、確定済みのコマンドだけを検査する（silent の契約）

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 両コピーを同じ変更で直し、バイト単位で同一に保つ（FR9）
- プラグインの version は変更しない（NFR4）

### 9.2 ビジネス上の制約

該当なし

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-escaped-hash-brace-case-heredoc/**`
- `test-docs/codex-guard-escaped-hash-brace-case-heredoc/**`

`feature-docs/codex-guard-escaped-hash-brace-case-heredoc/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-escaped-hash-brace-case-heredoc/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-escaped-hash-brace-case-heredoc/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-escaped-hash-brace-case-heredoc/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-escaped-hash-brace-case-heredoc/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

- 項目本体のコマンド位置の `}`（深さ 0）で波括弧形式の case 文が閉じる読みは、zsh の文法（本体が esac で閉じない以上、閉じは `}`）からの推定で、実測していない。TS-13 は `zsh -c` で包まない形にし、zsh が受け付けない場合も誤拒否は実行されない文字列に限られる（A3）

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1（FR1）: 再現手順 2 の `zsh -c 'echo "$(for x (<(: \ #x)) { :; })"; python3 -i'` を deny する
- [ ] AC-2（FR1）: 再現手順 3 の `zsh -c 'echo "$(: \ #x)"; python3 -i'` を deny する
- [ ] AC-3（FR2, FR3）: 再現手順 4 の `zsh -c 'echo "$(for x (<(case x { x) :;; })) { :; })"; python3 -i'` を deny する
- [ ] AC-4（FR1）: 継続行の前が語の文字なら `#` は語の文字、空白なら `#` はコメントの始まりとして読む。エスケープした `;`・`&`・`|`・`(` の後の `#` も語の文字として読む。パターン・項目本体・語一覧の最も外側の項目でも同じ
- [ ] AC-5（FR2, FR3, FR4）: 波括弧形式の case 文をパターン位置の `}`・`esac`、項目本体の深さ 0 の `}` で閉じ、本体の `{ }` 群・引用した括弧・引数の位置の `}`・入れ子の case 文を閉じと取り違えない
- [ ] AC-6（FR4, FR6）: 波括弧形式の本体の `esac`、深さ 1 以上での項目の終端、閉じない波括弧形式、波括弧形式の中のヒアドキュメントは判定不能（silent）
- [ ] AC-7（FR5）: 算術コマンドの読み直しを挟んでも波括弧形式の case 文を正しく閉じる
- [ ] AC-8（FR6, FR8, NFR2）: 既存 CASES 1051 行は deny、1050・1293・1298〜1300・1305 行は silent。それ以外の既存行の判定は変わらない
- [ ] AC-9（FR7, FR8）: docstring とコメントが実際の `#` の判定と波括弧形式の case の読みを述べ、文言を固定するテストが通る
- [ ] AC-10（FR8, FR9）: `python3 -m unittest tests.test_codex_hook_interactive_guard` が両コピーで通り、両コピーがバイト単位で同一

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1（AC-1）deny: `zsh -c 'echo "$(for x (<(: \ #x)) { :; })"; python3 -i'`
- [ ] TS-2（AC-2）deny: `zsh -c 'echo "$(: \ #x)"; python3 -i'`
- [ ] TS-3（AC-3）deny: `zsh -c 'echo "$(for x (<(case x { x) :;; })) { :; })"; python3 -i'`
- [ ] TS-4（AC-5, AC-8）deny: `echo "$(case x { x) :;; })"; python3 -i`（既存 1051 行の変更）
- [ ] TS-5（AC-4）deny: `echo "$(: a\<改行>#x)"; python3 -i`（語の文字の後の継続行の後の `#` は語の文字）
- [ ] TS-6（AC-4）silent: `zsh -c` で `printf x \<改行># )"; python3 -i; echo "<改行>)` を置換に入れた形（空白の後の継続行の後の `#` はコメントのままで、コメントの中の `)` で閉じない）
- [ ] TS-7（AC-4）deny: `echo "$(: a\;#x)"; python3 -i`（エスケープした `;` の後の `#` は語の文字）
- [ ] TS-8（AC-4）deny: `echo "$(case x in x) : \ #y;; esac)"; python3 -i`（項目本体）
- [ ] TS-9（AC-4）deny: `echo "$(case x in a\ #b) :;; esac)"; python3 -i`（パターン）
- [ ] TS-10（AC-4）deny: `echo "$(for x (a\ #b) { :; })"; python3 -i`（語一覧の最も外側の項目）
- [ ] TS-11（AC-8）deny: `echo "$(: >#x)"; python3 -i`（`>` の後の `#` の読みは今のまま）
- [ ] TS-12（AC-5）deny: `zsh -c 'echo "$(case x { x) :;; esac)"; python3 -i'`（パターン位置の `esac` で閉じる）
- [ ] TS-13（AC-5）deny: `echo "$(case x { x) :; })"; python3 -i`（項目本体の深さ 0 の `}` で閉じる）
- [ ] TS-14（AC-5）deny: `echo "$(case x { x) { :; };; })"; python3 -i`（本体の `{ }` 群は閉じでない）
- [ ] TS-15（AC-5）deny: `echo "$(case x { x) echo "}" '{' \{;; })"; python3 -i`（引用・エスケープした括弧は数えない）
- [ ] TS-16（AC-5）deny: `echo "$(case x { x) echo };; })"; python3 -i`（引数の位置の `}` は閉じない）
- [ ] TS-17（AC-5）deny: `echo "$(case x { x) case y in y) :;; esac;; })"; python3 -i`（波括弧形式の中の in 形式）
- [ ] TS-18（AC-5）deny: `echo "$(case x in x) case y { y) :;; };; esac)"; python3 -i`（in 形式の中の波括弧形式）
- [ ] TS-19（AC-6）silent: `echo "$(case x { x) cat <<E<改行>body<改行>E<改行>;; })"; python3 -i`（波括弧形式の中のヒアドキュメント）
- [ ] TS-20（AC-6）silent: `echo "$(case x { x) :;;"; python3 -i`（閉じない波括弧形式）
- [ ] TS-21（AC-6）silent: `echo "$(case x { x) :; esac)"; python3 -i`（波括弧形式の本体の `esac`）
- [ ] TS-22（AC-6）silent: `echo "$(case x { x) { :;; })"; python3 -i`（深さ 1 以上での項目の終端）
- [ ] TS-23（AC-5）silent: `echo "$(case x "{" x) :;; })"; python3 -i`（引用した `{` は in の代わりにならない）
- [ ] TS-24（AC-8）silent: `echo "$(case x { x) python3 -i;; })"`（置換の中身は判定しない）
- [ ] TS-25（AC-7）deny: `echo "$(case x { x) { ((echo a) ); };; })"; python3 -i`（算術コマンドの読み直しを挟む）
- [ ] TS-26（AC-9）pass: docstring の文言テスト（判定不能の一覧・語の始まり・語一覧の `#` の説明）
- [ ] TS-27（AC-10）pass: `python3 -m unittest tests.test_codex_hook_interactive_guard` と両コピーのバイト比較

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| p | `_skip_substitution` が読むコマンド列 |
| w | zsh の `for name (words)` の語一覧 |
| 判定不能 | `_Undecidable`。閉じ位置が確定せず、確定済みのコマンドだけを検査する |
| silent | フックが判定を出さず無出力で終わること |
| 波括弧形式の case | zsh の `case x { ... }` の形 |
| 継続行 | バックスラッシュの直後の改行 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 質問 requirement.brace-case-heredoc-handling: 回答 read_brace_case_keep_heredoc（batch の Codex 相談、記録上は前提）。波括弧形式の case を読み、ヒアドキュメントは rule 8 のまま判定不能で silent（A1）

### 14.2 未確認・保留事項

- [ ] 項目本体のコマンド位置の `}`（深さ 0）で波括弧形式の case 文が閉じることは実測していない（A3）

### 14.3 前提

- A1: 質問 requirement.brace-case-heredoc-handling の回答（read_brace_case_keep_heredoc、batch の Codex 相談、記録上は前提）に従う: 波括弧形式の case を読み、ヒアドキュメントは rule 8 のまま判定不能で silent
- A2: 前回の前提 A3（波括弧形式では esac は閉じ語でない）は回答の zsh 5.9 実測で置き換える: パターン位置の esac は閉じ、項目本体のコマンド位置の esac は parse error なので判定不能とする
- A3: 項目本体のコマンド位置の `}`（深さ 0）で波括弧形式の case 文が閉じる読みは、zsh の文法（本体が esac で閉じない以上、閉じは `}`）からの推定で、実測していない。TS-13 は `zsh -c` で包まない形にし、zsh が受け付けない場合も誤拒否は実行されない文字列に限られる
- A4: 深さ 1 以上で項目の終端を読んだときは判定不能とする（シェルの文法で `{ }` 群の中の `;;` は構文エラー）
- A5: 波括弧形式の読みはシェルの種類に関わらず適用する（既存 1051 行は `zsh -c` で包まない形で deny に変える回答に合わせる）
- A6: `#` の判定の修正は p だけでなく、同じ直前 1 文字の判定を持つパターン・群・語一覧の最も外側の項目にも当てる（docstring が語一覧の `#` を「same start condition as in a command list」と書いているため）
- A7: 対象外: in 形式のパターン位置の `}` による閉じ（zsh 5.9 は受理するが今の読みのまま）、メインの読みの `)` 救済 case 印（既存 870 行の既知の見逃し A9 は silent のまま）、`)`・`<`・`>` の直後の `#` の読み
- A8: task_description の該当行番号（2633・2663〜2669・2394・2469・2677）は現在のファイルではずれている。現在は `#` の判定が 2701・2771・2903・2998・3004 行、case without in が 2778・2875・2898 行、heredoc in a substitution が 2695・2885・3014 行

## 15. 参考資料

- `feature-docs/codex-guard-procsub-in-wordlist/reviews/round1.yaml`（ブランチ `em-workflow/codex-guard-procsub-in-wordlist/integration`）の `evaluation.round_summary`
- `.claude/rules/core-plugin-version-bump.md`
