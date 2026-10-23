---
title: "codex-guard-delim-brace-quote-per-shell"
created_date: 2026-10-23
status: draft
---

# codex-guard-delim-brace-quote-per-shell - 要件定義書

## 1. 概要

### 1.1 背景

codex-hook-interactive-guard は、入れ子の -c 文字列のヒアドキュメントの区切り語の位置にある `${ ... }` を、-c 文字列を直接持つシェルの種類によらず今の読み（引用除去）で読む。bash は区切り語の `${ ... }` を書かれたままの形で終端行と比べるため、bash -c の文字列では書かれたままの形の終端行の後にある `python3 -i` などの対話起動を見逃す（TS1 は今のコードで silent）。

### 1.2 目的

- codex-hook-interactive-guard が入れ子の bash / sh / ksh の -c 文字列で、ヒアドキュメントの区切り語の `${ ... }` をそのシェルの規則で読み、終端行の後の `python3 -i` などの対話起動を見逃さないようにする。
- sh の実体が bash か dash か分からない -c 文字列でも、どちらの規則で読んでも終端行の後にある起動を deny する。

### 1.3 スコープ

対象:

- 入れ子の -c 文字列の、区切り語（`<<` / `<<-` の目標の語）の位置の `${ ... }` の読み（FR1〜FR3）
- 2 通りの読みで読む文字列の NESTED_READ_LIMIT の数え方（FR5）
- `tests/test_codex_hook_interactive_guard.py` の CASES への回帰テストの追加（FR6）

変えないもの:

- フックが受け取るコマンドそのもの（入れ子でない文字列）の読み
- zsh・dash の -c 文字列の区切り語の読み
- FR4 に挙げる、区切り語の位置にない読み
- coproc / repeat の読みと、両スイッチを切った読み直しの有無（今の種類 bash / zsh / unknown のまま）

## 2. ビジネス要件

### 2.1 ビジネス目標

- codex-hook-interactive-guard が入れ子の bash / sh / ksh の -c 文字列で、ヒアドキュメントの区切り語の `${ ... }` をそのシェルの規則で読み、終端行の後の `python3 -i` などの対話起動を見逃さないようにする。
- sh の実体が bash か dash か分からない -c 文字列でも、どちらの規則で読んでも終端行の後にある起動を deny する。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | -c 文字列の種類ごとの区切り語の読み | resolved |
| FR2 | bash の読み | resolved |
| FR3 | sh / ksh の 2 通りの読み | resolved |
| FR4 | 区切り語の位置にない読みは変えない | resolved |
| FR5 | NESTED_READ_LIMIT の数え方 | resolved |
| FR6 | 回帰テスト | resolved |

### 4.2 機能詳細

#### FR1: -c 文字列の種類ごとの区切り語の読み

区切り語（`<<` / `<<-` の目標の語）の位置の `${ ... }` の読みを、-c 文字列を直接持つシェルの種類で決める。

| -c 文字列を直接持つシェル | 区切り語の `${ ... }` の読み |
|---|---|
| bash（bash5.2 など数字と `.` の接尾辞つき、パス付き、env などの option なしラッパー経由、`bash --posix` を含む） | FR2 の bash の読みだけ |
| zsh、dash（接尾辞つきを含む） | 今の読み（引用除去）だけ |
| sh・ksh（接尾辞つきを含む） | FR3 の 2 通りの読み |
| フックが受け取るコマンドそのもの（入れ子でない文字列） | 今の読みのまま変えない |

**ビジネスルール**:

- 種類は今と同じく、直接持つシェルのコマンド語で決まる。bash -c の中の zsh -c の文字列は zsh として読む。
- coproc / repeat の読みと、両スイッチを切った読み直しの有無は、今の種類（bash / zsh / unknown）のまま変えない。

#### FR2: bash の読み

**ビジネスルール**:

- 区切り語の語に `${ ... }` の範囲の外の引用（`'` `"` `\` の引用単位）が 1 つも無いとき、各 `${ ... }` の範囲を `"`・`'`・`\` を含めて書かれたまま区切り語にする。
    - ただし範囲の中の、単引用符の外にあるバックスラッシュ＋改行は取り除く（二重引用符の中のものも取り除く）。
- 範囲の外のバックスラッシュ＋改行は取り除き、範囲の外の引用に数えない。
- 区切り語に直接書かれた `$( ... )` の中の引用は、範囲の外の引用に数えない。
- 範囲の外に引用が 1 つでもあるときは、範囲の前にあるか後ろにあるかによらず、今と同じく語全体の引用を除いた形を登録する。
- 次は変えない。
    - 範囲の閉じの探し方（前の SPEC の FR2）
    - 範囲の中の引用されていない `$'` / `$"` の判定不能（前の SPEC の FR3）
    - 範囲の外の引用されていない `$'` / `$"` の判定不能（前の SPEC の FR4）

**例**（区切り語の書き方 → 登録する区切り語）:

| 区切り語の書き方 | 登録する区切り語 |
|---|---|
| `${v:-"x"}` | `${v:-"x"}` |
| `${v:-'x'}` | `${v:-'x'}` |
| `${v:-\x}` | `${v:-\x}` |
| `${v:-"a<バックスラッシュ><改行>b"}` | `${v:-"ab"}` |
| `P<バックスラッシュ><改行>${v:-"x"}` | `P${v:-"x"}` |
| `$(echo "P")${v:-"x"}` | `$(echo "P")${v:-"x"}` |
| `'P'${v:-"x"}` | `P${v:-x}` |
| `${v:-"x"}""` | `${v:-x}` |

#### FR3: sh / ksh の 2 通りの読み

**ビジネスルール**:

- sh・ksh の -c 文字列は、区切り語の位置の `${ ... }` を bash の読み（FR2）で読んだ場合と今の読み（引用除去）で読んだ場合の 2 通りで、文字列全体を独立に読む。
- どちらか一方でも deny になれば deny を出す。
- 2 通りの読みで区切り語の文字列が一致する文字列では 2 回目を読まない。
- 各読みには今の読み直し（両スイッチを切った再読）とチェックポイントの規則をそれぞれ当て、片方の読みが判定不能でも他方の deny を出す。
- 区切り語ごとの組み合わせは作らず、文字列全体に 1 つの規則を当てる 2 回の読みに限る。

#### FR4: 区切り語の位置にない読みは変えない

次の読みは、どの種類でも今の読みのまま変えない。

- 区切り語の位置にない `${ ... }` / `$'` / `$"`
- `<<<` と `<` のリダイレクト先
- 区切り語の中の二重引用符の中の `${ ... }`
- 区切り語の位置の `$( ... )`
- 匿名関数の引数の `( ... )` の範囲の引用除去

#### FR5: NESTED_READ_LIMIT の数え方

- 2 通りの読みで読む文字列も、今の読み直しと同じく、その文字列の長さで 1 回だけ NESTED_READ_LIMIT に数える。
- その文字列の中にある入れ子の -c 文字列は、読むたびに数える。

#### FR6: 回帰テスト

- `tests/test_codex_hook_interactive_guard.py` の CASES に、12 章のテストシナリオの各行を `(期待する判定, ラベル, コマンド)` の形で足す。
- 期待する判定は deny か silent。
- CASES は今のテストで 2 つのコピーの両方に流す。

## 5. 非機能要件

| ID | 名前 | 要件 |
|----|------|------|
| NFR1 | 2 つのコピーの同一性 | `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更の中で一緒に直し、バイト単位で同一に保つ。 |
| NFR2 | 線形時間 | 1 つの文字列を読む回数は、2 通りの読みとそれぞれの読み直しを合わせて定数回に限り、各読みは線形時間で行う。長さ上限や時間に関する今のテストは通る。 |
| NFR3 | 既存の構造テストの保持 | `_scan` の入れ子の parse 呼び出しを囲む try が 1 つであること（TestNestedParseErrorContainment）、再帰しないこと（TestNoRecursion）、フックのコマンドの読み直しが失敗したとき初回の読みに戻ること（TestRereadFallback）、NESTED_READ_LIMIT の今のテスト（TestNestedReadLimit の TS32 を含む）は変えずに通る。 |
| NFR4 | docstring の整合 | モジュール docstring の判定手順（step 7 の種類の説明、step 9 の読みの回数、区切り語の位置の読みの説明）を FR1 から FR5 と合わせる。docstring の marker を確かめる今のテスト（DELIMITER_RANGE_MARKERS、CHECKPOINT_MARKERS など）は変えずに通る。 |
| NFR5 | 既存ケースの保持 | CASES の今の deny / silent の行は消さず、期待する判定も変えない。 |
| NFR6 | 標準ライブラリのみ | フックとテストは Python 標準ライブラリだけを使う。 |
| NFR7 | version | プラグインの version は変えない。 |

## 9. 制約条件

### 9.1 技術的制約

- フックとテストは Python 標準ライブラリだけを使う（NFR6）。
- プラグインの version は変えない（NFR7）。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-delim-brace-quote-per-shell/**`
- `test-docs/codex-guard-delim-brace-quote-per-shell/**`

`feature-docs/codex-guard-delim-brace-quote-per-shell/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-delim-brace-quote-per-shell/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-delim-brace-quote-per-shell/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-delim-brace-quote-per-shell/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-delim-brace-quote-per-shell/**` は依然として正しい。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: 再現手順 TS1 が deny になる。（FR1、FR2 / TS1）
- [ ] AC2: bash の -c 文字列では、範囲の外に引用の無い区切り語の `${ ... }` が書かれたまま（単引用符の外のバックスラッシュ＋改行だけ除いて）登録され、その形の終端行の後の起動は deny、引用を除いた形の行では本文が閉じない。範囲の外のバックスラッシュ＋改行は取り除かれ、引用に数えない。`<<-` では先頭のタブを除いて比べる。版数つき・env 経由・`--posix` の bash も同じ。（FR1、FR2 / TS2〜TS9、TS15〜TS17、TS32）
- [ ] AC3: bash の -c 文字列で、区切り語の `${ ... }` の範囲の外（前でも後ろでも）に引用があるときは、語全体の引用を除いた形が登録される。（FR2 / TS10〜TS13）
- [ ] AC4: bash の読みでも、範囲の中の引用されていない `$'` は判定不能のまま。（FR2 / TS14）
- [ ] AC5: sh・ksh（パス付きを含む）の -c 文字列では、bash の読みと今の読みのどちらかで終端行の後にある起動が deny になる。片方の読みが判定不能でも他方の deny が出る。両方の読みで本文の中にある起動は deny にならない。（FR1、FR3 / TS18〜TS23、TS26、TS27）
- [ ] AC6: dash -c、zsh -c、フックが受け取るコマンドそのものの区切り語の読みは変わらない。（FR1 / TS24、TS25、TS28、TS29）
- [ ] AC7: 読みは -c 文字列を直接持つシェルの種類で決まる。（FR1 / TS30、TS31）
- [ ] AC8: 2 つのコピーがバイト単位で同一で、`python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` がどちらも成功する。（FR4、FR5、FR6、NFR1〜NFR5）

## 12. テストシナリオ

各行は CASES の `(expected, label, command)`。command の作り方と各行の lines の正確な値は SPEC.md の「Test Scenarios」に書く。「今」は今のコードでの判定。

| ID | 期待 | 今 | wrap | ラベル | 要件 |
|----|------|----|------|--------|------|
| TS1 | deny | silent | （なし） | bash -c の区切り語の ${...} を書かれたまま登録し、終端行の後の起動は deny (再現手順) | FR1, FR2 |
| TS2 | silent | deny | bash | bash -c では引用を除いた ${...} の行で本文が閉じない | FR2 |
| TS3 | deny | silent | bash | bash -c の ${...} の単引用符を残す | FR2 |
| TS4 | deny | silent | bash | bash -c の ${...} のバックスラッシュを残す | FR2 |
| TS5 | deny | silent | bash | bash -c の ${...} の二重引用符の中の } で閉じず、書かれたまま登録する | FR2 |
| TS6 | deny | silent | bash | bash -c の入れ子の ${...} を書かれたまま登録する | FR2 |
| TS7 | deny | deny | bash | bash -c の ${...} の中の $( ) は書かれたまま | FR2 |
| TS8 | deny | deny | bash | bash -c の ${...} の引用の外のバックスラッシュ＋改行は取り除く | FR2 |
| TS9 | deny | silent | bash | bash -c の ${...} の二重引用符の中のバックスラッシュ＋改行は取り除き、引用は残す | FR2 |
| TS10 | deny | deny | bash | bash -c で ${...} の前に引用があれば語全体の引用を除く | FR2 |
| TS11 | deny | deny | bash | bash -c で ${...} の後ろに引用があれば語全体の引用を除く | FR2 |
| TS12 | silent | silent | bash | bash -c で ${...} の後ろに引用があれば書かれたままの範囲の行では本文が閉じない | FR2 |
| TS13 | deny | deny | bash | bash -c で ${...} の前の二重引用符があれば範囲の単引用符も除く | FR2 |
| TS14 | silent | silent | bash | bash -c でも ${...} の中の引用されていない $' は判定不能 | FR2 |
| TS15 | deny | silent | bash | bash -c の <<- は先頭タブを除いて書かれたままの ${...} と比べる | FR2 |
| TS16 | deny | silent | env bash5.2 | env を経由した版数つきの bash も bash の読み | FR1 |
| TS17 | deny | silent | bash --posix | bash --posix も bash の読み | FR1 |
| TS18 | deny | silent | sh | sh -c は bash の読みの終端行の後の起動を deny（今の読みは判定不能） | FR3 |
| TS19 | deny | deny | sh | sh -c は今の読みの終端行の後の起動を deny（bash の読みは判定不能） | FR3 |
| TS20 | deny | silent | sh | sh -c は書かれたままの終端行の後で引用を除いた行の前の起動を deny | FR3 |
| TS21 | deny | deny | sh | sh -c は引用を除いた終端行の後で書かれたままの行の前の起動を deny | FR3 |
| TS22 | silent | silent | sh | sh -c の両方の読みで本文の中にある起動は deny しない | FR3 |
| TS23 | deny | silent | /bin/sh | パス付きの sh も 2 通りの読み | FR1, FR3 |
| TS24 | silent | silent | dash | dash -c は今の読みだけで、書かれたままの行では本文が閉じない | FR1 |
| TS25 | deny | deny | dash | dash -c は引用を除いた終端行の後の起動を deny | FR1 |
| TS26 | deny | silent | ksh | ksh -c も 2 通りの読みで、書かれたままの終端行の後の起動を deny | FR1, FR3 |
| TS27 | deny | deny | ksh | ksh -c も 2 通りの読みで、引用を除いた終端行の後の起動を deny | FR1, FR3 |
| TS28 | silent | silent | zsh | zsh -c の区切り語の読みは変えない | FR1 |
| TS29 | silent | silent | （なし） | フックが受け取るコマンドそのものの区切り語の読みは変えない | FR1 |
| TS30 | deny | silent | zsh, bash | zsh -c の中の bash -c の文字列は bash の読み | FR1 |
| TS31 | silent | silent | bash, zsh | bash -c の中の zsh -c の文字列は zsh の読み | FR1 |
| TS32 | deny | silent | bash | bash -c の ${...} の外のバックスラッシュ＋改行は取り除き、引用に数えない | FR2 |

### 12.1 テスト観点

- [ ] 結合: `python3 -m unittest tests.test_codex_hook_interactive_guard` が成功する（AC8）
- [ ] 結合: `python3 -m unittest discover -s tests` が成功する（AC8）
- [ ] 境界値: 範囲の後ろにある引用（TS11、TS12）: 語全体の引用を除く
- [ ] 境界値: 二重引用符の中のバックスラッシュ＋改行（TS9）: 取り除いて引用は残す
- [ ] 境界値: 範囲の外のバックスラッシュ＋改行（TS32）: 取り除き、引用に数えない
- [ ] 境界値: 片方の読みだけが判定不能（TS18、TS19）: 他方の deny を出す
- [ ] 境界値: `<<-` の先頭タブ（TS15）: タブを除いてから比べる
- [ ] パフォーマンス: 長さ上限や時間に関する今のテストが通る（NFR2、NFR3）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 区切り語 | `<<` / `<<-` の目標の語 |
| 範囲 | 区切り語の中の `${ ... }` の範囲 |
| 今の読み | 区切り語の `${ ... }` を引用除去で読む、今のコードの読み |
| bash の読み | FR2 の読み |
| 2 通りの読み | FR3 の、bash の読みと今の読みでそれぞれ文字列全体を読むこと |

## 14. 確認事項

### 14.1 確認済み事項

- [x] bash の -c 文字列の区切り語の読み: 区切り語の語に `${ ... }` の範囲の外の引用（`'` `"` `\`）が 1 つも無いとき、範囲を `"`・`'`・`\` を含めて書かれたまま区切り語にする（単引用符の外のバックスラッシュ＋改行だけは取り除く）。範囲の外に引用が 1 つでもあるときは、今と同じく語全体の引用を除いた形を登録する。（FR2）
- [x] sh -c の文字列の区切り語の読み: bash の読みと今の読みの 2 通りで文字列全体を独立に読み、どちらか一方でも deny になれば deny を出す。（FR3）
- [x] そのほかのシェルの区切り語の読み: dash（接尾辞つきを含む）は今の読みだけ。sh・ksh は 2 通りの読み。フックが受け取るコマンドそのものは今の読みのまま。（FR1）
- [x] A-3: bash 5.3.9 で実測して確かめた。`cat <<P<バックスラッシュ><改行>${v:-"x"}` は `P${v:-"x"}` の行で閉じる（範囲の外のバックスラッシュ＋改行は取り除かれ、引用に数えない）。`cat <<$(echo "P")${v:-"x"}` は `$(echo "P")${v:-"x"}` の行で閉じ、`$(echo P)${v:-x}` の行では閉じない（区切り語に直接書かれた `$( ... )` の中の引用は範囲の外の引用に数えない）。TS8 と TS9 の終端も同じく実測で確かめた。

### 14.2 未確認・保留事項

- [ ] status: tbd の要件は無い。

### 14.3 仮定

- A-1: ksh / mksh は未導入で未実測。2 通りの読みで見逃しを防げるのは、そのシェルが bash の規則か今の読み（引用除去）のどちらかに従う場合に限る。
- A-2: 2 通りの読みで読む文字列も、その長さで 1 回だけ NESTED_READ_LIMIT に数える（今の読み直しと同じ）。入れ子の -c 文字列が両方の読みに現れるときは、読むたびに数える。TestNestedReadLimit の TS32（sh -c の読み直しを 1 回と数える）は変えずに通る。
- A-3（確認済み）: 14.1 に記載。
- A-4: bash の読みでも範囲の中・外の引用されていない `$'` / `$"` は判定不能のまま（回答どおり）。bash は `${v:-$'x'}` を `${v:-'x'}` で閉じるが、この形の見逃しは受け入れる。
- A-5: 区切り語の位置の匿名関数の引数の `( ... )` の範囲の引用除去は zsh の構文の読みで、どの種類でも変えない。
- A-6: フックのコマンドそのものは今の読み（引用除去）だけで読み、2 通りの読みにしない（回答どおり）。TestRereadFallback の、既定の種類での parser の数が 2 であることは変わらない。
- A-7: bash 5.3.9 / bash --posix / dash / zsh 5.9 での終端行の閉じ方はオーケストレーターの実測に従う。
