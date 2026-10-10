# Feature: parse-tests-tab-held-id

## Overview

記録検査 `tests/test_tests_yaml_id_resolution.py` の `_RecordParser.parse_tests` で、項目と同じ深さまたは浅いタブ行の後に深い行が来たときの ID の扱いを直す。タブ行より前の読める ID を解決対象に残し、抽出エラーと解決エラーを 1 回の失敗メッセージに並べる。

## Objectives

- 記録検査 `tests/test_tests_yaml_id_resolution.py` の `_RecordParser.parse_tests` で、同じ深さまたは浅いタブ行の後に深い行が来ても、タブ行より前の読める ID を解決対象に残す。
- 抽出エラーと解決エラーを 1 回の失敗メッセージに並べる（タブ行を含む記録でも）。

## Technical Requirements

### Functional Requirements

- **FR1:** タブ行の後は ID を保持しない — `parse_tests` の item ループで、タブ行（先頭のスペースの後の最初の文字がタブの行）について `tab in indentation` を報告した後は、行の深さに関係なく、保持中の ID が無い状態（`last_is_id = False`）にする。
- **FR2:** 取り消しは項目より深いタブ行に限る — タブ行で直前の ID を `ids` から取り除くのは、タブ行が項目より深く（`indent > item_indent`）、かつ直前の要素が保持中の ID であるときだけにする。
- **FR3:** 同じ深さのタブ行の後に深いタブ行 — 項目と同じ深さのタブ行の直後に、項目より深いタブ行が来たとき、タブ行より前の ID を残す。エラーは 2 つのタブ行それぞれの `tab in indentation` だけになる。
- **FR4:** 同じ深さのタブ行の後にタブの無い深い行 — 項目と同じ深さのタブ行の直後に、タブの無い項目より深い行が来たとき、タブ行より前の ID を残す。エラーは `tab in indentation` 1 件と `tests item continues or nests on a deeper line (multi-line or nested value)` 1 件になる。
- **FR5:** コメントと docstring — タブ分岐のコメントのうち「the held state stays」とある記述と、`parse_tests` の docstring のタブ行に関する記述を、FR1 と FR2 の挙動に合わせる。
- **FR6:** 再発を検出するテスト — チケットの再現手順 1 と 2 のそれぞれについて、AC-1 の ID とエラーを検証するテストを `tests/test_tests_yaml_id_resolution.py` に追加する。

### Non-Functional Requirements

- **NFR1:** 既存のテスト（`TestTabLinesInTestsBlock` の AC-1〜AC-4、AC-6 のケースを含む）は変更せずに通る。
- **NFR2:** テストは Python 標準ライブラリの `unittest` だけを使う。サードパーティのパッケージは使わない。
- **NFR3:** テストコードではタブ文字を文字列リテラル中のエスケープシーケンスで書き、生のタブ文字は書かない（既存の `_tab_record` に合わせる）。

## Acceptance Criteria

記録の各行の `\t` はタブ文字を表す。

### AC-1（FR1, FR2, FR3, FR6）

次の記録を `extract_text` に渡すと、AC-1 の ID が `['tests.nope.kept', 'tests.nope.after']` になり、エラーは 5 行目と 6 行目の `tab in indentation` の 2 件だけになる。

```
acceptance_tests:
  AC-1:
    tests:
      - tests.nope.kept
      \t- tests.nope.bad
        \tcontinued
      - tests.nope.after
```

### AC-2（FR1, FR2, FR4, FR6）

AC-1 の 6 行目をタブの無い `        continued` にした記録を `extract_text` に渡すと、AC-1 の ID が `['tests.nope.kept', 'tests.nope.after']` になり、エラーは 5 行目の `tab in indentation` 1 件と 6 行目の `continues or nests` 1 件になる。

### AC-3（FR2, NFR1）

項目より深いタブ行で直前の ID を取り消す既存の挙動（DEEPER_TAB、連続した深いタブ行、ID でない要素の後の深いタブ行、深いタブ行の後のタブの無い行）と、同じ深さや浅いタブ行が前後の ID を残す既存の挙動は変わらず、既存テストが通る。

### AC-4（NFR1）

`python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### File Structure

```
tests/
└── test_tests_yaml_id_resolution.py   # _RecordParser.parse_tests の修正と、テストの追加
```

変更対象は `tests/test_tests_yaml_id_resolution.py` だけで、プラグイン配下のファイルは変更しない。`test/README.md` は変更しない。

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を述べる。上の feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

feature 固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/parse-tests-tab-held-id/**`
- `test-docs/parse-tests-tab-held-id/**`

`feature-docs/parse-tests-tab-held-id/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、設計の工程が生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有し、この節はそれらの規則を言い直さない。

`test-docs/parse-tests-tab-held-id/**` はタスクごとのテスト記録 `test-docs/parse-tests-tab-held-id/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有し、この節はその規則を言い直さない。

この 2 つの既定の宣言は、SPEC の作成者が明示的に外さない限り宣言に含まれる。書かれていないことを理由に外れたとはみなさない。外すのは意図した明示的な絞り込みに限る。

この宣言は上位集合としての宣言で、検証時に観測した実際の変更集合は宣言した集合に含まれていればよく、一致する必要はない。implement のタスクを生まない feature では `test-docs/parse-tests-tab-held-id/` は作られないが、その場合も宣言した `test-docs/parse-tests-tab-held-id/**` は正しい。宣言したパスが実際に作られなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS-1（AC-1）: `TestTabLinesInTestsBlock` に再現手順 1 の記録を追加し、`extract_text` の AC-1 の ID とエラーの一覧（タブ 2 件だけ）を検証する。
- [ ] TS-2（AC-2）: 再現手順 2 の記録で、`extract_text` の AC-1 の ID と、エラーがタブ 1 件（5 行目）と continues or nests 1 件（6 行目）であることを検証する。
- [ ] TS-3（AC-3, AC-4）: 既存の `TestTabLinesInTestsBlock` と、`test_tests_yaml_id_resolution` の残りのテストを変更せずに実行する。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Assumptions

- **A1:** チケットの「関連」にある、先頭のタブ行の直後にタブの無い深い続き行があると `skip_deeper(f + 1, key_indent)` が後ろの読める ID まで読み飛ばす欠陥（変更前からある、レビューで low に下がったもの）は、この feature の範囲外とする。チケットの期待する挙動と完了の定義に含まれていない。
- **A2:** タブの表記そのものは引き続き未対応の表記で、タブ行に書かれた要素は ID にならない。
- **A3:** 変更対象はテストコード（`tests/test_tests_yaml_id_resolution.py`）だけで、プラグイン配下のファイルは変更しない。`test/README.md` の記録の書き方の説明はこの粒度の挙動を扱っていないため変更しない。

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
