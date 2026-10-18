---
title: "codex-guard-anon-arg-backquote-comment"
created_date: 2026-10-18
status: draft
---

# codex-guard-anon-arg-backquote-comment - 要件定義書

## 1. 概要

### 1.1 背景

zsh 匿名関数の引数中の `(`〜`)` 範囲がバッククォートで群の読みに戻り、その範囲の空白の後に `#` があると、本体の明示的な `python3 -i` が deny されない。これは codex-guard-anon-arg-backquote が持ち込んだ後退で、review round1 の ab990994bd365064 で挙がった。

### 1.2 目的

- zsh 匿名関数の引数中の `(`〜`)` 範囲がバッククォートで群の読みに戻り、その範囲の空白の後に `#` があっても、本体の明示的な `python3 -i` を deny する
- 再発を `CASES` で検出できるようにする

### 1.3 スコープ

- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`（バイト単位で同一の 2 つのコピー）
- `tests/test_codex_hook_interactive_guard.py`（`CASES` と docstring テスト）
- FR5 に挙げたものは変えない

## 2. ビジネス要件

### 2.1 ビジネス目標

- codex-guard-anon-arg-backquote が持ち込んだ後退（review round1 の ab990994bd365064）を直し、本体の明示的な `python3 -i` を deny する
- 再発を `CASES` で検出できるようにする

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow / em-review の利用者 | `codex-hook-interactive-guard.py` の判定を受ける |
| 保守する開発者 | 2 つのコピー・docstring・テストを保守する |

### 2.3 期待される効果

- 再現コマンドとその派生形（11.1 の AC-1〜AC-4）で、本体の明示的な `python3 -i` が deny される
- 既存の `CASES` と他のテストの判定が変わらない

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター |
|----|----------------|----------|
| UC01 | 引数の範囲に空白と `#` を含む匿名関数の `python3 -i` を拒否する | em-workflow / em-review の利用者 |

### 3.2 ユースケース詳細

#### UC01: 引数の範囲に空白と `#` を含む匿名関数の `python3 -i` を拒否する

**アクター**: em-workflow / em-review の利用者

**事前条件**:
- `codex-hook-interactive-guard.py` に判定対象のコマンドが渡る

**基本フロー**:
1. コマンド ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)'`` がフックに渡る
2. 引数中の `(`〜`)` 範囲がバッククォートで群の読みに戻り、例外の効いた群になる（FR2）
3. 語の頭の `#` をコメントにせず、語の文字として読む（FR2）
4. 本体の `python3 -i` を判定し、`permissionDecision: deny` を出力する（FR1）

**代替フロー**:
- 例外の効いた群が最も内側の開いた群であるあいだに `;`、単独の `&`、`&&`、`|&`、改行を読んだら例外を外し、それ以後その群では `#` をコメントとして読む（FR4）
- 閉じないバッククォートは判定不能（出力なし）にする（FR5）

**事後条件**:
- 本体の明示的な `python3 -i` が deny される

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | 再現コマンドの deny | 再現コマンドを両コピーに渡すと deny を出力する |
| FR2 | バッククォート契機の群では `#` を語の文字として読む | 例外の効いた群が最も内側の開いた群であるあいだ、語の頭の引用されていない `#` を語の文字として読む |
| FR3 | 入れ子の群への継承 | 例外の効いた群の中で開いた群は、開いた時点の親の例外を引き継ぐ |
| FR4 | 直接の区切りで例外を外す | `;`、単独の `&`、`&&`、`\|&`、改行で例外を外す |
| FR5 | 変えないもの | 終端判定・課金・救済・接続などの既存の規則を変えない |
| FR6 | 両コピーの同時修正 | 2 つのコピーを同じ変更で直し、バイト単位で同一に保つ |
| FR7 | 再発を検出する CASES | `CASES` に deny の行を足す |
| FR8 | docstring の更新 | docstring に FR2〜FR4 の規則を書き、docstring テストにマーカーを足す |

### 4.2 機能詳細

#### FR1: 再現コマンドの deny

**説明**: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)'`` を両コピーに渡すと `permissionDecision: deny` を出力する。

#### FR2: バッククォート契機の群では `#` を語の文字として読む

**説明**: `_read_argument_parens` が開く仮の群のうち、`_scan_parens` が `end` を返し（対応する `)` がある）、`separated` が false で `backquoted` が true だったために開いた群を、例外の効いた群とする。例外の効いた群が最も内側の開いた群であるあいだ、語の頭にある引用されていない `#` はコメントの始まりにせず、語の文字として読む。

**ビジネスルール**:
- 例外の効いた群を自分で開く条件: `_scan_parens` が `end` を返す、`separated` が false、`backquoted` が true
- 例外が効くのは、その群が最も内側の開いた群であるあいだだけ

#### FR3: 入れ子の群への継承

**説明**: 例外の効いた群の中で開いた群（`(` 群、`{` 群、仮の群）は、開いた時点で親の例外が効いていれば例外を引き継ぐ。群が閉じた後は、親の状態がそのまま効く。自分で開く条件（FR2）を満たさず、例外の効いた親からも引き継がない群では、今までどおり `#` をコメントとして読む。

**ビジネスルール**:
- 入れ子の群が引き継ぐのは、開いた時点での親の状態とする（仮定 A2）
- 入れ子の群の中で読んだ区切りは、外側の群の例外を変えない（仮定 A2）

#### FR4: 直接の区切りで例外を外す

**説明**: 例外の効いた群が最も内側の開いた群であるあいだに、パーサ自身の `;`、`&`（単独）、`&&`、`|&`、改行を読んだら、その群の例外を外す。それ以後その群では `#` を今までどおりコメントとして読む。

``zsh -c 'setopt nonomatch nobareglobqual nobadpattern; function { python3 -i; } foo(`case x in x) echo x;; esac`; # '"'"' ignored<改行>python3 -i'`` は deny になる（`;` で例外が外れて `#` 以降はコメントになり、仮の群は `;` で救済され、改行の後の `python3 -i` が判定される）。

**ビジネスルール**:
- 例外を外す区切りは `;`、単独の `&`、`&&`、`|&`、改行に限る（仮定 A1）
- `|` と `||` は外さない。リダイレクトの `&>` と `>&`、引用符で囲んだ区切り、バックスラッシュで打ち消した区切りも外さない（仮定 A1）

#### FR5: 変えないもの

**説明**:
- `_scan_parens` の終端判定と返り値、`_read_argument_parens` の `paren_budget` への課金、`_skip_parens` と `_skip_substitution`（`$(` の中のコメントの読みを含む）は変えない
- 前の SPEC の FR5 が定める入力の終わりの扱い・救済の条件（`_rescue_separator`、`_rescue_argument_groups`、`_closes_after_rescue`）・接続の規則も変えない
- `first_sep` の記録も変えない
- 群の外のコメント、`;` `&` 改行を契機に開いた仮の群、`)` が見つからずに開いた仮の群は、今までどおり `#` をコメントとして読む
- 閉じないバッククォートは、今までどおり判定不能（出力なし）にする
- 前の SPEC の仮定 A2（群の読みに新しい読みを足さない）には、FR2〜FR4 のこの 1 つの例外だけを足す

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 判定不能 | 閉じないバッククォート | 出力なし（今までどおり） |

#### FR6: 両コピーの同時修正

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR7: 再発を検出する CASES

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に deny の行を足す。表は両コピーに流す。既存の行は期待値を変えず、消さない。足す行の対象は次の 4 つ。

- 再現コマンド
- 再現コマンドの後に改行と `python3 -i` が続く形
- 範囲の中に入れ子の括弧がある形
- FR4 の走査がバッククォートの中の `)` で早く止まる形

#### FR8: docstring の更新

**説明**: 両コピーのモジュール docstring の手順 4、`_Parser` の docstring、`_read_argument_parens` の docstring、例外の状態を持たせる `_Group` の属性の説明に、FR2〜FR4 の規則を書く。docstring テストに、この規則のマーカーを足す。

**ビジネスルール**:
- 既存のマーカーは残す（`a backquote and a comment get no special reading`、`BACKQUOTE_MODULE/PARSER/SCAN/READER_MARKER`、`ANONYMOUS_ARGUMENT_MARKERS`、`RESCUE_PROVISIONAL_MARKER`）
- `STALE_DOCSTRING_SENTENCES` と `STALE_GROUP_SENTENCES` の文は docstring に戻さない

## 5. 非機能要件

### 5.1 パフォーマンス要件（NFR1）

- 解析全体を文字列長に対して線形時間に保つ
- 例外の状態は群を開くときに親から 1 回だけ決め、区切りを読むときと `#` を読むときは最も内側の群だけを見る（定数時間）
- 再帰は使わない
- 既存の性能テスト（バッククォートを含む範囲の入れ子、TS-16 の救済の形）と再帰検査テストを両コピーで通す

### 5.2 セキュリティ要件（NFR2）

- 標準ライブラリのみを使い、ファイル・ネットワーク・子プロセスに触れない
- 判定はコマンド文字列だけで決まる
- `TestStaticConstraints` を通す
- 既存の deny ケースを silent に変えない

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- ドキュメント: FR8 のとおり docstring を更新する

### 5.5 互換性要件（NFR3）

- 既存の `CASES` と他のテストの判定を変えない
- `plugin.json` と `marketplace.json` の version は変えない

## 6. UI/UX要件

該当なし（画面を持たないフックの、静的解析の不具合修正のため）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 2 つのコピーはバイト単位で同一に保つ（FR6）
- 標準ライブラリのみを使う（NFR2）
- 再帰は使わない（NFR1）

### 9.2 ビジネス上の制約

- version は変えない（NFR3、仮定 A8）

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-arg-backquote-comment/**`
- `test-docs/codex-guard-anon-arg-backquote-comment/**`

`feature-docs/codex-guard-anon-arg-backquote-comment/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-arg-backquote-comment/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-arg-backquote-comment/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-anon-arg-backquote-comment/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-anon-arg-backquote-comment/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 対応 |
|------|------|
| ``function { python3; } foo(`echo x` #) < /dev/null`` は、群は `)` で閉じるが、入力リダイレクトは本体を接続しないので deny になる | 前の SPEC の既知の誤拒否（572 行）と同じ扱いとする |
| 語の途中の `(`〜`)` の中にある空白と `#` が語の一部になることを zsh では検証していない | 仮定 A4 として扱う |

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1（FR1, FR2, FR6）: 再現コマンドの JSON を両コピーの標準入力に渡すと deny を出力する
- [ ] AC-2（FR2, FR7）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)<改行>python3 -i'`` が両コピーで deny になる
- [ ] AC-3（FR3, FR7）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` (a #))'`` が両コピーで deny になる
- [ ] AC-4（FR4, FR7）: ``zsh -c 'setopt nonomatch nobareglobqual nobadpattern; function { python3 -i; } foo(`case x in x) echo x;; esac`; # '"'"' ignored<改行>python3 -i'`` が両コピーで deny になる
- [ ] AC-5（FR5, NFR3）: 既存の `CASES` が変更なしで通る。対象には、`#)` を含む救済のケース（585-629 行、644 行）、バッククォートのケース（563-584 行。閉じないバッククォートの 576・577 行を含む）、群の外のコメントのケース（101・102・196・197 行）が含まれる
- [ ] AC-6（FR6）: `TestCopies.test_the_two_copies_are_byte_identical` が通る
- [ ] AC-7（FR8）: docstring テストが両コピーで通る（既存のマーカーと、FR2〜FR4 の新しいマーカー）
- [ ] AC-8（NFR1, NFR2）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: 再現コマンド（TS1）、改行と `python3 -i` が続く形（TS2）、入れ子の括弧がある形（TS3）、FR4 の走査がバッククォートの中の `)` で早く止まる形（TS4）が deny になる
- [ ] 正常系: 既存の `CASES` のすべての行が変わらない（TS5）。2 つのコピーの同一性と docstring のテストが通る（TS6）
- [ ] 異常系: 閉じないバッククォート（`` foo(`echo x) ``）は今までどおり判定不能（silent）
- [ ] 境界値: 区切りを契機にした群で `)` がコメントの中にある形（`foo(a; python3 -i #)`）は、今までどおりコメントとして読んで救済する（既存のケース）
- [ ] 境界値: 範囲に `;` とバッククォートの両方がある形は、`separated` が true なので例外は効かず、今までどおり読む
- [ ] 境界値: 語の途中の `#`（`` foo(`x`#) ``）は、語が始まっているので、今もコメントではない
- [ ] 境界値: 例外の効いた群の中の `|` と `||` は FR4 の区切りに含まれないので、例外は外れない
- [ ] 境界値: ``function { python3; } foo(`echo x` #) < /dev/null`` は deny（前の SPEC の既知の誤拒否 572 行と同じ扱い）
- [ ] セキュリティ: 既存の deny ケースを silent に変えない。`TestStaticConstraints` を通す
- [ ] パフォーマンス: 既存の性能テスト（``"function { :; } x(`:` " * depth + ")" * depth`` と TS-16 の形）が両コピーで制限時間内に応答する（TS7）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 仮の群 | `_read_argument_parens` が開く群 |
| 例外の効いた群 | 仮の群のうち、`_scan_parens` が `end` を返し、`separated` が false で `backquoted` が true だったために開いた群。および、開いた時点で例外の効いた親から例外を引き継いだ群（FR3） |
| 直接の区切り | 例外の効いた群が最も内側の開いた群であるあいだに、パーサ自身が読んだ `;`、単独の `&`、`&&`、`\|&`、改行 |
| 前の SPEC | `feature-docs/codex-guard-anon-arg-backquote/SPEC.md` |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 修正方針（requirement.fix-approach）: 前の SPEC の仮定 A2（群の読みに新しい読みを足さない）に、FR2〜FR4 の 1 つの例外だけを足す。前の SPEC の FR5（救済の規則）は変えない。前の feature の SPEC ファイルそのものは書き換えず、この feature の SPEC で例外を述べる

### 14.2 未確認・保留事項

- [ ] 仮定 A4（zsh では、語の途中の `(`〜`)` の中にある空白と `#` は語の一部で、コメントにならない）は zsh では検証していない

### 14.3 仮定

- A1: FR4 で例外を外す区切りは、回答で挙がった `;`、単独の `&`、`&&`、`|&`、改行に限る。`|` と `||` は外さない。リダイレクトの `&>` と `>&`、引用符で囲んだ区切り、バックスラッシュで打ち消した区切りも外さない（これらは `_separator` に届かない）。
- A2: 例外を外すのは、その群が最も内側の開いた群であるあいだに読んだ区切りだけにする。入れ子の群の中で読んだ区切りは、外側の群の例外を変えない。入れ子の群が引き継ぐのは、開いた時点での親の状態とする。
- A3: 前の SPEC の仮定 A2（群の読みに新しい読みを足さない）には、FR2〜FR4 の 1 つの例外だけを足す。前の SPEC の FR5（救済の規則）は変えない。前の feature の SPEC ファイルそのものは書き換えず、この feature の SPEC で例外を述べる。
- A4: zsh では、語の途中の `(`〜`)` の中にある空白と `#` は語の一部で、コメントにならない。
- A5: `$(` の中の `#` は今までどおり `_skip_substitution` の規則で読み、この例外の対象にしない。
- A6: 例外の状態を `_Group` の新しい属性に持たせるか、別の形で持たせるかは計画に委ねる。どちらにしても、消したり名前を変えたりする記号は無い。
- A7: LICENSE ファイルは無く、ライセンスは未検出として扱う。
- A8: version は変えない。

## 15. 参考資料

- 前の SPEC: `feature-docs/codex-guard-anon-arg-backquote/SPEC.md`
- 対象コード: `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`
- テスト: `tests/test_codex_hook_interactive_guard.py`
