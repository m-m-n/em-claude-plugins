---
title: "codex-guard-delim-subst-undecidable"
created_date: 2026-10-23
status: draft
---

# codex-guard-delim-subst-undecidable - 要件定義書

## 1. 概要

### 1.1 背景
codex-guard-heredoc-delim-brace-case で、ヒアドキュメントの区切り語の `${ ... }` の中の `$( ... )` を読む処理に fail-open の回帰が入った。区切り語の `${ }` の中の `$( )` に、置換内の `<<`、コマンドの位置の算術の `<<`、引数の語の中の括弧のいずれかがあると、終端行の後の `python3 -i` が deny にならない。

### 1.2 目的
ヒアドキュメントの区切り語の `${ ... }` の中の `$( ... )` に、置換内の `<<`、コマンドの位置の算術の `<<`、引数の語の中の括弧のどれがあっても、区切り語の終わりを zsh と同じ位置に置き、終端行の後の `python3 -i` を deny に戻す。

### 1.3 スコープ
- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

上記 2 つのコピーの共有スキップ `_skip_substitution` の読み（FR1〜FR3）、両コピーの同一性（FR4）、回帰テスト（FR5）、docstring（FR6）を対象とする。

## 2. ビジネス要件

### 2.1 ビジネス目標
- ヒアドキュメントの区切り語の `${ ... }` の中の `$( ... )` に、置換内の `<<`、コマンドの位置の算術の `<<`、引数の語の中の括弧のどれがあっても、区切り語の終わりを zsh と同じ位置に置き、終端行の後の `python3 -i` を deny に戻す（codex-guard-heredoc-delim-brace-case で入った fail-open の回帰を直す）。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 区切り語の `${ }` の中の `$( )` を含む構成で、終端行の後の `python3 -i` が両方のコピーで deny になる。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | 置換内の同じ行で閉じる `<<` の読み | resolved |
| FR2 | コマンドの位置の `((` は算術、`))` で閉じなければサブシェル | resolved |
| FR3 | 引数の語の中の括弧は語の文脈 | resolved |
| FR4 | 両コピーの同一性 | resolved |
| FR5 | 回帰テスト | resolved |
| FR6 | docstring の追従 | resolved |

### 4.2 機能詳細

#### FR1: 置換内の同じ行で閉じる `<<` の読み

**説明**: 共有スキップ `_skip_substitution`（em-workflow / em-review の `scripts/codex-hook-interactive-guard.py`）は、case 文の外の `<<` のうち、置換を閉じる `)` までに引用されていない改行が無いものを判定不能にしない。閉じの位置を変えずに読み進め、本文は読まない。

**ビジネスルール**:
- `<<` の後、置換が閉じる前に引用されていない改行が来る形は、今のとおり判定不能にする。
- case 文の中（subject・パターン・項目の本体）の `<<` は、今のとおり判定不能にする。
- `<<<` は今のとおり heredoc ではない。
- この読みは二重引用符の中の `$( )` と、区切り語の `${ }` の中の引用されていない `$( )` の両方に効く。
- 改行が来るかどうかは `<<` ごとに先読みし直して確かめず、1 回の走査の中で判定して線形時間を保つ。

#### FR2: コマンドの位置の `((` は算術、`))` で閉じなければサブシェル

**説明**: `_skip_substitution` の中で、コマンドの位置の `((`（for の後の `((` を含む。空白を挟んだ `( (` は含まない）は、`))` で閉じれば算術の文脈として読む。中の `<<` は左シフトで、heredoc とみなさない。

**ビジネスルール**:
- 閉じた後は、包むリストがコマンドの位置になる（今の close_command の意味を保つ）。
- `((` に対応する閉じが `))` にならない場合は、その `((` から入れ子のサブシェル 2 段として読み直し、今の読みと同じ結果にする。
- 読み直しは 1 つの `((` につき 1 回までにする。
- 読み直しで読む文字の総量には上限を設け、明示スタックで処理して線形時間を保つ。
- 上限を超えたら判定不能にする。

#### FR3: 引数の語の中の括弧は語の文脈

**説明**: `_skip_substitution` の中で、コマンドの位置でない `(` は語の括弧の新しい文脈で開く。対象は語の途中の `(` と、引数の位置の語頭の `(` の両方。

**ビジネスルール**:
- 中の語はコマンドの位置にならず、case・閉じの語・head は効かない。
- `#` は語の文字として読み、注釈にしない（`(#q...)` などのグロブフラグのため）。
- `;`・`&`・`|` と改行も語の文字として読み、判定不能にしない。
- 引用・`\` の組・`$( )`・`$(( ))`・`${ }`・バッククォートは、ほかの文脈と同じく追う。
- 入れ子の `(` は同じ文脈の入れ子として開き、`)` は語の中で閉じる。
- 閉じた後、包むリストは元の状態のまま語の中を読み続ける。
- コマンドの位置の `(`（サブシェル）、`<(`、`>(`、zsh の `=(`、関数 head の `name()`、`for name (words)` の語の並び（w 文脈）は、今の読みを保つ。
- 既存の w 文脈は流用しない（w は `#` を注釈として読むため）。

#### FR4: 両コピーの同一性

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更で直し、バイト単位で同一に保つ。

#### FR5: 回帰テスト

**説明**: テストシナリオ（12 章）の行を `tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で足し、両方のコピーに流す。既存の deny / silent の行は消さない。

#### FR6: docstring の追従

**説明**: `_skip_substitution` の docstring（と、必要ならモジュールの docstring）を FR1〜FR3 の読みに合わせる。

**ビジネスルール**:
- 『a heredoc anywhere in the chunk (item bodies included)』の文言は case 文の中の heredoc について残す。
- heredoc を常に判定不能とする書き方は改める。
- テストが固定している文言（`TestSubstitutionSkipDocumentation` の `UNDECIDABLE_MARKERS` / `RULE_MARKERS` など）を変える場合は、テスト側の文言も同じ変更で直す。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1: 線形時間を保つ。1 文字あたりの仕事は定数（読み直しは FR2 の上限の範囲内）で、明示スタックを使い再帰しない（`TestNoRecursion`、大規模入力の時間テスト）

### 5.2 セキュリティ要件
- NFR3: 今は判定できている形を新たに判定不能（出力なし）に変えない

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2: `_skip_substitution` の呼び出し構造の制約を保つ。`_skip_substitution` を呼ぶのは `_read_quoted_unit` だけで、`_skip_substitution` から到達できるメソッドに `_skip_substitution` / `_read_quoted_unit` / `parse` / `_remove_range_quotes` を含めない（`TestSharedQuotedUnitReader`、`TestSubstitutionSkipCallStructure`）

### 5.5 互換性要件
- NFR4: plugin の version は変えない

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 2 つのコピーは同じ変更の中で一緒に直し、バイト単位で同一に保つ。`CASES` の新しい行は両方のコピーに流す。（A1）
- 線形時間と呼び出し構造の制約を保つ（NFR1, NFR2）。（A2）

### 9.2 ビジネス上の制約
- plugin の version は変えない。（A3）

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-delim-subst-undecidable/**`
- `test-docs/codex-guard-delim-subst-undecidable/**`

`feature-docs/codex-guard-delim-subst-undecidable/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-delim-subst-undecidable/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-delim-subst-undecidable/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-delim-subst-undecidable/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-delim-subst-undecidable/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| TS13 の行を分けた形の期待値は zsh の実測で確定していない | 低 | 実装時に zsh の実測で確かめて確定する。合わない場合は同じ行に収まる `*(#qN)` の形に置き換える |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: 再現手順の文字列 `zsh -c 'if false; then\n: <<${v:-$(echo <<EOF)}\n${v:-$(echo <<EOF)}\nfi\npython3 -i'` をフックの標準入力の `tool_input.command` に渡すと、両方のコピーが deny を返す
- [ ] AC-2: 区切り語の `${ }` に `$( ((1 << 2)) )` を置いた同じ構成と、`$(for ((i=0;i<1<<2;i++)) do :; done)` を置いた同じ構成で、両方のコピーが deny を返す
- [ ] AC-3: 区切り語の `${ }` に `$(echo foo(case x))` を置いた同じ構成と、`$(echo foo(a;b))` を置いた同じ構成で、両方のコピーが deny を返す
- [ ] AC-4: 今 deny の `echo "$(echo foo(a;b))"; python3 -i` と `echo "$( ((echo a) ) )"; python3 -i` が、両方のコピーで deny のまま
- [ ] AC-5: 2 つのコピーがバイト単位で同一
- [ ] AC-6: SPEC に zsh 5.9 の実測結果（`zsh -f`、`python3 -i` の代わりに無害な `echo`）が記録されている（内容は SPEC.md の「zsh 5.9 Measurements」を参照）
- [ ] AC-7: テストシナリオの行が `CASES` にあり、両方のコピーに流れる
- [ ] AC-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点

コマンドは Python の式で表す。

- [ ] TS1 (deny, AC-1): `"\n".join(["zsh -c 'if false; then", ": <<${v:-$(echo <<EOF)}", "${v:-$(echo <<EOF)}", "fi", "python3 -i'"])`
- [ ] TS2 (deny): `"\n".join(["cat <<${v:-$(echo <<EOF)}", "${v:-$(echo <<EOF)}", "python3 -i"])`
- [ ] TS3 (silent): 終端行が EOF だけでは本文が閉じない。`"\n".join(["cat <<${v:-$(echo <<EOF)}", "EOF", "python3 -i"])`
- [ ] TS4 (deny, AC-2): `"\n".join(["cat <<${v:-$( ((1 << 2)) )}", "${v:-$( ((1 << 2)) )}", "python3 -i"])`
- [ ] TS5 (silent): 短い終端行では本文が閉じない。`"\n".join(["cat <<${v:-$( ((1 << 2)) )}", "2)) )}", "python3 -i"])`
- [ ] TS6 (deny, AC-2): `"\n".join(["cat <<${v:-$(for ((i=0;i<1<<2;i++)) do :; done)}", "${v:-$(for ((i=0;i<1<<2;i++)) do :; done)}", "python3 -i"])`
- [ ] TS7 (deny, AC-3): `"\n".join(["cat <<${v:-$(echo foo(case x))}", "${v:-$(echo foo(case x))}", "python3 -i"])`
- [ ] TS8 (silent): `"\n".join(["cat <<${v:-$(echo foo(case x))}", "x))}", "python3 -i"])`
- [ ] TS9 (deny, AC-3): `"\n".join(["cat <<${v:-$(echo foo(a;b))}", "${v:-$(echo foo(a;b))}", "python3 -i"])`
- [ ] TS10 (deny, AC-4 回帰): `'echo "$(echo foo(a;b))"; python3 -i'`
- [ ] TS11 (deny, AC-4 回帰): `'echo "$( ((echo a) ) )"; python3 -i'`
- [ ] TS12 (deny): 二重引用符の中の同じ行の heredoc は判定できる。`'echo "$(cat <<EOF)"; python3 -i'`
- [ ] TS13 (deny): 語の括弧の中の改行。`"\n".join(["cat <<${v:-$(echo *(e:true", ":N))}", "${v:-$(echo *(e:true", ":N))}", "python3 -i"])`。区切り語は 1 行で比べるため、行を分けたこの形の期待値は実装時に zsh の実測で確かめて確定する。合わない場合は、同じ行に収まる `*(#qN)` の形（`cat <<${v:-$(echo *(#qN))}` / `${v:-$(echo *(#qN))}` / `python3 -i` → deny）に置き換える
- [ ] TS14 (silent, 既存の行を保つ): `CASES` 967 行目の、case 文の項目の本体の中の heredoc は判定不能
- [ ] TS15 (silent): `<<` の後、置換の中で改行が来る形は判定不能。`'echo "$(cat <<EOF\nbody\nEOF\n)"; python3 -i'`

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 判定不能 | フックが判定を出さない（出力なし、silent） |
| 2 つのコピー | `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: 2 つのコピーは同じ変更の中で一緒に直し、バイト単位で同一に保つ。`CASES` の新しい行は両方のコピーに流す。（根拠: `.claude/rules/hook-tests.md`）
- [x] A2: 線形時間と呼び出し構造の制約を保つ（NFR1, NFR2）。（根拠: 既存テストで固定されている）
- [x] A3: plugin の version は変えない。（根拠: `.claude/rules/core-plugin-version-bump.md`）
- [x] A4: 置換内の `<<` は shared_same_line で読む（FR1）。（根拠: batch の Codex 相談の回答。zsh 5.9 の実測 1〜4 と一致する）
- [x] A5: コマンドの位置の `((` は arith_or_subshell で読む（FR2）。（根拠: batch の Codex 相談の回答。zsh 5.9 の実測 5・6・8 と一致する）
- [x] A6: 語の括弧は word_ctx_all_chars で読む（FR3）。（根拠: batch の Codex 相談の回答。zsh 5.9 の実測 7 と、`${v:-$(echo foo(a;b))}`・`*(e:true<改行>:N)` が受理されることに一致する）
- [x] A7: design ステップは飛ばす。（根拠: batch の決定表で推奨 skip を採用した。UI の無いフックスクリプトの構文解析のバグ修正で、design の対象が無い）

### 14.2 未確認・保留事項
- [ ] TS13 の行を分けた形の期待値（実装時に zsh の実測で確定する）

## 15. 参考資料

- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
