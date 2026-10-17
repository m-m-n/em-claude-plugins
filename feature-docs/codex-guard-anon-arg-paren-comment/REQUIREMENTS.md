---
title: "codex-guard-anon-arg-paren-comment"
created_date: 2026-10-17
status: draft
---

# codex-guard-anon-arg-paren-comment - 要件定義書

表記: コマンド例の `<改行>` は、コマンド文字列中の改行 1 文字を表す。

## 1. 概要

### 1.1 背景

codex-hook-interactive-guard（em-workflow / em-review の両コピー）は、zsh 匿名関数の引数中の `(` から仮に開いた群が閉じないとき（閉じ括弧がコメントの中にある、または閉じ括弧が無い）、判定不能（出力なし）になる。このため、実際の区切り `;` / `&` の後にある対話起動を見逃す。

### 1.2 目的

- 匿名関数の引数中の `(` から仮に開いた群が閉じないとき、実際の区切り `;` / `&` の後の対話起動を見逃さないようにする。
- zsh 5.9 が実行しない形（改行の形）と本物の未閉鎖群は従来どおり判定不能（出力なし）に保ち、誤爆を増やさない。

### 1.3 スコープ

- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

## 2. ビジネス要件

### 2.1 ビジネス目標

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、zsh 匿名関数の引数中の `(` から仮に開いた群が閉じないとき（閉じ括弧がコメントの中にある、または閉じ括弧が無い）に、実際の区切り `;` / `&` の後の対話起動を見逃さないようにする。
- zsh 5.9 が実行しない形（改行の形）と本物の未閉鎖群は従来どおり判定不能（出力なし）に保ち、誤爆を増やさない。

### 2.2 対象ユーザー

該当なし

### 2.3 期待される効果

- 匿名関数の引数中の閉じない `(` の後でも、`;` / 単独の `&` の後の対話起動が deny になる。
- 改行の形と本物の未閉鎖群は出力なしのまま変わらない。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 |
|----|--------|
| FR1 | ; の形の救済 |
| FR2 | & の形の救済 |
| FR3 | 改行の形は判定不能のまま |
| FR4 | 救済の契機は ; と単独の & に限る |
| FR5 | 本物の未閉鎖群は判定不能のまま |
| FR6 | 入力接続と関数定義の除外を保つ |
| FR7 | docstring の更新 |
| FR8 | 2 つのコピーを同時に直す |
| FR9 | 再発を検出するテスト |

### 4.2 機能詳細

#### FR1: ; の形の救済

**説明**: 匿名関数の引数中の `(`（`_read_argument_parens` が読む `(`。語中 `foo(` と語頭 `(` の両方）から仮に開いた群が文字列の終わりまで閉じず、その群の中で直接読んだ最初の実際の区切りが `;` のとき、その `(` を引数語の文字として読み、`;` の後のコマンドを匿名関数の後に続くコマンドとして判定する。

**入力と出力**:
- `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` → deny

#### FR2: & の形の救済

**説明**: FR1 と同じ条件で、最初の実際の区切りが単独の `&`（バックグラウンド）のときも同じく救済する。

**入力と出力**:
- `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'` → deny

#### FR3: 改行の形は判定不能のまま

**説明**: 仮に開いた群の中で直接読んだ最初の実際の区切りが改行のときは救済せず、従来どおり出力なしとする。

**入力と出力**:
- `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>python3 -i #)'` → 出力なし（silent）

#### FR4: 救済の契機は ; と単独の & に限る

**説明**: 救済の契機になるのは、主の読み取りが区切りとして読む `;` と単独の `&` だけとする。次のものは契機にならず、それらが最初の区切りの群は従来どおり出力なしとする。
- `&&` `||` `|` `|&`
- リダイレクトの `&>` `>&`
- 引用符内・バックスラッシュ後の `;` `&`

#### FR5: 本物の未閉鎖群は判定不能のまま

**説明**: 匿名関数の引数から仮に開いた群でない群（コマンド位置の `(`、`{` 群、関数定義の本体など）が閉じないときは、救済の後に残る場合も含めて従来どおり出力なしとする（ガードの `if self.frames: raise _Undecidable("group")` の判定を保つ）。区切りを含まない閉じない引数の `(`（`function { python3 -i; } foo(`）も出力なしのままとする。

#### FR6: 入力接続と関数定義の除外を保つ

**説明**: 救済の後のコマンドにも、既存の入力接続（入力リダイレクト・パイプ・接続された群からの継承）の確定と、関数定義の本体を判定しない規則（ガードの群の接続・skipped の確定ループ）をそのまま適用する。匿名関数の頭部のパイプ・入力リダイレクトの接続は、引数を終える区切りの後のコマンドには届かない。

#### FR7: docstring の更新

**説明**: 次の docstring に、救済の規則（仮に開いた群、契機は `;` と単独の `&`、改行が最初なら救済しない、本物の未閉鎖群は出力なし）を書く。
- モジュール docstring の手順 4（`` so it does when no matching `)` is found, and a group that is never closed -> no output `` の段落）
- `_Parser` の docstring
- `_read_argument_parens` の docstring

既存の docstring テストのマーカー（`` holds an unquoted `;`, `&` or newline, the `(` opens a group ``、`a backquote and a comment get no special reading` など）は残す。文言を変える場合は、テストのマーカーを同じ変更で揃える。

#### FR8: 2 つのコピーを同時に直す

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR9: 再発を検出するテスト

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` で次を行う。表は両コピーに流す。
- 既存の silent ケース「引数の ( ) の中に ; があり閉じ括弧がコメントの中なら従来どおり判定不能」を deny に変え、ラベルも改める。
- & の形の deny、改行の形の silent、FR4〜FR6 を固定するケースを足す。
- 既存の deny ケースは消さない。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR1（線形時間）: 救済を含めて解析全体を文字列長に対して線形時間に保つ。仮に開いた未閉鎖群が深く入れ子になった入力（既存の性能テストの `unclosed ranges` の形、救済が起きる形を含む）にも既存の制限時間内に応答する。再帰は使わない（既存の再帰検査テストを通す）。

### 5.2 既存の制約の維持

- NFR2（既存の制約の維持）: 標準ライブラリのみ、ファイル・ネットワーク・子プロセスに触れない、判定はコマンド文字列だけで決まる、という既存の制約とその検査テストを保つ。

### 5.3 version

- NFR3（version を変えない）: plugin.json と marketplace.json の version は変えない（patch は main への push 時に Actions が上げる）。

## 6. UI/UX要件

該当なし（UI を持たないフックスクリプトの判定ロジックの修正）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 標準ライブラリのみを使う。ファイル・ネットワーク・子プロセスに触れない。判定はコマンド文字列だけで決まる（NFR2）。
- 解析は文字列長に対して線形時間で、再帰を使わない（NFR1）。
- 2 つのコピーはバイト単位で同一に保つ（FR8）。

### 9.2 ビジネス上の制約

- plugin.json と marketplace.json の version は変えない（NFR3）。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-arg-paren-comment/**`
- `test-docs/codex-guard-anon-arg-paren-comment/**`

`feature-docs/codex-guard-anon-arg-paren-comment/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-arg-paren-comment/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-arg-paren-comment/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-anon-arg-paren-comment/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-anon-arg-paren-comment/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

- 語頭 `(` の形（`function { :; } (a; python3 -i #)`）は Codex の zsh 5.9 で実測していない。実測は語中 `foo(` の形のみ。救済の対象に語頭の形を含めるのは仮定（14.2）として扱う。
- 入れ子の仮の群を救済する実現方法（再読み取りなど）は、線形時間（NFR1）を保つ範囲で計画に委ねる。

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1（FR1, FR9）: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` を両コピーに渡すと deny を 1 つ出力する
- [ ] AC-2（FR2, FR9）: `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'` を両コピーに渡すと deny を出力する
- [ ] AC-3（FR3, FR9）: `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>python3 -i #)'` を両コピーに渡すと何も出力しない
- [ ] AC-4（FR4, FR9）: 最初の区切りが `&&` の形（`foo(a && python3 -i #)`）は何も出力しない
- [ ] AC-5（FR5, FR9）: コマンド位置の閉じない `(`（`(python3 -i #)`、および外側にコマンド位置の閉じない `(` がある `(function { :; } foo(a; python3 -i #)`）と、区切りの無い閉じない引数の `(`（`function { python3 -i; } foo(`）は何も出力しない
- [ ] AC-6（FR6, FR9）: 救済の後のコマンドに入力リダイレクトがあれば何も出力せず、頭部がパイプの右側でも区切りの後のプログラム無し起動は deny、関数定義の本体の中で救済されたコマンドは判定しない
- [ ] AC-7（FR7）: 両コピーのモジュール docstring・`_Parser`・`_read_argument_parens` の docstring が救済の規則を述べ、docstring テストが通る
- [ ] AC-8（FR8）: 2 つのコピーがバイト単位で同一であることを確かめる既存テストが通る
- [ ] AC-9（NFR1）: 仮に開いた未閉鎖群を深く入れ子にした入力（救済が起きる形を含む）に、両コピーが既存の制限時間内に応答し、再帰検査テストが通る
- [ ] AC-10（FR9, NFR2）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` が通り、既存の deny ケース（引数の ( ) の中に ; / & / 改行があり閉じている形の deny を含む）が残っている

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系（救済して deny）
    - TS1: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` → deny
    - TS2: `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'` → deny
    - TS4: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i'` → deny（閉じ括弧が無い形。zsh から見るとコメント除去後の TS1 と同じ）
    - TS5: `zsh -c 'setopt nobadpattern; function { :; } (a; python3 -i #)'` → deny（語頭の ( の形）
    - TS7: `zsh -c 'setopt nobadpattern; function { :; } foo(a; b<改行>python3 -i #)'` → deny（最初の区切りが ; なら後の改行の先も判定する）
- [ ] 異常系（救済せず出力なし）
    - TS3: `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>python3 -i #)'` → silent
    - TS6: `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>b; python3 -i #)'` → silent（最初の区切りが改行）
    - TS8: `zsh -c 'setopt nobadpattern; function { :; } foo(a && python3 -i #)'` → silent
    - TS9: `zsh -c '(python3 -i #)'` → silent
    - TS10: `zsh -c 'setopt nobadpattern; (function { :; } foo(a; python3 -i #)'` → silent
    - TS11: `zsh -c 'function { python3 -i; } foo('` → silent（既存ケース。変えない）
- [ ] 入力接続と関数定義
    - TS12: `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 < /dev/null #)'` → silent
    - TS13: `zsh -c 'setopt nobadpattern; echo x | function { :; } foo(a; python3 #)'` → deny
    - TS14: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i #)<改行>}'` → silent
- [ ] 回帰
    - TS15: 既存の 3 ケース `foo(a; python3 -i)` / `foo(a & python3 -i)` / `foo(a<改行>python3 -i)`（閉じている形）は変えずに deny のまま
- [ ] パフォーマンス
    - TS16: 性能テストに `"function { :; } x(" * depth + "; python3 -i #"` の形を足し、既存の `unclosed ranges` の形とあわせて両コピーが制限時間内に応答することを確かめる
- [ ] ドキュメントと同一性
    - TS17: TestGuardDocumentation に救済の規則のマーカーを足して通す。バイト同一テストを通す

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 仮に開いた群 | 匿名関数の引数中の `(`（`_read_argument_parens` が読む `(`。語中 `foo(` と語頭 `(` の両方）から開いた群 |
| 救済 | 仮に開いた群が閉じず、群の中で直接読んだ最初の実際の区切りが `;` または単独の `&` のとき、その `(` を引数語の文字として読み、区切りの後のコマンドを匿名関数の後に続くコマンドとして判定すること |
| 本物の未閉鎖群 | 匿名関数の引数から仮に開いた群でない群（コマンド位置の `(`、`{` 群、関数定義の本体など）が閉じないもの |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 救済の契機: 回答「実際に区切りになる ; / &」を、単独の演算子 `;` と `&` と読んだ（14.2 の仮定 2）

### 14.2 未確認・保留事項

次の仮定はいずれも可逆とする。

- [ ] 救済の対象は語中 `foo(` と語頭 `(` の両方（どちらも `_read_argument_parens` が読む「匿名関数の引数から仮に開いた群」）とする。Codex の zsh 5.9 実測は語中の形で、語頭の形（TS5）は実測していない
- [ ] 救済の契機は `;` と単独の `&` に限り、`&&` `||` `|` `|&` は契機にしない（回答の「実際に区切りになる ; / &」を単独の演算子と読んだ）
- [ ] 改行が最初の区切りの群は、後に `;` / `&` があっても救済しない（zsh 5.9 は改行の形を number expected で実行しないため）
- [ ] 閉じている形の既存 deny ケース `foo(a<改行>python3 -i)` は、zsh で実行されるかどうかにかかわらず変えない（既存の deny ケースは消さないルール）
- [ ] 入れ子の仮の群は内側から順に救済し、救済の後にも本物の未閉鎖群が残れば出力なしとする。実現方法（再読み取りなど）は線形時間を保つ範囲で計画に委ねる
- [ ] LICENSE ファイルは無い。ライセンスは未検出として扱う
- [ ] version は変えない（core-plugin-version-bump ルール）

## 15. 参考資料

- `feature-docs/codex-guard-anon-arg-paren-comment/SPEC.md`
