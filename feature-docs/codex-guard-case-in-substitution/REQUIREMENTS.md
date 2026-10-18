---
title: "codex-guard-case-in-substitution"
created_date: 2026-10-19
status: draft
---

# codex-guard-case-in-substitution - 要件定義書

## 1. 概要

### 1.1 背景

codex-hook-interactive-guard（em-workflow / em-review の両コピー）の `_skip_substitution` は、`$( ... )` の中の `case` の予約語で `_Undecidable("case in a substitution")` を出す。そのため、二重引用符の中の `$(case ...)` と、匿名関数の引数位置のヒアドキュメント区切り語の範囲の中の `$(case ...)` で判定不能になり、同じ `-c` 文字列にある後続の `python3 -i` が silent になって fail-open している。

### 1.2 目的

- `_skip_substitution` が `$( ... )` の中の `case` 文を読み、パターンの閉じ括弧 `)` を置換の終わりと取り違えずに、置換の終わりを zsh と同じ位置に見つける。
- 語の読み取り側（二重引用符の中の `$(case ...)`）と、匿名関数の引数位置のヒアドキュメント区切り語の範囲の両方で、同じ `-c` 文字列にある後続の `python3 -i` を deny にする。
- 再発を `tests/test_codex_hook_interactive_guard.py` の `CASES` で検出できるようにする。

### 1.3 スコープ

- 対象: 二重引用符の中の置換を読む `_skip_substitution`（両コピー）、`tests/test_codex_hook_interactive_guard.py` の `CASES`、関係する docstring。
- 対象外: 引用符の外の `$(case ...)` を読む `_dollar` → `_skip_parens` / `_scan_parens`。

## 2. ビジネス要件

### 2.1 ビジネス目標

- 二重引用符の中の置換と、区切り語の範囲の中の置換に `case` 文があっても、後続の `python3 -i` を deny にし、fail-open をなくす。
- 再発を `CASES` で検出できるようにする。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 |
|----|--------|
| FR1 | 置換の中の case 文を読む |
| FR2 | パターンの中の読み |
| FR3 | 項目の本体の読み |
| FR4 | 確定できない形は判定不能のまま |
| FR5 | 再現入力を deny にする |
| FR6 | 変えないもの |
| FR7 | 再発を検出する CASES の行 |
| FR8 | 2 つのコピーの同一性 |
| FR9 | docstring の更新 |

### 4.2 機能詳細

#### FR1: 置換の中の case 文を読む

`_skip_substitution` は、コマンドリストの文脈（スタックの `p`）で `_is_case_keyword` が `case` の予約語と判定した位置で `_Undecidable("case in a substitution")` を出さず、case 文として読む。

- case 文は、対象の語、空白や改行のあとの `in`、0 個以上の項目、`esac` の順に読む。
- 各項目は、省略できる先頭の `(`、`|` で区切ったパターン、パターンを閉じる `)`、コマンドリスト、項目の終端からなる。
- パターンを閉じる `)` は、置換も、置換の中の `(` の群も閉じない。
- 項目の終端は `;;`、`;&`、`;|`（zsh）、`;;&`（bash）のどれか。
- 最後の項目は終端を省いて `esac` で終われる。
- `esac` は、パターンの位置（`in` の直後、項目の終端の直後）か、項目の本体のコマンドの位置にある単独の語のときだけ case 文を閉じる。
- case 文を閉じたあとの `)` は、今までどおり置換を閉じる。

#### FR2: パターンの中の読み

- パターンの中の `\` の対、単引用符、`$'...'`、二重引用符、`$(`、`$((`、`${`、バッククォートは、今の文脈（`d` / `b` / `p` / `a` / `k` / `K`）と同じ規則で読み飛ばし、その中の `)` や `|` はパターンを閉じない。
- 先頭の省略できる `(` のあとのパターンの中の `(` と `)` は入れ子として数え、入れ子の外の `)` がパターンを閉じる。

#### FR3: 項目の本体の読み

- 項目の本体はコマンドリストとして今の `p` の文脈と同じ規則で読む（入れ子の置換、サブシェルの `(` `)`、コメント、`<<<`）。
- 本体の中で `case` の予約語を認める位置は、今の `_is_case_keyword` の位置に加えて、パターンを閉じた `)` の直後と、項目の終端の直後を含む。これにより case 文の入れ子も読む。
- 入れ子の case 文と入れ子の置換は、明示的なスタックで読む。

#### FR4: 確定できない形は判定不能のまま

次は判定不能（`_Undecidable`）にする。どれも出力は silent で、今の方針と同じ。

1. `case` の対象の語のあとに `in` が来ない（zsh の `case x { ... }` の形を含む）。
2. 入力の終わりまでに `esac` で閉じない。
3. パターンの位置で、パターンを持たない `)` が来る。
4. 置換の中の heredoc（`<<` / `<<-`）。case 文の本体の中も含め、`heredoc in a substitution` の扱いは変えない。

#### FR5: 再現入力を deny にする

Notion 課題の 2 つの再現入力が、両コピーで deny になる。

- (a) 区切り語の範囲の側: `zsh -c ` + shlex.quote(inner)。inner は次の 3 行。

  ```
  function { :; } << foo("$(case x in x) echo foo;; esac)")
  foo($(case x in x) echo foo;; esac))
  python3 -i
  ```

- (b) 語の読み取りの側: `zsh -c ` + shlex.quote(`echo "$(case x in x) :;; esac)"; python3 -i`)。

#### FR6: 変えないもの

次は変えない。

- 引用符の外の `$(` を `_skip_parens` / `_scan_parens` で読む規則と `_dollar`（引用符の外の `$(case ...)` は対象外）
- `_scan_parens` による区切り語の範囲の見つけ方
- `_read_argument_parens`、`_remove_range_quotes`、`_read_quoted_unit` の呼び出し構造
- バッククォートの文脈（`b`）の読み
- 置換の中身を判定しないこと
- 置換の中の heredoc を判定不能にすること
- チェックポイントの規則
- 既存の `CASES` の行は消さず、期待値も変えない。

#### FR7: 再発を検出する CASES の行

- `tests/test_codex_hook_interactive_guard.py` の `CASES` に、FR5 の 2 入力と 12 章のテストシナリオの行を `(期待する判定, ラベル, コマンド)` の形で足す。
- 期待する判定は `deny` か `silent`。
- 表は今までどおり両コピーに流す。
- ラベルとコマンドは既存の行と重ならないようにする（`test_cases_are_unique`）。

#### FR8: 2 つのコピーの同一性

`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で一緒に直し、バイト単位で同一に保つ（`TestCopies`）。

#### FR9: docstring の更新

- `_skip_substitution` の docstring の「a heredoc or a `case` inside it」を直し、case 文を読むことと、FR4 の形が判定不能になることを書く。
- `_is_case_keyword` を変えたらその docstring も直す。
- モジュール docstring の手順 3 の「A chunk that is not closed, or whose close cannot be located with certainty -> no output」は残す。
- `TestGuardDocumentation` の既存の目印の文はすべて残す。

## 5. 非機能要件

### 5.1 パフォーマンス要件（NFR1: 性能）

- 処理時間は入力の長さに対して線形を保つ。
- case 文の読みは 1 文字あたり定数の仕事で、予約語の判定で後ろを見る範囲は直前の空白の並びと英字の並びに限る。
- 多数の項目と深い case 文の入れ子を持つ置換も時間内に答える。
- 既存の性能テスト（`TestMalformedAndDeepInput` など）は両コピーで通る。

### 5.4 保守性要件

- NFR2: 呼び出し構造
    - 再帰と循環呼び出しは持ち込まない（`TestNoRecursion`）。
    - `_skip_substitution` を呼ぶのは共通の読み取り関数 `_read_quoted_unit` だけのままにし、`_skip_substitution` と、そこから足す補助関数は、`_read_quoted_unit`、`parse`、`_remove_range_quotes` を呼ばない（`TestSharedQuotedUnitReader`）。
- NFR3: 静的な制約
    - 標準ライブラリだけを使い、ファイルへの書き込み、ネットワーク、子プロセスの起動をしない（`TestStaticConstraints`）。
- NFR4: Version
    - `plugin.json` と `marketplace.json` の version は変えない（main への push 時に Actions が上げる）。

## 9. 制約条件

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-case-in-substitution/**`
- `test-docs/codex-guard-case-in-substitution/**`

`feature-docs/codex-guard-case-in-substitution/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-case-in-substitution/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-case-in-substitution/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-case-in-substitution/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-case-in-substitution/**` は依然として正しい。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: FR5(a) の区切り語の範囲の再現入力が、両コピーで deny になる。
- [ ] AC-2: FR5(b) の語の読み取りの再現入力が、両コピーで deny になる。
- [ ] AC-3: AC-1 と AC-2 の 2 入力が `tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` の形で入っている。
- [ ] AC-4: テストシナリオの TS3〜TS15 の行が `CASES` に入り、両コピーで期待どおりの判定になる。
- [ ] AC-5: 2 つのコピーがバイト単位で同一（`TestCopies.test_the_two_copies_are_byte_identical`）。
- [ ] AC-6: リポジトリルートで実行した `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` がすべて通る。既存の `CASES`、`TestNoRecursion`、`TestSharedQuotedUnitReader`、`TestStaticConstraints`、`TestGuardDocumentation`、性能テストを含む。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1（deny、CASES）: FR5(a) の 3 行の inner を `zsh -c ` + shlex.quote で包んだ入力。区切り語は `foo($(case x in x) echo foo;; esac))` で登録され、2 行目で本文が閉じ、3 行目の起動が deny。(FR1, FR5 / AC-1)
- [ ] TS2（deny、CASES）: `zsh -c ` + shlex.quote(`echo "$(case x in x) :;; esac)"; python3 -i`)。(FR1, FR5 / AC-2)
- [ ] TS3（deny、CASES）: 省略できる先頭の `(` を持つパターン。`echo "$(case x in (x) :;; esac)"; python3 -i`。(FR1, FR2)
- [ ] TS4（deny、CASES）: `|` で区切ったパターンと zsh の終端 `;&` / `;|`。`zsh -c` で `echo "$(case x in a|b) :;& x) :;| *) :;; esac)"; python3 -i`。(FR1)
- [ ] TS5（deny、CASES）: bash の終端 `;;&`。`bash -c` で `echo "$(case x in x) :;;& *) :;; esac)"; python3 -i`。(FR1)
- [ ] TS6（deny、CASES）: 最後の項目が終端を省いて `esac` で終わる。`echo "$(case x in x) :; esac)"; python3 -i`、および `;` の代わりに改行を置いた形。(FR1)
- [ ] TS7（deny、CASES）: パターンを閉じた `)` の直後の入れ子の case 文。`echo "$(case x in x) case y in y) :;; esac;; esac)"; python3 -i`。(FR3)
- [ ] TS8（deny、CASES）: 引用符の中の `)` を持つパターンと、本体のサブシェル。`echo "$(case x in ')') (:);; x) :;; esac)"; python3 -i`。(FR2, FR3)
- [ ] TS9（deny、CASES）: 項目の本体の入れ子の置換の中の case 文。`echo "$(case x in x) echo "$(case y in y) :;; esac)";; esac)"; python3 -i`。(FR3)
- [ ] TS10（deny、CASES）: 引数の `esac` とコメントの中の `esac` は case 文を閉じない。`echo "$(case x in x) echo esac;; esac)"; python3 -i` と、本体に `: # esac` と改行を置いた形。(FR1, FR3)
- [ ] TS11（silent、CASES）: 置換の中身は判定しない。`echo "$(case x in x) python3 -i;; esac)"`。(FR6)
- [ ] TS12（silent、CASES）: `esac` で閉じない case 文は判定不能。`echo "$(case x in x) :;;"; python3 -i`。(FR4)
- [ ] TS13（silent、CASES）: case 文の本体の中の heredoc は判定不能のまま。1 行目に `echo "$(case x in x) cat <<E` を置き、本文と `E`、`;; esac)"; python3 -i` を続ける形。(FR4)
- [ ] TS14（silent、CASES）: zsh の `case x { ... }` の形は判定不能。`echo "$(case x { x) :;; })"; python3 -i`。(FR4)
- [ ] TS15（deny、CASES）: 区切り語の範囲の二重引用符の中で、項目が複数ある case 文。TS1 と同じ形で、範囲の中の置換を `$(case x in a) :;; x) echo foo;; esac)` にしたもの。(FR1, FR5)
- [ ] TS16（性能、テストメソッド）: 多数の項目を持つ case 文と、深く入れ子にした case 文を二重引用符の中の置換に置き、後ろの `python3 -i` が時間内に deny になる。両コピーで確かめる。(NFR1)
- [ ] TS17（既存）: バッククォートの中の case 文の行（569、807、816、823 行）を含む既存の `CASES` の行と、`TestNoRecursion`、`TestSharedQuotedUnitReader`、`TestStaticConstraints`、`TestGuardDocumentation`、`TestCopies` が今のまま通る。(FR6, FR8, NFR2, NFR3)

## 14. 確認事項

### 14.1 確認済み事項

- なし

### 14.2 未確認・保留事項（前提として置いたもの）

- [ ] A1（影響: 中、可逆）: 対象は二重引用符の中の置換を読む `_skip_substitution` だけ。引用符の外の `$(case ...)` を読む `_dollar` → `_skip_parens` / `_scan_parens` は対象外とする。課題の該当箇所と期待する挙動が `_skip_substitution` だけを名指ししており、前の機能（codex-guard-anon-heredoc-delim-dq-subst の FR8）も `_skip_parens` / `_scan_parens` を対象外にしている。
- [ ] A2（影響: 低、可逆）: zsh の `case word { ... }` の形は読まず、判定不能（silent）のままにする。今と同じ fail-open で、この形での後退はない。
- [ ] A3（影響: 低、可逆）: `_is_case_keyword` の今の判定（直前が `;&|(\n{!` か予約語）は残し、パターンを閉じた `)` の直後と項目の終端の直後をコマンドの位置として足すだけにする。`>&` / `<&` / `>|` の直後のリダイレクト先の語 `case` を予約語と取り違える今の挙動は直さない。取り違えても、続く語が `in` でなければ判定不能、`esac` が無ければ判定不能になる。
- [ ] A4（影響: 低、可逆）: 置換の中の heredoc（`heredoc in a substitution`）を判定不能にする規則は、case 文の本体の中でも変えない。
- [ ] A5（影響: 低、可逆）: パターンの位置の語頭の `#` は、今の `p` の文脈のコメントの規則で読む。zsh の `(#i)` のような glob の修飾子をパターンに書いた入力の読みは確かめていない。
- [ ] A6（影響: 低、可逆）: 既存の `CASES` に、二重引用符の中の `$(case ...)` を silent と固定している行は無い。case を含む既存の行（569、807、816、823 行）はどれもバッククォートの文脈で、`_skip_substitution` の `b` の文脈は case を見ないので、判定は変わらない。

### 14.3 デザインステップ

- スキップ: 画面や UI の無い、フックのスクリプトの解析処理のバグ修正のため。
