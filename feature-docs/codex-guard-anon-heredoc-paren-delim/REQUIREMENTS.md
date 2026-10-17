---
title: "codex-guard-anon-heredoc-paren-delim"
created_date: 2026-10-17
status: draft
---

# codex-guard-anon-heredoc-paren-delim - 要件定義書

## 1. 概要

### 1.1 背景
codex-hook-interactive-guard は、zsh 匿名関数の引数位置にある heredoc の区切り語の `(`〜`)` の範囲を、zsh と同じ区切り語として読んでいない。そのため本文中の行を起動として deny する。

### 1.2 目的
codex-hook-interactive-guard が、zsh 匿名関数の引数位置にある heredoc の区切り語の `(`〜`)` の範囲を zsh と同じ区切り語として読み、本文中の行を起動として deny しないようにする。

### 1.3 スコープ
- 対象: 匿名関数の引数位置で `<<` または `<<-` のリダイレクト先を読んでいる間に、`(`〜`)` の範囲を 1 語として読むときの区切り語の扱い（FR1〜FR3）
- 対象ファイル:
    - `em-workflow/scripts/codex-hook-interactive-guard.py`
    - `em-review/scripts/codex-hook-interactive-guard.py`
    - `tests/test_codex_hook_interactive_guard.py`
- 対象外（変えない読み方、FR4）:
    - heredoc の区切り語でない引数の範囲
    - `<` や `<<<` のリダイレクト先の範囲
    - 範囲が `;` `&` 改行やバッククォートを含むときに群を開く読み方
    - `PAREN_SCAN_FACTOR` による探索量の上限

## 2. ビジネス要件

### 2.1 ビジネス目標
- codex-hook-interactive-guard が、zsh 匿名関数の引数位置にある heredoc の区切り語の `(`〜`)` の範囲を zsh と同じ区切り語として読み、本文中の行を起動として deny しないようにする

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 匿名関数の引数位置にある heredoc の本文中の行が、起動として deny されない

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | 区切り語の範囲の引用除去 | resolved |
| FR2 | 範囲の外は二重に除去しない | resolved |
| FR3 | 範囲内の $' と $" | resolved |
| FR4 | 変えない読み方 | resolved |
| FR5 | 両コピー | resolved |
| FR6 | docstring | resolved |
| FR7 | 回帰テスト | resolved |

### 4.2 機能詳細

#### FR1: 区切り語の範囲の引用除去

**説明**: 匿名関数の引数位置で `<<` または `<<-` のリダイレクト先を読んでいる間に限り、`(`〜`)` の範囲を 1 語として読むときは、範囲のテキストから引用を除去してから区切り語として登録する。除去の規則は通常経路と同じとする。

**ビジネスルール**:
- 引用符の外のバックスラッシュは除き、次の文字を残す。
- バックスラッシュと改行の対は両方除く。
- 単引用符の中身はそのまま残す（バックスラッシュも残す）。
- 二重引用符の中では、`\` の後が `$` `` ` `` `"` `\` 改行のときだけバックスラッシュを除き、それ以外は `\` と次の文字を残す。
- 例: `foo('x')` は `foo(x)` になる。

#### FR2: 範囲の外は二重に除去しない

**説明**: 区切り語のうち範囲の外の部分は、既に通常経路で引用除去された文字列として扱い、もう一度除去しない。除去するのは範囲のテキストだけとする。

#### FR3: 範囲内の $' と $"

**説明**: 区切り語として読む範囲に、引用されていない `$'` または `$"` があるときは、文字列全体を判定不能（無出力）にする。

**ビジネスルール**:
- 単引用符や二重引用符の中にある `$'` や `$"`、バックスラッシュで逃がした `$` は契機にしない。

#### FR4: 変えない読み方

**説明**: heredoc の区切り語でない引数の範囲、`<` や `<<<` のリダイレクト先の範囲、範囲が `;` `&` 改行やバッククォートを含むときに群を開く読み方、`PAREN_SCAN_FACTOR` による探索量の上限は変えない。

#### FR5: 両コピー

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR6: docstring

**説明**: モジュール docstring の判定手順（step 4 の匿名関数の引数の範囲の説明）に FR1 と FR3 の規則を書く。既存の `TestGuardDocumentation` のマーカー文は残す。

#### FR7: 回帰テスト

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に、再現手順のコマンドを silent として追加する。テストシナリオ（12 章）のケースも `CASES` に `(期待する判定, ラベル, コマンド)` の形で追加する。

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | 解析時間は入力長に対して線形のまま。引用除去と `$'` の確認は、1 語として読む範囲 1 つにつき 1 回、範囲の長さに比例する手間で行う |
| NFR2 | 再帰や循環呼び出しを持ち込まない（既存の AST 検査が通る） |
| NFR3 | 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（既存の制約検査が通る） |
| NFR4 | 読めない入力は無出力のまま |

## 6. UI/UX要件

該当なし（UI を持たないフック判定ロジックの修正。デザインステップは実施しない）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 2 つのコピーを同じ変更の中で直し、バイト単位で同一に保つ（FR5）
- 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（NFR3）
- 再帰や循環呼び出しを持ち込まない（NFR2）

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-heredoc-paren-delim/**`
- `test-docs/codex-guard-anon-heredoc-paren-delim/**`

`feature-docs/codex-guard-anon-heredoc-paren-delim/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-heredoc-paren-delim/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-heredoc-paren-delim/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-anon-heredoc-paren-delim/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-anon-heredoc-paren-delim/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
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

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 受け入れ基準 | 期待する判定 | コマンド |
|----|--------------|--------------|----------|
| TS-1 | AC-1 | silent | `zsh -c "function { :; } << foo('x')\nfoo('x')\npython3 -i\nfoo(x)"` |
| TS-2 | AC-2 | deny | `zsh -c "function { :; } << foo('x')\nfoo(x)\npython3 -i"` |
| TS-3 | AC-3 | silent | `zsh -c 'function { :; } << foo(python3)\nfoo\npython3 -i\nfoo(python3)'` |
| TS-4 | AC-4 | deny | `zsh -c 'function { :; } << foo("x")\nfoo(x)\npython3 -i'` |
| TS-5 | AC-4 | deny | `zsh -c 'function { :; } << foo(\x)\nfoo(x)\npython3 -i'` |
| TS-6 | AC-5 | deny | `zsh -c "function { :; } <<- foo('x')\n\tfoo(x)\npython3 -i"` |
| TS-7 | AC-6 | deny | `zsh -c "function { python3 -i; } << foo('x')\nfoo(x)"` |
| TS-8 | AC-7 | silent | 区切り語 `foo($'x')` で、本文に `foo($'x')` と `python3 -i` の行を置く |
| TS-9 | AC-7 | silent | 区切り語 `foo($"x")` で、本文に `foo($"x")` と `python3 -i` の行を置く |
| TS-10 | AC-8 | deny | 区切り語 `foo("$'")` で、本文に `foo($')` の行、その後に `python3 -i` の行を置く |
| TS-11 | AC-8 | deny | 区切り語 `foo(\$'x')` で、本文に `foo($x)` の行、その後に `python3 -i` の行を置く |

TS-note（AC-7, AC-8）: TS-8 から TS-11 を `zsh -c "..."` の二重引用符で包むときは、外側の `$` を `\$` と書く。外側で `$` が展開扱いになると `-c` の文字列全体が動的になり、判定されないまま silent になって検査にならない。外側を包まずに最上位のコマンドとして書いてもよい（ガードはシェルを区別せずに読む）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 範囲 | 匿名関数の引数位置で `(`〜`)` を 1 語として読む部分 |
| 判定不能 | 無出力にすること |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 区切り語の範囲の直し方（requirement.fr1.fix-approach）: 範囲のテキストから引用を除去する（FR1）
- [x] 区切り語の範囲内の `$'` / `$"` の扱い（requirement.edge.dollar-quote-in-delimiter-range）: 引用されていないものがあれば判定不能にする（FR3）

### 14.2 未確認・保留事項
なし

### 14.3 前提
- as-1: 2 つのコピーを同じ変更の中で直し、バイト単位で同一に保つ
- as-2: 範囲が `;` `&` 改行やバッククォートを含み群として開くときは、heredoc の区切り語を待っている間でも従来の読みのままにし、FR1 と FR3 は適用しない
- as-3: 範囲内の `$x` や `$(...)` のように引用でない展開は、文字のまま区切り語に残す（FR3 の `$'` と `$"` を除く）
- as-4: プラグインの version は変更しない

## 15. 参考資料

- `.claude/rules/hook-tests.md`: codex-hook-interactive-guard のテスト手順
