---
title: "codex-guard-anon-brace-forms"
created_date: 2026-10-12
status: draft
---

# codex-guard-anon-brace-forms - 要件定義書

## 1. 概要

### 1.1 背景
codex-hook-interactive-guard（em-workflow / em-review の両コピー）は、zsh の匿名関数の次の 3 形で本体を判定していない（見逃し、fail-open）。

- `function { ...; }`（括弧なし）
- `function () { ...; } arg`（閉じ波括弧の後に引数）
- `() { ...; } arg`（語の無い空の `()`）

### 1.2 目的
- 上の 3 形で匿名関数の本体を判定し、本体に対話起動があれば deny する。
- パイプの右側に置いた匿名関数を誤って deny しない。
- この見逃し（fail-open）の再発をテストで検出できる状態にする。

### 1.3 スコープ
- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

## 2. ビジネス要件

### 2.1 ビジネス目標
- codex-hook-interactive-guard（em-workflow / em-review の両コピー）が zsh の匿名関数の本体を判定し、本体に対話起動があれば deny する。対象は `function { ...; }`（括弧なし）、`function () { ...; } arg`（閉じ波括弧の後に引数）、`() { ...; } arg`（語の無い空の `()`）の 3 形。
- パイプの右側に置いた匿名関数を誤って deny しない。
- この見逃し（fail-open）の再発をテストで検出できる状態にする。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 匿名関数の 3 形の本体にある対話起動が deny される。
- パイプの右側の匿名関数が誤って deny されない。

## 3. ユースケース

該当なし（UI を持たないフックスクリプトのパーサー修正とテスト追加のみ）

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | ステータス |
|----|--------|------------|
| FR1 | 括弧なしの匿名関数を読む | resolved |
| FR2 | 匿名関数の本体を特定し、閉じ波括弧の後の語を引数として読む | resolved |
| FR3 | パイプの接続を匿名関数の本体に渡す | resolved |
| FR4 | 既存の読みを保つ | resolved |
| FR5 | 説明文を新しい規則に合わせる | resolved |
| FR6 | 両コピーへ同一の変更 | resolved |
| FR7 | 回帰テストを追加する | resolved |

### 4.2 機能詳細

#### FR1: 括弧なしの匿名関数を読む

**説明**: 予約語の連なり（RESERVED_WORDS の先頭の連なりと、`time` 直後の非動的な `-p`）を除いたあとに残った語が、引用・エスケープ・展開を含まない（bare な）`function` 1 語のとき、続く単独の `{` 語で波括弧グループを開き、中のコマンドを判定する。引用・エスケープ付きの `function`、2 語以上（`function f {`）、動的な語の場合は、従来どおりグループを開かない。

#### FR2: 匿名関数の本体を特定し、閉じ波括弧の後の語を引数として読む

**説明**: 次の波括弧グループを匿名関数の本体とする。

- (a) FR1 で開いたグループ。
- (b) 予約語除去後に残った語が bare な `function` 1 語である空の `()` の直後のグループ。
- (c) `(` を開いた時点で語が 1 つも無い空の `()` の直後のグループ。

(b) と (c) では、`()` と `{` の間に改行があってもよい。

**ビジネスルール**:
- 本体の閉じ `}` の後の語は匿名関数の引数として読み、コマンドとして判定せず、判定不能にもしない。
- 引数は次の区切り（`;` `&&` `||` `|` `|&` `&` 改行）で終わる。
- 引数の後の標準入力リダイレクト（`<` `<<` `<<<` `<&` `0<`）は、閉じ直後に置いたときと同じく本体を接続する。

#### FR3: パイプの接続を匿名関数の本体に渡す

**説明**: `function` の語、または語の無い空の `()` が `|` / `|&` の右側にあるとき、その接続を匿名関数の本体のグループに渡す。

**ビジネスルール**:
- 本体の中の入れ子のグループにも、既存の規則どおり接続が届く。
- この継承は匿名関数の本体に限る。本体の後に続く別のコマンドには接続を渡さない。
- 接続下でも `-i` などの明示的な対話起動は deny のまま。

#### FR4: 既存の読みを保つ

**説明**: 次の判定を変えない。

- 匿名関数でない波括弧グループの後の語（`{ python3 -i; } arg`）と、関数定義の本体の後の語（`f() { python3 -i; } arg`、`function f () { python3 -i; } arg`）は、判定不能（silent）のまま。
- 括弧なしの名前付き定義 `function f { python3 -i; }` と、引用付きの `'function' { python3 -i; }` も silent のまま。
- 前の feature で決まった判定（`function () { ... }` の本体を判定する、`'function' ()` と `function function ()` は関数定義として扱う）は変えない。

#### FR5: 説明文を新しい規則に合わせる

**説明**: 次の 3 か所に、匿名関数の 3 形、閉じた後の引数、パイプ接続の継承を書き加える。

- モジュール docstring の手順 4
- `_Group` の説明
- 括弧なし形の判別を担う関数の docstring

**ビジネスルール**:
- 手順 4 の「`{` and `}` delimit a group only as a standalone word at command position」は新しい規則に合わせて改める。
- 既存テストが固定している文言（DOCSTRING_MARKERS / GROUP_HEAD_MARKERS / NAMES_FUNCTION_MARKERS）は残す。

#### FR6: 両コピーへ同一の変更

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` に同じ変更を入れ、バイト単位で同一に保つ。

#### FR7: 回帰テストを追加する

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に、(期待する判定, ラベル, コマンド) 形式で次を追加する（`\n` は改行）。

deny:
- `zsh -c 'function { python3 -i; }'`
- `zsh -c 'function () { python3 -i; } arg'`
- `zsh -c 'function { python3 -i; } arg'`
- `zsh -c '! function { python3 -i; }'`
- `zsh -c '() { python3 -i; } arg'`
- `zsh -c 'function ()\n{ python3 -i; } arg'`
- `zsh -c 'echo x | function { python3 -i; }'`
- `zsh -c 'echo x | function { cat; }; python3'`

silent:
- `zsh -c 'function f { python3 -i; }'`
- `zsh -c "'function' { python3 -i; }"`
- `zsh -c 'function { echo hi; } python3'`
- `zsh -c 'function () { python3; } arg < f'`
- `zsh -c 'echo x | function { python3; }'`
- `zsh -c 'echo x | function () { python3; }'`
- `zsh -c 'echo x | () { python3; }'`
- `zsh -c 'echo x | function { { python3; }; }'`
- `zsh -c '{ python3 -i; } arg'`
- `zsh -c 'f() { python3 -i; } arg'`

## 5. 非機能要件

### 5.1 パフォーマンス要件
- **NFR3**: 括弧なし形の判別では、`{` のたびに語の列を走査し直さず、線形時間を保つ。`test_a_long_run_of_reserved_words_before_a_paren_is_answered` の入力に、予約語の長い連なりの後に `function { python3 -i; }` が続く形を加え、既存の入力と同じ時間内に応答することを確かめる。

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- **NFR1**: 既存の CASES の deny / silent ケースは削除・変更しない。既存テストはすべて通る。
- **NFR2**: 標準ライブラリのみを使い、再帰しない（関数の自己呼び出しも循環も作らない）。`_names_function` の名前と、1 回の前向き走査（words を変更しない）という性質を保つ。
- **NFR4**: 変更後、リポジトリルートで `python3 -m unittest tests.test_codex_hook_interactive_guard` を実行し、すべて通る。

### 5.5 互換性要件
該当なし

### 5.6 バージョン
- **NFR5**: `<plugin>/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は変更しない。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 標準ライブラリのみを使い、再帰しない（NFR2）。
- 括弧なし形の判別は線形時間を保つ（NFR3）。
- 両コピーをバイト単位で同一に保つ（FR6）。

### 9.2 ビジネス上の制約
- version は変更しない（NFR5）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-brace-forms/**`
- `test-docs/codex-guard-anon-brace-forms/**`

`feature-docs/codex-guard-anon-brace-forms/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-brace-forms/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-brace-forms/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-anon-brace-forms/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-anon-brace-forms/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: `zsh -c 'function { python3 -i; }'` と `zsh -c 'function () { python3 -i; } arg'` を `{"tool_input": {"command": ...}}` として両コピーの標準入力に渡すと、deny の JSON が 1 つ出力される（FR1, FR2, FR6）
- [ ] AC2: `zsh -c '() { python3 -i; } arg'`、`zsh -c 'function { python3 -i; } arg'`、`zsh -c '! function { python3 -i; }'`、`zsh -c 'function ()\n{ python3 -i; } arg'`（`\n` は改行）が両コピーで deny になる（FR1, FR2）
- [ ] AC3: `zsh -c 'echo x | function { python3; }'`、`zsh -c 'echo x | function () { python3; }'`、`zsh -c 'echo x | () { python3; }'`、`zsh -c 'echo x | function { { python3; }; }'` が silent になる。`zsh -c 'echo x | function { python3 -i; }'` と `zsh -c 'echo x | function { cat; }; python3'` は deny になる（FR3）
- [ ] AC4: `zsh -c 'function f { python3 -i; }'`、`zsh -c "'function' { python3 -i; }"`、`zsh -c 'function { echo hi; } python3'`、`zsh -c 'function () { python3; } arg < f'`、`zsh -c '{ python3 -i; } arg'`、`zsh -c 'f() { python3 -i; } arg'` が両コピーで silent のまま（FR2, FR4）
- [ ] AC5: FR7 のケースが CASES にあり、`python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る。バイト一致テスト、docstring 文言テスト、線形性テストを含む（FR5-FR7, NFR1-NFR4）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1: 括弧なしの匿名関数 `zsh -c 'function { python3 -i; }'` - deny（AC1）
- [ ] TS2: 閉じ波括弧の後に引数 `zsh -c 'function () { python3 -i; } arg'` - deny（AC1）
- [ ] TS3: 括弧なしで引数あり / ! の直後 / 語の無い () で引数あり / () と { の間の改行 - deny（AC2）
- [ ] TS4: パイプの右側の匿名関数 3 形と入れ子 - silent。接続下の -i と群の後の別コマンド - deny（AC3）
- [ ] TS5: 名前付き括弧なし定義、引用付き function、引数に置いた python3、引数の後の入力リダイレクト、匿名関数でない波括弧の後の語、定義本体の後の語 - silent（AC4）
- [ ] TS6: 予約語の長い連なりの後の `function { python3 -i; }` が線形時間で応答する（NFR3）
- [ ] TS7: 既存スイート全体 `python3 -m unittest tests.test_codex_hook_interactive_guard` - 全テスト成功（AC5）

既存の E2E テスト: なし

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| bare な語 | 引用・エスケープ・展開を含まない語 |
| 予約語の連なり | RESERVED_WORDS の先頭の連なりと、`time` 直後の非動的な `-p` |
| silent | 判定不能。deny を出力しない |

## 14. 確認事項

### 14.1 確認済み事項

- [x] scope.nameless-paren-form: include（batch-codex-consultation）。直前に語の無い空の `()` の直後の波括弧グループも匿名関数の本体として扱い、閉じた後の語を引数として読む。`zsh -c '() { python3 -i; } arg'` を deny として CASES に追加する。
- [x] requirement.anon-body-stdin-connection: connect（batch-codex-consultation）。`function` / `()` の前のパイプ接続を匿名関数の本体のグループに渡す。
- [x] zsh 5.9 での `'function' { echo x; }`: parse error になり実行されない（オーケストレーターが確認済み）。
- [x] zsh 5.9 での閉じ `}` の後の語: `function { echo $1; } A` は A、`function () { echo $1; } B` は B、`() { echo $1; } C` は C を出力した（オーケストレーターが確認済み）。
- [x] zsh 5.9 での `echo piped | function { cat; }`: piped を出力する（確認済み）。

### 14.2 未確認・保留事項
なし

### 14.3 前提

- A1: 括弧なし形を判別する条件は、前の feature と同じ予約語除去をしたあとに残った語が bare な `function` 1 語であること。`'function' { echo x; }` は zsh 5.9 では parse error になり実行されないため、silent のままでよい（オーケストレーターが zsh 5.9 で確認済み）。
- A2: 匿名関数の本体の閉じ `}` の後の語は引数である。zsh 5.9 で `function { echo $1; } A` は A、`function () { echo $1; } B` は B、`() { echo $1; } C` は C を出力した（オーケストレーターが確認済み）。引数の後の標準入力リダイレクトは、閉じ直後と同じく本体を接続する。
- A3: 匿名関数でない波括弧グループの後の語と、関数定義の本体の後の語は、従来どおり判定不能（silent）とする。
- A4: `()` と `{` の間に改行があっても、匿名関数の本体として扱う（既存の関数定義の本体の規則と揃える）。`function` と `{` の間の改行は扱わず、括弧なし形は同じ行に書かれた場合に限る。
- A5: 語の無い空の `()` の形（FR2 (c)）は、`(` を開いた時点で語が 1 つも無い場合に限る。予約語の後の `()`（`then () { ... }` など）は、既存の関数名判定に従う。
- A6: 判定はシェルの種類を区別しない（前の feature の A5 と同じ）。
- A7: version は手で上げない。docstring は、既存テストが固定している文言を残したまま書き加える。
- A8: 回答（scope.nameless-paren-form = include、batch-codex-consultation）により、直前に語の無い空の `()` の直後の波括弧グループも匿名関数の本体として扱い、閉じた後の語を引数として読む。`zsh -c '() { python3 -i; } arg'` を deny として CASES に追加する。
- A9: 回答（requirement.anon-body-stdin-connection = connect、batch-codex-consultation）により、`function` / `()` の前のパイプ接続を匿名関数の本体のグループに渡す。`echo x | function { python3; }`、`echo x | function () { python3; }`、`echo x | () { python3; }` は silent にする。継承は匿名関数の本体に限る。`-i` などの明示的な対話起動は、接続下でも deny のまま。入れ子、群の後の別コマンド、接続下の -i の回帰ケースを CASES に追加する。zsh 5.9 で `echo piped | function { cat; }` が piped を出力することは確認済み。このため、既存の `echo x | function () { python3; }` の判定は deny から silent に変わる（既存の CASES には無い）。

## 15. 参考資料

- SPEC.md: `feature-docs/codex-guard-anon-brace-forms/SPEC.md`
