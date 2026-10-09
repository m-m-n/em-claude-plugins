# Feature: tests-yaml-id-resolution-gaps

## Overview

記録検査 `tests/test_tests_yaml_id_resolution.py` に残る 6 件の穴（レビュー round1 の medium 3 件・low 3 件）をふさぐ。あわせて、`test/README.md` と検査モジュールの docstring にある非実行の保証を、実際の動作と一致する範囲に揃える。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- 誤った記録の書き方や特殊なテストモジュールがあっても、記録検査がずれを見逃さず、途中で止まらない。
- `test/README.md` と検査モジュールの docstring にある非実行の保証を、実際の動作と一致する範囲に揃える。

## User Stories

対象外

## Technical Requirements

### Functional Requirements
- **FR1:** 2 セグメント未満の ID を構文検査で拒否する。canonical_id_failure（Syntax gate）は、ドット区切りのセグメント数が 2 未満の ID を不正とする。単独の `tests` は、理由が `not a canonical ID` で始まるエラーとして拒否する。拒否はどの import よりも前に行い、モジュール検索パスとモジュールキャッシュを変えない。
- **FR2:** 抽出エラーのある AC でも読めた ID を解決判定する。AC に抽出エラーがあっても、その AC の `tests` から 1 行で完結したスカラーとして読めた ID はすべて解決判定する。抽出エラーと解決エラーの両方を、同じ記録の失敗メッセージに並べる。対象には同じ AC 内の `tests` キーの重複と AC キーの重複も含み、読めた ID はその AC キーの名前で報告する。抽出エラーそのものになった要素（マッピング、入れ子、空の要素、深い行に続く複数行の値、閉じていない引用符、読み取りに失敗したフロー形式のリスト）は ID として扱わず、解決判定しない。
- **FR3:** 走査エラーを対象パス付きの検査失敗として報告する。`test-docs/` 配下の走査（os.walk）で一覧を取れなかったディレクトリは、通常の実行（`python3 -m unittest discover -s tests`）で集められるテストの失敗として報告する。失敗メッセージには、リポジトリ相対のパスと理由を含める。走査エラーがあってもモジュールの import は止めない。読めた記録は、これまでどおり記録ごとのテストで検査する。`test-docs/` 自体が存在しない場合は走査エラーにせず、これまでどおり「記録 0 件」としてゼロ件ガードで失敗させる。
- **FR4:** ローダーの戻り値を確認し、反復中の例外も ID ごとのエラーにする。ローダー確認（_loader_failure）では、loadTestsFromName の戻り値が unittest.TestSuite のインスタンスであることを確認する。そうでなければ、その ID の解決エラーとする。戻り値を再帰的にたどる途中で出た例外も、その ID の解決エラーとして返す。同じ記録の後続の ID は、これまでどおり判定を続ける。
- **FR5:** ダンダー名をメソッド ID として拒否する。構造判定で、最後のセグメントがダンダー名（`__` で始まり `__` で終わる名前。例: `__init__`）のメソッド ID を、理由が `not a test method` のエラーとして拒否する。テストケースクラス自身が定義している場合も同じに扱う。拒否はローダー確認より前に行う。
- **FR6:** 非実行の保証の記述を書き直す。`test/README.md` の非実行の保証を「テストメソッドの本体は実行しない。ローダー確認では、通常の収集と同じくテストクラスの生成（独自の `__init__` を含む）と load_tests フックが動く」の範囲に書き直す。同じ範囲になるよう、検査モジュールの docstring と resolver 節のコメントも直す。README の Syntax gate は「two or more dot-separated segments」に改める。Structural resolution にはダンダー名の拒否を、Loader confirmation には戻り値がスイートでない場合と反復中の例外を失敗条件として書き加える。モジュールの docstring、canonical_id_failure、extract_text、check_record、Extraction の各説明も、FR1〜FR5 の動作に合わせて更新する。
- **FR7:** 再発を検出するテスト。FR1〜FR5 の動作それぞれに、`tests/test_tests_yaml_id_resolution.py` のフィクスチャテストを用意する。FR6 で README に書いた記述（2 セグメント以上、非実行の保証の範囲）は、`tests/test_tests_yaml_id_rules_docs.py` の文言検査で固定する。
- **FR8:** 古い動作を固定している既存テストと記録の更新。古い動作を前提にした既存テストを、新しい動作に合わせて直す。対象は `tests` を通る ID として扱う箇所（TestSyntaxGate.test_canonical_ids_pass_the_gate、TestResolutionWithoutExecution.PASSING、TestSearchPathAndModuleCache.test_root_is_at_the_front_of_the_search_path_only_for_the_duration_of_the_call）と、抽出エラーのある AC を解決しないことを確かめる TestExtractionErrors.test_an_ac_with_an_extraction_error_gets_no_resolution_errors。後者は期待が逆になるので名前を変え、`test-docs/tests-yaml-test-id-resolution/task0001.tests.yaml` の AC-2 にある該当 ID も新しい名前に直す。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみ:** `tests/test_tests_yaml_id_resolution.py` と `tests/test_tests_yaml_id_rules_docs.py` は、引き続き標準ライブラリだけを import する。
- **NFR2 - 通常の実行に含める:** 追加するテストと走査エラーの報告は、`python3 -m unittest discover -s tests` で登録作業なしに実行される。
- **NFR3 - 既存の検査を保つ:** `tests/test_exit4_ac2_test_id_drift.py` は変更しない。実リポジトリの全記録の記録ごとのテストとゼロ件ガードは、変更後も通る。
- **NFR4 - バージョン:** em-workflow の version は変更しない。

## Implementation Approach

### Architecture

検査モジュール内の変更箇所:

| 箇所 | 対応する要件 |
|------|--------------|
| canonical_id_failure（Syntax gate） | FR1 |
| extract_text / check_record（Extraction） | FR2 |
| `test-docs/` の走査（os.walk）と走査エラー用の生成テストケースクラス | FR3 |
| _loader_failure（Loader confirmation） | FR4 |
| 構造判定（Structural resolution） | FR5 |
| モジュールの docstring、resolver 節のコメント | FR6 |

### 走査エラーの扱い（前提 A3）

- 走査エラーは別経路で集め、専用の生成テストケースクラスの 1 テストで、リポジトリ相対のパスと理由を並べて失敗させる。
- enumerate_records の戻り値の形は変えない。
- 記録ごとのテストクラスを生成したときの走査で出たエラーを、そのクラスに渡す。

### Dependencies

**Internal Dependencies:**
- `test/README.md`: FR6 で記述を書き直し、FR7 の文言検査で固定する。
- `test-docs/tests-yaml-test-id-resolution/task0001.tests.yaml`: FR8 の改名に合わせて AC-2 の ID を直す。

**External Dependencies:**
- 標準ライブラリのみ（NFR1）

### File Structure

```
tests/
├── test_tests_yaml_id_resolution.py   # 検査モジュール（FR1〜FR6, FR7, FR8）
└── test_tests_yaml_id_rules_docs.py   # 文書契約テスト（FR7）
test/
└── README.md                          # FR6
test-docs/
└── tests-yaml-test-id-resolution/
    └── task0001.tests.yaml            # FR8
```

変更しないファイル:
- `tests/test_exit4_ac2_test_id_drift.py`（NFR3）
- `feature-docs/tests-yaml-test-id-resolution/SPEC.md`、`reviews/round1.yaml`（前提 A5）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/tests-yaml-id-resolution-gaps/**`
- `test-docs/tests-yaml-id-resolution-gaps/**`

`feature-docs/tests-yaml-id-resolution-gaps/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/tests-yaml-id-resolution-gaps/**` covers `test-docs/tests-yaml-id-resolution-gaps/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1（AC-1 / FR1, FR7）: 単独の `tests` を canonical_id_failure と check_record にかける - `not a canonical ID` で拒否され、モジュールキャッシュとモジュール検索パスが変わらない。
- [ ] TS-2（AC-2 / FR2, FR7）: マッピング要素と存在しない ID を混ぜた AC、`tests` キーが重複した AC、AC キーが重複した記録、複数行の値の断片を含む AC を check_record にかける - 読めた ID の解決エラーと抽出エラーが両方並び、断片は判定されない。
- [ ] TS-3（AC-3 / FR3, FR7）: os.scandir を模擬して配下ディレクトリで PermissionError を起こす - 走査エラーのテストがパスと理由を示して失敗し、読めた記録のテストは残る。`test-docs/` が無い根では走査エラーにならない。
- [ ] TS-4（AC-4 / FR4, FR7）: load_tests が None を返すフィクスチャモジュールと、反復中に例外を出すスイートを返す模擬ローダーを使い、resolve_id と check_record にかける - ID ごとの解決エラーになり、後続 ID の判定も続く。
- [ ] TS-5（AC-5 / FR5, FR7）: 独自の `__init__` でマーカーを作る TestCase 派生クラスを持つフィクスチャで、`...Cls.__init__` を resolve_id にかける - `not a test method` で拒否され、マーカーが作られない。

### Integration Tests
- [ ] TS-6（AC-6 / FR6, FR7）: `tests/test_tests_yaml_id_rules_docs.py` の文言検査で、README の 2 セグメント以上の記述と非実行の保証の範囲を確かめる - 記述を消すと、その検査が失敗する。
- [ ] TS-7（AC-7 / FR8, NFR1, NFR2, NFR3）: `python3 -m unittest discover -s tests` を実行する - 全スイートと実リポジトリの記録ごとのテストが通る。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] `test-docs/` 自体が無い場合、os.walk は onerror に FileNotFoundError を渡す。これは走査エラーにせず、ゼロ件ガードで扱う。
- [ ] ブロック形式の項目が深い行に続く場合（複数行のプレーンスカラー）、1 行目だけが ids に追加される現在の実装経路があるが、この断片は解決判定しない。
- [ ] 読み取りに失敗したフロー形式のリストからは、ID を 1 件も取り出さない。
- [ ] load_tests がテストケースのリストを返す場合は、TestSuite ではないので解決エラーになる。
- [ ] ダンダー名の拒否はメソッド ID の最後のセグメントに限る。モジュールやクラスのセグメントの扱いは変えない。

### Performance Tests
対象外

## Security Considerations

対象外

## Error Handling

### Error Codes

| 条件 | 理由（失敗メッセージ） | 要件 |
|------|------------------------|------|
| ドット区切りのセグメント数が 2 未満の ID | `not a canonical ID` で始まる | FR1 |
| メソッド ID の最後のセグメントがダンダー名 | `not a test method` | FR5 |
| loadTestsFromName の戻り値が unittest.TestSuite のインスタンスでない | その ID の解決エラー | FR4 |
| 戻り値を再帰的にたどる途中で例外が出た | その ID の解決エラー | FR4 |
| `test-docs/` 配下のディレクトリの一覧を取れない | リポジトリ相対のパスと理由 | FR3 |

### Error Flow

```
抽出エラー・解決エラー → 同じ記録の失敗メッセージに並べる（FR2）
ID ごとの解決エラー → 同じ記録の後続 ID の判定を続ける（FR4）
走査エラー → import を止めず、走査エラー用のテストで失敗させる（FR3）
```

## Performance Optimization

対象外

## Success Criteria

- [ ] AC-1: `acceptance_tests: {AC-1: {tests: [tests]}}` の記録を check_record に渡すと、`tests` を `not a canonical ID` とするエラー行が返り、import は起きない。2 セグメント以上の正しい ID はこれまでどおり通る。
- [ ] AC-2: `tests: [tests.nope.A.b, {name: x}]`（ブロック形式でマッピング要素を含む）の記録を check_record に渡すと、マッピング要素の抽出エラーと `tests.nope.A.b` の解決エラーが両方返る。複数行の値の断片など、抽出エラーになった要素は解決判定されない。
- [ ] AC-3: os.scandir を模擬して配下ディレクトリで PermissionError を起こすと、通常の実行で集められるテストが、そのディレクトリのパスと理由を示して失敗する。読めた記録はそれぞれ検査され、`test-docs/` が存在しない根では、これまでどおりゼロ件ガードだけが失敗する。
- [ ] AC-4: load_tests フックがスイート以外（例: None）を返すモジュール ID と、反復中に例外を出すスイートを返すモジュール ID は、どちらもその ID の解決エラーになる。同じ記録の後続 ID の判定結果も、失敗メッセージに並ぶ。
- [ ] AC-5: テストケースクラスが自分で定義した `__init__` を指すメソッド ID は `not a test method` で拒否され、ローダー確認に進まない。
- [ ] AC-6: `test/README.md` の Syntax gate が 2 セグメント以上を求めている。非実行の保証は「テストメソッドの本体は実行しない。ローダー確認では通常の収集と同じくクラス生成と load_tests フックが動く」範囲で書かれている。検査モジュールの docstring も同じ範囲になっている。この記述が文書契約テストで固定されている。
- [ ] AC-7: `python3 -m unittest discover -s tests` が通る。古い動作を固定していた既存テストは新しい動作に合わせて直してある。task0001.tests.yaml の ID は改名後のテストを指し、記録検査を通る。

## Assumptions

- A1: FR4 の「スイート」は unittest.TestSuite のインスタンスを指す。
- A2: FR2 では、`tests` キーの重複と AC キーの重複も「抽出エラーのある AC」に含め、読めた ID を解決判定する。
- A3: 走査エラーは別経路で集め、専用の生成テストケースクラスの 1 テストで、リポジトリ相対のパスと理由を並べて失敗させる。enumerate_records の戻り値の形は変えない。記録ごとのテストクラスを生成したときの走査で出たエラーをそのクラスに渡す。
- A4: README の Test Docs Records 節には、走査エラーの記載を加えない。
- A5: 完了済みの `feature-docs/tests-yaml-test-id-resolution/SPEC.md`（FR6 の「解決したオブジェクトを呼び出さない」）と `reviews/round1.yaml` は書き換えない。
- A6: 実リポジトリの記録には、単独の `tests` やダンダー名のメソッドを指す ID は無い前提にする。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/tests-yaml-id-resolution-gaps/REQUIREMENTS.md`
