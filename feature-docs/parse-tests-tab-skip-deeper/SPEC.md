# Feature: parse-tests-tab-skip-deeper

## Overview

記録検査 `tests/test_tests_yaml_id_resolution.py` の `_RecordParser.parse_tests` で、tests ブロックの先頭のタブ行の直後にタブの無い深い続き行が来たときの扱いを直す。続き行だけを読み飛ばし、後ろの読める ID を解決対象に残して、抽出エラーと解決エラーを 1 回の失敗メッセージに並べる。

## Objectives

- 記録検査 `tests/test_tests_yaml_id_resolution.py` の `_RecordParser.parse_tests` で、tests ブロックの先頭のタブ行の直後にタブの無い深い続き行があっても、続き行だけを読み飛ばし、後ろの読める ID を解決対象に残す。
- 抽出エラーと解決エラーを 1 回の失敗メッセージに並べる（先頭のタブ行に深い続き行がある記録でも）。

## Technical Requirements

### Functional Requirements

- **FR1:** 先頭のタブ行の続き行だけを読み飛ばす — `parse_tests` の最初の項目より前の走査で、タブ行（空行とコメントは間に挟まってよい）の直後に来た、タブの無い、ダッシュで始まらない行が、直前のタブ行より深い（先頭のスペースの数が多い）とき、その行について `tests item continues or nests on a deeper line (multi-line or nested value)` を 1 件報告する。その後、直前のタブ行より深い後続行を読み飛ばし、最初の項目より前の走査に戻る。項目の深さは、従来どおり最初のタブの無いダッシュ行で決まる。
- **FR2:** その他の場合の挙動は変えない — タブ行が先行しない場合、およびタブ行の後の深い非ダッシュ行が直前のタブ行より深くない場合は、変更前と同じく `tests value is not a block sequence of scalars` を報告し、`skip_deeper(f + 1, key_indent, limit)` で `tests` キーより深い後続行を読み飛ばす。
- **FR3:** docstring とコメント — `parse_tests` の docstring と最初の項目より前の走査のコメントのうち、先頭のタブ行の扱いに関する記述を FR1 と FR2 の挙動に合わせる。
- **FR4:** 再発を検出するテスト — チケットの再現手順の記録について、AC-1 の ID と抽出エラー、および記録検査の失敗メッセージを検証するテストを `tests/test_tests_yaml_id_resolution.py` の `TestTabLinesInTestsBlock` に追加する。FR2 の、タブ行が先行しない深い非ダッシュ行の挙動を検証するテストも追加する。

### Non-Functional Requirements

- **NFR1:** 既存のテスト（`TestTabLinesInTestsBlock` の既存ケースを含む）は変更せずに通る。
- **NFR2:** テストは Python 標準ライブラリの `unittest` だけを使う。サードパーティのパッケージは使わない。
- **NFR3:** テストコードではタブ文字を文字列リテラル中のエスケープシーケンスで書き、生のタブ文字は書かない（既存の `_tab_record` に合わせる）。

## Acceptance Criteria

記録の各行の `\t` はタブ文字を表す。

### AC-1（FR1, FR4）

次の記録を `extract_text` に渡すと、AC-1 の ID が `['tests.nope.after']` になり、エラーは 4 行目の `tab in indentation` と 5 行目の `tests item continues or nests on a deeper line (multi-line or nested value)` の 2 件だけになる。

```
acceptance_tests:
  AC-1:
    tests:
      \t- tests.nope.bad
        continued
      - tests.nope.after
```

### AC-2（FR1, FR4）

AC-1 の記録を記録検査にかけると、失敗メッセージに 4 行目の `tab in indentation`、5 行目の `continues or nests`、`tests.nope.after` の解決エラーがそれぞれ 1 件ずつ並び、`tests.nope.bad` は現れない。

### AC-3（FR2, FR4）

タブ行が先行せず、`tests:` の直後にダッシュで始まらない深い行が来る記録では、変更前と同じく `tests value is not a block sequence of scalars` が報告され、`tests` キーより深い後続行は ID にならない。

### AC-4（NFR1）

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

- `feature-docs/parse-tests-tab-skip-deeper/**`
- `test-docs/parse-tests-tab-skip-deeper/**`

`feature-docs/parse-tests-tab-skip-deeper/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、設計の工程が生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有し、この節はそれらの規則を言い直さない。

`test-docs/parse-tests-tab-skip-deeper/**` はタスクごとのテスト記録 `test-docs/parse-tests-tab-skip-deeper/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有し、この節はその規則を言い直さない。

この 2 つの既定の宣言は、SPEC の作成者が明示的に外さない限り宣言に含まれる。書かれていないことを理由に外れたとはみなさない。外すのは意図した明示的な絞り込みに限る。

この宣言は上位集合としての宣言で、検証時に観測した実際の変更集合は宣言した集合に含まれていればよく、一致する必要はない。implement のタスクを生まない feature では `test-docs/parse-tests-tab-skip-deeper/` は作られないが、その場合も宣言した `test-docs/parse-tests-tab-skip-deeper/**` は正しい。宣言したパスが実際に作られなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS-1（AC-1）: `TestTabLinesInTestsBlock` に再現手順の記録を追加し、`extract_text` の AC-1 の ID と、エラーの一覧（タブ 1 件と continues or nests 1 件）を検証する。
- [ ] TS-2（AC-2）: 再現手順の記録を `check_record` にかけ、タブ、continues or nests、`tests.nope.after` の解決エラーが 1 件ずつ並び、`tests.nope.bad` が無いことを検証する。
- [ ] TS-3（AC-3）: タブ行が先行しない深い非ダッシュ行の記録で、`tests value is not a block sequence of scalars` が報告され、後続の深い行が ID にならないことを検証する。
- [ ] TS-4（AC-4）: 既存の `TestTabLinesInTestsBlock` と `test_tests_yaml_id_resolution` の残りのテストを変更せずに実行する。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 続き行が複数行あるとき: 最初の続き行だけを 1 件報告し、直前のタブ行より深い行をすべて読み飛ばす（項目の後の深い行の扱いと同じ）。
- [ ] 続き行の範囲にある、直前のタブ行より深いタブ行は、続き行として読み飛ばされ、個別には報告されない（項目の後の `skip_deeper(f + 1, item_indent, limit)` と同じ）。
- [ ] 続き行の後に項目が無く別のフィールドかブロックの終わりが来るとき: エラーはタブと continues or nests だけで、`tests key has neither a value nor items` は報告されない（`tab_seen` による既存の扱い）。
- [ ] 続き行の後にまたタブ行が来るとき: 最初の項目より前の走査に戻るので、そのタブ行は `tab in indentation` として報告される。

## Assumptions

- **A1:** 「続き行」は、直前のタブ行の深さ（タブの前の先頭のスペースの数）より深い行とする。項目の後のタブ行の深さの比較（`indent > item_indent`）と同じ深さの数え方を使う。
- **A2:** 続き行のエラー文言は既存の `tests item continues or nests on a deeper line (multi-line or nested value)` を使う。feature `parse-tests-tab-held-id` の FR4（項目と同じ深さのタブ行の後のタブの無い深い行）と同じエラーの形になる。
- **A3:** タブの表記そのものは引き続き未対応の表記で、タブ行に書かれた要素は ID にならない。
- **A4:** 直前のタブ行より深くない深い非ダッシュ行（例: タブ行より浅いが `tests` キーより深い行）の扱いは、この feature の範囲外とし、変更しない。
- **A5:** 変更対象は `tests/test_tests_yaml_id_resolution.py` だけで、プラグイン配下のファイルと `test/README.md` は変更しない。

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
- チケット: [https://www.notion.so/3f53509ec8ee81299204f23bb8238a0f](https://www.notion.so/3f53509ec8ee81299204f23bb8238a0f)
