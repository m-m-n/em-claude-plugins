# Feature: parse-tests-tab-skip-key-bound

## Overview

記録検査 `tests/test_tests_yaml_id_resolution.py` の `_RecordParser.parse_tests` で、最初の項目より前の走査が、`tests` キーより浅いタブ行の続き行を読み飛ばすときの範囲を直す。`tests` キーと同じ深さの行は読み飛ばさずに残し、その後ろの 2 つ目の `tests` キーやダッシュの項目を引き続き読み、報告する。

## Objectives

- 記録検査 `tests/test_tests_yaml_id_resolution.py` の `_RecordParser.parse_tests` で、最初の項目より前の走査は、`tests` キーより浅いタブ行の続き行を読み飛ばす。`tests` キーと同じ深さの行は残し、その後ろの 2 つ目の `tests` キーやダッシュの項目を引き続き読み、報告する。

## Technical Requirements

### Functional Requirements

- **FR1:** 続き行の読み飛ばしの範囲を `max(tab_indent, key_indent)` で区切る — `parse_tests` の最初の項目より前の走査（`tests/test_tests_yaml_id_resolution.py:644`）で、続き行を報告した後の読み飛ばしを `skip_deeper(f + 1, tab_indent, limit)` から `skip_deeper(f + 1, max(tab_indent, key_indent), limit)` に変える。読み飛ばすのは、直前のタブ行と `tests` キーの両方より深い行だけにする。`tests` キーと同じ深さかそれより浅い行は読み飛ばさず、その行から走査を再開する。行が続き行かどうかの判定（637〜642 行目: `tab_indent` が None でない、ダッシュでない、`scan_indent > key_indent`、`scan_indent > tab_indent`）は変えない。
- **FR2:** タブ行が `tests` キーと同じ深さかそれより深いときの挙動は変えない — `tab_indent >= key_indent` のとき、`max(tab_indent, key_indent)` は `tab_indent` に等しいので、挙動は変更前と同じになる。
- **FR3:** docstring とコメントの更新 — `parse_tests` の docstring（586〜589 行目付近）と、最初の項目より前の走査のコメント（617〜619 行目付近）にある「そのタブ行より深い行を読み飛ばす」という記述を、そのタブ行と `tests` キーの両方より深い行を読み飛ばす、という記述に変える。
- **FR4:** 再発を検出するテストの追加 — `tests/test_tests_yaml_id_resolution.py` の `TestTabLinesInTestsBlock` にテストケースを追加する。このケースは、`tests` キーより浅いタブ行、続き行、キーと同じ深さの 2 つ目の `tests` キーとダッシュの項目を組み合わせる。チケットの再現手順の記録のテストも追加する。

### Non-Functional Requirements

- **NFR1:** 既存のテスト（`TestTabLinesInTestsBlock` の既存ケースを含む）は変更せずに通る。
- **NFR2:** テストは Python 標準ライブラリの `unittest` だけを使う。
- **NFR3:** テストコードではタブ文字を文字列リテラル中のエスケープシーケンスで書き（既存の `_tab_record` と同じ）、生のタブ文字は書かない。
- **NFR4:** 変更するファイルは `tests/test_tests_yaml_id_resolution.py` だけで、プラグイン配下のファイルと `test/README.md` は変更しない。

## Acceptance Criteria

記録の各行の `\t` はタブ文字を表す。

### AC-1（FR1, FR4）

チケットの再現手順の次の記録を `extract_text` に渡すと、AC-1 の ID が `['tests.nope.second']` になる。エラーは、4 行目の `tab in indentation`、5 行目の `tests item continues or nests on a deeper line (multi-line or nested value)`、`duplicate tests key` の 3 件だけになる。

```
acceptance_tests:
  AC-1:
    tests:
   \t- tests.nope.bad
      continued
    tests: [tests.nope.second]
```

### AC-2（FR1, FR4）

次の記録を `extract_text` に渡すと、AC-1 の ID が `['tests.nope.after', 'tests.nope.second']` になる。エラーは、4 行目の `tab in indentation`、5 行目の `continues or nests`、`duplicate tests key` の 3 件だけになる。

```
acceptance_tests:
  AC-1:
    tests:
   \t- tests.nope.bad
      continued
    - tests.nope.after
    tests: [tests.nope.second]
```

### AC-3（FR2, NFR1）

`python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### File Structure

```
tests/
└── test_tests_yaml_id_resolution.py   # _RecordParser.parse_tests の修正と、テストの追加
```

変更対象は `tests/test_tests_yaml_id_resolution.py` だけで、プラグイン配下のファイルと `test/README.md` は変更しない。

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を述べる。上の feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

feature 固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/parse-tests-tab-skip-key-bound/**`
- `test-docs/parse-tests-tab-skip-key-bound/**`

`feature-docs/parse-tests-tab-skip-key-bound/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、設計の工程が生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有し、この節はそれらの規則を言い直さない。

`test-docs/parse-tests-tab-skip-key-bound/**` はタスクごとのテスト記録 `test-docs/parse-tests-tab-skip-key-bound/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有し、この節はその規則を言い直さない。

この 2 つの既定の宣言は、SPEC の作成者が明示的に外さない限り宣言に含まれる。書かれていないことを理由に外れたとはみなさない。外すのは意図した明示的な絞り込みに限る。

この宣言は上位集合としての宣言で、検証時に観測した実際の変更集合は宣言した集合に含まれていればよく、一致する必要はない。implement のタスクを生まない feature では `test-docs/parse-tests-tab-skip-key-bound/` は作られないが、その場合も宣言した `test-docs/parse-tests-tab-skip-key-bound/**` は正しい。宣言したパスが実際に作られなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS-1（AC-1）: `TestTabLinesInTestsBlock` で、チケットの再現手順の記録を `extract_text` に渡し、AC-1 の ID の一覧とエラーの一覧を完全に検証する。`assert_ids_and_errors` は `unsupported notation at line N` のエラーしか扱わないので、`duplicate tests key` のエラーは `test_the_field_loop_resumes_at_the_first_line_without_a_tab`（1819〜1826 行目）と同じやり方で別に検証する。
- [ ] TS-2（AC-2）: `TestTabLinesInTestsBlock` で、組み合わせた記録（浅いタブ行、続き行、キーと同じ深さのダッシュの項目、2 つ目の `tests` キー）を `extract_text` に渡し、AC-1 の ID の一覧とエラーの一覧を完全に検証する。
- [ ] TS-3（AC-3）: 既存の `TestTabLinesInTestsBlock` と `test_tests_yaml_id_resolution` の残りのテストを変更せずに実行する。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] タブ行が `tests` キーより深いとき（既存の 6 スペースの `TAB_ITEM` のケース）: 区切りは `tab_indent` のままなので、挙動と既存テストの期待値は変わらない。
- [ ] タブ行が `tests` キーと同じ深さのとき: max は `key_indent` = `tab_indent` なので、挙動は変わらない。
- [ ] タブ行が `tests` キーより浅く、その後にキーより深いが続き行ではない行（例: 5 スペースのダッシュ行）が来るとき: その行は両方より深いので、従来どおり読み飛ばされる。
- [ ] タブ行が `tests` キーより浅く、続き行が無いとき（`test_a_line_deeper_than_a_shallow_tab_line_but_not_than_the_tests_key_is_no_continuation`、2117 行目）: 読み飛ばしに到達しないので、変わらない。
- [ ] 再開した行がキーと同じ深さのダッシュの項目のとき: 項目の深さはその行で決まり（`item_indent = key_indent`）、項目のループは同じ深さの次のダッシュでない行（2 つ目の `tests` キー）で終わる。その後、フィールドのループがそのキーを読む。

## Assumptions

- **A1:** チケットのテストケース（浅いタブ行、続き行、キーと同じ深さの 2 つ目の `tests` キーとダッシュの項目）は、2 つの記録で扱う。チケットの再現手順の記録（AC-1）と、ダッシュの項目と 2 つ目の `tests` キーの両方を持つ組み合わせた記録（AC-2）。
- **A2:** テストは抽出結果（`extract_text`）を検証する。記録検査（`check_record`）の失敗メッセージのテストは追加しない。
- **A3:** 続き行のエラー文言は既存の `tests item continues or nests on a deeper line (multi-line or nested value)` のままとする。
- **A4:** プラグインの version は変更しない。

## Success Criteria

- [ ] すべての機能要件が実装され、テストされている
- [ ] すべてのテストシナリオが通る
- [ ] `python3 -m unittest discover -s tests` が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## References

- 対象のテストコード: `tests/test_tests_yaml_id_resolution.py`
