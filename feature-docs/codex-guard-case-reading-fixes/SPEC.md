# Feature: codex-guard-case-reading-fixes

## 概要

codex-hook-interactive-guard（em-workflow / em-review の両コピー）の `_skip_substitution` で、`$( )` の中の case 文の読み違いをなくす。対象は、引数の `esac` / `case`、パターンの直後のコメント、行継続の 3 つ。要件は `REQUIREMENTS.md` に従う。

## 目的

- `$( )` の中の case 文の読み違い（引数の `esac` / `case`、パターンの直後のコメント、行継続）をなくす。
- 誤拒否（fail-closed）と拒否漏れ（fail-open）の両方をなくす。

## 受け入れ基準

- [ ] AC1: 再現手順 1〜3（TS1〜TS3）が期待どおりの判定になる（両コピー）。
- [ ] AC2: 派生の行 TS4〜TS19 が `CASES` に入り、両コピーに対して期待どおりの判定になる。
- [ ] AC3: 既存の `CASES` の行がすべて元の判定のまま通る。`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。
- [ ] AC4: `TestCopies` により両コピーのバイト単位の同一性が確かめられる。
- [ ] AC5: TS20〜TS22 の入力が、`TestCaseStatementsInASubstitution` と同じ規模と時間制限の中で答えを返し、後ろの起動を deny にする（NFR1）。
- [ ] AC6: `python3 -m unittest discover -s tests` が通る。

## 技術要件

### 機能要件

- **FR1:** コマンドの位置を状態として追跡する。チャンクの中のコマンドリスト（`$(` と `(` の中、および case 文の項目の本体）ごとに、次の語がコマンドの位置にあるかを状態として持つ。コマンドの位置になるのは次の場合。
    - リストの先頭
    - `;` `&` `|`（`&&` `||` を含む）の後
    - 改行の後
    - サブシェルの `(` の後
    - コマンドの位置にある予約語 `then` / `do` / `else` / `elif` / `if` / `while` / `until` / `time` と `!` と `{` の後

  それ以外の語の後はコマンドの位置ではない。直前の語の文字を後ろ向きに見る判定はやめる。
- **FR2:** 引数の case / esac で文を開閉しない。`case` は、コマンドの位置にある単独の語のときだけ case 文を開く。項目の本体では、`esac` はコマンドの位置にある単独の語のときだけ case 文を閉じる。引数の位置の `case` / `esac` は、引数の予約語の後にあるものも含め、文を開くことも閉じることもしない。
- **FR3:** パターンの `)` の直後の `#` をコメントとして読む。項目のパターンを閉じる `)` の直後の `#` を、空白がなくてもコメントの始まりとして読み、改行まで読み飛ばす。コメントの中の `esac` や引用符では文を閉じず、引用も始めない。
- **FR4:** 待ちフェーズで行継続を読み飛ばす。語や `in` を待つフェーズ（対象の語の前、対象の語の後、パターンの位置、先頭の `(` の後、項目の本体の開始位置）では、バックスラッシュと改行の対を語の始まりとして扱わずに読み飛ばし、フェーズを保つ。
- **FR5:** キーワードに接する行継続と分断する行継続。`case` / `in` / `esac` がキーワードかどうかは、バックスラッシュと改行の対を取り除いた文字の並びで判定する。
    - キーワードの文字の間にある対（例: `ca\<NL>se`、`i\<NL>n`、`es\<NL>ac`）は読み飛ばしてキーワードとして読む。
    - キーワードの直後の対（例: `case\<NL> x`、`in\<NL> x)`、`esac\<NL>)`）も読み飛ばし、その先の文字で単独の語かを判定する。
    - 対を取り除くとキーワードにならない並び（例: `ca\<NL>sex`、`es\<NL>acx`、`x\<NL>case`）はキーワードとして読まない。
    - 語の途中にある対は語を区切らない。
- **FR6:** 両コピーを同時に直す。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR7:** docstring を更新する。`_skip_substitution` の docstring（フェーズの説明を含む）を、新しい読み方に合わせて書き直す。キーワード判定のメソッドを残す場合は、その docstring も書き直す。`TestSubstitutionSkipDocumentation` が固定している文言は残す。
- **FR8:** CASES に再現と派生の行を足す。`tests/test_codex_hook_interactive_guard.py` の `CASES` に TS1〜TS19 の行を `(期待する判定, ラベル, コマンド)` の形で足す。行は両コピーに流す。

### 非機能要件

- **NFR1 - 線形時間:** 読み取りは入力の長さに対して線形の時間で終わる。キーワードの照合が失敗した場合や、行継続の対が長く続く場合も同じ。各位置からの照合はキーワードの文字数と、その間と直後にある対の並びだけを見る。同じ対の並びを読み直す照合の数は定数に収まる。コマンドの位置の状態は、各コンテキストに定数サイズで持つ。
- **NFR2 - 再帰を使わない:** `_skip_substitution` から到達できるメソッドに、`_skip_substitution`・`_read_quoted_unit`・`parse`・`_remove_range_quotes` を含めない（`TestNoRecursion` と `TestSubstitutionSkipCallStructure` を通す）。
- **NFR3 - 標準ライブラリだけを使う:** 標準ライブラリだけを使い、`TestStaticConstraints` の制約を守る。
- **NFR4 - version を変えない:** プラグインの version は変えない。

## 実装方針

### 構成

- 変更するのは `_skip_substitution` の読み取り（FR1〜FR5）と、その docstring（FR7）。
- コマンドの位置の状態は、`$(` と `(` の中、および項目の本体の各コンテキストに定数サイズで持つ（FR1、NFR1）。
- キーワード（`case` / `in` / `esac`）の判定は、行継続の対を取り除いた文字の並びで行う（FR5）。
- `_skip_substitution` から到達できるメソッドに再帰の経路を作らない（NFR2）。

### 依存関係

**内部依存:**
- `tests/test_codex_hook_interactive_guard.py`: `CASES` と、`TestCopies`・`TestNoRecursion`・`TestSubstitutionSkipCallStructure`・`TestStaticConstraints`・`TestSubstitutionSkipDocumentation`・`TestCaseStatementsInASubstitution` が対象のスクリプトを検査する。

**外部依存:**
- なし（標準ライブラリだけを使う。NFR3）

### ファイル構成

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1〜FR7
em-review/scripts/codex-hook-interactive-guard.py     # FR1〜FR7（em-workflow 側とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR8、TS20〜TS22
```

## 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

既定で、次の 2 つのワークフロー生成物を宣言に含める。

- `feature-docs/codex-guard-case-reading-fixes/**`
- `test-docs/codex-guard-case-reading-fixes/**`

`feature-docs/codex-guard-case-reading-fixes/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md`（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-case-reading-fixes/**` に含まれるもの: `test-docs/codex-guard-case-reading-fixes/{T}.tests.yaml`（タスクごとのテスト記録）。生成主体は `implement-phase.md`（引用のみ、ルールは再掲しない）。

この 2 つの既定のメンバーは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載がないことを除外とはみなさない。除外は意図的な絞り込みとして明示する。

この宣言はスーパーセットの主張であり、検証時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。等しい必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。生成されないパスを宣言していても違反にはならない。

## テストシナリオ

表記:

- `<NL>` は改行を表す。
- `\<NL>` はバックスラッシュの直後に改行が続く対（行継続の対）を表す。

### 単体テスト（`CASES` の行、両コピーに流す）

| ID | 期待する判定 | コマンド | 内容 | 要件 |
|----|--------------|----------|------|------|
| TS1 | silent | `echo "$(case y in x) echo if esac;; y) echo "; python3 -i;";; esac)"` | 再現手順 1 | FR1, FR2, FR8 |
| TS2 | silent | `echo "$(case x in x)#; esac<NL>:;; y) printf '%s' '"; python3 -i; #';; esac)"` | 再現手順 2 | FR3, FR8 |
| TS3 | deny | `echo "$(case x \<NL>in x) :;; esac)"; python3 -i` | 再現手順 3 | FR4, FR8 |
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

### 結合テスト

- [ ] 既存の `CASES` の行がすべて元の判定のまま通る（AC3）。
- [ ] `TestCopies` が両コピーのバイト単位の同一性を確かめる（AC4、FR6）。
- [ ] `TestNoRecursion` と `TestSubstitutionSkipCallStructure` が通る（NFR2）。
- [ ] `TestStaticConstraints` が通る（NFR3）。
- [ ] `TestSubstitutionSkipDocumentation` が通る（FR7）。
- [ ] `python3 -m unittest discover -s tests` が通る（AC6）。

### E2E テスト
**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

### エッジケース
- [ ] TS18: 対を取り除くとキーワードにならない並びは、キーワードとして読まない。
- [ ] TS19: 対を取り除くとキーワードにならないパターンは、文を閉じない。
- [ ] TS11: 現状でも deny になる最初のパターンの前の行継続が、deny のまま残る。

### パフォーマンステスト（NFR1、AC5）

規模と時間制限は `TestCaseStatementsInASubstitution` の `DEPTH` と `TIMEOUT` に合わせる。いずれも期待する判定は deny。

- [ ] TS20: 待ちフェーズ（対象の語の前、in の前、パターンの位置）とキーワードの文字の間に、行継続の対を DEPTH 個連ね、置換の後に `python3 -i` を置く。
- [ ] TS21: 項目の本体に `c\<NL>a\<NL>s\<NL>x ` のような、照合に失敗する分断された語を DEPTH 個連ね、置換の後に `python3 -i` を置く。
- [ ] TS22: 項目の本体の引数に `then ` を DEPTH 個連ねて esac で閉じ、置換の後に `python3 -i` を置く。

## セキュリティ

- 誤拒否（fail-closed）と拒否漏れ（fail-open）の両方をなくす（目的）。拒否漏れの再現と派生は TS3、TS6〜TS11、TS14〜TS18 で確かめる。

## エラー処理

該当なし

## パフォーマンス

- 読み取りは入力の長さに対して線形の時間で終わる（NFR1）。

## 成功基準

- [ ] FR1〜FR8 が実装され、テストされている
- [ ] TS1〜TS22 が期待どおりの判定になる
- [ ] NFR1〜NFR4 を満たす
- [ ] AC1〜AC6 を満たす

## 未解決事項

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## 前提

- A1: コマンドの位置を状態として追跡する範囲は、チャンクの中のコマンドリスト全部（`$(` と `(` の中、および項目の本体）とする。
- A2: 予約語 `then` / `do` / `else` / `elif` / `if` / `while` / `until` / `time` と、`!` および `{` は、それ自体がコマンドの位置にあるときだけ、次の語をコマンドの位置にする。
- A3: time のオプションの後、代入の後、リダイレクトの後の語はコマンドの位置として扱わない（現状と同じ）。
- A4: メインパーサーの case の印（TS-* と A9 の行）と、`_skip_substitution` の外でのキーワードを分断する行継続の扱いは変えない。
- A5: `#` をコメントとして読む範囲は、パターンの `)` の直後だけに広げる。項目の本体の中でサブシェルや置換を閉じる `)` の直後の `#`、および本体の中の `x\<NL>#c` を今のコードがコメントと読む既存の誤読は変えない。
- A6: 既存の `CASES` の行は削除も判定の変更もしない。`TestSubstitutionSkipDocumentation` が固定している docstring の文言は残す。
- A7: プラグインの version は変えない。
- A8: zsh の extendedglob で `(x)#` を glob として読む可能性はあるが、パターンの `)` の直後の `#` は一律にコメントとして読む。

## 参照

- 要件定義書: `feature-docs/codex-guard-case-reading-fixes/REQUIREMENTS.md`
