---
title: "codex-guard-case-reading-fixes"
created_date: 2026-10-21
status: draft
---

# codex-guard-case-reading-fixes - 要件定義書

## 1. 概要

### 1.1 背景
codex-hook-interactive-guard（em-workflow / em-review の両コピー）の `_skip_substitution` は、`$( )` の中の case 文を次の 3 つの場面で読み違える。

- 引数の `esac` / `case`
- パターンの直後のコメント
- 行継続

### 1.2 目的
`_skip_substitution` で、`$( )` の中の case 文の読み違いをなくす。誤拒否（fail-closed）と拒否漏れ（fail-open）の両方をなくす。

### 1.3 スコープ

対象:

- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

対象外（前提 A3〜A5 を参照）:

- time のオプションの後、代入の後、リダイレクトの後の語の扱い
- メインパーサーの case の印と、`_skip_substitution` の外でのキーワードを分断する行継続の扱い
- パターンの `)` 以外の `)` の直後の `#` の読み方、および項目の本体の中の `x\<NL>#c` の読み方

## 2. ビジネス要件

### 2.1 ビジネス目標
`$( )` の中の case 文について、引数の `esac` / `case`、パターンの直後のコメント、行継続の 3 つの読み違いをなくし、誤拒否と拒否漏れの両方をなくす。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 1.1 の 3 つの場面で、誤拒否が起きない。
- 1.1 の 3 つの場面で、拒否漏れが起きない。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | コマンドの位置を状態として追跡する | 次の語がコマンドの位置にあるかを、コマンドリストごとの状態として持つ | 高 |
| FR2 | 引数の case / esac で文を開閉しない | コマンドの位置にある単独の語の case / esac だけが文を開閉する | 高 |
| FR3 | パターンの `)` の直後の `#` をコメントとして読む | 空白がなくてもコメントとして改行まで読み飛ばす | 高 |
| FR4 | 待ちフェーズで行継続を読み飛ばす | バックスラッシュと改行の対を語の始まりとして扱わない | 高 |
| FR5 | キーワードに接する行継続と分断する行継続 | 対を取り除いた文字の並びでキーワードを判定する | 高 |
| FR6 | 両コピーを同時に直す | 2 つのコピーを同じ変更で直し、バイト単位で同一に保つ | 高 |
| FR7 | docstring を更新する | `_skip_substitution` の docstring を新しい読み方に合わせる | 中 |
| FR8 | CASES に再現と派生の行を足す | TS1〜TS19 の行を CASES に足し、両コピーに流す | 高 |

### 4.2 機能詳細

#### FR1: コマンドの位置を状態として追跡する

**説明**: チャンクの中のコマンドリスト（`$(` と `(` の中、および case 文の項目の本体）ごとに、次の語がコマンドの位置にあるかを状態として持つ。直前の語の文字を後ろ向きに見る判定はやめる。

**ビジネスルール**:
- コマンドの位置になるのは次の場合。
    - リストの先頭
    - `;` `&` `|`（`&&` `||` を含む）の後
    - 改行の後
    - サブシェルの `(` の後
    - コマンドの位置にある予約語 `then` / `do` / `else` / `elif` / `if` / `while` / `until` / `time` と `!` と `{` の後
- それ以外の語の後はコマンドの位置ではない。

#### FR2: 引数の case / esac で文を開閉しない

**説明**: `case` は、コマンドの位置にある単独の語のときだけ case 文を開く。項目の本体では、`esac` はコマンドの位置にある単独の語のときだけ case 文を閉じる。

**ビジネスルール**:
- 引数の位置の `case` / `esac` は、引数の予約語の後にあるものも含め、文を開くことも閉じることもしない。

#### FR3: パターンの `)` の直後の `#` をコメントとして読む

**説明**: 項目のパターンを閉じる `)` の直後の `#` を、空白がなくてもコメントの始まりとして読み、改行まで読み飛ばす。

**ビジネスルール**:
- コメントの中の `esac` や引用符では文を閉じず、引用も始めない。

#### FR4: 待ちフェーズで行継続を読み飛ばす

**説明**: 語や `in` を待つフェーズでは、バックスラッシュと改行の対を語の始まりとして扱わずに読み飛ばし、フェーズを保つ。

**ビジネスルール**:
- 対象となるフェーズは次のとおり。
    - 対象の語の前
    - 対象の語の後
    - パターンの位置
    - 先頭の `(` の後
    - 項目の本体の開始位置

#### FR5: キーワードに接する行継続と分断する行継続

**説明**: `case` / `in` / `esac` がキーワードかどうかは、バックスラッシュと改行の対を取り除いた文字の並びで判定する。

**ビジネスルール**:
- キーワードの文字の間にある対（例: `ca\<NL>se`、`i\<NL>n`、`es\<NL>ac`）は読み飛ばしてキーワードとして読む。
- キーワードの直後の対（例: `case\<NL> x`、`in\<NL> x)`、`esac\<NL>)`）も読み飛ばし、その先の文字で単独の語かを判定する。
- 対を取り除くとキーワードにならない並び（例: `ca\<NL>sex`、`es\<NL>acx`、`x\<NL>case`）はキーワードとして読まない。
- 語の途中にある対は語を区切らない。

#### FR6: 両コピーを同時に直す

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR7: docstring を更新する

**説明**: `_skip_substitution` の docstring（フェーズの説明を含む）を、新しい読み方に合わせて書き直す。

**ビジネスルール**:
- キーワード判定のメソッドを残す場合は、その docstring も書き直す。
- `TestSubstitutionSkipDocumentation` が固定している文言は残す。

#### FR8: CASES に再現と派生の行を足す

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に、12 章の TS1〜TS19 の行を `(期待する判定, ラベル, コマンド)` の形で足す。

**ビジネスルール**:
- 行は両コピーに流す。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1: 読み取りは入力の長さに対して線形の時間で終わる。キーワードの照合が失敗した場合や、行継続の対が長く続く場合も同じ。
    - 各位置からの照合は、キーワードの文字数と、その間と直後にある対の並びだけを見る。
    - 同じ対の並びを読み直す照合の数は定数に収まる。
    - コマンドの位置の状態は、各コンテキストに定数サイズで持つ。

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2: 再帰を使わない。`_skip_substitution` から到達できるメソッドに、`_skip_substitution`・`_read_quoted_unit`・`parse`・`_remove_range_quotes` を含めない（`TestNoRecursion` と `TestSubstitutionSkipCallStructure` を通す）。
- NFR3: 標準ライブラリだけを使い、`TestStaticConstraints` の制約を守る。
- ドキュメント: FR7 のとおり。

### 5.5 互換性要件
- NFR4: プラグインの version は変えない。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 再帰を使わない（NFR2）。
- 標準ライブラリだけを使う（NFR3）。

### 9.2 ビジネス上の制約
- プラグインの version は変えない（NFR4）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-case-reading-fixes/**`
- `test-docs/codex-guard-case-reading-fixes/**`

`feature-docs/codex-guard-case-reading-fixes/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-case-reading-fixes/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-case-reading-fixes/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 再現手順 1〜3（TS1〜TS3）が期待どおりの判定になる（両コピー）。
- [ ] AC2: 派生の行 TS4〜TS19 が `CASES` に入り、両コピーに対して期待どおりの判定になる。
- [ ] AC3: 既存の `CASES` の行がすべて元の判定のまま通る。`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。
- [ ] AC4: `TestCopies` により両コピーのバイト単位の同一性が確かめられる。
- [ ] AC5: TS20〜TS22 の入力が、`TestCaseStatementsInASubstitution` と同じ規模と時間制限の中で答えを返し、後ろの起動を deny にする（NFR1）。TS20〜TS22 は、行継続の対を長く連ねた入力、キーワード照合の失敗を多数繰り返す入力、引数の予約語を長く連ねた入力。
- [ ] AC6: `python3 -m unittest discover -s tests` が通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

表記:

- `<NL>` は改行を表す。
- `\<NL>` はバックスラッシュの直後に改行が続く対（行継続の対）を表す。

### 12.1 テスト観点

#### 再現手順（TS1〜TS3）

| ID | 期待する判定 | コマンド | 内容 |
|----|--------------|----------|------|
| TS1 | silent | `echo "$(case y in x) echo if esac;; y) echo "; python3 -i;";; esac)"` | 再現手順 1 |
| TS2 | silent | `echo "$(case x in x)#; esac<NL>:;; y) printf '%s' '"; python3 -i; #';; esac)"` | 再現手順 2 |
| TS3 | deny | `echo "$(case x \<NL>in x) :;; esac)"; python3 -i` | 再現手順 3 |

#### 派生（TS4〜TS19）

| ID | 期待する判定 | コマンド | 内容 |
|----|--------------|----------|------|
| TS4 | silent | `echo "$(case y in x) echo then esac;; y) echo "; python3 -i;";; esac)"` | 引数の then（TS1 の if を then に替えた形） |
| TS5 | silent | `echo "$(case y in x) echo ! esac;; y) echo "; python3 -i;";; esac)"` | 引数の !（TS1 の if を ! に替えた形） |
| TS6 | deny | `echo "$(case x in x) echo then esac;; y) echo '"';; esac)"; python3 -i #'` | 引用がずれる形 |
| TS7 | deny | `echo "$(echo then case x in x)"; python3 -i` | 項目の本体の外の引数の case |
| TS8 | deny | `echo "$(case x in x)#)<NL>:;; esac)"; python3 -i` | パターンの直後のコメントの中の ) |
| TS9 | deny | `echo "$(case \<NL>x in x) :;; esac)"; python3 -i` | 対象の語の前の行継続 |
| TS10 | deny | `echo "$(case x in \<NL>esac)"; python3 -i` | 空の case の esac の前の行継続 |
| TS11 | deny | `echo "$(case x in \<NL>x) :;; esac)"; python3 -i` | 最初のパターンの前の行継続（現状でも deny。後退を防ぐ行） |
| TS12 | silent | `echo "$(case\<NL> x in x) echo "; python3 -i; ";; esac)"` | case の直後の行継続 |
| TS13 | silent | `echo "$(ca\<NL>se x in x) echo "; python3 -i; ";; esac)"` | case を分断する行継続 |
| TS14 | deny | `echo "$(case x in\<NL> x) :;; esac)"; python3 -i` | in の直後の行継続 |
| TS15 | deny | `echo "$(case x in x) :;; esac\<NL>)"; python3 -i` | esac の直後の行継続 |
| TS16 | deny | `echo "$(case x i\<NL>n x) :;; esac)"; python3 -i` | in を分断する行継続 |
| TS17 | deny | `echo "$(case x in x) :;; es\<NL>ac)"; python3 -i` | esac を分断する行継続 |
| TS18 | deny | `echo "$(ca\<NL>sex in x) echo "; python3 -i; ";; esac)"` | 対を取り除くと casex になり、キーワードではない。x) で置換が閉じ、引用の外の起動を拒否する |
| TS19 | silent | `echo "$(case x in es\<NL>acx) echo "; python3 -i; ";; esac)"` | 対を取り除くと esacx のパターンになり、文を閉じない |

#### 線形時間（TS20〜TS22、NFR1）

規模と時間制限は `TestCaseStatementsInASubstitution` の `DEPTH` と `TIMEOUT` に合わせる。

| ID | 期待する判定 | 入力 |
|----|--------------|------|
| TS20 | deny | 待ちフェーズ（対象の語の前、in の前、パターンの位置）とキーワードの文字の間に、行継続の対を DEPTH 個連ね、置換の後に `python3 -i` を置く |
| TS21 | deny | 項目の本体に `c\<NL>a\<NL>s\<NL>x ` のような、照合に失敗する分断された語を DEPTH 個連ね、置換の後に `python3 -i` を置く |
| TS22 | deny | 項目の本体の引数に `then ` を DEPTH 個連ねて esac で閉じ、置換の後に `python3 -i` を置く |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| コマンドの位置 | 次の語がコマンドとして読まれる位置。FR1 の条件で決まる |
| コマンドリスト | チャンクの中の `$(` と `(` の中、および case 文の項目の本体 |
| 行継続の対 | バックスラッシュと改行の対 |
| 待ちフェーズ | 語や `in` を待つフェーズ。対象の語の前、対象の語の後、パターンの位置、先頭の `(` の後、項目の本体の開始位置 |
| 誤拒否（fail-closed） | 拒否すべきでないコマンドを拒否すること |
| 拒否漏れ（fail-open） | 拒否すべきコマンドを拒否しないこと |

## 14. 確認事項

### 14.1 確認済み事項
なし

### 14.2 未確認・保留事項
なし

### 14.3 前提
- A1: コマンドの位置を状態として追跡する範囲は、チャンクの中のコマンドリスト全部（`$(` と `(` の中、および項目の本体）とする。
- A2: 予約語 `then` / `do` / `else` / `elif` / `if` / `while` / `until` / `time` と、`!` および `{` は、それ自体がコマンドの位置にあるときだけ、次の語をコマンドの位置にする。
- A3: time のオプションの後、代入の後、リダイレクトの後の語はコマンドの位置として扱わない（現状と同じ）。
- A4: メインパーサーの case の印（TS-* と A9 の行）と、`_skip_substitution` の外でのキーワードを分断する行継続の扱いは変えない。
- A5: `#` をコメントとして読む範囲は、パターンの `)` の直後だけに広げる。項目の本体の中でサブシェルや置換を閉じる `)` の直後の `#`、および本体の中の `x\<NL>#c` を今のコードがコメントと読む既存の誤読は変えない。
- A6: 既存の `CASES` の行は削除も判定の変更もしない。`TestSubstitutionSkipDocumentation` が固定している docstring の文言は残す。
- A7: プラグインの version は変えない。
- A8: zsh の extendedglob で `(x)#` を glob として読む可能性はあるが、パターンの `)` の直後の `#` は一律にコメントとして読む。

## 15. 参考資料

なし
