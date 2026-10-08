---
title: "tests-yaml-test-id-resolution"
created_date: 2026-10-09
status: draft
---

# tests-yaml-test-id-resolution - 要件定義書

## 1. 概要

### 1.1 背景
`test-docs/**/*.tests.yaml` の `acceptance_tests.*.tests` に、unittest の標準ローダーで直接選択できない ID が含まれている。事前調査の件数は 14.2 の前提 A2 に記す。

### 1.2 目的
- `test-docs/**/*.tests.yaml` の `acceptance_tests.*.tests` に書かれた全 ID を、unittest の標準ローダーで直接選択できる状態にする。
- テストの名前変更・削除で記録の ID がずれたとき、通常のテスト実行（`python3 -m unittest discover -s tests`）で検出できるようにする。
- 記録を書く側（implementer）に、プロジェクトのテスト実行コマンドで直接選択できる ID だけを書く規則を与え、再発を防ぐ。

### 1.3 スコープ
- 全記録の `acceptance_tests.*.tests` の ID の整理（FR1〜FR4）
- `tests/` への全件検査モジュールの新設（FR5〜FR9）
- `em-workflow/agents/implementer.md` への書き込み規則・確認手順の追加（FR10〜FR12）
- `test/README.md` への ID 形式と読み取り範囲の記載（FR7、FR13）

変更するパスは 9.4 に記す。

## 2. ビジネス要件

### 2.1 ビジネス目標
- `test-docs/**/*.tests.yaml` の `acceptance_tests.*.tests` に書かれた全 ID を、unittest の標準ローダーで直接選択できる状態にする。
- テストの名前変更・削除で記録の ID がずれたとき、通常のテスト実行（`python3 -m unittest discover -s tests`）で検出できるようにする。
- 記録を書く側（implementer）に、プロジェクトのテスト実行コマンドで直接選択できる ID だけを書く規則を与え、再発を防ぐ。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| implementer | 記録（`test-docs/{feature}/{T}.tests.yaml`）を書くエージェント（FR10〜FR12） |
| テスト実行者 | `python3 -m unittest discover -s tests` を実行する者（NFR2） |

### 2.3 期待される効果
- 全記録の全 ID が全件検査で解決する（AC-1、AC-2）。
- 記録の ID のずれが通常のテスト実行で失敗として現れる（NFR2、FR9）。

## 3. ユースケース

該当なし（機能要件は 4 章に記す）。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | ID 形式の統一 | resolved |
| FR2 | unittest 以外の記載の扱い | resolved |
| FR3 | 古い ID の対応付けと削除 | resolved |
| FR4 | 対象フィールド | resolved |
| FR5 | 全件検査モジュールの新設 | resolved |
| FR6 | 解決の判定基準 | resolved |
| FR7 | 記録の読み取り範囲 | resolved |
| FR8 | 空リストと読み取り失敗の区別 | resolved |
| FR9 | 新しいずれの見え方 | resolved |
| FR10 | implementer.md の書き込み規則 | resolved |
| FR11 | 記録を書いた後の確認 | resolved |
| FR12 | 他機能の記録を壊したときの扱い | resolved |
| FR13 | このリポジトリの ID 形式の記載 | resolved |

### 4.2 機能詳細

#### FR1: ID 形式の統一

**説明**: このリポジトリの記録の `tests` 要素は、`tests.` で始まるドット区切りの ID に統一する。メソッド ID に加えて、unittest が直接選択できるモジュール ID（例: `tests.test_x`）とクラス ID（例: `tests.test_x.TestY`）も認める。`path::Class::method` 形式の既存 ID はドット区切り形式に書き換える。

**関連する受け入れ基準**: AC-1、AC-2

#### FR2: unittest 以外の記載の扱い

**説明**: `tests` 要素のうち unittest の ID でないもの（別の実行器のスクリプト、説明文など）は `tests` から外す。対象を実際に検証している既存の unittest がある場合（例: destructive-guard の実行器を包む `tests/test_destructive_guard_command_substitution.py` のテスト）はその ID に置き換える。無い場合、その AC に残る ID が無ければ `tests: []` にする。外した説明は既存の `red_reason` の末尾へ追記し、既存の記述と `red_confirmed` は変えない。

**関連する受け入れ基準**: AC-1、AC-2、AC-4

#### FR3: 古い ID の対応付けと削除

**説明**: 解決できない ID は次の順で扱う。

1. 略称は、その記録内の定義から正式名を確定する（例: 記録内で定義された TBE）。
2. 名前変更・統合は、git 履歴から対応先を確認する。
3. 対象を特定できるワイルドカードは、実在する ID へ展開する。
4. 対応先が無い ID は削除する。

変更・削除した ID ごとに、ファイル・AC・旧 ID・新 ID または削除・根拠を、`test-docs/tests-yaml-test-id-resolution/` 配下の文書として記録する。ID 整理の作業では既存の `red_confirmed` / `red_reason` を変えない（FR2 の追記を除く）。

**関連する受け入れ基準**: AC-1、AC-2、AC-3、AC-4

#### FR4: 対象フィールド

**説明**: 書き換えと検査の対象は `acceptance_tests.*.tests` だけにする。`baseline_failures` / `final_failures` は書き換えない。

**関連する受け入れ基準**: AC-4

#### FR5: 全件検査モジュールの新設

**説明**: `tests/` に新しいテストモジュールを追加する。`test-docs/**/*.tests.yaml` の全記録を列挙し、`acceptance_tests.*.tests` の全 ID を抽出して解決を判定する。抽出エラーと解決エラーは途中で止めず全件集め、ファイル・AC・ID・理由を付けて失敗メッセージに並べる。`tests/test_exit4_ac2_test_id_drift.py` は変更しない。

**関連する受け入れ基準**: AC-1、AC-5

#### FR6: 解決の判定基準

**説明**: ID が `tests.` で始まり、リポジトリルートを `sys.path` に置いた状態で、次のどれかに解決できるとき、解決できたと判定する。

- モジュール
- `unittest.TestCase` の派生クラス
- そのクラス（`TestCase` 自身を除く継承元を含む）で定義されたメソッド

そのうえで `unittest.TestLoader().loadTestsFromName` でも確認し、例外が出た場合だけでなく、`loader.errors` に記録が残った場合や `_FailedTest` が返った場合も失敗と判定する。判定の過程でテストを実行せず、解決したオブジェクトを呼び出さない。検査後に `sys.path` を元に戻す。

**関連する受け入れ基準**: AC-1、AC-2、AC-5、AC-6

#### FR7: 記録の読み取り範囲

**説明**: 抽出は、対応する YAML 表記の範囲を明示したうえで行う。

**対応する表記**:
- `tests` のブロック形式のリスト
- `tests` の 1 行のフロー形式のリスト（`[]` を含む）
- 引用符付きスカラー
- 行末コメント
- 他キー（`red_reason` など）の複数行スカラー（`>` / `|`）

**ビジネスルール**:
- 複数行スカラーの本文中に `tests:` や `-` で始まる行があっても、ID として読まない。
- AC キーは `AC-n` 以外の名前（例: `D4-parser-unavailable`）も受け付ける。
- 対応する表記の範囲は `test/README.md` に書く。

**エラーケース**（いずれもファイルと AC を示して失敗させる）:
| エラー | 条件 |
|--------|------|
| 未対応形式 | 対応する表記の範囲外の形式 |
| AC キーの重複 | 同じ AC キーが複数ある |
| tests キーの重複 | 同じ AC に `tests` キーが複数ある |
| tests キーの欠落 | AC に `tests` キーが無い |
| acceptance_tests の欠落 | 記録に `acceptance_tests` が無い |

**関連する受け入れ基準**: AC-7

#### FR8: 空リストと読み取り失敗の区別

**説明**: `tests: []` は正当な記録として受け入れ、全 AC が `tests: []` の記録も失敗にしない。読み取りに失敗した記録を空リストとして扱わない。検査対象の記録が 1 件も見つからない場合は失敗させる。

**関連する受け入れ基準**: AC-8

#### FR9: 新しいずれの見え方

**説明**: 全件検査の失敗は、記録ファイルごとに別のテスト名として現れるようにする。ある記録がすでに失敗している状態でも、別の記録に新しく不正な ID が入れば、失敗したテスト名の差分（implementer.md Step 4b の baseline との比較）に現れる。

**関連する受け入れ基準**: AC-9

#### FR10: implementer.md の書き込み規則

**説明**: `em-workflow/agents/implementer.md` の Step 4c に、言語に依存しない規則を追加する。

**ビジネスルール**:
- `tests` の各要素は、そのプロジェクトのテスト実行コマンドで直接選択できる ID とする。
- 説明文・略称・ワイルドカード・実行器スクリプトのパスは書かない。
- 説明は `red_reason` に書く。

**関連する受け入れ基準**: AC-10

#### FR11: 記録を書いた後の確認

**説明**: `implementer.md` に、Step 4c で記録を書いた後に `project_commands.test` を実行し、baseline にない失敗が無いことを確認する手順を追加する。記録が原因の失敗は記録の側を直す。

**関連する受け入れ基準**: AC-10

#### FR12: 他機能の記録を壊したときの扱い

**説明**: `implementer.md` に次の規則を追加する。

**ビジネスルール**:
- テストの名前変更・削除で他の機能やタスクの記録が全件検査に失敗するようになった場合は、その記録の ID も直す。
- 予定の範囲外のファイル変更は `deviations` に報告する。
- 変更範囲への追加を求める場合は、既存の AC、必要なパス、直さないと失敗する検査を示す。

**関連する受け入れ基準**: AC-10

#### FR13: このリポジトリの ID 形式の記載

**説明**: `test/README.md` に次を書く。
- このリポジトリの記録で使う ID 形式（`tests.` で始まるドット区切り。モジュール・クラス・メソッドのどれでもよい）
- 全件検査が読み取る YAML 表記の範囲（FR7）

**関連する受け入れ基準**: AC-10

### 4.3 全件検査のエラーケース
| エラー | 条件 | 対応 |
|--------|------|------|
| 抽出エラー | FR7 のエラーケースに当たる記録 | 途中で止めず集め、ファイル・AC・ID・理由を付けて失敗メッセージに並べる（FR5） |
| 解決エラー | FR6 で解決できない ID | 途中で止めず集め、ファイル・AC・ID・理由を付けて失敗メッセージに並べる（FR5） |
| 読み取り失敗 | 記録を読み取れない | 空リストとして扱わず失敗させる（FR8） |
| 対象 0 件 | 検査対象の記録が 1 件も見つからない | 失敗させる（FR8） |

## 5. 非機能要件

### 5.1 非機能要件一覧
| ID | 名前 | 内容 |
|----|------|------|
| NFR1 | 標準ライブラリのみ | 新しい検査モジュールは標準ライブラリだけを import する。YAML ライブラリや他のテストモジュールは import しない。 |
| NFR2 | 通常のテスト実行に含める | 全件検査は `python3 -m unittest discover -s tests` で自動的に実行される。登録作業や別コマンドは要らない。 |
| NFR3 | 既存テストの維持 | `tests/test_exit4_ac2_test_id_drift.py` を変更せず、通り続ける状態を保つ。この検査が固定している `test-docs/exit4-tip-argument/task0002.tests.yaml` の内容（AC ごとの ID 数、AC-2 の `red_reason` の 1 行引用符付き形式、`red_confirmed: true`）を変えない。 |
| NFR4 | バージョン | em-workflow の version は変更しない。 |

### 5.2 パフォーマンス要件
該当なし。

### 5.3 セキュリティ要件
該当なし。

### 5.4 可用性要件
該当なし。

### 5.5 互換性要件
該当なし。

## 6. UI/UX要件

該当なし。

## 7. データ要件

### 7.1 データモデル概要
対象は記録ファイル（`test-docs/**/*.tests.yaml`）と、ID の対応記録（`test-docs/tests-yaml-test-id-resolution/` 配下）。

### 7.2 データ項目
| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| 記録 | `acceptance_tests` | マップ | ○ | AC キーごとの記録。欠落は失敗（FR7） |
| 記録 | `acceptance_tests.*.tests` | リスト | ○ | 書き換えと検査の対象（FR4）。`[]` は正当（FR8） |
| 記録 | `acceptance_tests.*.red_reason` | 文字列 | × | FR2 による末尾への追記だけを行う |
| 記録 | `acceptance_tests.*.red_confirmed` | 真偽値 | × | 変えない（FR2、FR3） |
| 記録 | `baseline_failures` / `final_failures` | - | × | 書き換えない（FR4） |
| ID の対応記録 | ファイル | 文字列 | ○ | 変更・削除した ID がある記録ファイル（FR3） |
| ID の対応記録 | AC | 文字列 | ○ | 該当する AC キー（FR3） |
| ID の対応記録 | 旧 ID | 文字列 | ○ | 変更・削除前の ID（FR3） |
| ID の対応記録 | 新 ID または削除 | 文字列 | ○ | 変更後の ID、または削除（FR3） |
| ID の対応記録 | 根拠 | 文字列 | ○ | 対応付け・削除の根拠（FR3） |

### 7.3 データ保持期間
該当なし。

## 8. 外部連携

### 8.1 連携システム
該当なし。

### 8.2 API仕様要件
該当なし。

## 9. 制約条件

### 9.1 技術的制約
- 新しい検査モジュールは標準ライブラリだけを import する（NFR1）。
- 判定の過程でテストを実行せず、解決したオブジェクトを呼び出さない（FR6）。
- `tests/test_exit4_ac2_test_id_drift.py` は変更しない（FR5、NFR3）。

### 9.2 ビジネス上の制約
- em-workflow の version は変更しない（NFR4）。

### 9.3 スケジュール制約
- 該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。そのうえで、このフィーチャーはデフォルトメンバーに加えて次のパスを変更することを明示する。

**デフォルト外のパス**:
- `test-docs/**/*.tests.yaml` — 他の機能のものを含む全記録。書き換えるのは `acceptance_tests.*.tests` と、FR2 による `red_reason` 末尾への追記だけ。`test-docs/exit4-tip-argument/task0002.tests.yaml` は NFR3 が固定する内容を変えない。
- `em-workflow/agents/implementer.md` — FR10〜FR12
- `test/README.md` — FR7、FR13
- `tests/` 配下に新設する全件検査モジュール — FR5〜FR9

**明示するデフォルトメンバー内のパス**:
- `test-docs/tests-yaml-test-id-resolution/` — ID の対応記録（FR3）

**変更しないパス**:
- `tests/test_exit4_ac2_test_id_drift.py`（FR5、NFR3）

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/tests-yaml-test-id-resolution/**`
- `test-docs/tests-yaml-test-id-resolution/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし。

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: `test-docs/**/*.tests.yaml` の全記録で、`acceptance_tests.*.tests` の全 ID が全件検査で抽出エラー・解決エラーなしに解決する。（FR1、FR2、FR3、FR5、FR6）
- [ ] AC-2: タスク説明の再現手順（全記録の全 ID を `unittest.TestLoader().loadTestsFromName` で解決する）を実行すると、解決できない ID が 0 件になる。（FR1、FR2、FR3、FR6）
- [ ] AC-3: 変更・削除した全 ID について、ファイル・AC・旧 ID・新 ID または削除・根拠の記録があり、その件数が実際の差分と一致する。（FR3）
- [ ] AC-4: ベースからの差分で、記録の `red_confirmed`・`baseline_failures`・`final_failures` は変わっていない。`red_reason` の変更は FR2 による末尾への追記だけで、追記前の記述が先頭にそのまま残っている。（FR2、FR3、FR4）
- [ ] AC-5: 存在しないメソッド・クラス・モジュールを指す ID、`tests.` で始まらない ID、`path::Class::method` 形式の ID、説明文の要素を持つ記録のフィクスチャを全件検査にかけると、ファイル・AC・ID を示して失敗する。複数の不正 ID は 1 回の失敗メッセージにすべて並ぶ。（FR5、FR6）
- [ ] AC-6: `loadTestsFromName` が例外を出さずに `loader.errors` / `_FailedTest` で失敗を返す ID を、全件検査が失敗と判定する。テストを実行しないこと（解決した対象のテスト本体が持つ副作用が起きないこと）が確認できる。（FR6）
- [ ] AC-7: ブロック形式・フロー形式・引用符付き・コメント付きの `tests` と、本文に `tests:` や `-` 行を含む複数行の `red_reason` を持つフィクスチャから、期待どおりの ID だけが抽出される。対応しない形式・重複キー・`tests` キーの欠落・`acceptance_tests` の欠落はファイルと AC を示して失敗する。（FR7）
- [ ] AC-8: 全 AC が `tests: []` の記録は失敗しない。読み取りに失敗する記録は空リスト扱いにならず失敗する。対象記録 0 件では失敗する。（FR8）
- [ ] AC-9: ある記録がすでに失敗している状態で別の記録に不正 ID を加えると、新しい失敗テスト名が増える。（FR9）
- [ ] AC-10: `implementer.md` に FR10・FR11・FR12 の規則が、`test/README.md` に FR13 の記載がある。（FR10、FR11、FR12、FR13）
- [ ] AC-11: 新しい検査モジュールの import が標準ライブラリだけである。`python3 -m unittest discover -s tests` で新モジュールが実行され、`tests/test_exit4_ac2_test_id_drift.py` は無変更のまま通る。（NFR1、NFR2、NFR3）

### 11.2 KPI
| 指標 | 目標値 | 測定方法 |
|------|--------|----------|
| 解決できない ID の件数 | 0 件 | 全件検査（AC-1）と再現手順（AC-2） |

## 12. テストシナリオ

### 12.1 テスト観点
| ID | 受け入れ基準 | シナリオ |
|----|--------------|----------|
| TS-1 | AC-1 | 実リポジトリの `test-docs/**/*.tests.yaml` を全件検査にかけ、記録ファイルごとのテストがすべて通る。 |
| TS-2 | AC-2 | 再現手順（各 ID を `loadTestsFromName` で解決）を実行し、失敗 0 件を確認する（verify で実施）。 |
| TS-3 | AC-3、AC-4 | ベースとの git diff で、記録の変更が `tests` 要素と `red_reason` 末尾への追記だけであることと、変更 ID と対応記録の件数の一致を確認する（verify で実施）。 |
| TS-4 | AC-5 | 一時ディレクトリのフィクスチャ記録に、存在しないメソッド・クラス・モジュール、`tests.` 接頭辞なし、`path::` 形式、説明文を入れて検査し、メッセージにファイル・AC・全不正 ID が含まれることを確かめる。 |
| TS-5 | AC-6 | 既存クラス上の存在しないメソッド ID で `loader.errors` / `_FailedTest` 経路を通し、失敗判定を確認する。テスト本体でマーカーファイルを作るフィクスチャのテストモジュールを解決させ、マーカーが作られないことを確かめる。`TestCase` 以外の属性や呼び出し可能なモジュール属性は呼ばれずに拒否される。 |
| TS-6 | AC-7 | 表記ごとのフィクスチャで抽出結果を比較し、未対応形式・AC キー重複・`tests` キー重複・`tests` キー欠落・`acceptance_tests` 欠落がそれぞれファイルと AC を示して失敗することを確かめる。 |
| TS-7 | AC-8 | 全 AC が `tests: []` の記録が通り、読み取れない記録と対象 0 件が失敗することを確かめる。 |
| TS-8 | AC-9 | 2 つの記録フィクスチャで、片方を失敗させた状態にもう片方へ不正 ID を加え、失敗テスト名の集合が増えることを確かめる。 |
| TS-9 | AC-10 | `implementer.md` と `test/README.md` を読み、規則の記述があることを文書契約テストで確かめる。 |
| TS-10 | AC-11 | 新モジュールの import を `ast` で列挙し `sys.stdlib_module_names` に含まれることを確かめる。全スイートを実行する。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 記録 | `test-docs/**/*.tests.yaml` の各ファイル |
| 全件検査 | FR5 で `tests/` に新設するテストモジュール |
| 解決 | FR6 の判定基準を満たすこと |
| ID の対応記録 | FR3 で `test-docs/tests-yaml-test-id-resolution/` 配下に作る、変更・削除した ID の一覧 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] ID 形式: `tests.` で始まるドット区切りに統一し、モジュール ID・クラス ID も認める（FR1）
- [x] unittest 以外の記載: 対象を検証する既存の unittest の ID に置き換え、無ければ外して `red_reason` 末尾へ追記する（FR2）
- [x] 古い ID: 略称・名前変更・ワイルドカードを対応付け、対応先が無ければ削除して記録する（FR3）
- [x] 対象フィールド: `acceptance_tests.*.tests` だけ（FR4）
- [x] 検査の形: 標準ライブラリだけの新モジュールで全件を検査し、エラーを集約する（FR5、NFR1）
- [x] 読み取る表記: ブロック形式とフロー形式の両方に対応し、範囲を明示する（FR7）
- [x] 書き込み規則: implementer.md には言語に依存しない規則、このリポジトリの形式は `test/README.md` に書く（FR10、FR13）
- [x] 検査の実行場所: 通常のテスト実行に含め、壊した他機能の記録も直す（NFR2、FR12）
- [x] デザインステップ: 実施しない

### 14.2 前提

- A1: 解決判定はリポジトリルートを `sys.path` に置いた状態で行う。`python3 -m unittest discover -s tests` をリポジトリルートから実行したときは、`tests/` とリポジトリルートの両方が `sys.path` にあり、`tests.` 付きの ID がこの状態で解決する。
- A2: 件数（409 ファイル、失敗 ID 1,035 件 / 133 ファイル、ドット形式への変換で解決するもの 257 件、残り 778 件 / 123 ファイル、旧抽出器が拒否する 90 ファイル）は事前調査の値で、要件では件数を固定しない。タスク説明の「約 769 件」とは差がある。
- A3: ID の対応記録の置き場所は `test-docs/tests-yaml-test-id-resolution/` とする。
- A4: ID 整理で AC の ID がすべて削除され `tests: []` になっても、`red_confirmed` / `red_reason` は変えない。全件検査は `red_confirmed` との整合を判定しない。

### 14.3 未確認・保留事項
- なし

## 15. 参考資料

- SPEC: `feature-docs/tests-yaml-test-id-resolution/SPEC.md`
