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

task0001 でこれを直した。その review round 1 で、high の finding 2 件（2fe94b219da49a89 / 8aed11cf08b2dc4c）が見つかった。task0001 の読み方は、複合コマンドの閉じの後と関数の頭の後の予約語を引数として扱う。このため後ろの `case` が文を開かず、パターンの `)` で置換が早く閉じる。同じ原因で、ループと coproc の頭の後でも後退している。

### 1.2 目的
- `_skip_substitution` で、`$( )` の中の case 文の読み違いをなくす。
- 誤拒否（fail-closed）と拒否漏れ（fail-open）の両方をなくす。
- 複合コマンドの閉じの後、関数の頭の後、ループと coproc の頭の後の予約語をコマンドの位置で読み、task0001 で生じた後退をなくす。

### 1.3 スコープ

対象:

- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

対象外:

- time のオプションの後、代入の後、リダイレクトの後の語の扱い（A3）
- メインパーサーの case の印と、`_skip_substitution` の外でキーワードを分断する行継続の扱い（A4）
- パターンの `)` 以外の `)` の直後の `#` の読み方、および項目の本体の中の `x\<NL>#c` の読み方（A5）
- `[[ ... ]]` の中の語の読み方（A9）
- zsh で、引数の位置の `}` が閉じる読み方（A10）
- zsh の複数の名前を並べた関数定義と、関数名の妥当性の判定（A11）

## 2. ビジネス要件

### 2.1 ビジネス目標
`$( )` の中の case 文について、次の読み違いをなくし、誤拒否と拒否漏れの両方をなくす: 引数の `esac` / `case`、パターンの直後のコメント、行継続、複合コマンドの閉じ・関数の頭・ループと coproc の頭の後の予約語。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 1.1 に挙げた場面で、誤拒否が起きない。
- 1.1 に挙げた場面で、拒否漏れが起きない。

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
| FR8 | CASES に再現と派生の行を足す | TS1〜TS19、TS23〜TS40、TS44〜TS59 の行を CASES に足し、両コピーに流す | 高 |
| FR9 | 複合コマンドの閉じの後をコマンドの位置にする | `)`・`]]`・`esac`・`fi`・`done`・`}` の閉じの後の語をコマンドの位置にする | 高 |
| FR10 | 関数の頭の後をコマンドの位置にする | `name()` と `function name` の後の語をコマンドの位置にする | 高 |
| FR11 | ループと coproc の頭の後をコマンドの位置にする | `for`・`select`・`coproc`・`repeat` から始まる頭の後の語をコマンドの位置にする | 高 |

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
    - 複合コマンドの閉じ（FR9）の後
    - 関数の頭（FR10）の後
    - ループと coproc の頭（FR11）の後
- それ以外の語の後はコマンドの位置ではない。
- 語の途中で閉じるものの後は語の続きとして読み、コマンドの位置にしない。対象は、置換（`$( )`、バッククォート）の閉じ、引用の閉じ、`${ }` の閉じ、コマンドの位置で開いていない `(` を閉じる `)`。
- 予約語は、FR5 と同じく行継続の対を取り除いた文字の並びで判定する。

#### FR2: 引数の case / esac で文を開閉しない

**説明**: `case` は、コマンドの位置（FR9・FR10・FR11 によるものを含む）にある単独の語のときだけ case 文を開く。項目の本体では、`esac` はコマンドの位置にある単独の語のときだけ case 文を閉じる。

**ビジネスルール**:
- 引数の位置の `case` / `esac` は、文を開くことも閉じることもしない。
- 次の語の後にあるものも、引数の位置として同じ扱いにする。
    - 引数の位置の予約語
    - 語の中の閉じ（`$( )` や、コマンドの位置で開いていない `( )`）
    - `[[` を閉じていない `]]`
    - 引数の位置の `fi` / `done` / `}`
    - 引数の位置や引用された `for` / `select` / `coproc` / `repeat` / `function`

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
- キーワードの文字の間にある対（例: `ca\<NL>se`、`i\<NL>n`、`es\<NL>ac`）は読み飛ばし、キーワードとして読む。
- キーワードの直後の対（例: `case\<NL> x`、`in\<NL> x)`、`esac\<NL>)`）も読み飛ばし、その先の文字で単独の語かを判定する。
- 対を取り除くとキーワードにならない並び（例: `ca\<NL>sex`、`es\<NL>acx`、`x\<NL>case`）はキーワードとして読まない。
- 語の途中にある対は語を区切らない。

#### FR6: 両コピーを同時に直す

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR7: docstring を更新する

**説明**: `_skip_substitution` の docstring（フェーズの説明を含む）を、FR1〜FR5 と FR9〜FR11 の読み方に合わせて書き直す。

**ビジネスルール**:
- 今ある 1 文 "A list that goes on after a nested context closes (a substitution, a subshell, quotes, a case statement) goes on inside a word, so its state is false." も書き直しの対象。
- キーワード判定のメソッド（`_keyword_end`、`_read_command_word`）を残す場合は、その docstring も書き直す。
- 本フィーチャーより前からある、`TestSubstitutionSkipDocumentation` が固定している文言（READ_MARKERS、UNDECIDABLE_MARKERS、MODULE_SENTENCE、STALE_SENTENCE が無いこと）は残す。
- 本フィーチャーの task0001 で足した RULE_MARKERS の文言は、docstring と同じ変更の中で書き換えてよい。

#### FR8: CASES に再現と派生の行を足す

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に、12 章の TS1〜TS19、TS23〜TS40、TS44〜TS59 の行を `(期待する判定, ラベル, コマンド)` の形で足す。

**ビジネスルール**:
- 行は両コピーに流す。
- 線形時間のシナリオ（TS20〜TS22、TS41〜TS43、TS60）は `TestCaseStatementsInASubstitution` に置く。

#### FR9: 複合コマンドの閉じの後をコマンドの位置にする

**説明**: 次の閉じの後は、次の語をコマンドの位置にする。

- コマンドの位置で開いた `(` を閉じる `)`（`((` 〜 `))` を含む）
- コマンドの位置で読んだ `[[` の条件式を閉じる、単独の語の `]]`
- case 文を閉じる `esac`（項目の本体で閉じた場合も、パターンの位置で閉じた場合も）
- コマンドの位置で読んだ単独の語の `fi` / `done` / `}`

**ビジネスルール**:
- 次のものは閉じとして扱わない。
    - コマンドの位置で開いていない `(` を閉じる `)`（zsh の glob 修飾子、`<(` / `>(` など）
    - 置換の閉じ
    - `[[` を開いていない `]]`
    - 引数の位置の `fi` / `done` / `}`

#### FR10: 関数の頭の後をコマンドの位置にする

**説明**: 次の関数の頭の後は、次の語をコマンドの位置にする。

- `name()`: 単純コマンドの最初の語をコマンドの位置で読み、その直後か空白を挟んだ後に空の `()`（中は空白だけ）が続く形
- `function name`: コマンドの位置で読んだ単独の語の `function` と、その後の 1 語。名前の後に `()` があってもよい

**ビジネスルール**:
- `function` の後の名前の語は、`case` などのキーワードとして読まない。
- 引数の位置の `function` や、引用・エスケープされた `function` からは、関数の頭の状態に入らない。

#### FR11: ループと coproc の頭の後をコマンドの位置にする

**説明**: 次の頭は、コマンドの位置で読んだ単独の語から始まるときだけ扱う。語は引用・エスケープを含まないもので、FR5 と同じく行継続の対を取り除いて判定する。引数の位置の語や、引用・エスケープされた語からは、頭の状態に入らない。

**ビジネスルール**:
- `for` / `select`: 直後の 1 語は名前で、普通の語として読み、キーワードとして読まない。名前の後は次の語をコマンドの位置にする（`for x do`、`select x do`）。`for x in a b; do` の `in` とその後の語は普通の語。
- 算術の for: `for` の直後の `((` 〜 `))` の後をコマンドの位置にする（`for ((i=0;i<1;i++)) do`）。
- zsh の `for name (words)`: 名前の直後の `(` 〜 `)` は語の並びとして読み、その中の語をキーワードとして読まない。その `)` の後をコマンドの位置にする（`for x (a) {`）。
- `coproc`: 直後の語をコマンドの位置にする（`coproc {`）。その語が普通の語（NAME やコマンド名）なら、その後の語もコマンドの位置にする（`coproc NAME {`）。
- zsh の `repeat`: 直後の 1 語（回数）は普通の語として読み、キーワードとして読まない。その後の語をコマンドの位置にする（`repeat 1 {`）。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1: 読み取りは、入力の長さに対して線形の時間で終わる。キーワードの照合が失敗した場合や、行継続の対が長く続く場合も同じ。
    - 各位置からの照合は、キーワードの文字数と、その間と直後にある対の並びだけを見る。
    - 同じ対の並びを読み直す照合の数は定数に収まる。
    - コマンドの位置の状態は、各コンテキストに定数サイズで持つ。`[[` の追跡、複合コマンドの閉じの判定、関数の頭の判定、ループと coproc の頭の判定も含む。
    - 空の `()` の判定で、中の空白を読み直す回数は定数に収まる。

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
- [ ] AC1: 再現手順 1〜3（TS1〜TS3）が、両コピーで期待どおりの判定になる。
- [ ] AC2: 派生の行 TS4〜TS19 が `CASES` に入り、両コピーで期待どおりの判定になる。
- [ ] AC3: 既存の `CASES` の行が、すべて元の判定のまま通る。`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。
- [ ] AC4: `TestCopies` により、両コピーがバイト単位で同一であることが確かめられる。
- [ ] AC5: TS20〜TS22 の入力が、`TestCaseStatementsInASubstitution` と同じ規模と時間制限の中で答えを返し、後ろの起動を deny にする（NFR1）。TS20〜TS22 は次の 3 つ: 行継続の対を長く連ねた入力、キーワード照合の失敗を多数繰り返す入力、引数の予約語を長く連ねた入力。
- [ ] AC6: `python3 -m unittest discover -s tests` が通る。
- [ ] AC7: review round 1 の finding について、両コピーで次の判定になる: 8aed11cf08b2dc4c の再現例 TS23 は deny。2fe94b219da49a89 の誤拒否の形 TS32 は silent、拒否漏れの形 TS33 は deny。
- [ ] AC8: 複合コマンドの閉じと関数の頭の行（TS24〜TS31、TS34〜TS40）が `CASES` に入り、両コピーで期待どおりの判定になる。
- [ ] AC9: TS41〜TS43 と TS60 の入力が、`TestCaseStatementsInASubstitution` と同じ規模と時間制限の中で答えを返し、後ろの起動を deny にする（NFR1）。
- [ ] AC10: ループと coproc の頭の行（TS44〜TS59）が `CASES` に入り、両コピーで期待どおりの判定になる。

### 11.2 KPI
該当なし

## 12. テストシナリオ

表記:

- `<NL>` は改行を表す。
- `\<NL>` はバックスラッシュの直後に改行が続く対（行継続の対）を表す。
- 線形時間のシナリオの規模と時間制限は、`TestCaseStatementsInASubstitution` の `DEPTH` と `TIMEOUT` に合わせる。

### 12.1 テスト観点

#### 再現手順（TS1〜TS3）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS1 | silent | `echo "$(case y in x) echo if esac;; y) echo "; python3 -i;";; esac)"` | 再現手順 1 | FR1, FR2, FR8 |
| TS2 | silent | `echo "$(case x in x)#; esac<NL>:;; y) printf '%s' '"; python3 -i; #';; esac)"` | 再現手順 2 | FR3, FR8 |
| TS3 | deny | `echo "$(case x \<NL>in x) :;; esac)"; python3 -i` | 再現手順 3 | FR4, FR8 |

#### 派生（TS4〜TS19）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS4 | silent | `echo "$(case y in x) echo then esac;; y) echo "; python3 -i;";; esac)"` | 引数の then（TS1 の if を then に替えた形） | FR1, FR2, FR8 |
| TS5 | silent | `echo "$(case y in x) echo ! esac;; y) echo "; python3 -i;";; esac)"` | 引数の !（TS1 の if を ! に替えた形） | FR1, FR2, FR8 |
| TS6 | deny | `echo "$(case x in x) echo then esac;; y) echo '"';; esac)"; python3 -i #'` | 引用がずれる形 | FR1, FR2, FR8 |
| TS7 | deny | `echo "$(echo then case x in x)"; python3 -i` | 項目の本体の外の引数の case | FR1, FR2, FR8 |
| TS8 | deny | `echo "$(case x in x)#)<NL>:;; esac)"; python3 -i` | パターンの直後のコメントの中の ) | FR3, FR8 |
| TS9 | deny | `echo "$(case \<NL>x in x) :;; esac)"; python3 -i` | 対象の語の前の行継続 | FR4, FR8 |
| TS10 | deny | `echo "$(case x in \<NL>esac)"; python3 -i` | 空の case の esac の前の行継続 | FR4, FR8 |
| TS11 | deny | `echo "$(case x in \<NL>x) :;; esac)"; python3 -i` | 最初のパターンの前の行継続（現状でも deny。後退を防ぐ行） | FR4, FR8 |
| TS12 | silent | `echo "$(case\<NL> x in x) echo "; python3 -i; ";; esac)"` | case の直後の行継続 | FR5, FR8 |
| TS13 | silent | `echo "$(ca\<NL>se x in x) echo "; python3 -i; ";; esac)"` | case を分断する行継続 | FR5, FR8 |
| TS14 | deny | `echo "$(case x in\<NL> x) :;; esac)"; python3 -i` | in の直後の行継続 | FR5, FR8 |
| TS15 | deny | `echo "$(case x in x) :;; esac\<NL>)"; python3 -i` | esac の直後の行継続 | FR5, FR8 |
| TS16 | deny | `echo "$(case x i\<NL>n x) :;; esac)"; python3 -i` | in を分断する行継続 | FR5, FR8 |
| TS17 | deny | `echo "$(case x in x) :;; es\<NL>ac)"; python3 -i` | esac を分断する行継続 | FR5, FR8 |
| TS18 | deny | `echo "$(ca\<NL>sex in x) echo "; python3 -i; ";; esac)"` | 対を取り除くと casex になり、キーワードではない。x) で置換が閉じ、引用の外の起動を拒否する | FR5, FR8 |
| TS19 | silent | `echo "$(case x in es\<NL>acx) echo "; python3 -i; ";; esac)"` | 対を取り除くと esacx のパターンになり、文を閉じない | FR5, FR8 |

#### 複合コマンドの閉じ（TS23〜TS31）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS23 | deny | `echo "$(if (:) then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | finding 8aed11cf08b2dc4c の再現例。サブシェルの ) の後の then | FR1, FR9, FR8 |
| TS24 | deny | `echo "$(if [[ x ]] then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | ]] の後の then | FR9, FR8 |
| TS25 | deny | `echo "$(while (false) do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | サブシェルの ) の後の do | FR9, FR8 |
| TS26 | deny | `echo "$(if ((1)) then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | )) の後の then | FR9, FR8 |
| TS27 | deny | `echo "$(if if :; then :; fi then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | fi の後の then | FR9, FR8 |
| TS28 | deny | `echo "$(if while false; do :; done then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | done の後の then | FR9, FR8 |
| TS29 | deny | `echo "$(if { :; } then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | } の後の then | FR9, FR8 |
| TS30 | deny | `echo "$(if case y in y) :;; esac then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | esac の後の then | FR9, FR8 |
| TS31 | deny | `echo "$(if [[ x ]] { case x in x) printf '%s' '"';; esac; })"; python3 -i` | zsh の短い形。]] の後の { | FR9, FR8 |

#### 関数の頭（TS32〜TS36）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS32 | silent | `echo "$(f() { case x in x) echo "; python3 -i;";; esac; }; f)"` | finding 2fe94b219da49a89 の誤拒否の形 | FR10, FR8 |
| TS33 | deny | `echo "$(f() { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | finding 2fe94b219da49a89 の拒否漏れの形。f() の後の { | FR10, FR8 |
| TS34 | deny | `echo "$(f () { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | 空白を挟んだ () | FR10, FR8 |
| TS35 | deny | `echo "$(function f { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | function name の後の { | FR10, FR8 |
| TS36 | deny | `echo "$(function f() { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | function name() の後の { | FR10, FR8 |

#### 引数の位置の閉じ（TS37〜TS40）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS37 | deny | `echo "$(echo "$(:)" then case x in x)"; python3 -i` | 語の中の置換の閉じの後の then は引数 | FR1, FR2, FR9, FR8 |
| TS38 | deny | `echo "$(echo x(N) then case x in x)"; python3 -i` | 語の中の ( ) の閉じ（zsh の glob 修飾子）の後の then は引数 | FR1, FR2, FR9, FR8 |
| TS39 | deny | `echo "$(echo ]] then case x in x)"; python3 -i` | [[ を閉じていない ]] の後の then は引数 | FR2, FR9, FR8 |
| TS40 | deny | `echo "$(echo fi then case x in x)"; python3 -i` | 引数の位置の fi の後の then は引数 | FR2, FR9, FR8 |

#### ループと coproc の頭（TS44〜TS51）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS44 | deny | `echo "$(for ((i=0;i<1;i++)) do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | 算術の for の )) の後の do | FR11, FR8 |
| TS45 | deny | `echo "$(for x do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | for name の後の do | FR11, FR8 |
| TS46 | deny | `echo "$(coproc { case x in x) printf '%s' '"';; esac; })"; python3 -i` | coproc の後の { | FR11, FR8 |
| TS47 | deny | `echo "$(coproc c { case x in x) printf '%s' '"';; esac; })"; python3 -i` | coproc NAME の後の { | FR11, FR8 |
| TS48 | deny | `echo "$(for case in x; do :; done; echo case x in x)"; python3 -i` | for の後の名前 case はキーワードではない。後ろの引数の case も文を開かず、x) で置換が閉じる | FR11, FR2, FR8 |
| TS49 | deny | `echo "$(for x (a) { case x in x) printf '%s' '"';; esac; })"; python3 -i` | zsh の for name (words) の後の { | FR11, FR8 |
| TS50 | deny | `echo "$(repeat 1 { case x in x) printf '%s' '"';; esac; })"; python3 -i` | zsh の repeat word の後の { | FR11, FR8 |
| TS51 | deny | `echo "$(select x do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | select name の後の do | FR11, FR8 |

#### ループと coproc の頭（誤拒否の防止、TS52〜TS55）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS52 | silent | `echo "$(for x do case x in x) echo "; python3 -i;";; esac; done)"` | for name の後の case 文の本体の、引用符の中の python3 -i を拒否しない | FR11, FR8 |
| TS53 | silent | `echo "$(coproc { case x in x) echo "; python3 -i;";; esac; })"` | coproc の後の case 文の本体の、引用符の中の python3 -i を拒否しない | FR11, FR8 |
| TS54 | silent | `echo "$(for x (a) { case x in x) echo "; python3 -i;";; esac; })"` | zsh の for name (words) の後の case 文の本体の、引用符の中の python3 -i を拒否しない | FR11, FR8 |
| TS55 | silent | `echo "$(repeat 1 { case x in x) echo "; python3 -i;";; esac; })"` | zsh の repeat word の後の case 文の本体の、引用符の中の python3 -i を拒否しない | FR11, FR8 |

#### ループと coproc の頭（引数と引用、TS56〜TS59）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS56 | deny | `echo "$(echo for x do case x in x)"; python3 -i` | 引数の位置の for からは頭の状態に入らない。case は文を開かず、x) で置換が閉じる | FR11, FR2, FR8 |
| TS57 | deny | `echo "$("for" x do case x in x)"; python3 -i` | 引用された for からは頭の状態に入らない | FR11, FR2, FR8 |
| TS58 | deny | `echo "$(echo coproc { case x in x)"; python3 -i` | 引数の位置の coproc からは頭の状態に入らない | FR11, FR2, FR8 |
| TS59 | deny | `echo "$(echo repeat 1 { case x in x)"; python3 -i` | 引数の位置の repeat からは頭の状態に入らない | FR11, FR2, FR8 |

#### 結合

- [ ] 既存の `CASES` の行が、すべて元の判定のまま通る（AC3）。
- [ ] `TestCopies` が、両コピーのバイト単位の同一性を確かめる（AC4、FR6）。
- [ ] `TestNoRecursion` と `TestSubstitutionSkipCallStructure` が通る（NFR2）。
- [ ] `TestStaticConstraints` が通る（NFR3）。
- [ ] `TestSubstitutionSkipDocumentation` が通る（FR7）。
- [ ] `python3 -m unittest discover -s tests` が通る（AC6）。

#### E2E

- 既存の E2E テスト: なし
- 実行コマンド: 検出なし

#### 境界値・エッジケース

- [ ] TS18: 対を取り除くとキーワードにならない並びは、キーワードとして読まない。
- [ ] TS19: 対を取り除くとキーワードにならないパターンは、文を閉じない。
- [ ] TS11: 最初のパターンの前の行継続（現状でも deny）が、deny のまま残る。
- [ ] TS37〜TS40: 語の中の閉じ、[[ を閉じていない ]]、引数の位置の fi の後は、コマンドの位置にならない。
- [ ] TS48: for の後の名前は、case であってもキーワードとして読まない。
- [ ] TS56〜TS59: 引数の位置や引用された for / coproc / repeat からは、頭の状態に入らない。
- [ ] zsh の短い形 `if [[ x ]] case …` では、FR9 によって case が文を開く（zsh の文法と同じ読み方）。

#### セキュリティ

- [ ] 誤拒否と拒否漏れの両方をなくす。拒否漏れの再現と派生は、TS3、TS6〜TS11、TS14〜TS18、TS23〜TS31、TS33〜TS40、TS44〜TS51、TS56〜TS59 で確かめる。

#### パフォーマンス（線形時間、NFR1）

規模と時間制限は `TestCaseStatementsInASubstitution` の `DEPTH` と `TIMEOUT` に合わせる。

| ID | 期待する判定 | 入力 | 要件 |
|----|--------------|------|------|
| TS20 | deny | 待ちフェーズ（対象の語の前、in の前、パターンの位置）とキーワードの文字の間に、行継続の対を DEPTH 個連ね、置換の後に `python3 -i` を置く | NFR1 |
| TS21 | deny | 項目の本体に、`c\<NL>a\<NL>s\<NL>x ` のような照合に失敗する分断された語を DEPTH 個連ね、置換の後に `python3 -i` を置く | NFR1 |
| TS22 | deny | 項目の本体の引数に `then ` を DEPTH 個連ねて esac で閉じ、置換の後に `python3 -i` を置く | NFR1 |
| TS41 | deny | `'echo "$(' + 'if (:) then ' * DEPTH + 'case x in x) :;; esac' + '; fi' * DEPTH + ')"; python3 -i'`（複合コマンドの閉じの後の then を DEPTH 段入れ子にする） | NFR1, FR9 |
| TS42 | deny | `'echo "$(' + 'f() { ' * DEPTH + 'case x in x) :;; esac' + '; }' * DEPTH + ')"; python3 -i'`（関数の頭を DEPTH 段入れ子にする） | NFR1, FR10 |
| TS43 | deny | `'echo "$(echo ' + ']] fi done then ' * DEPTH + 'case x in x)"; python3 -i'`（引数の位置の閉じの語と予約語を DEPTH 回並べる） | NFR1, FR2 |
| TS60 | deny | `'echo "$(' + 'for x do ' * DEPTH + 'case x in x) :;; esac' + '; done' * DEPTH + ')"; python3 -i'`（ループの頭を DEPTH 段入れ子にする） | NFR1, FR11 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| コマンドの位置 | 次の語がコマンドとして読まれる位置。FR1 の条件で決まる |
| コマンドリスト | チャンクの中の `$(` と `(` の中、および case 文の項目の本体 |
| 複合コマンドの閉じ | FR9 に挙げる `)`・`]]`・`esac`・`fi`・`done`・`}` |
| 関数の頭 | FR10 に挙げる `name()` と `function name` |
| ループと coproc の頭 | FR11 に挙げる `for`・`select`・`coproc`・`repeat` から始まる頭 |
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
- A2: 予約語 `then` / `do` / `else` / `elif` / `if` / `while` / `until` / `time` と、`!` および `{` は、それ自体がコマンドの位置にあるときだけ、次の語をコマンドの位置にする。ここでいうコマンドの位置には、複合コマンドの閉じの後、関数の頭の後、ループと coproc の頭の後を含む。`fi` / `done` / `}` は、コマンドの位置で読んだときだけ複合コマンドの閉じになる。
- A3: time のオプションの後、代入の後、リダイレクトの後の語は、コマンドの位置として扱わない（現状と同じ。複合コマンドの閉じの後のリダイレクトも同じ）。
- A4: メインパーサーの case の印（TS-* と A9 の行）と、`_skip_substitution` の外でキーワードを分断する行継続の扱いは変えない。
- A5: `#` をコメントとして読む範囲は、パターンの `)` の直後だけに広げる。項目の本体の中でサブシェルや置換を閉じる `)` の直後の `#`、および本体の中の `x\<NL>#c` を今のコードがコメントと読む既存の誤読は変えない。
- A6: 既存の `CASES` の行は、削除も判定の変更もしない。`TestSubstitutionSkipDocumentation` が固定している文言のうち、本フィーチャーより前からあるものは残す。本フィーチャーの task0001 で足した RULE_MARKERS は、FR7 のとおり docstring と一緒に書き換えてよい。
- A7: プラグインの version は変えない。
- A8: zsh の extendedglob で `(x)#` を glob として読む可能性はあるが、パターンの `)` の直後の `#` は一律にコメントとして読む。
- A9: `[[ ... ]]` の中の語の読み方（`&&` などの後をコマンドの位置とする今の読み方）は変えない。`[[` を追跡するのは、それを閉じる `]]` を見分けるためだけとする。
- A10: zsh で、引数の位置の単独の `}` が波括弧群を閉じる読み方（IGNORE_CLOSE_BRACES が無効のとき）は扱わない。`}` を閉じとして扱うのは、コマンドの位置で読んだときだけ。
- A11: 関数の頭として扱うのは、単純コマンドの最初の語（コマンドの位置で読んだ語）の後にある空の `()` だけとする。zsh の複数の名前を並べた定義（`a b () {`）と、メインパーサーの `_names_function` が行う名前の妥当性の判定は、読み取りに持ち込まない。

## 15. 参考資料

なし
