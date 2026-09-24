# Feature: classification-table-escaped-pipe

要件定義書: `feature-docs/classification-table-escaped-pipe/REQUIREMENTS.md`

## Overview

`tests/test_hook_classification_pin.py` の `parse_classification_table()` は `\|` エスケープを解釈しない。`\|` を含み 2 列にならない行に対して送出する `ClassificationTableError` のメッセージに、`\|` エスケープ非対応の旨を加え、その挙動をテストで固定する。行の分割方式は変えない。

## Objectives

- `parse_classification_table()` に `\|` を含む行を渡したとき、その行が黙って落ちず、パーサの限界（`\|` エスケープ非対応）が原因だとエラーメッセージから即座に分かる状態にする。
- `\|` を含むセルを持つ表に対するパーサの挙動（`ClassificationTableError` の送出）をテストで固定する。

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1:** `\|` を含む列数不一致行のエラーメッセージに非対応の旨を含める。`parse_classification_table()` が区切り行以外で 2 列にならない行に出会ったとき、既存どおり `ClassificationTableError` を送出する。その行（生の `row_line`）に部分文字列 `\|` が含まれる場合、エラーメッセージに、既存の内容（2 列を期待する旨と該当行の repr）に加えて、`\|` エスケープはこのパーサでは非対応である旨を含める。メッセージにはリテラル `\|` と語句 "not supported" を含める。行に `\|` が含まれない場合のメッセージは既存の内容から変えない。
- **FR2:** 行の分割方式は変えない。`\|` エスケープの解釈は実装しない。行の分割処理（`row_line.strip("|").split("|")`）、列数判定、分類語彙の検証は既存のまま変更しない。
- **FR3:** `\|` を含む行の挙動を固定するテスト。`tests/test_hook_classification_pin.py` の `TestParseClassificationTableFailureModes` に、次の 2 ケースで `ClassificationTableError` が送出され、そのメッセージが FR1 の非対応の旨（リテラル `\|` と "not supported"）を含むことを検証するテストを追加する。
    1. hook セルに `\|` を含み、分類セルは正規値（READS_STATUS）の行。
    2. hook セルは正規のパス、分類セルは再現手順の値 ``reads `tasks.{T}.status` \| `journal` `` の行。
- **FR4:** docstring に `\|` 非対応を明記する。`parse_classification_table()` の docstring の Raises 記述（malformed row）に、`\|` エスケープは解釈せず、`\|` を含む行は列数不一致として非対応の旨のメッセージ付きで `ClassificationTableError` になることを記す。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみ:** テストコードは Python 標準ライブラリ（unittest）のみを使う。既存モジュールの AC-7（標準ライブラリのみ、`em-workflow/hooks/` 配下へ書き込まない）を維持する。
- **NFR2 - 変更範囲:** 変更対象は `tests/test_hook_classification_pin.py` のみ。`em-workflow/references/implement-phase.md` の分類テーブル、`tests/_gate_vocabulary.py`、`tests/test_recycled_task_id_consistency.py` は変更しない。
- **NFR3 - 既存テストの維持:** `python3 -m unittest discover -s tests` で新たな失敗を出さない。既存の `test_malformed_row_wrong_column_count_raises` を含む既存テストは変更・削除しない。

## Implementation Approach

### Architecture

**System Architecture:**
該当なし

**Component Diagram:**
```
tests/test_hook_classification_pin.py
├── parse_classification_table()                  # FR1: 列数不一致時のメッセージ分岐 / FR4: docstring
└── TestParseClassificationTableFailureModes      # FR3: `\|` を含む行のテスト 2 件を追加
```

### Data Flow

```
row_line（区切り行以外）
  → row_line.strip("|").split("|")（FR2: 変更なし）
  → 2 列でない
      → 生の row_line に部分文字列 `\|` を含む → 既存メッセージ + 非対応の旨で ClassificationTableError
      → 含まない                           → 既存メッセージのまま ClassificationTableError
```

- 非対応の旨の判定は、生の `row_line` に部分文字列 `\|` が含まれるかどうかで行う。`\\|` のようなバックスラッシュ自体のエスケープの解析はしない。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `parse_classification_table()`（`tests/test_hook_classification_pin.py`）: FR1 / FR4 の変更対象。

**External Dependencies:**
- Python 標準ライブラリ unittest: テストの実行（NFR1）。

### File Structure

```
tests/
└── test_hook_classification_pin.py   # 変更対象（NFR2）
```

- 変更は `em-workflow/` 配下ではなくリポジトリルートの `tests/` のみなので、`.claude/rules/core-plugin-version-bump.md` の対象外で、プラグインの version は上げない。

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリをデフォルトで宣言する。

- `feature-docs/classification-table-escaped-pipe/**`
- `test-docs/classification-table-escaped-pipe/**`

`feature-docs/classification-table-escaped-pipe/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/classification-table-escaped-pipe/**` に含まれるもの: タスクごとのテスト記録 `test-docs/classification-table-escaped-pipe/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

この 2 つのデフォルトエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的で明示的な絞り込みである。

この宣言はスーパーセット（superset）の主張であり、検証時に観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要があり、一致する必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/classification-table-escaped-pipe/` ディレクトリを生成しないが、宣言された `test-docs/classification-table-escaped-pipe/**` は依然として正しい。宣言されたパスが実際に生成されなくても違反にはならない。

## Test Scenarios

### Unit Tests
- [ ] TS1（AC2, AC4）: hook セルが `` `em-workflow/hooks/queue\|stop_guard.py` `` のように `\|` を含み、分類セルが READS_STATUS の 1 行表を渡す - `ClassificationTableError` が送出され、メッセージにリテラル `\|` と "not supported" が含まれる。
- [ ] TS2（AC1, AC2, AC4）: hook セルが `` `em-workflow/hooks/queue_stop_guard.py` ``、分類セルが ``reads `tasks.{T}.status` \| `journal` `` の 1 行表を渡す - `ClassificationTableError` が送出され、メッセージにリテラル `\|` と "not supported" が含まれる。
- [ ] TS3（AC3）: `| only-one-column |` の 1 列行を渡す - `ClassificationTableError` が送出され、メッセージに "not supported" が含まれない。

### Integration Tests
- [ ] TS4（AC5）: `python3 -m unittest discover -s tests` を実行する - 実ドキュメントの表が 4 行にパースされる既存テストを含め、新たな失敗が無い。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 1 セル内に `\|` が 1 つだけあり、分割結果がちょうど 2 列になる行: FR1 の非対応の旨は付かない。既存の分類語彙の検証（unrecognized classification value）か、分類が正規値に一致した場合は reads_per_task_status のパス解決検証で `ClassificationTableError` になり、黙って落ちることはない。この経路のメッセージ変更は今回の範囲外とする。
- [ ] `\\|` のようなバックスラッシュ自体のエスケープ: 解析しない。生の `row_line` に部分文字列 `\|` が含まれるかどうかだけで判定する。
- [ ] 行末の `\|`: 外枠パイプとして扱うかの要件は設けない。

### Performance Tests
該当なし

## Security Considerations

該当なし

## Error Handling

### Error Codes

該当なし

`ClassificationTableError` のメッセージ:

- `\|` を含み 2 列にならない行: 2 列を期待する旨、該当行の repr、リテラル `\|`、語句 "not supported" を含む。
- `\|` を含まず 2 列にならない行: 既存の内容のままで、語句 "not supported" を含まない。
- メッセージは既存メッセージと同じく英語で書く。テストが固定するのはリテラル `\|` と語句 "not supported" の有無で、それ以外の文言は実装に委ねる。

### Error Flow

```
2 列にならない行 → 生の row_line に `\|` を含むか判定 → ClassificationTableError（含む場合は非対応の旨を追加）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1（FR1, FR2, FR3）: 再現手順の値（``reads `tasks.{T}.status` \| `journal` ``）を分類セルに持つ行を含む表を `parse_classification_table()` に渡すと、行が黙って捨てられず `ClassificationTableError` が送出される。
- [ ] AC2（FR1）: `\|` を含み 2 列にならない行に対する `ClassificationTableError` のメッセージは、2 列を期待する旨、該当行の repr、リテラル `\|`、語句 "not supported" を含む。
- [ ] AC3（FR1）: `\|` を含まず 2 列にならない行（例: `| only-one-column |`）に対する `ClassificationTableError` のメッセージは既存の内容のままで、語句 "not supported" を含まない。
- [ ] AC4（FR3）: FR3 の (1)(2) の 2 ケースを検証するテストが `tests/test_hook_classification_pin.py` に存在し、通る。
- [ ] AC5（FR2, FR4, NFR1, NFR2, NFR3）: 実ドキュメントの分類テーブルは従来どおり 4 行にパースされ、`python3 -m unittest discover -s tests` が新たな失敗なく通る。行の分割処理は変わっておらず、`parse_classification_table()` の docstring に `\|` 非対応が記されている。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/classification-table-escaped-pipe/REQUIREMENTS.md`
