---
title: "codex-guard-redirect-only-list-pending"
created_date: 2026-10-21
status: draft
---

# codex-guard-redirect-only-list-pending - 要件定義書

## 1. 概要

### 1.1 背景

codex-hook-interactive-guard は、`&&` / `||` の右辺がリダイレクトだけの単純コマンドのとき、および `(` 群を閉じる `)` の直前の単純コマンドがリダイレクトだけのとき、リストの継続 (`list_pending`) を終わらせない。そのため、後ろに判定不能な文字列 (閉じない `'` など) が続くと、先行行の明示的な `python3 -i` を deny しない。

### 1.2 目的

- `&&` / `||` の右辺がリダイレクトだけの単純コマンドのときにもリストの継続 (`list_pending`) を終わらせ、その後の改行をチェックポイントにする。
- `(` 群を閉じる `)` の直前の単純コマンドがリダイレクトだけのときにもリストの継続を終わらせる。
- 判定不能な文字列 (閉じない `'` など) に達しても、先行行の明示的な `python3 -i` を deny する。

### 1.3 スコープ

対象:

- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

対象外:

- プラグインの version
- モジュール docstring の step 9 と `CHECKPOINT_MARKERS` が固定している文言

## 2. 機能要件

### 2.1 機能一覧

| ID | 機能名 |
|----|--------|
| FR1 | `_separator` での `list_pending` の解除規則 |
| FR2 | 再現手順の deny |
| FR3 | `list_pending` の説明の更新 |
| FR4 | 2 つのコピーの同一性 |
| FR5 | CASES への行の追加 |
| FR6 | `)` で `(` 群を閉じるときの `list_pending` の解除 |

### 2.2 機能詳細

#### FR1: `_separator` での `list_pending` の解除規則

- `_Parser._separator` は `list_pending` を `pipe_pending` と同じ規則で扱う。
- `sep` が `&&` または `||` なら `list_pending` を True にする。
- それ以外の `sep` では、次のどちらかのときに `list_pending` を False にする。
    - `sep` が改行でない。
    - 区切りで終わった単純コマンドがリダイレクトを持っていた (`_flush` が返す `redirected` が True)。
- リダイレクトを持たない空のコマンドを終える改行 (空行、コメントだけの行) と heredoc の本文は、`list_pending` をそのまま残す。
- 既存の解除 (`_flush` で語のあるコマンドを終えたとき、`_open_group` で群を開いたとき) は変えない。
- `&& ;` / `&& &` の構文エラー形が後ろに判定不能な行を伴うときに deny になる誤拒否は、既知として受け入れる。

#### FR2: 再現手順の deny

次のコマンドを標準入力で渡すと、フックは先行行の `python3 -i` を deny する。これらを `bash -c` の文字列の中に入れた形も deny する。

- `python3 -i &&\n< /dev/null\necho '`
- `python3 -i && > /dev/null\necho '`
- `python3 -i || > /dev/null\necho '`
- `python3 -i && > /dev/null;\necho '`
- `python3 -i &&\n<<EOF\nx\nEOF\necho '`

#### FR3: `list_pending` の説明の更新

- `_Parser` の docstring の list continuation の段落 (現在「`&&` or `||` が読まれたときに立ち、語のある単純コマンドを終えたときか群が開いたときに下りる」と書かれている箇所) と、`__init__` の `list_pending` のフィールドコメントを、FR1 と FR6 の解除条件に合わせて書き直す。追加する解除条件は次のとおり。
    - リダイレクトだけのコマンドを終えたとき
    - 改行以外の区切りを読んだとき
    - `(` 群を閉じる `)` の直前の単純コマンドがリダイレクトを持っていたとき
- `_close_paren` と `_close_paren_after_rescue` の docstring に、`)` で終えた単純コマンドがリダイレクトを持っていたら list continuation を下ろすことを書く。
- `_close_paren` の docstring に既にある case mark / inherited value の記述は残す。
- モジュール docstring の step 9 と `CHECKPOINT_MARKERS` が固定している文言 (no group is open, no pipe is pending, no list continuation is pending など) は変えない。

#### FR4: 2 つのコピーの同一性

`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` に同じ変更を入れ、バイト単位で同一に保つ。

#### FR5: CASES への行の追加

`tests/test_codex_hook_interactive_guard.py` の `CASES` に、次の行を `("deny", ラベル, コマンド)` / `("silent", ラベル, コマンド)` で追加する。`CASES` のコマンドは一意に保つ。

- deny: FR2 の各コマンドと、それらを `bash -c` の中に入れた形
- silent: `&&` の後のコメントだけの行が継続を保つことを固定する `python3 -i &&\n# c\necho '`
- deny (FR6):
    - `(python3 -i && < /dev/null)\necho '`
    - `(python3 -i || < /dev/null)\necho '`
    - `(function { :; } foo(a; python3 -i && < /dev/null)\necho '`
    - `(python3 -i && < /dev/null);\necho '`
    - `(python3 -i && < /dev/null) &\necho '`
- silent (FR6):
    - `(python3 -i &&)\necho '`
    - `(function { :; } foo(a; python3 -i &&)\necho '`

#### FR6: `)` で `(` 群を閉じるときの `list_pending` の解除

- unquoted な `)` が `(` 群を閉じるとき、次の両方の経路で、`)` の直前に `_flush` が終えた単純コマンドがリダイレクトを持っていた (`_flush` が返す `redirected` が True) なら `list_pending` を False にする。
    - `_close_paren` の通常の `(` 分岐 (`_flush` の後に `_close_group`)
    - `_close_paren_after_rescue` (仮の群の連鎖を救済して外側の `(` 群を閉じる経路)
- リダイレクトを持たない場合 (`(python3 -i &&)`) は `list_pending` をそのまま残す。
- `pipe_pending` は `_close_group` が条件なしで False にしているので、この経路に追加の処理は要らない。
- `)` が区切りとして読まれる経路 (`(` 群が最内でないとき、`_separator(")")` に渡る) は FR1 の規則に従う。

## 3. 非機能要件

- NFR1: 改行 1 つ、`)` 1 つあたりの処理は定数時間のまま。新しい状態や list のコピーを足さない。
- NFR2: 標準ライブラリだけを使う。既存の `TestStaticConstraints` を通る。
- NFR3: プラグインの version は触らない (`.claude/rules/core-plugin-version-bump.md`)。
- NFR4: 既存の deny / silent 行は消さず、判定も変えない。
- NFR5: docstring を書き換えても、既存のドキュメント検査のテストを通る。`_close_paren` の docstring は case mark と inherited value の語を含み続け、`CASE_MARK_PERMANENCE_PHRASES` (The mark is never cleared / It is never cleared / for the rest of its life) をどの docstring にも入れない。

## 4. 制約条件

### 4.1 技術的制約

- 標準ライブラリだけを使う (NFR2)。
- 2 つのコピーはバイト単位で同一に保つ (FR4)。

### 4.2 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-redirect-only-list-pending/**`
- `test-docs/codex-guard-redirect-only-list-pending/**`

`feature-docs/codex-guard-redirect-only-list-pending/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-redirect-only-list-pending/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-redirect-only-list-pending/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 5. 成功基準

### 5.1 受け入れ基準

- [ ] AC1: FR2 の 5 つのコマンドが両コピーで deny になる。
- [ ] AC2: FR2 の各コマンドを `bash -c` の文字列の中に入れた形が両コピーで deny になる。
- [ ] AC3: 既存の silent 行 `python3 -i &&\necho '`、`python3 -i ||\necho '`、`python3 -i &&\n\necho '` は silent のまま。追加する `python3 -i &&\n# c\necho '` も silent。
- [ ] AC4: 2 つのコピーがバイト単位で同一。
- [ ] AC5: `python3 -m unittest tests.test_codex_hook_interactive_guard` がリポジトリルートからすべて通る (ドキュメント検査のテストを含む)。
- [ ] AC6: `(python3 -i && < /dev/null)\necho '`、`(python3 -i || < /dev/null)\necho '`、`(function { :; } foo(a; python3 -i && < /dev/null)\necho '`、`(python3 -i && < /dev/null);\necho '`、`(python3 -i && < /dev/null) &\necho '` が両コピーで deny になる。
- [ ] AC7: `(python3 -i &&)\necho '` と `(function { :; } foo(a; python3 -i &&)\necho '` が両コピーで silent のまま。

## 6. テストシナリオ

コマンド中の `\n` は改行を表す。

| ID | 期待する判定 | コマンド |
|----|--------------|----------|
| TS1 | deny | `python3 -i &&\n< /dev/null\necho '` |
| TS2 | deny | `python3 -i && > /dev/null\necho '` |
| TS3 | deny | `python3 -i \|\| > /dev/null\necho '` |
| TS4 | deny | `python3 -i && > /dev/null;\necho '` |
| TS5 | deny | `python3 -i &&\n<<EOF\nx\nEOF\necho '` |
| TS6 | deny | TS1-TS5 の各コマンドを `bash -c` の文字列に入れた形 (既存行と同じく `shlex.quote` などで引用する) |
| TS7 | silent | `python3 -i &&\n# c\necho '` |
| TS8 | silent (既存行) | `python3 -i &&\necho '` / `python3 -i \|\|\necho '` / `python3 -i &&\n\necho '` |
| TS9 | deny (HEAD では silent。FR6 で解消) | `(python3 -i && < /dev/null)\necho '` |
| TS10 | deny (HEAD では silent。FR6 で解消) | `(python3 -i \|\| < /dev/null)\necho '` |
| TS11 | deny (HEAD では silent。FR6 の `_close_paren_after_rescue` 経路で解消) | `(function { :; } foo(a; python3 -i && < /dev/null)\necho '` |
| TS12 | deny (HEAD では silent。外側の `;` で FR1 が解除する) | `(python3 -i && < /dev/null);\necho '` |
| TS13 | deny (HEAD では silent。外側の `&` で FR1 が解除する) | `(python3 -i && < /dev/null) &\necho '` |
| TS14 | silent | `(python3 -i &&)\necho '` |
| TS15 | silent | `(function { :; } foo(a; python3 -i &&)\necho '` |

テストの実行コマンド: `python3 -m unittest tests.test_codex_hook_interactive_guard`

## 7. 確認事項

### 7.1 確認済み事項

- [x] `_separator` での `list_pending` の解除規則 (requirement.list-pending-clear-rule): `list_pending` を `pipe_pending` と同じ規則で扱う。`&& ;` / `&& &` の構文エラー形が後ろに判定不能な行を伴うときに deny になる誤拒否は、既知として受け入れる。
- [x] `)` で `(` 群を閉じるときの扱い (requirement.close-paren-redirect-scope): この feature に含める。`_close_paren` の通常の `(` 分岐と `_close_paren_after_rescue` の両方で、閉じる直前の単純コマンドがリダイレクトを持っていたら解除する。リダイレクトの無い `(python3 -i &&)` は silent のまま。

### 7.2 前提

- AS1: 構文エラーになる形 (`python3 -i && ;`、`python3 -i && &`、目的語のない `python3 -i && >`) でも FR1 により `list_pending` が下り、後ろに判定不能な行が続くと先行行の `python3 -i` を deny する。bash はこれらの行を実行しないので誤拒否になるが、既知として受け入れる (回答 requirement.list-pending-clear-rule)。これらの形に必須のテスト行は置かない。
- AS2: 2 つのコピーはバイト単位で同一 (`TestCopies.test_the_two_copies_are_byte_identical` が固定している不変条件)。
- AS3: `&&` / `||` の後の空行・コメント行・heredoc 本文が継続を保つという既存の振る舞いは維持する (既存の silent 行が固定している)。
- AS4: `_close_group` は `pipe_pending` を条件なしで False にしている (現行コードの事実)。FR6 で `)` の経路に足すのは `list_pending` の解除だけになる。

### 7.3 未確認・保留事項

なし。
