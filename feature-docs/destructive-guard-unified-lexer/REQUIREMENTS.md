---
title: "destructive-guard-unified-lexer"
created_date: 2026-10-05
status: draft
---

# destructive-guard-unified-lexer - 要件定義書

## 1. 概要

### 1.1 背景

destructive-guard.py は、`$'...'`（ANSI-C 引用）と、`${...}`・`$((...))`・`((...))`・`$[...]` の中身を bash と異なる形で読んでいる。このため、後ろに続く破壊的コマンドが、文の区切りごと隠れたり、ヒアドキュメント本文として捨てられたりする（4d76e1accb9e8fed、e812ca2e1c631029 とその別形 7357c6a8618d8556、09f237155908ac2f）。また、引用・コメント・展開の読み取りが複数箇所に分かれている（7e700e9f9906edc7）。

### 1.2 目的

- destructive-guard.py が `$'...'`（ANSI-C 引用）と、`${...}`・`$((...))`・`((...))`・`$[...]` の中身を bash と同じ形で読む。後ろに続く破壊的コマンドを、文の区切りごと隠したり、ヒアドキュメント本文として捨てたりしないようにする。
- 引用・コメント・展開の状態を 1 回のパスで追う字句解析を作り、これを唯一の判定元にする。読み取りが複数箇所に分かれている問題（7e700e9f9906edc7）を合わせて解消する。

### 1.3 スコープ

- 対象: em-workflow/hooks/destructive-guard.py の字句解析、em-workflow/hooks/tests/destructive-guard-cases.json へのケース追加、repo ルート tests/ への一致検査のテスト 1 ファイルの追加（NFR4）。
- 対象外: hooks.json と version の変更（NFR4）。round2.yaml で unresolved の medium 5 件（0fb4a67c477e8034、54b0115faf5bc202、80dc2417b7e6670b、9f48c2f446a190b2、548598739d198748）（前提 A1）。

## 2. ビジネス要件

### 2.1 ビジネス目標

- destructive-guard.py が `$'...'`（ANSI-C 引用）と、`${...}`・`$((...))`・`((...))`・`$[...]` の中身を bash と同じ形で読む（4d76e1accb9e8fed、e812ca2e1c631029 とその別形 7357c6a8618d8556、09f237155908ac2f）。
- 引用・コメント・展開の状態を 1 回のパスで追う字句解析を唯一の判定元にする（7e700e9f9906edc7）。

### 2.2 対象ユーザー

該当なし

### 2.3 期待される効果

- 後ろに続く破壊的コマンドが、文の区切りごと隠れたり、ヒアドキュメント本文として捨てられたりしない。
- 引用・コメント・展開の範囲の判定元が 1 箇所になる。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | ANSI-C 引用を bash と同じ範囲で読む | confirmed |
| FR2 | パラメータ展開の中の `<<` を演算子にしない | confirmed |
| FR3 | 算術式の中の `<<` を演算子にしない | confirmed |
| FR4 | 展開の中の置換の検査を保つ | confirmed |
| FR5 | 閉じない文脈は開かない | confirmed |
| FR6 | 引用・コメント・展開の状態を 1 つの字句解析で決める | confirmed |
| FR7 | 位置追跡用の書き換えと検査用の値を分ける | confirmed |
| FR8 | ヒアドキュメント本文を状態追跡から外し、位置を対応させる | confirmed |
| FR9 | 置換を拾う 3 つの方針を保つ | confirmed |
| FR10 | 読み取りの一致を確かめるテスト | confirmed |
| FR11 | 修正より前にケースを足す | confirmed |
| FR12 | 既存ケースを保つ | confirmed |

### 4.2 機能詳細

#### FR1: ANSI-C 引用を bash と同じ範囲で読む

引用の外（`${...}` の中を含む）の `$'` から ANSI-C 引用を開く。中ではバックスラッシュが次の 1 文字をエスケープし、エスケープされていない `'` で閉じる。二重引用符の中の `$'` は引用を開かない。`$$` などの特殊パラメータの直後の `'` は、普通の単一引用として読む。文の区切り・コメント・ヒアドキュメント演算子の判定は、すべてこの範囲に従う。（4d76e1accb9e8fed、7357c6a8618d8556）

#### FR2: パラメータ展開の中の `<<` を演算子にしない

`${` は、対応する `}` で閉じる展開として読む。中の `<<` はヒアドキュメント演算子として扱わず、中の `#` はコメントを開始しない。中の引用は追い、引用の中の `}` では閉じない。中の `(` は括弧の入れ子に数えない。（e812ca2e1c631029）

#### FR3: 算術式の中の `<<` を演算子にしない

`$((...))`、`$[...]`（入れ子の `[ ]` を含む）、コマンド位置の `((...))` の中の `<<` を、ヒアドキュメント演算子として扱わない。コマンド位置には、予約語の後ろと `for ((...))` を含む。算術式の中の `;` は文の区切りに数えない。（e812ca2e1c631029、09f237155908ac2f）

#### FR4: 展開の中の置換の検査を保つ

`${...}` と算術式の中にある `$(...)` とバッククォートは、これまでどおり置換として取り出して検査する。

#### FR5: 閉じない文脈は開かない

`${`・`$((`・`$[`・`((`・`$'` が入力の終わりまでに閉じないときは、その文脈を開かなかったものとして後ろを読む。

#### FR6: 引用・コメント・展開の状態を 1 つの字句解析で決める

新しい字句解析が 1 回のパスで、引用・コメント・展開の範囲を決める唯一の場所になる。対象は `$'`・`$"`・`${}`・`$(( ))`・`(( ))`・`$[ ]`・コメント・`<<<`・`$( )`・バッククォート。

- _OperatorContext と _blank_comments() はこれに置き換える。
- scan_structure() は、引用・コメント・展開の判定をこの結果から取る。
- shlex（_TrackingLexer）は、字句解析が文字位置を保ったまま書き換えたテキストだけを受け取り、トークン化だけを続ける。
- パースに失敗したときの tokens() の shlex.split(comments=True) にも元の文字列を直接渡さず、この字句解析の結果を通す。

これを 7e700e9f9906edc7 の解消の条件とする。

#### FR7: 位置追跡用の書き換えと検査用の値を分ける

shlex に渡すための書き換えは、位置の追跡だけに使う。書き換えた文字（伏字）は、検査に渡す値に残さない。Tok の is_operator / quoted / unresolved は、元の入力での由来を保つ（例: `rm -rf /tmp/safe$'\t'` の対象を未解決の変数として扱わない）。

#### FR8: ヒアドキュメント本文を状態追跡から外し、位置を対応させる

本物のヒアドキュメントの本文の行は、引用・コメント・展開の状態追跡から外す。位置は、元の入力・本文を除いた後・置換の印を入れた後の 3 つの間で対応させる。

#### FR9: 置換を拾う 3 つの方針を保つ

置換を拾う既存の 3 つの方針は、それぞれ区別したまま保つ。

- shell モード
- heredoc-body モード
- 単一引用の中の置換も拾う広い探索（honor_single_quotes=False）

#### FR10: 読み取りの一致を確かめるテスト

repo ルートの tests/ にテストを 1 ファイル置く。字句解析と shlex・scan_structure()・tokens() の結果について、引用の範囲・文の境界・演算子の位置・Tok の由来（is_operator / quoted / unresolved）・検査用の値が一致することを確かめる。対象のコマンドは、cases.json の既存ケース全件、AC-1 と AC-7 の攻撃形、無害な対照例。

#### FR11: 修正より前にケースを足す

.claude/rules/hook-tests.md に従い、修正より前に destructive-guard-cases.json へ `[期待する判定, ラベル, コマンド]` 形式でケースを足す。足すのは、AC-1 と AC-7 の各形（deny）と、AC-2 の形（allow）。

#### FR12: 既存ケースを保つ

既存の 574 件と、無人実行の降格ケース 1 件の期待する判定を変えない。既存の deny / ask ケースは 1 件も消さない。round 2 の loop 1 の退行を防ぐケース（cases.json 592〜596）は、期待する判定のまま通る。

## 5. 非機能要件

| ID | 名前 | 内容 |
|----|------|------|
| NFR1 | 静的解析のみ | 判定は決定的で、同じコマンドには常に同じ判定を返す。ファイルシステムにはアクセスせず、コマンドや置換は評価しない。 |
| NFR2 | 依存を増やさない | フックもテストも、Python 標準ライブラリだけで実装する。 |
| NFR3 | 性能 | 字句解析は、入力長に対して線形の計算量にする。判定は hooks.json の timeout（10 秒）に十分収まる。既存の約 60KB の性能ケースも、10 秒以内に判定を返す。 |
| NFR4 | 変更範囲 | 変更するのは em-workflow/hooks/destructive-guard.py、em-workflow/hooks/tests/destructive-guard-cases.json、repo ルート tests/ に足す一致検査のテスト 1 ファイルに限る。hooks.json と version は変えない。 |

### 5.1 パフォーマンス要件

- NFR3 のとおり。

### 5.2 セキュリティ要件

- NFR1 のとおり。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

該当なし

### 5.5 互換性要件

- FR12 のとおり。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 静的解析のみで判定する（NFR1）。
- Python 標準ライブラリだけで実装する（NFR2）。

### 9.2 ビジネス上の制約

該当なし

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャーで変更するパス（NFR4、前提 A5）:

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- repo ルート `tests/` に足す一致検査のテスト 1 ファイル（`tests/test_*.py`）

hooks.json と version は変更集合に含めない。

create-plan では、`workflow.yaml` の各タスクの `files` から変更集合を導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-unified-lexer/**`
- `test-docs/destructive-guard-unified-lexer/**`

`feature-docs/destructive-guard-unified-lexer/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-unified-lexer/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-unified-lexer/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: 次の各形が deny になり、deny ケースとして cases.json にある。
    1. `cat $'\'' ; bash -s \' <<EOF\ngit reset --hard HEAD\nEOF`
    2. `echo $'\'' ; rm -rf /home/sakura/valuable \'`
    3. `echo $'\'' ' #' ; rm -rf /home/sakura/valuable\necho \'`
    4. `echo ${x/<<EOF/}\nrm -rf /home/sakura/valuable\nEOF`
    5. `echo ${x:-<<EOF}\nrm -rf /home/sakura/valuable\nEOF`
    6. `x=${y/<<EOF/}; ls\ngit reset --hard HEAD~3\nEOF`
    7. `echo $((1<<2))\nrm -rf /home/sakura/valuable\n2`
    8. `((x=1<<2))\nrm -rf /home/sakura/valuable\n2`
    9. `echo $[1<<2]\nrm -rf /home/sakura/valuable\n2`
    10. `if ((1<<2)); then :; fi\nrm -rf /home/sakura/valuable\n2`
    11. `echo $[a[1]<<2]\nrm -rf /home/sakura/valuable\n2`
- [ ] AC-2: `echo $((1<<2)); cat <<'EOF'\nrm -rf /tmp/zz\nEOF` が allow になり、allow ケースとして cases.json にある。
- [ ] AC-3: cases.json の 592〜596（`$$'`、`${x:-a #}`、`$${`、`rm -rf /tmp/safe$'\t'`、`"${x:-a(b}"`）が、期待する判定のまま通る。
- [ ] AC-4: 既存の 574 件と無人実行の降格ケース 1 件が、期待する判定のまま通る。既存の deny / ask ケースは 1 件も消えていない。
- [ ] AC-5: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する（各ケース 10 秒以内）。`python3 -m unittest discover -s tests` も pass する。
- [ ] AC-6: FR10 の一致検査のテストが pass する。
- [ ] AC-7: 次の各形が deny になり、deny ケースとして cases.json にある。
    1. `for ((i=0; i<3; i++)); do rm -rf /home/sakura/valuable; done`
    2. `echo $(( $(rm -rf /home/sakura/valuable) + 1 ))`
    3. `echo ${x:-$(rm -rf /home/sakura/valuable)}`
    4. `echo "$'" ; rm -rf /home/sakura/valuable`
    5. `echo ${x\nrm -rf /home/sakura/valuable`

コマンド中の `\n` は改行を表す。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 種別 | 対象 | 内容 |
|----|------|------|------|
| TS-1 | unit | FR1, FR2, FR3, FR11, AC-1 | AC-1 の 11 形を deny ケースとして cases.json に足す - deny |
| TS-2 | unit | FR3, FR11, AC-2 | AC-2 の形を allow ケースとして足す - allow |
| TS-3 | unit | FR3, FR4, FR5, FR1, FR11, AC-7 | AC-7 の 5 形を deny ケースとして足す - deny |
| TS-4 | unit | FR7, FR12, AC-3 | cases.json 592〜596 が期待する判定のまま通る |
| TS-5 | unit | FR6, FR7, FR8, FR9, FR10, AC-6 | tests/ の一致検査のテストを実行する（詳細は下記） - pass |
| TS-6 | integration | FR12, AC-4, AC-5 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` を実行する - 全件 pass |
| TS-7 | performance | NFR3 | 既存の約 60KB の性能ケース（`echo ' + $(×30000 + ' ; rm -rf <対象>`）が、10 秒の制限時間内に deny を返す |
| TS-8 | edge_case | FR1, FR2, FR3, FR5, FR8 | TS-5 の一致検査で、境界の形が bash と同じ範囲で読まれることを確かめる（詳細は下記） |

**TS-5 の詳細**: 対象は cases.json の全コマンド、AC-1 / AC-7 の攻撃形、無害な対照例（`rm -rf /tmp/safe$'\t'`、`echo "${x:-a(b}"; cat <<'EOF'\ngit reset --hard HEAD\nEOF`、`echo $((1<<2)); cat <<'EOF'\nrm -rf /tmp/zz\nEOF`、`for ((i=0; i<3; i++)); do echo $i; done`、`echo "$'x'"` など）。引用の範囲・文の境界・演算子の位置・Tok の由来・検査用の値が一致し、検査用の値に伏字が残らない。

**TS-8 の詳細**: 次の形が bash と同じ範囲で読まれることを確かめる。

- 二重引用符の中の `$'`
- `$"..."`
- `$$'...'`・`$?'...'`
- `$'...'` の中の `\\` と `\'`
- `${#x}`・`${x#pat}`・`$#`
- `${x:-"}"}`
- `${x:-${y}}`
- `$((...))` と `$( (...) )`
- `( (cmd) )`
- 算術式の外の `a[1] <<EOF`
- `<<<`
- 置換の中の本物のヒアドキュメント
- 1 行に複数の文脈が並ぶ形と行をまたぐ形

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 伏字 | shlex に渡すために字句解析が書き換えた文字（FR7） |
| コマンド位置 | `((...))` を算術式として読む位置。予約語の後ろと `for ((...))` を含む（FR3） |

## 14. 確認事項

### 14.1 確認済み事項

該当なし

### 14.2 未確認・保留事項

次の前提を置いている。

- [ ] A1（影響: medium、可逆）: round2.yaml で unresolved の medium 5 件（0fb4a67c477e8034、54b0115faf5bc202、80dc2417b7e6670b、9f48c2f446a190b2、548598739d198748）は、この機能の範囲外とする。
- [ ] A2（影響: medium、可逆）: 既存の allow ケースも、期待する判定を変えない。
- [ ] A3（影響: high、可逆）: bash の読みを静的に確定できない形では、字句解析は後ろのテキストを検査から外さない読みを取る。閉じない `${`・`$((`・`$[`・`$'`、`))` で閉じない `((` などが該当する。外さない読みとは、ヒアドキュメント本文として取り込まない、コメントとして消さない、文の区切りを飲み込まない、の 3 つをいう。
- [ ] A4（影響: low、可逆）: 完了の定義の「修正版に追随している」は、自前のコードで上流の修正版が無いため、この修正そのものを対応として SPEC に記載する。
- [ ] A5（影響: low、可逆）: 変更するのは em-workflow/hooks/destructive-guard.py、em-workflow/hooks/tests/destructive-guard-cases.json、repo ルート tests/ に足す一致検査のテスト 1 ファイル（test/README.md の命名規則に従う test_*.py）に限る。hooks.json と version は変えない。

## 15. 参考資料

- `.claude/rules/hook-tests.md`
