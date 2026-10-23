---
title: "codex-guard-for-wordlist-glob-qualifier"
created_date: 2026-10-23
status: draft
---

# codex-guard-for-wordlist-glob-qualifier - 要件定義書

## 1. 概要

### 1.1 背景
`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）は、zsh の `for name (words)` の語一覧の中で開いた入れ子の `(`（glob 修飾子）でも、直前が `(` の `#` をコメントの始まりと読む。`*(#qN)` の `#` は語の途中にあり、zsh ではコメントにならない。後ろに改行がなければ判定不能（`_Undecidable`）になり、置換の後ろの `python3 -i` を拒否しない（拒否漏れ）。

feature `codex-guard-subst-reading-regressions` の review round 1 で deferred になった指摘（stable_id `fa91f061156d70be`、medium）。

### 1.2 目的
codex-hook-interactive-guard が、zsh の `for name (words)` の語一覧の中の glob 修飾子 `*(#qN)` の `#` をコメントと読み違えて、置換の後ろの `python3 -i` を拒否し損なう（fail-open）状態をなくす。

### 1.3 スコープ
- 対象: `_skip_substitution` の文脈 w（語一覧）での `#` の読み方
- 対象: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`
- 対象: `tests/test_codex_hook_interactive_guard.py` の `CASES`
- 対象外: p の文脈の `$(ls *(#qN))` の読み違え

## 2. ビジネス要件

### 2.1 ビジネス目標
codex-hook-interactive-guard が、zsh の `for name (words)` の語一覧の中の glob 修飾子 `*(#qN)` の `#` をコメントと読み違えて、置換の後ろの `python3 -i` を拒否し損なう（fail-open）状態をなくす。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow / em-review の利用者 | codex-hook-interactive-guard を PreToolUse(Bash) フックとして使う Claude Code 利用者 |

### 2.3 期待される効果
- `$( )` の中の zsh の for の語一覧に `#` で始まる glob 修飾子を書いた場合でも、置換の後ろの `python3 -i` が deny になる

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 語一覧に glob 修飾子を含むコマンドの判定 | PreToolUse(Bash) フック | 高 |

### 3.2 ユースケース詳細

#### UC01: 語一覧に glob 修飾子を含むコマンドの判定

**アクター**: PreToolUse(Bash) フック

**事前条件**:
- `tool_input.command` に、`$( )` の中の zsh の for の語一覧に `*(#qN)` を含み、置換の後ろに `python3 -i` があるコマンドが入っている

**基本フロー**:
1. フックの標準入力に PreToolUse(Bash) の JSON を渡す（コマンド自体は実行しない）
2. フックが語一覧の入れ子の `(` の直後の `#` を語の文字として読む
3. フックが置換の後ろの `python3 -i` を読み、deny を返す

**事後条件**:
- 両コピーが deny を返す

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 語一覧の入れ子の ( の直後の # を語の文字として読む | 入れ子の entry では直前が `(` の `#` をコメントの始まりにしない | 高 |
| FR2 | コメントは一番外の語一覧の entry でだけ始まる | 一番外の entry での読み方は変えない | 高 |
| FR3 | 両コピーを同じに直す | 2 つのコピーをバイト単位で同一に保つ | 高 |
| FR4 | 再発を検出するテスト | 再現手順の 2 つの入力を deny の行として `CASES` に足す | 高 |

### 4.2 機能詳細

#### FR1: 語一覧の入れ子の ( の直後の # を語の文字として読む

**説明**: `_skip_substitution` の文脈 w で、語一覧の中で開いた入れ子の `(` の entry（`stack[-2]` が `w` のもの）では、直前が `(` の `#` をコメントの始まりにせず語の文字として読む。

**入力**:
- `tool_input.command`: 文字列 - PreToolUse(Bash) の JSON のコマンド

**出力**:
- 判定: deny

**ビジネスルール**:
- `echo "$(for x (*(#qN)) { :; })"; python3 -i` は deny になる
- `zsh -c 'setopt extendedglob; echo "$(for x (*(#qN)) { :; })"; python3 -i'` は deny になる

#### FR2: コメントは一番外の語一覧の entry でだけ始まる

**説明**: 文脈 w の `#` がコメントを始めるのは、一番外の語一覧の entry（`stack[-2]` が `w` でないもの）を読んでいるときだけとする。

**ビジネスルール**:
- 一番外の entry での読み方は変えない: 直前が空白・タブ・改行・`;` `&` `|` `(` の `#` がコメントを始め、次の改行まで続く
- 既存の置換読み TS8 の `for x (# c<改行>a)` の読み方を含む

#### FR3: 両コピーを同じに直す

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR4: 再発を検出するテスト

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に、再現手順の 2 つの入力（zsh -c 版と最上位版）を deny の行として足し、両コピーに流す。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR1 読み取りの線形性: 読み取りの線形性を保つ。追加する判定は 1 文字ごとに定数時間（`stack[-2]` の参照）とし、既存の TS26（語一覧のコメント行を DEPTH 行並べたもの）の時間内判定を維持する

### 5.2 セキュリティ要件
- 該当なし（FR1 の拒否漏れの解消に含まれる）

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件
- 該当なし

### 5.5 互換性要件
- 該当なし

## 6. UI/UX要件

該当なし。フックスクリプトの読み取り規則の修正で、画面や UI が無い。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- 2 つのコピーはバイト単位で同一に保つ
- plugin の version は触らない

### 9.2 ビジネス上の制約
- 該当なし

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-for-wordlist-glob-qualifier/**`
- `test-docs/codex-guard-for-wordlist-glob-qualifier/**`

`feature-docs/codex-guard-for-wordlist-glob-qualifier/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-for-wordlist-glob-qualifier/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-for-wordlist-glob-qualifier/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-for-wordlist-glob-qualifier/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-for-wordlist-glob-qualifier/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 入れ子の entry かどうかの判定（前提 A1） | 中 | `stack[-2] == "w"` で判定する |

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: `zsh -c 'setopt extendedglob; echo "$(for x (*(#qN)) { :; })"; python3 -i'` を tool_input.command に渡すと、両コピーが deny を返す
- [ ] AC2: `echo "$(for x (*(#qN)) { :; })"; python3 -i` を渡すと、両コピーが deny を返す
- [ ] AC3: AC1 と AC2 の入力が CASES に deny の行として 1 行ずつあり、test_cases_run_against_both_copies と test_cases_are_unique が通る
- [ ] AC4: 既存の置換読み TS1・TS5・TS6・TS7・TS8・TS28 の行と test_ts26_commented_lines_in_a_for_word_list_are_read_in_time が変わらず通る
- [ ] AC5: TestCopies.test_the_two_copies_are_byte_identical が通る
- [ ] AC6: `python3 -m unittest tests.test_codex_hook_interactive_guard` が全件通る

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系（TS1, FR1・FR4）: `zsh -c 'setopt extendedglob; echo "$(for x (*(#qN)) { :; })"; python3 -i'` が deny
- [ ] 正常系（TS2, FR1・FR4）: `echo "$(for x (*(#qN)) { :; })"; python3 -i` が deny
- [ ] 回帰（TS3, FR2）: 既存の置換読み TS8 `echo "$(for x (# c\na) { case x in x) printf '%s' '"';; esac; })"; python3 -i` が deny のまま通り続ける（変更しない）
- [ ] 回帰（TS4, FR2）: 既存の置換読み TS1・TS5・TS6・TS7・TS28 が deny のまま通り続ける（変更しない）
- [ ] パフォーマンス（TS5, NFR1）: 既存の test_ts26_commented_lines_in_a_for_word_list_are_read_in_time が通る（変更しない）
- [ ] 同一性（TS6, FR3）: TestCopies.test_the_two_copies_are_byte_identical が通る

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 文脈 w | `_skip_substitution` で zsh の `for name (words)` の語一覧を読んでいる文脈 |
| 一番外の語一覧の entry | 文脈 w の entry のうち、`stack[-2]` が `w` でないもの |
| 入れ子の entry | 語一覧の中で開いた入れ子の `(` の entry。`stack[-2]` が `w` のもの |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 前提 A1: 入れ子の entry かどうかは `stack[-2] == "w"` で判定できる。文脈 w の中で読んだ `(` は必ず w の entry を積み、一番外の w の下は p・8 など w 以外になる
- [x] 前提 A2: FR2 により、入れ子の entry では直前が空白などの `#` もコメントを始めない
- [x] 前提 A3: p の文脈の `$(ls *(#qN))` の読み違えは今回の範囲外で、変更しない
- [x] 前提 A4: plugin の version は触らない

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- 該当箇所: `em-review/scripts/codex-hook-interactive-guard.py:2539`
- 該当箇所: `em-workflow/scripts/codex-hook-interactive-guard.py`（同一内容）
