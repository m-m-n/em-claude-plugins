---
title: "tests-yaml-id-resolution-gaps"
created_date: 2026-10-09
status: draft
---

# tests-yaml-id-resolution-gaps - 要件定義書

## 1. 概要

### 1.1 背景
記録検査 `tests/test_tests_yaml_id_resolution.py` には、レビュー round1 で挙がった 6 件の穴（medium 3 件・low 3 件）が残っている。

### 1.2 目的
- 記録検査に残る 6 件の穴をふさぎ、誤った記録の書き方や特殊なテストモジュールがあっても、ずれの見逃しや検査の途中停止が起きないようにする。
- `test/README.md` と検査モジュールの docstring にある非実行の保証を、実際の動作と一致する範囲に揃える。

### 1.3 スコープ
- `tests/test_tests_yaml_id_resolution.py`（検査モジュールとそのフィクスチャテスト）
- `tests/test_tests_yaml_id_rules_docs.py`（文書契約テスト）
- `test/README.md`（Syntax gate、Structural resolution、Loader confirmation、非実行の保証の記述）
- `test-docs/tests-yaml-test-id-resolution/task0001.tests.yaml`（AC-2 の ID の改名追従）

スコープ外:
- `tests/test_exit4_ac2_test_id_drift.py`（変更しない）
- `feature-docs/tests-yaml-test-id-resolution/SPEC.md` と `reviews/round1.yaml`（書き換えない）
- README の Test Docs Records 節への走査エラーの記載
- em-workflow の version

## 2. ビジネス要件

### 2.1 ビジネス目標
- 誤った記録の書き方や特殊なテストモジュールがあっても、記録検査がずれを見逃さず、途中で止まらない。
- 非実行の保証の記述が実際の動作と一致している。

### 2.2 対象ユーザー
対象外

### 2.3 期待される効果
- 記録検査に残る 6 件の穴がふさがる。
- 非実行の保証の記述が実際の動作と一致する。

## 3. ユースケース

対象外

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | ステータス |
|----|--------|------------|
| FR1 | 2 セグメント未満の ID を構文検査で拒否する | confirmed |
| FR2 | 抽出エラーのある AC でも読めた ID を解決判定する | confirmed |
| FR3 | 走査エラーを対象パス付きの検査失敗として報告する | confirmed |
| FR4 | ローダーの戻り値を確認し、反復中の例外も ID ごとのエラーにする | confirmed |
| FR5 | ダンダー名をメソッド ID として拒否する | confirmed |
| FR6 | 非実行の保証の記述を書き直す | confirmed |
| FR7 | 再発を検出するテスト | confirmed |
| FR8 | 古い動作を固定している既存テストと記録の更新 | confirmed |

### 4.2 機能詳細

#### FR1: 2 セグメント未満の ID を構文検査で拒否する

**説明**: canonical_id_failure（Syntax gate）は、ドット区切りのセグメント数が 2 未満の ID を不正とする。

**ビジネスルール**:
- 単独の `tests` は、理由が `not a canonical ID` で始まるエラーとして拒否する。
- 拒否はどの import よりも前に行い、モジュール検索パスとモジュールキャッシュを変えない。

**バリデーション**:
| 項目 | ルール | エラーメッセージ |
|------|--------|------------------|
| ID | ドット区切りのセグメントが 2 つ以上 | `not a canonical ID` で始まる |

#### FR2: 抽出エラーのある AC でも読めた ID を解決判定する

**説明**: AC に抽出エラーがあっても、その AC の `tests` から 1 行で完結したスカラーとして読めた ID はすべて解決判定する。抽出エラーと解決エラーの両方を、同じ記録の失敗メッセージに並べる。

**ビジネスルール**:
- 同じ AC 内の `tests` キーの重複と AC キーの重複も対象に含む。読めた ID はその AC キーの名前で報告する。
- 抽出エラーそのものになった要素は ID として扱わず、解決判定しない。該当する要素は次のとおり。
    - マッピング
    - 入れ子
    - 空の要素
    - 深い行に続く複数行の値
    - 閉じていない引用符
    - 読み取りに失敗したフロー形式のリスト

#### FR3: 走査エラーを対象パス付きの検査失敗として報告する

**説明**: `test-docs/` 配下の走査（os.walk）で一覧を取れなかったディレクトリは、通常の実行（`python3 -m unittest discover -s tests`）で集められるテストの失敗として報告する。

**ビジネスルール**:
- 失敗メッセージには、リポジトリ相対のパスと理由を含める。
- 走査エラーがあってもモジュールの import は止めない。
- 読めた記録は、これまでどおり記録ごとのテストで検査する。
- `test-docs/` 自体が存在しない場合は走査エラーにせず、これまでどおり「記録 0 件」としてゼロ件ガードで失敗させる。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 走査エラー | `test-docs/` 配下のディレクトリの一覧を取れない | リポジトリ相対のパスと理由を示してテストを失敗させる |
| 記録 0 件 | `test-docs/` 自体が存在しない | 走査エラーにせず、ゼロ件ガードで失敗させる |

#### FR4: ローダーの戻り値を確認し、反復中の例外も ID ごとのエラーにする

**説明**: ローダー確認（_loader_failure）では、loadTestsFromName の戻り値が unittest.TestSuite のインスタンスであることを確認する。

**ビジネスルール**:
- 戻り値が unittest.TestSuite のインスタンスでなければ、その ID の解決エラーとする。
- 戻り値を再帰的にたどる途中で出た例外も、その ID の解決エラーとして返す。
- 同じ記録の後続の ID は、これまでどおり判定を続ける。

#### FR5: ダンダー名をメソッド ID として拒否する

**説明**: 構造判定で、最後のセグメントがダンダー名（`__` で始まり `__` で終わる名前。例: `__init__`）のメソッド ID を、理由が `not a test method` のエラーとして拒否する。

**ビジネスルール**:
- テストケースクラス自身が定義している場合も同じに扱う。
- 拒否はローダー確認より前に行う。

**バリデーション**:
| 項目 | ルール | エラーメッセージ |
|------|--------|------------------|
| メソッド ID の最後のセグメント | ダンダー名でない | `not a test method` |

#### FR6: 非実行の保証の記述を書き直す

**説明**: `test/README.md` の非実行の保証を、次の範囲に書き直す。

> テストメソッドの本体は実行しない。ローダー確認では、通常の収集と同じくテストクラスの生成（独自の `__init__` を含む）と load_tests フックが動く。

**ビジネスルール**:
- 同じ範囲になるよう、検査モジュールの docstring と resolver 節のコメントも直す。
- README の Syntax gate は「two or more dot-separated segments」に改める。
- README の Structural resolution に、ダンダー名の拒否を書き加える。
- README の Loader confirmation に、戻り値がスイートでない場合と反復中の例外を失敗条件として書き加える。
- モジュールの docstring、canonical_id_failure、extract_text、check_record、Extraction の各説明も、FR1〜FR5 の動作に合わせて更新する。

#### FR7: 再発を検出するテスト

**説明**: FR1〜FR5 の動作それぞれに、`tests/test_tests_yaml_id_resolution.py` のフィクスチャテストを用意する。FR6 で README に書いた記述（2 セグメント以上、非実行の保証の範囲）は、`tests/test_tests_yaml_id_rules_docs.py` の文言検査で固定する。

#### FR8: 古い動作を固定している既存テストと記録の更新

**説明**: 古い動作を前提にした既存テストを、新しい動作に合わせて直す。

**ビジネスルール**:
- `tests` を通る ID として扱う箇所を直す。
    - TestSyntaxGate.test_canonical_ids_pass_the_gate
    - TestResolutionWithoutExecution.PASSING
    - TestSearchPathAndModuleCache.test_root_is_at_the_front_of_the_search_path_only_for_the_duration_of_the_call
- 抽出エラーのある AC を解決しないことを確かめる TestExtractionErrors.test_an_ac_with_an_extraction_error_gets_no_resolution_errors は、期待が逆になるので名前を変える。
- `test-docs/tests-yaml-test-id-resolution/task0001.tests.yaml` の AC-2 にある該当 ID も新しい名前に直す。

## 5. 非機能要件

| ID | 要件名 | 内容 |
|----|--------|------|
| NFR1 | 標準ライブラリのみ | `tests/test_tests_yaml_id_resolution.py` と `tests/test_tests_yaml_id_rules_docs.py` は、引き続き標準ライブラリだけを import する。 |
| NFR2 | 通常の実行に含める | 追加するテストと走査エラーの報告は、`python3 -m unittest discover -s tests` で登録作業なしに実行される。 |
| NFR3 | 既存の検査を保つ | `tests/test_exit4_ac2_test_id_drift.py` は変更しない。実リポジトリの全記録の記録ごとのテストとゼロ件ガードは、変更後も通る。 |
| NFR4 | バージョン | em-workflow の version は変更しない。 |

### 5.1 パフォーマンス要件
対象外

### 5.2 セキュリティ要件
対象外

### 5.3 可用性要件
対象外

### 5.4 保守性要件
- ドキュメント: FR6 のとおり

### 5.5 互換性要件
- NFR3 のとおり

## 6. UI/UX要件

対象外（UI を持たない変更）

## 7. データ要件

対象外

## 8. 外部連携

対象外

## 9. 制約条件

### 9.1 技術的制約
- NFR1: 標準ライブラリのみを import する。
- NFR2: `python3 -m unittest discover -s tests` で登録作業なしに実行される。

### 9.2 ビジネス上の制約
- NFR4: em-workflow の version は変更しない。

### 9.3 スケジュール制約
- なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/tests-yaml-id-resolution-gaps/**`
- `test-docs/tests-yaml-id-resolution-gaps/**`

`feature-docs/tests-yaml-id-resolution-gaps/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/tests-yaml-id-resolution-gaps/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/tests-yaml-id-resolution-gaps/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題（エッジケース）
- `test-docs/` 自体が無い場合、os.walk は onerror に FileNotFoundError を渡す。これは走査エラーにせず、ゼロ件ガードで扱う。
- ブロック形式の項目が深い行に続く場合（複数行のプレーンスカラー）、1 行目だけが ids に追加される現在の実装経路があるが、この断片は解決判定しない。
- 読み取りに失敗したフロー形式のリストからは、ID を 1 件も取り出さない。
- load_tests がテストケースのリストを返す場合は、TestSuite ではないので解決エラーになる。
- ダンダー名の拒否はメソッド ID の最後のセグメントに限る。モジュールやクラスのセグメントの扱いは変えない。

### 10.2 ビジネスリスク
対象外

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR1, FR7）: `acceptance_tests: {AC-1: {tests: [tests]}}` の記録を check_record に渡すと、`tests` を `not a canonical ID` とするエラー行が返り、import は起きない。2 セグメント以上の正しい ID はこれまでどおり通る。
- [ ] AC-2（FR2, FR7）: `tests: [tests.nope.A.b, {name: x}]`（ブロック形式でマッピング要素を含む）の記録を check_record に渡すと、マッピング要素の抽出エラーと `tests.nope.A.b` の解決エラーが両方返る。複数行の値の断片など、抽出エラーになった要素は解決判定されない。
- [ ] AC-3（FR3, FR7）: os.scandir を模擬して配下ディレクトリで PermissionError を起こすと、通常の実行で集められるテストが、そのディレクトリのパスと理由を示して失敗する。読めた記録はそれぞれ検査され、`test-docs/` が存在しない根では、これまでどおりゼロ件ガードだけが失敗する。
- [ ] AC-4（FR4, FR7）: load_tests フックがスイート以外（例: None）を返すモジュール ID と、反復中に例外を出すスイートを返すモジュール ID は、どちらもその ID の解決エラーになる。同じ記録の後続 ID の判定結果も、失敗メッセージに並ぶ。
- [ ] AC-5（FR5, FR7）: テストケースクラスが自分で定義した `__init__` を指すメソッド ID は `not a test method` で拒否され、ローダー確認に進まない。
- [ ] AC-6（FR6, FR7）: `test/README.md` の Syntax gate が 2 セグメント以上を求めている。非実行の保証は「テストメソッドの本体は実行しない。ローダー確認では通常の収集と同じくクラス生成と load_tests フックが動く」範囲で書かれている。検査モジュールの docstring も同じ範囲になっている。この記述が文書契約テストで固定されている。
- [ ] AC-7（FR8, NFR1, NFR2, NFR3）: `python3 -m unittest discover -s tests` が通る。古い動作を固定していた既存テストは新しい動作に合わせて直してある。task0001.tests.yaml の ID は改名後のテストを指し、記録検査を通る。

### 11.2 KPI
対象外

## 12. テストシナリオ

### 12.1 テスト観点
| ID | 種別 | 対象 AC | シナリオ |
|----|------|---------|----------|
| TS-1 | unit | AC-1 | 単独の `tests` を canonical_id_failure と check_record にかける。`not a canonical ID` で拒否され、モジュールキャッシュとモジュール検索パスが変わらない。 |
| TS-2 | unit | AC-2 | マッピング要素と存在しない ID を混ぜた AC、`tests` キーが重複した AC、AC キーが重複した記録、複数行の値の断片を含む AC を check_record にかける。読めた ID の解決エラーと抽出エラーが両方並び、断片は判定されない。 |
| TS-3 | unit | AC-3 | os.scandir を模擬して配下ディレクトリで PermissionError を起こす。走査エラーのテストがパスと理由を示して失敗し、読めた記録のテストは残る。`test-docs/` が無い根では走査エラーにならない。 |
| TS-4 | unit | AC-4 | load_tests が None を返すフィクスチャモジュールと、反復中に例外を出すスイートを返す模擬ローダーを使い、resolve_id と check_record にかける。ID ごとの解決エラーになり、後続 ID の判定も続く。 |
| TS-5 | unit | AC-5 | 独自の `__init__` でマーカーを作る TestCase 派生クラスを持つフィクスチャで、`...Cls.__init__` を resolve_id にかける。`not a test method` で拒否され、マーカーが作られない。 |
| TS-6 | integration | AC-6 | `tests/test_tests_yaml_id_rules_docs.py` の文言検査で、README の 2 セグメント以上の記述と非実行の保証の範囲を確かめる。記述を消すと、その検査が失敗する。 |
| TS-7 | integration | AC-7 | `python3 -m unittest discover -s tests` を実行し、全スイートと実リポジトリの記録ごとのテストが通る。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| ダンダー名 | `__` で始まり `__` で終わる名前。例: `__init__` |
| 走査エラー | `test-docs/` 配下の走査（os.walk）で一覧を取れなかったディレクトリ |
| スイート | unittest.TestSuite のインスタンス |

## 14. 確認事項

### 14.1 確認済み事項
- [x] デザインステップ: skipped（UI を持たない変更（テストモジュール、テスト、README の記述）のため）

### 14.2 未確認・保留事項
- なし

### 14.3 前提
- A1: FR4 の「スイート」は unittest.TestSuite のインスタンスを指す。
- A2: FR2 では、`tests` キーの重複と AC キーの重複も「抽出エラーのある AC」に含め、読めた ID を解決判定する。
- A3: 走査エラーは別経路で集め、専用の生成テストケースクラスの 1 テストで、リポジトリ相対のパスと理由を並べて失敗させる。enumerate_records の戻り値の形は変えない。記録ごとのテストクラスを生成したときの走査で出たエラーをそのクラスに渡す。
- A4: README の Test Docs Records 節には、走査エラーの記載を加えない。
- A5: 完了済みの `feature-docs/tests-yaml-test-id-resolution/SPEC.md`（FR6 の「解決したオブジェクトを呼び出さない」）と `reviews/round1.yaml` は書き換えない。
- A6: 実リポジトリの記録には、単独の `tests` やダンダー名のメソッドを指す ID は無い前提にする。

## 15. 参考資料

- `tests/test_tests_yaml_id_resolution.py`
- `tests/test_tests_yaml_id_rules_docs.py`
- `test/README.md`
- `test-docs/tests-yaml-test-id-resolution/task0001.tests.yaml`
