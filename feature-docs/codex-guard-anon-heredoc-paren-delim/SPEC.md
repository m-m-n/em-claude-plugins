# Feature: codex-guard-anon-heredoc-paren-delim

## 概要

codex-hook-interactive-guard が、zsh 匿名関数の引数位置にある heredoc の区切り語の `(`〜`)` の範囲を、zsh と同じ区切り語として読むようにする。範囲のテキストから引用を除去して区切り語として登録し、本文中の行を起動として deny しないようにする。要件は `REQUIREMENTS.md` を参照する。

## 目的

- codex-hook-interactive-guard が、zsh 匿名関数の引数位置にある heredoc の区切り語の `(`〜`)` の範囲を zsh と同じ区切り語として読み、本文中の行を起動として deny しないようにする

## ユーザーストーリー

該当なし

## 技術要件

### 機能要件
- **FR1:** 区切り語の範囲の引用除去 — 匿名関数の引数位置で `<<` または `<<-` のリダイレクト先を読んでいる間に限り、`(`〜`)` の範囲を 1 語として読むときは、範囲のテキストから引用を除去してから区切り語として登録する。除去の規則は通常経路と同じとする。
    - 引用符の外のバックスラッシュは除き、次の文字を残す。
    - バックスラッシュと改行の対は両方除く。
    - 単引用符の中身はそのまま残す（バックスラッシュも残す）。
    - 二重引用符の中では、`\` の後が `$` `` ` `` `"` `\` 改行のときだけバックスラッシュを除き、それ以外は `\` と次の文字を残す。
    - 例: `foo('x')` は `foo(x)` になる。
- **FR2:** 範囲の外は二重に除去しない — 区切り語のうち範囲の外の部分は、既に通常経路で引用除去された文字列として扱い、もう一度除去しない。除去するのは範囲のテキストだけとする。
- **FR3:** 範囲内の $' と $" — 区切り語として読む範囲に、引用されていない `$'` または `$"` があるときは、文字列全体を判定不能（無出力）にする。単引用符や二重引用符の中にある `$'` や `$"`、バックスラッシュで逃がした `$` は契機にしない。
- **FR4:** 変えない読み方 — heredoc の区切り語でない引数の範囲、`<` や `<<<` のリダイレクト先の範囲、範囲が `;` `&` 改行やバッククォートを含むときに群を開く読み方、`PAREN_SCAN_FACTOR` による探索量の上限は変えない。
- **FR5:** 両コピー — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR6:** docstring — モジュール docstring の判定手順（step 4 の匿名関数の引数の範囲の説明）に FR1 と FR3 の規則を書く。既存の `TestGuardDocumentation` のマーカー文は残す。
- **FR7:** 回帰テスト — `tests/test_codex_hook_interactive_guard.py` の `CASES` に、再現手順のコマンドを silent として追加する。テストシナリオのケース（TS-1〜TS-11）も `CASES` に `(期待する判定, ラベル, コマンド)` の形で追加する。

### 非機能要件
- **NFR1:** 解析時間は入力長に対して線形のまま。引用除去と `$'` の確認は、1 語として読む範囲 1 つにつき 1 回、範囲の長さに比例する手間で行う
- **NFR2:** 再帰や循環呼び出しを持ち込まない（既存の AST 検査が通る）
- **NFR3:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（既存の制約検査が通る）
- **NFR4:** 読めない入力は無出力のまま

## 実装方針

### 前提
- as-1: 2 つのコピーを同じ変更の中で直し、バイト単位で同一に保つ
- as-2: 範囲が `;` `&` 改行やバッククォートを含み群として開くときは、heredoc の区切り語を待っている間でも従来の読みのままにし、FR1 と FR3 は適用しない
- as-3: 範囲内の `$x` や `$(...)` のように引用でない展開は、文字のまま区切り語に残す（FR3 の `$'` と `$"` を除く）
- as-4: プラグインの version は変更しない

### 依存関係

**外部依存:**
- 標準ライブラリのみ（NFR3）

### 対象ファイル

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1-FR4, FR6
em-review/scripts/codex-hook-interactive-guard.py     # FR1-FR4, FR6（FR5: 上とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR7
```

## 宣言された変更集合

このセクションは手で書いた一覧ではなく、create-plan での導出を述べる。上記のフィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/codex-guard-anon-heredoc-paren-delim/**`
- `test-docs/codex-guard-anon-heredoc-paren-delim/**`

`feature-docs/codex-guard-anon-heredoc-paren-delim/**` には `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物が含まれる。生成主体は各フェーズドキュメントおよび `references/phase-state.md` であり、このセクションは引用のみでルールを再掲しない。

`test-docs/codex-guard-anon-heredoc-paren-delim/**` には、タスクごとのテスト記録 `test-docs/codex-guard-anon-heredoc-paren-delim/{T}.tests.yaml` が含まれる。生成主体は `implement-phase.md` であり、このセクションは引用のみでルールを再掲しない。

この 2 つの既定のメンバーは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的で明示的な絞り込みとする。

この宣言はスーパーセットの主張であり、検証時に観測される実際の変更集合は宣言された集合に含まれる（CONTAINED IN）必要がある。一致は求めない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/codex-guard-anon-heredoc-paren-delim/` ディレクトリを生成しないが、その場合も宣言された `test-docs/codex-guard-anon-heredoc-paren-delim/**` は正しい。宣言されたパスが生成されないことは違反ではない。

## テストシナリオ

### 単体テスト

`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で追加する（FR7）。

- [ ] TS-1（AC-1 / FR1, FR7）: `zsh -c "function { :; } << foo('x')\nfoo('x')\npython3 -i\nfoo(x)"` - silent
- [ ] TS-2（AC-2 / FR1, FR7）: `zsh -c "function { :; } << foo('x')\nfoo(x)\npython3 -i"` - deny
- [ ] TS-3（AC-3 / FR1, FR7）: `zsh -c 'function { :; } << foo(python3)\nfoo\npython3 -i\nfoo(python3)'` - silent
- [ ] TS-4（AC-4 / FR1, FR7）: `zsh -c 'function { :; } << foo("x")\nfoo(x)\npython3 -i'` - deny
- [ ] TS-5（AC-4 / FR1, FR7）: `zsh -c 'function { :; } << foo(\x)\nfoo(x)\npython3 -i'` - deny
- [ ] TS-6（AC-5 / FR1, FR7）: `zsh -c "function { :; } <<- foo('x')\n\tfoo(x)\npython3 -i"` - deny
- [ ] TS-7（AC-6 / FR1, FR7）: `zsh -c "function { python3 -i; } << foo('x')\nfoo(x)"` - deny
- [ ] TS-8（AC-7 / FR3, FR7）: 区切り語 `foo($'x')` で、本文に `foo($'x')` と `python3 -i` の行を置く - silent
- [ ] TS-9（AC-7 / FR3, FR7）: 区切り語 `foo($"x")` で、本文に `foo($"x")` と `python3 -i` の行を置く - silent
- [ ] TS-10（AC-8 / FR3, FR7）: 区切り語 `foo("$'")` で、本文に `foo($')` の行、その後に `python3 -i` の行を置く - deny
- [ ] TS-11（AC-8 / FR3, FR7）: 区切り語 `foo(\$'x')` で、本文に `foo($x)` の行、その後に `python3 -i` の行を置く - deny

TS-note（AC-7, AC-8）: TS-8 から TS-11 を `zsh -c "..."` の二重引用符で包むときは、外側の `$` を `\$` と書く。外側で `$` が展開扱いになると `-c` の文字列全体が動的になり、判定されないまま silent になって検査にならない。外側を包まずに最上位のコマンドとして書いてもよい（ガードはシェルを区別せずに読む）。

### 既存テスト

実行コマンド: `python3 -m unittest tests.test_codex_hook_interactive_guard`

- [ ] AC-9（FR4, FR5, NFR1-3）: 既存テストがすべて通る（CASES の重複検査、両コピーのバイト一致、深い入力の時間検査、再帰検査を含む）
- [ ] AC-10（FR6）: モジュール docstring に FR1 と FR3 の規則が書かれ、既存の docstring マーカー検査が通る

### E2E テスト
**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

### エッジケース
- [ ] 範囲内の引用されていない `$'` / `$"`: 判定不能（無出力）にする（FR3、TS-8, TS-9）
- [ ] 二重引用符の中の `$'`、逃がした `\$`: 契機にせず、除去後の区切り語で読む（FR3、TS-10, TS-11）
- [ ] `<<-`: 先頭タブを除いて区切り語と比べる（AC-5、TS-6）

## 安全性

- **入力検証:** 読めない入力は無出力のまま（NFR4）
- 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（NFR3）

## 性能

- 解析時間は入力長に対して線形のまま。引用除去と `$'` の確認は、1 語として読む範囲 1 つにつき 1 回、範囲の長さに比例する手間で行う（NFR1）
- `PAREN_SCAN_FACTOR` による探索量の上限は変えない（FR4）

## 成功基準

- [ ] AC-1 (FR1, FR7): 次の command は両コピーで無出力・終了コード 0・標準エラー空になる。CASES に silent として載る: `zsh -c "function { :; } << foo('x')\nfoo('x')\npython3 -i\nfoo(x)"`
- [ ] AC-2 (FR1): 本当の区切り語の行より後の起動は deny される: `zsh -c "function { :; } << foo('x')\nfoo(x)\npython3 -i"`
- [ ] AC-3 (FR1): 本文に区切り語の範囲より前の部分だけの行があっても、本文は終わらない（silent）: `zsh -c 'function { :; } << foo(python3)\nfoo\npython3 -i\nfoo(python3)'`
- [ ] AC-4 (FR1): 二重引用符とバックスラッシュも除去されて deny される: `zsh -c 'function { :; } << foo("x")\nfoo(x)\npython3 -i'` と `zsh -c 'function { :; } << foo(\x)\nfoo(x)\npython3 -i'`
- [ ] AC-5 (FR1): `<<-` では先頭タブを除いて区切り語と比べ、deny される: `zsh -c "function { :; } <<- foo('x')\n\tfoo(x)\npython3 -i"`
- [ ] AC-6 (FR1): 区切り語で heredoc が閉じたあとも、匿名関数の本体の `-i` は deny される: `zsh -c "function { python3 -i; } << foo('x')\nfoo(x)"`
- [ ] AC-7 (FR3): 範囲内の引用されていない `$'` と `$"` は判定不能（silent）になる: `<<  foo($'x')` と `foo($"x")` のそれぞれで、本文に同じ行と `python3 -i` を置いたコマンド
- [ ] AC-8 (FR3): 二重引用符の中の `$'` と、逃がした `\$` は契機にならず、除去後の区切り語で読まれて deny される。例: `function { :; } << foo("$'")\nfoo($')\npython3 -i` と `function { :; } << foo(\$'x')\nfoo($x)\npython3 -i`
- [ ] AC-9 (FR4, FR5, NFR1-3): `python3 -m unittest tests.test_codex_hook_interactive_guard` の既存テストがすべて通る（CASES の重複検査、両コピーのバイト一致、深い入力の時間検査、再帰検査を含む）
- [ ] AC-10 (FR6): モジュール docstring に FR1 と FR3 の規則が書かれ、既存の docstring マーカー検査が通る

## 未解決事項

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## 参考資料

- 要件定義書: `feature-docs/codex-guard-anon-heredoc-paren-delim/REQUIREMENTS.md`
