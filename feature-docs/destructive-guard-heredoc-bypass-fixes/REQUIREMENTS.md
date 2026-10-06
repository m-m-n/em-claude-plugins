---
title: "destructive-guard-heredoc-bypass-fixes"
created_date: 2026-10-06
status: draft
---

# destructive-guard-heredoc-bypass-fixes - 要件定義書

## 1. 概要

### 1.1 背景
`em-workflow/hooks/destructive-guard.py` の字句解析に、回避経路 3 件（b0734a006de6f4d7 / a7c0d90ac3e44e5b / f34ee27bc8c323b1）が残っている。bash が実行する破壊的な行を、フックが本文として隠したり、配列代入として認識しなかったりして allow を返す。

### 1.2 目的
- `em-workflow/hooks/destructive-guard.py` の字句解析に残る回避経路 3 件（b0734a006de6f4d7 / a7c0d90ac3e44e5b / f34ee27bc8c323b1）を塞ぎ、bash が実行する破壊的な行をフックが allow で通す状態をなくす
- 既存の deny / ask ケースを 1 件も減らさない（特に T2 E-1 / T2 E-9）

### 1.3 スコープ
- 対象: `word_transition()` の代入語・組み込み命令名の判定、宣言組み込みと eval / let / alias の引数にある `NAME[` の扱い、`_count_extglob_units()` の解析単位の数え方、`em-workflow/hooks/tests/destructive-guard-cases.json` へのケース追加
- 範囲外: 765c3a53859569c2（subscript / extglob の走査器の共通化）、8633a419fec4b21c など round 2 の medium の所見（14.2 参照）

## 2. ビジネス要件

### 2.1 ビジネス目標
- 回避経路 3 件を塞ぎ、bash が実行する破壊的な行をフックが allow で通す状態をなくす
- 既存の deny / ask ケースを 1 件も減らさない（特に T2 E-1 / T2 E-9）

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 1.2 の目的と同じ

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | 語の内部の行継続を除いた論理的な語で代入語と組み込み命令名を判定する（b0734a006de6f4d7） | 4.2 FR1 参照 |
| FR2 | 宣言組み込みの引数の NAME[ で保留中のヒアドキュメントの本文を遅らせない（a7c0d90ac3e44e5b） | 4.2 FR2 参照 |
| FR3 | eval / let / alias を宣言組み込みと分けて扱う | 4.2 FR3 参照 |
| FR4 | extglob の解析単位を元の位置と出自で区別して数える（f34ee27bc8c323b1） | 4.2 FR4 参照 |
| FR5 | 再現入力をケース表に足す | 4.2 FR5 参照 |

### 4.2 機能詳細

#### FR1: 語の内部の行継続を除いた論理的な語で代入語と組み込み命令名を判定する（b0734a006de6f4d7）

**説明**: `word_transition()` は、代入語（`NAME=` / `NAME+=` / `NAME[`）と組み込み命令名（宣言組み込み、eval / let / alias）の判定を、語の内部のバックスラッシュ改行をすべて取り除いた論理的な語で行う。配列の開始位置（`ARR_END`）と添字の開始位置（`SUB_AT`）は元の入力上の位置で保つ。`x\<改行>=( <<EOF` と `decl\<改行>are x=( <<EOF` の後に破壊的な行を置いたコマンドは deny になる。

**受け入れ基準**: AC1、AC2

#### FR2: 宣言組み込みの引数の NAME[ で保留中のヒアドキュメントの本文を遅らせない（a7c0d90ac3e44e5b）

**説明**: declare / typeset / local / export / readonly の引数にある `NAME[` を読むとき、bash が本文として読む行を、フックが本文の開始を遅らせてコマンド以外として隠すことがないようにする。基準版で deny だった再現入力は deny に戻る。T2 E-9（`declare -a x[0]=( <<EOF` の後の git reset --hard）は deny のまま保つ。

**受け入れ基準**: AC3、AC6

#### FR3: eval / let / alias を宣言組み込みと分けて扱う

**説明**: eval / let / alias の引数にある `NAME[` は宣言組み込みと別の扱いにする。FR2 と同じ形のうち、bash 5.3.9 で隠れた行が実行されると実測で確かめた eval / let / alias の形は deny ケースとして足し、deny になるよう直す。T2 E-1（`eval x[a b]=( <<EOF` の後の git reset --hard）の deny と、`tests/test_destructive_guard_lexer_agreement.py` の `SUBSCRIPT_ARRAY_FORMS` の読み（ヒアドキュメント演算子を 1 つも登録しない）は保つ。

**受け入れ基準**: AC4、AC6、AC7

#### FR4: extglob の解析単位を元の位置と出自で区別して数える（f34ee27bc8c323b1）

**説明**: `_count_extglob_units()` は、解析単位を括弧より前の文字列だけで重複排除せず、元の入力上の位置と、eval / -c 展開のどれから来たかで区別する。括弧より前の文字列が同じ別の単位（外側と内側の eval が同じ接頭辞 `x=(@` を持つ形など）を 1 つにまとめない。この再現入力は extglob-switch の ask になる。

**受け入れ基準**: AC5、AC8

#### FR5: 再現入力をケース表に足す

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` に、b0734a006de6f4d7 と a7c0d90ac3e44e5b（FR3 の eval / let / alias の形を含む）の再現入力を deny、f34ee27bc8c323b1 の再現入力を ask で、`[期待する判定, ラベル, コマンド]` の 3 要素で足す。既存のケースは消さず、期待する判定も変えない。

**受け入れ基準**: AC9

## 5. 非機能要件

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | 検知力を減らさない | ケース表の deny と ask の件数は減らない。既存のすべてのケース（allow を含む）が期待する判定のまま通る。 |
| NFR2 | 作業量の上限 | 論理的な語の判定と解析単位の区別は、既存の字句解析の作業量上限（`LEX_WORK_FACTOR`）の中で、入力を読み直さずに行う。既存の線形性のテストが通る。 |
| NFR3 | テストの実行 | 同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` がすべて通る。 |
| NFR4 | 標準ライブラリのみ | フックとテストは Python 標準ライブラリだけを使う。 |
| NFR5 | version | em-workflow の version は手で変えない。 |

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- NFR2、NFR4、NFR5 を参照

### 9.2 ビジネス上の制約
- 該当なし

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-heredoc-bypass-fixes/**`
- `test-docs/destructive-guard-heredoc-bypass-fixes/**`

`feature-docs/destructive-guard-heredoc-bypass-fixes/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-heredoc-bypass-fixes/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-heredoc-bypass-fixes/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1）: 次の入力が deny になる
  ```
  x\
  =( <<EOF
  git reset --hard HEAD
  EOF
  ```
- [ ] AC2（FR1）: 次の入力が deny になる
  ```
  decl\
  are x=( <<EOF
  git reset --hard HEAD
  EOF
  ```
- [ ] AC3（FR2）: 宣言組み込み（declare / typeset / local / export / readonly）の引数の `NAME[` で保留中のヒアドキュメントの本文を遅らせる再現入力が deny になる
- [ ] AC4（FR3）: bash 5.3.9 で隠れた行が実行されると実測で確かめた eval / let / alias の同じ形の再現入力が deny になる
- [ ] AC5（FR4）: 外側と内側の eval が同じ接頭辞 `x=(@` を持ち、extglob を途中で切り替える再現入力が ask になる
- [ ] AC6（FR2, FR3, NFR1）: T2 E-1 と T2 E-9 が deny のまま通る
- [ ] AC7（FR3）: `SUBSCRIPT_ARRAY_FORMS` の各形でヒアドキュメント演算子が登録されないことを確かめる既存のテストが変更なしで通る
- [ ] AC8（FR4, NFR1）: T2 AC-4.7（`x=( @(foo|bar) ); cat <<"EOF"\nhello\nEOF`）が allow のまま通る
- [ ] AC9（FR5, NFR1）: 各再現入力がケース表に足されており、deny と ask の件数が変更前より減っていない
- [ ] AC10（NFR2, NFR3）: `run-destructive-guard.py` と `unittest discover -s tests` がすべて通る

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 期待する判定 | 対応する受け入れ基準 | 入力 |
|----|--------------|----------------------|------|
| TS1 | deny | AC1 | AC1 の入力 |
| TS2 | deny | AC2 | AC2 の入力 |
| TS3 | deny | AC3 | 先にヒアドキュメント演算子を置き、同じ行の declare / typeset / local / export / readonly の引数に `NAME[` を置き、続く行に bash が実行する破壊的な行を置く形。具体的な入力は bash 5.3.9 で破壊的な行が実行されることを確かめて決める |
| TS4 | deny | AC4 | TS3 と同じ形で命令名を eval / let / alias にしたもののうち、bash 5.3.9 で破壊的な行が実行されると実測で確かめた形 |
| TS5 | ask | AC5 | 外側と内側の eval がどちらも接頭辞 `x=(@` を持ち、その間で extglob を切り替える形（f34ee27bc8c323b1 の再現入力） |
| TS6 | deny | AC6 | 既存ケース T2 E-1 / T2 E-9 |
| TS7 | allow | AC8 | 既存ケース T2 AC-4.7 |
| TS8 | pass | AC7、AC10 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` / `python3 -m unittest discover -s tests` |

### 12.2 エッジケース
- 語の内部に連続するバックスラッシュ改行（`x\<改行>\<改行>=(`）
- `NAME[` や `+=` の途中の行継続（`x\<改行>[0]=(`、`x+\<改行>=(`）
- eval / let / alias と他の宣言組み込みの命令名の途中の行継続
- 引用符つきの引数の eval / let / alias は配列を開かない（T2 E-15 の allow を保つ）
- builtin / command を前置した declare は範囲外で allow のまま（T2 E-16 / E-17）
- 新しいケースは `tests/test_destructive_guard_lexer_agreement.py` の `TestStageAgreement`（拡張パターンの括弧を含むものは `TestStageAgreementUnderExtglobOn` も）の対象に自動で入り、そこでも通る必要がある

## 13. 用語定義

該当なし

## 14. 確認事項

### 14.1 確認済み事項
- なし

### 14.2 未確認・保留事項（前提として置いた事項。いずれも覆せる）
- [ ] 765c3a53859569c2（subscript / extglob の走査器の共通化）はこの機能の範囲外で、別タスクで扱う
- [ ] f34ee27bc8c323b1 の再現入力は ask で足し、無人実行での deny は `decide()` の既存の降格（`run-destructive-guard.py` 末尾の降格ケース）で担保する
- [ ] bash が実行するかどうかの基準は bash 5.3.9 の実測とする
- [ ] 8633a419fec4b21c（同じ括弧の再解析を複数の単位として数える過剰な ask）など round 2 の medium の所見は範囲外
- [ ] 既存の deny / ask ケースは消さず、期待する判定も変えない

## 15. 参考資料

- `feature-docs/destructive-guard-heredoc-syntax-error/reviews/round2.yaml`
