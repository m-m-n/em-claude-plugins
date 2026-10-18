---
title: "codex-guard-anon-heredoc-delim-dq-subst"
created_date: 2026-10-18
status: draft
---

# codex-guard-anon-heredoc-delim-dq-subst - 要件定義書

## 1. 概要

### 1.1 背景
codex-hook-interactive-guard は、匿名関数の引数位置にある heredoc の区切り語の範囲で、二重引用符の中の `$( )` / `$(( ))` の中の引用符を除去している。このため zsh と異なる区切り語が登録され、見逃し（fail-open）と誤 deny が起きる。

### 1.2 目的
- 匿名関数の引数位置にある heredoc の区切り語の範囲で、zsh と同じ区切り語を登録する。二重引用符の中の `$( )` / `$(( ))` の中の引用符を除去していることで起きる見逃し（fail-open）と誤 deny をなくす。
- `\` の対、単引用符、二重引用符の引用除去の規則を 1 つの共通関数にまとめ、語の読み取りと区切り語の範囲から呼ぶ。2 つの読みが再び食い違わないようにする。

### 1.3 スコープ
- 対象: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`（2 つのコピー）、`tests/test_codex_hook_interactive_guard.py`。
- 対象外: 4.2 の F08 に挙げる 4 点。

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 の 2 点。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 区切り語の範囲の二重引用符の中に置換がある入力で、見逃し（fail-open）と誤 deny が起きない。
- 語の読み取りと区切り語の範囲の引用除去が 1 つの共通関数を通る。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| F01 | 引用の 1 単位を読む共通関数 | `\` の対、単引用符、二重引用符のどれか 1 単位を読む | 高 |
| F02 | 共通関数を両方から呼ぶ | parse 本体と `_remove_range_quotes` の 3 分岐から共通関数を呼ぶ | 高 |
| F03 | 二重引用符の中の置換を原文のまま残す | `` ` `` / `$(` / `$((` を `_skip_substitution` で読み飛ばし、原文を残す | 高 |
| F04 | 上限を越える読み飛ばしは判定不能 | 読み飛ばしが上限を越えたら判定不能にする | 高 |
| F05 | 語の読み取りの区別を保つ | 語の読み取り側の挙動を変えない | 高 |
| F06 | 2 つのコピーの同一性 | 2 つのコピーを一緒に直し、バイト単位で同一に保つ | 高 |
| F07 | docstring の更新 | モジュールと `_remove_range_quotes` の docstring を更新する | 中 |
| F08 | 対象外 | 対象外の 4 点を SPEC に明記する | 中 |

### 4.2 機能詳細

#### F01: 引用の 1 単位を読む共通関数

**説明**: `\` の対、単引用符（`'...'`）、二重引用符（`"..."`）のどれか 1 単位を読む共通関数を作る。

**入力**:
- 開始位置
- 上限: その位置を含まない

**出力**:
- 除去後の文字列
- 次の位置

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 判定不能（`_Undecidable`） | 上限の前で単位が閉じない | 判定不能にする |

#### F02: 共通関数を両方から呼ぶ

**説明**:
- parse 本体の `\` / `'` / `"` の 3 分岐は、上限を入力の終わりとして共通関数を呼ぶ。
- `_remove_range_quotes` の同じ 3 分岐は、上限を範囲の終わりとして呼ぶ。
- 今の `_double_quoted` が持つ二重引用符の読みは共通関数に移す。

#### F03: 二重引用符の中の置換を原文のまま残す

**説明**: 共通関数は、二重引用符の中の `` ` `` / `$(` / `$((` を `_skip_substitution` で読み飛ばし、置換の原文を中の引用符も含めて残す。区切り語の範囲でも語の読み取りでも同じ。

#### F04: 上限を越える読み飛ばしは判定不能

**説明**: `_skip_substitution` が返した位置が上限を越えたら判定不能にする。`_skip_substitution` が自分で出す判定不能（置換が閉じない、置換の中の heredoc や case）もそのまま伝える。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 判定不能 | `_skip_substitution` が返した位置が上限を越えた | 判定不能にする |
| 判定不能 | `_skip_substitution` 自身が判定不能を出した（置換が閉じない、置換の中の heredoc や case） | そのまま伝える |

#### F05: 語の読み取りの区別を保つ

**説明**: 語の読み取り側の挙動は変えない。次の 3 つ。
- 二重引用符の中の置換と `$` で語を dynamic にすること。
- 空の引用（`''` や `""`）が語を始めることと、`\` と改行の対が文字を足さず語も始めないことの区別。
- 入力の終わりにある `\` を判定不能にすること。

#### F06: 2 つのコピーの同一性

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で一緒に直し、バイト単位で同一に保つ。

#### F07: docstring の更新

**説明**: モジュールの docstring の区切り語の範囲の段落と、`_remove_range_quotes` の docstring を更新する。次を書く。
- 二重引用符の中の `$( )` / `$(( ))` が原文のまま残ること。
- 読み飛ばしが範囲を越えると判定不能になること。
- 引用除去は共通関数が担うこと。

**ビジネスルール**:
- `DELIMITER_RANGE_MARKERS` の 4 文と、`DOCSTRING_MARKERS` の「inside double quotes」は残す。

#### F08: 対象外

**説明**: 次は対象外とし、SPEC に明記する。
1. 区切り語の範囲の引用符の外にある `${ ... }` の読み。中の引用符を除去する今の処理のままにする。
2. `$` の扱い全般（`_dollar`、範囲の中の `$'` / `$"` を判定不能にする規則、引用符の外の `$(` を `_skip_parens` で読む規則）。
3. 通常の語の読み取り側（`_dollar`）の `${ ... }` の食い違い。これは別の課題として扱う。
4. `_scan_parens` による範囲の見つけ方。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 処理時間は入力の長さに対して線形を保つ。既存の `test_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied`（TS-17）が通ること。

### 5.2 セキュリティ要件
- 標準ライブラリだけを使い、書き込みやプロセスの起動をしない（`TestStaticConstraints`）。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- 呼び出しは「読み取り側 → 共通関数 → 反復で読む `_skip_substitution`」に限る。再帰と循環呼び出しは持ち込まない（`TestNoRecursion`）。

### 5.5 互換性要件
- `plugin.json` と `marketplace.json` の version は変えない。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 5.1〜5.5 の非機能要件。
- 2 つのコピーをバイト単位で同一に保つ（F06）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-heredoc-delim-dq-subst/**`
- `test-docs/codex-guard-anon-heredoc-delim-dq-subst/**`

`feature-docs/codex-guard-anon-heredoc-delim-dq-subst/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-heredoc-delim-dq-subst/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-heredoc-delim-dq-subst/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
前提（requirements-analyst の assumptions）。いずれも影響度は低、取り消し可能。

| 前提 | 影響度 |
|------|--------|
| 範囲の中のバッククォートは共通関数に届かない。バッククォートを含む範囲は、`_read_argument_parens` がこれまでどおり群として開く（1246 行）ため。 | 低 |
| 区切り語として登録される語では dynamic フラグは使われない（`_finish_word` が redirect の分岐で早く返る、741〜748 行）。共通関数が返す dynamic を範囲側で捨てても、判定は変わらない。 | 低 |
| zsh 5.9 は heredoc の区切り語の `${ ... }` の中でも引用符を除去する。範囲側の今の `${ ... }` の処理は zsh と一致している（batch の Codex 相談での実測による）。 | 低 |
| `_double_quoted` は共通関数に吸収するので、なくしてもよい。名前を残す必要はない。テストからは名前で参照されていない。 | 低 |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: 見逃し側の再現入力（`zsh -c` + `shlex.quote` で包んだ 4 行。`function { :; } << foo("$(echo "x")")` / `foo("$(echo "x")")` / `foo($(echo "x"))` / `python3 -i`）が deny になる。
- [ ] AC-2: 誤 deny 側の再現入力（`function { :; } << foo("$(echo "a")")` / `foo($(echo a))` / `python3 -i` / `foo($(echo "a"))` の 4 行）が silent になる。
- [ ] AC-3: AC-1 と AC-2 の 2 入力を、`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` の形で追加する。
- [ ] AC-4: 区切り語の範囲の二重引用符の中で、置換の読み飛ばしが範囲の終わりを越える入力が silent（判定不能）になる。
- [ ] AC-5: parse 本体の `\` / `'` / `"` の分岐と、`_remove_range_quotes` の同じ 3 分岐が、どちらも共通関数を呼んでいる。parse 本体にも `_remove_range_quotes` にも、二重引用符の中を読むループが残っていない。
- [ ] AC-6: リポジトリルートで実行した `python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る。既存の `CASES`、`TestCopies`（バイト単位の同一性）、`TestNoRecursion`、TS-17、`TestGuardDocumentation` を含む。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（deny、`CASES` に追加）: AC-1 の見逃し側の再現入力。
- [ ] TS2（silent、`CASES` に追加）: AC-2 の誤 deny 側の再現入力。
- [ ] TS3（silent、`CASES` に追加）: 読み飛ばしが範囲の終わりを越える。例: `function { :; } << foo("$(echo ")")")` と本文の後ろの `python3 -i`。`_scan_parens` は範囲を `("$(echo ")` で閉じ、置換の読み飛ばしはその先で閉じる。
- [ ] TS4（deny、`CASES` に追加）: 二重引用符の中の `$(( ))` を原文のまま残した区切り語の行で本文が閉じ、その後ろの `python3 -i` が deny になる。例: `function { :; } << foo("$((1+2))")` / `foo($((1+2)))` / `python3 -i`
- [ ] TS5（deny、`CASES` に追加）: 二重引用符の中で置換が入れ子になり、中に引用符がある区切り語を原文のまま残す。例: `function { :; } << foo("$(a "$(b "c")")")` / `foo($(a "$(b "c")"))` / `python3 -i`
- [ ] TS6（silent、`CASES` に追加）: 空の引用は語を始める（語の読み取り側の区別を保つ）。`python3 '' -i` と `python3 "" -i` は、空の語がオペランドになるので silent。既存の「行継続」（`python3 \<改行> -i` → deny、153 行）と対になる。実装の前に、変更前の判定が silent であることを確かめる。
- [ ] TS7（既存）: 714〜752 行の区切り語の範囲のケース、TS-10（二重引用符の中の `$'` は契機にしない）、749 行（引用符の外の `$( )` の中の引用符を除去しない）が今のまま通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 区切り語の範囲 | 匿名関数の引数位置にある heredoc の区切り語の範囲 |
| 共通関数 | `\` の対、単引用符、二重引用符のどれか 1 単位を読む関数（F01） |
| 判定不能 | `_Undecidable`。判定結果は silent |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 共通関数の範囲: `\` の対・単引用符・二重引用符の 3 種類を 1 単位ずつ読む共通関数を作り、parse 本体と `_remove_range_quotes` の両方から呼ぶ（batch の Codex 相談で quoted-unit-reader を採用）。
- [x] 範囲の引用符の外にある `${ ... }` の読み: 今のまま（中の引用符も除去する）とし、対象外に明記する（batch の Codex 相談で out-of-scope を採用）。通常の語の読み取り側の食い違いは別の課題として扱う。
- [x] design step: 省略する（batch policy decide_autonomously）。フックの判定ロジックの修正で、画面に関わる変更もデザインシステムの候補もない。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- `feature-docs/codex-guard-anon-heredoc-delim-dq-subst/SPEC.md`
