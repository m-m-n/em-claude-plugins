---
title: "codex-guard-anon-stdin-args"
created_date: 2026-10-17
status: draft
---

# codex-guard-anon-stdin-args - 要件定義書

## 1. 概要

### 1.1 背景
feature codex-guard-anon-brace-forms の変更で、codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、標準入力を接続した zsh 匿名関数の非対話実行を deny する誤爆（回帰）が入った。

### 1.2 目的
- codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、標準入力を接続した zsh 匿名関数の非対話実行を deny しないようにする。feature codex-guard-anon-brace-forms で入った誤爆（回帰）を解消する。
- 検知できる範囲（deny する範囲）と判定不能（silent）の範囲は、今回の対象の形を除いて変えない。

### 1.3 スコープ
- 対象:
    - `em-workflow/scripts/codex-hook-interactive-guard.py`
    - `em-review/scripts/codex-hook-interactive-guard.py`
    - `tests/test_codex_hook_interactive_guard.py`
- 対象外（判定は今と同じのままにする）:
    - `()` と `{` の間にある標準入力リダイレクト（`() < f { ...; }` の形）
    - 匿名関数でない群（`< f { ...; }`、`< f ( ... )`）の前にあるリダイレクト

## 2. ビジネス要件

### 2.1 ビジネス目標
- codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、標準入力を接続した zsh 匿名関数の非対話実行を deny しないようにする。feature codex-guard-anon-brace-forms で入った誤爆（回帰）を解消する。
- 検知できる範囲（deny する範囲）と判定不能（silent）の範囲は、今回の対象の形を除いて変えない。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 1.2 の目的のとおり

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | 匿名関数の頭の標準入力リダイレクトを本体に引き継ぐ | resolved |
| FR2 | 引き継ぎの範囲 | resolved |
| FR3 | 匿名関数の引数中の `(` を引数の語の一部として読む | resolved |
| FR4 | docstring を挙動に合わせる | resolved |
| FR5 | 両コピーを同一に保つ | resolved |
| FR6 | 回帰テストを追加する | resolved |

### 4.2 機能詳細

#### FR1: 匿名関数の頭の標準入力リダイレクトを本体に引き継ぐ

匿名関数の本体の群を開くとき、頭の単純コマンドで本体より前に読んだ標準入力リダイレクト（`<` `<<` `<<<` `<&` `0<`）を本体の群に引き継ぎ、本体を接続済みとして扱う。

対象は 3 つの形すべて:
- 括弧なしの `function { ...; }`（リダイレクトが `function` の前、または `function` と `{` の間にある）
- `function () { ...; }`（リダイレクトが `function` の前にある）
- `() { ...; }`（リダイレクトが `(` の前にある）

`()` と `{` の間に改行があっても、頭で読んだリダイレクトは本体に届く。本体の中の入れ子の群にも、既存の接続の伝わり方どおりに届く。

#### FR2: 引き継ぎの範囲

FR1 で引き継いだ接続は、その匿名関数の本体（と本体の中の群）だけに届く。次には届かない。
- 頭の `()` の `(` 群そのもの
- 引数の後の区切り（`;` `&&` `||` `|` `|&` `&` 改行）より後ろのコマンド
- 匿名関数でない群（通常の `{ ...; }` やサブシェル `( ... )`）

標準入力以外のリダイレクト（`>` `2>` など）は本体を接続しない。本体の中の明示的な `-i` は従来どおり deny する。

#### FR3: 匿名関数の引数中の `(` を引数の語の一部として読む

匿名関数の本体の閉じ `}` の後の引数を読んでいる間に現れた `(` は、語の途中（`foo(x)`）でも語の先頭（`(x)`）でも、対応する `)` までを 1 つの引数の語の一部として読む。このとき本体を指す after_group は保たれ、後ろの標準入力リダイレクトは本体を接続する。

- 範囲の中の空白や `|` も語の一部として扱う（`foo(a b|c)` は 1 つの引数）。
- `(` から対応する `)` までの範囲に、引用されていない `;` `&` 改行のいずれかが含まれるときは、今回の変更前と同じ読み方（群を開く）を保つ。
- 閉じない `(` は従来どおり判定不能（silent）。
- 対応する `(` の無い `)` は判定不能ではなく、現行の `_close_paren` どおり区切りとして扱う（囲むサブシェルがあればそれを閉じる）。

#### FR4: docstring を挙動に合わせる

モジュール docstring の手順 4 と、必要に応じて `_Group` / `_Parser` の該当 docstring に、FR1〜FR3 の挙動（頭の標準入力リダイレクトの引き継ぎ、引数中の `(` の読み方と `;` `&` 改行を含む場合の例外）を記述する。

- 引数が終わる位置の記述（`;` `&&` `||` `|` `|&` `&` 改行）は、`(` 〜 `)` の範囲内の `|` が引数を終えないことと矛盾しないようにする。
- `(` 〜 `)` の探索を「完全な引用対応探索」とは書かない（`_skip_parens` はバッククォートとコメントを専用に扱わない）。

#### FR5: 両コピーを同一に保つ

`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR6: 回帰テストを追加する

`tests/test_codex_hook_interactive_guard.py` の `CASES` に、再現手順の 3 コマンドを silent として追加し、12 章のテストシナリオの各ケースを `(期待する判定, ラベル, コマンド)` の形で追加する。`foo(x)` や `(x)` を引数に含むケースには `setopt nonomatch nobareglobqual;` を前置する。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR2: 読み取りの計算量は入力長に対して線形のままにする。引数中の `(` の範囲走査が、`;` を含む範囲で群を開いた後に入れ子の匿名関数の引数で再び走査される形（例: `function { :; } x(` の繰り返し）でも二乗時間にならない。既存の `TestMalformedAndDeepInput` は 60 秒の制限内で通る。

### 5.2 セキュリティ要件
- NFR1: 既存の `CASES` の deny / ask / silent ケースはすべて同じ判定のまま通る。既存の deny ケースは消さない。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR3: 標準ライブラリのみ・再帰なし・ファイル / ネットワーク / 子プロセスに触れない、という既存の制約（`TestNoRecursion`、`TestStaticConstraints`）を保つ。
- NFR4: `TestGuardDocumentation` が固定している既存の docstring の文言（例: `A stdin redirect among or after the arguments connects the body`、`the pipe connection passes to the body`、`the anonymous body takes it as its `pipe``、`the pipe connection comes from the head`）は残す。

### 5.5 互換性要件
- NFR5: プラグインの version は変更しない。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- NFR3 のとおり（標準ライブラリのみ・再帰なし・ファイル / ネットワーク / 子プロセスに触れない）。
- FR5 のとおり（両コピーをバイト単位で同一に保つ）。

### 9.2 ビジネス上の制約
- NFR5 のとおり（プラグインの version は変更しない）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-stdin-args/**`
- `test-docs/codex-guard-anon-stdin-args/**`

`feature-docs/codex-guard-anon-stdin-args/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-stdin-args/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-stdin-args/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-anon-stdin-args/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-anon-stdin-args/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR6）: `zsh -c 'function < /dev/null { python3; }'` を渡すと出力が無い（silent）。
- [ ] AC2（FR1, FR6）: `zsh -c '< /dev/null function { python3; }'` を渡すと silent。
- [ ] AC3（FR3, FR6）: `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null'` を渡すと silent。
- [ ] AC4（FR1）: `() { ...; }` と `function () { ...; }` の形でも、頭の前の標準入力リダイレクトで本体が接続され silent になる。
- [ ] AC5（FR2）: 頭の標準入力リダイレクトがあっても、本体の `python3 -i`、引数の後の区切りより後ろの `python3`、標準入力以外のリダイレクトだけの本体の `python3` は deny のまま。
- [ ] AC6（FR3）: 語の先頭の `(x)`、空白や `|` を含む `foo(a b|c)`、引用された `;` を含む `foo(';')` は 1 つの引数として読まれ、後ろの `< /dev/null` が本体を接続して silent になる。
- [ ] AC7（FR3）: 引数中の `(` 〜 `)` に引用されていない `;` `&` 改行を含む場合は今回の変更前と同じ判定になる（`foo(a; python3 -i)` 等は deny、`foo(a; python3 -i #)` は silent のまま）。
- [ ] AC8（FR4）: モジュール docstring が FR1〜FR3 の挙動を記述し、`TestGuardDocumentation` の既存マーカーがすべて残る。
- [ ] AC9（FR5）: `TestCopies` が通る（両コピーがバイト単位で同一）。
- [ ] AC10（NFR1, NFR2, NFR3）: `python3 -m unittest tests.test_codex_hook_interactive_guard` が全件通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` の形で追加する（TS20、TS21 を除く）。

| ID | 参照 | 期待する判定 | コマンド | ラベル |
|----|------|--------------|----------|--------|
| TS1 | AC1 | silent | `zsh -c 'function < /dev/null { python3; }'` | function と { の間の入力リダイレクトは括弧なしの匿名関数の本体を接続する |
| TS2 | AC2 | silent | `zsh -c '< /dev/null function { python3; }'` | function の前の入力リダイレクトは括弧なしの匿名関数の本体を接続する |
| TS3 | AC3 | silent | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null'` | 引数中の ( を含む語の後の入力リダイレクトは本体を接続する |
| TS4 | AC4 | silent | `zsh -c '< /dev/null () { python3; }'` | 語の無い () の匿名関数の頭の前の入力リダイレクトは本体を接続する |
| TS5 | AC4 | silent | `zsh -c '< /dev/null function () { python3; }'` | function () の匿名関数の頭の前の入力リダイレクトは本体を接続する |
| TS6 | AC4, FR1 | silent | `zsh -c '< /dev/null function { { python3; }; }'` | 頭の入力リダイレクトの接続は匿名関数の本体の入れ子の群にも届く |
| TS7 | AC5 | deny | `zsh -c '< /dev/null function { python3 -i; }'` | 頭の入力リダイレクトがあっても本体の -i は deny |
| TS8 | AC5 | deny | `zsh -c '< /dev/null function { :; } arg; python3'` | 頭の入力リダイレクトの接続は引数の後の区切りの先には届かない |
| TS9 | AC5 | deny | `zsh -c '2> /dev/null function { python3; }'` | 頭の標準入力以外のリダイレクトは本体を接続しない |
| TS10 | AC6 | silent | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } (x) < /dev/null'` | 引数の語の先頭の ( も引数として読む |
| TS11 | AC6 | silent | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(a b\|c) < /dev/null'` | 引数中の ( 〜 ) の空白と \| は語の一部 |
| TS12 | AC6 | silent | `zsh -c "setopt nonomatch nobareglobqual; function { python3; } foo(';') < /dev/null"` | 引数中の ( 〜 ) の引用された ; は群を開かない |
| TS13 | AC6, FR3 | silent | `zsh -c 'setopt nonomatch nobareglobqual; () { python3; } foo(x) < /dev/null'` | 語の無い () の匿名関数でも引数中の ( の後の入力リダイレクトは本体を接続する |
| TS14 | AC5, FR3 | deny | `zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(x) < /dev/null'` | 引数中の ( があっても本体の -i は deny |
| TS15 | AC5, FR3 | deny | `zsh -c 'setopt nonomatch nobareglobqual; function { :; } foo(x); python3'` | 引数中の ( を含む語の後の区切りの先の起動は deny |
| TS16 | AC7 | deny | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i)'` | 引数中の ( 〜 ) に ; があるときは従来どおり群として読む |
| TS17 | AC7 | deny | `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i)'` | 引数中の ( 〜 ) に & があるときは従来どおり群として読む |
| TS18 | AC7 | deny | `zsh -c 'setopt nobadpattern; function { :; } foo(a<改行>python3 -i)'`（`<改行>` は実際の改行文字） | 引数中の ( 〜 ) に改行があるときは従来どおり群として読む |
| TS19 | AC7 | silent | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` | 引数中の ( 〜 ) に ; があり閉じ括弧がコメントの中の形は従来どおり判定不能（既存の見逃しのまま変わらない） |
| TS20 | NFR2 | 終了コード 0・標準エラー出力なし・出力は空か deny 1 件（`TestMalformedAndDeepInput` の形） | `function { :; } x(` を 6000 回繰り返し、`; :` の後に `)` を 6000 個続けた入力 | 引数中の ( の範囲走査が入れ子で二乗時間にならない |
| TS21 | AC8 | pass | `TestGuardDocumentation` | 既存マーカーが残る |

### 12.1 テスト観点
- [ ] 正常系: TS1〜TS6、TS10〜TS13（標準入力を接続した匿名関数は silent）
- [ ] 異常系: TS7〜TS9、TS14〜TS15（接続されない起動・明示的な `-i` は deny）
- [ ] 境界値: TS16〜TS19（引数中の `(` 〜 `)` に引用されていない `;` `&` 改行を含む場合は従来どおり）
- [ ] パフォーマンス: TS20
- [ ] ドキュメント: TS21

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| silent | フックが出力を出さない判定（判定不能を含む） |
| deny | フックが実行を拒否する判定 |
| 頭 | 匿名関数の本体より前の単純コマンド部分（`function`、`()`、`function ()` とその前後のリダイレクト） |
| 本体 | 匿名関数の `{ ...; }` の群 |
| 接続済み | 標準入力が接続されており、非対話実行として扱う状態 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: 頭の標準入力リダイレクトの引き継ぎは、括弧なしの形に加えて `() { ...; }` と `function () { ...; }` の形も対象にする（実 zsh 5.9 で本体まで stdin が届くことを Codex が確認）。
- [x] A2: 引数中の `(` 〜 対応する `)` を 1 語として読むのは、その範囲に引用されていない `;` `&` 改行が無い場合に限る。含む場合は今回の変更前の読み方（群を開く）を保ち、検知力も判定不能の範囲も変えない。
- [x] A3: 語の先頭の `(`（`function { python3; } (x) < /dev/null`）も A2 の対象に含める。
- [x] A4: `foo(x)` や `(x)` を引数に含むテストのコマンドには `setopt nonomatch nobareglobqual;` を前置する。前置しないと実 zsh は `no matches found` で本体に到達しない。
- [x] A5: 対応する `(` の無い `)` は現行の `_close_paren` が区切りとして扱い、閉じない `(` は従来どおり判定不能になる。この区別は変えない。
- [x] A6: `_skip_parens` はバッククォートとコメントを専用に扱わないため、仕様に「完全な引用対応探索」とは書かない。
- [x] A7: `()` と `{` の間にある標準入力リダイレクト（`() < f { ...; }` の形）、匿名関数でない群（`< f { ...; }`、`< f ( ... )`）の前にあるリダイレクトは今回の対象外で、判定は今と同じのままにする。
- [x] A8: バグ修正のため minor / major は上げず、version は変更しない（patch は main への push 時に Actions が上げる）。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- 仕様書: `feature-docs/codex-guard-anon-stdin-args/SPEC.md`
