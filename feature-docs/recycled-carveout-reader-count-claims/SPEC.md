# Feature: recycled-carveout-reader-count-claims

## Overview

`feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行（36 行目）と Manual Testing 項目（89 行目）を書き換え、対象を SPEC AC-6 の範囲である `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` に絞る。`tests/test_recycled_task_id_consistency.py` の docstring は確認だけ行い、変更しない。要件の詳細は `feature-docs/recycled-carveout-reader-count-claims/REQUIREMENTS.md` を参照。

## Objectives

- `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 の主張を、出典である SPEC AC-6 の範囲に合わせる。対象は `ORCHESTRATOR_ONLY_SCOPE_PHRASE` の改訂で読み取り箇所を失った定数（`HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES`）だけとする。
- recycled-task-id-carveout の検証記録と `tests/test_recycled_task_id_consistency.py` のモジュール docstring に、モジュールから数えた実数と食い違う読み取り箇所数の主張を残さない。

## User Stories

該当なし。

## Technical Requirements

### Functional Requirements

- **FR1:** TS-13 行を AC-6 の対象定数に絞る — `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行（36 行目）を書き換え、Scenario と Expected Result の対象を `tests/test_recycled_task_id_consistency.py` の `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけにする。判定基準は「各定数は、すべての参照とともに削除されている（定義なし・読み取り箇所 0）か、読み取り箇所が 2 以上ある」。読み取り箇所は定義行以外のコード上の参照とし、コメントと docstring は数えない。全称の文言 `No module-level constant ... is left with fewer than two reader sites` と `every constant has 0 (retired with its readers) or >= 2` を削除する。ID `TS-13`、出典表記 `(SPEC AC-6)`、Test Type `Inspection` は変えない。
- **FR2:** TS-13 の手動確認項目を同じく絞る — 同じ `VERIFICATION.md` の Manual Testing 項目（89 行目、`Count the reader sites of every module-level constant in that module and confirm none is left with exactly one (TS-13).`）を書き換え、`HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけを FR1 の判定基準と読み取り箇所の定義で確認する内容にする。TS-13 の引用は残す。
- **FR3:** モジュール docstring に誤った読み取り箇所数の主張が無いことを確認する — `tests/test_recycled_task_id_consistency.py` の docstring に、実数と食い違う読み取り箇所数の主張を含めない。base_revision 時点で docstring に読み取り箇所数の主張は無い。`leaving no module-level constant in this module with fewer than two reader sites` という文は存在せず、モジュール内を `reader` で大文字小文字を区別せず検索しても何も見つからない。よってこの要件は編集ではなく確認で満たす。テストモジュールは変更しない。
- **FR4:** 変更を VERIFICATION.md の 2 箇所に限る — 変更するのは `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行と 89 行目の手動確認項目、およびこのフィーチャー自身のワークフロー生成文書だけとする。`VERIFICATION.md` の他の行は、TS-12、TS-14、Verification Summary、105 行目を含めバイト単位で変えない。

### Non-Functional Requirements

- **NFR1 - プラグインの version を上げない:** `em-workflow/` 配下のファイルは変更しない。よって `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は現在の値のままとする。
- **NFR2 - 過去の記録を変更しない:** 次のファイルは変更しない: `feature-docs/recycled-task-id-carveout/workflow.yaml`（verify のメモを含む）、`feature-docs/recycled-task-id-carveout/SPEC.md`、`feature-docs/recycled-task-id-carveout/tasks/task0004.md`、`test-docs/recycled-task-id-carveout/task0001.tests.yaml`、`test-docs/recycled-task-id-carveout/task0004.tests.yaml`、`tests/test_recycled_task_id_consistency.py`。
- **NFR3 - テストスイートが通る:** リポジトリルートで `python3 -m unittest discover -s tests` が終了コード 0 で終わる。

## Implementation Approach

### Architecture

該当なし。検証文書のテキスト編集のみ。

変更箇所:

| ファイル | 箇所 | 要件 |
|----------|------|------|
| `feature-docs/recycled-task-id-carveout/VERIFICATION.md` | 36 行目（TS-13 行） | FR1 |
| `feature-docs/recycled-task-id-carveout/VERIFICATION.md` | 89 行目（Manual Testing 項目） | FR2 |

確認のみ（変更しない）:

| ファイル | 確認内容 | 要件 |
|----------|----------|------|
| `tests/test_recycled_task_id_consistency.py` | docstring に読み取り箇所数の主張が無いこと | FR3 |

### Data Flow

該当なし。

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `feature-docs/recycled-task-id-carveout/SPEC.md` AC-6: TS-13 の出典。書き換え後の TS-13 の範囲はこれに合わせる。
- `tests/test_recycled_task_id_consistency.py`: 読み取り箇所の測定対象。

**External Dependencies:**
- なし

### File Structure

```
feature-docs/
└── recycled-task-id-carveout/
    └── VERIFICATION.md      # 36 行目と 89 行目だけを変更
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、既定で、フィーチャー固有のパスに加えて次の 2 つのワークフロー生成エントリを宣言する。

- `feature-docs/recycled-carveout-reader-count-claims/**`
- `test-docs/recycled-carveout-reader-count-claims/**`

`feature-docs/recycled-carveout-reader-count-claims/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` であり、この節はそれを引用するだけで、ルールは再掲しない。

`test-docs/recycled-carveout-reader-count-claims/**` に含まれるもの: タスクごとのテスト記録 `test-docs/recycled-carveout-reader-count-claims/{T}.tests.yaml`。生成主体は `implement-phase.md` であり、この節はそれを引用するだけで、ルールは再掲しない。

この 2 つの既定エントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的で明示的な絞り込みである。

この宣言はスーパーセット（SUPERSET）の主張である。verify 時点で観測される実際の変更集合は、宣言された集合と等しい必要はなく、宣言に含まれて（CONTAINED IN）いればよい。implement タスクを 1 つも生成しないフィーチャーは `test-docs/recycled-carveout-reader-count-claims/` ディレクトリを生成しないが、その場合も宣言された `test-docs/recycled-carveout-reader-count-claims/**` は正しい。宣言されたパスが実際に生成されなくても違反にはならない。

## Test Scenarios

### Unit Tests

該当なし。

### Inspection

- [ ] TS-1（AC-1、AC-3）: TS-13 行と 89 行目の項目を読む - どちらも `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけを挙げ、読み取り箇所の定義つきで「削除済み、または 2 以上」の判定基準を書いており、全定数を指す全称の文言を含まない。
- [ ] TS-2（AC-2）: `tests/test_recycled_task_id_consistency.py` で、`HOOK_FILENAMES` の定義行以外の参照を、コメントと docstring を除いて数える - 2 以上であること（base 時点では 3）。`JOURNAL_ONLY_HOOK_FILENAMES` に定義も参照も無いこと。
- [ ] TS-3（AC-4）: モジュール docstring を確認する - 読み取り箇所数の主張が無い。
- [ ] TS-4（AC-5）: base に対する `git diff --stat` を見る - 出るのは `feature-docs/recycled-task-id-carveout/VERIFICATION.md` と `feature-docs/recycled-carveout-reader-count-claims/` 配下のファイルだけである。`VERIFICATION.md` の差分が触れるのは 36 行目と 89 行目だけである。

### Integration Tests

- [ ] TS-5（AC-6）: リポジトリルートで `python3 -m unittest discover -s tests` を実行する - 終了コード 0 で終わる。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

該当なし。

### Edge Cases

該当なし。

### Performance Tests

該当なし。

## Security Considerations

該当なし。

## Error Handling

該当なし。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC-1（FR1）: TS-13 行が挙げる定数は `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけである。Expected Result に判定基準「すべての参照とともに削除（定義なし・読み取り箇所 0）、または読み取り箇所 2 以上」と、読み取り箇所の定義（定義行以外のコード上の参照。コメントと docstring は除く）が書かれている。行内に「モジュールレベルの全定数」を指す全称の文言が残っていない。
- [ ] AC-2（FR1）: 統合後の `tests/test_recycled_task_id_consistency.py` で測って TS-13 の判定基準が成り立つ。`HOOK_FILENAMES` の読み取り箇所は 3 つ（base 時点で 1290、1291、1429 行目）。`JOURNAL_ONLY_HOOK_FILENAMES` は定義も参照も無い。
- [ ] AC-3（FR2）: 89 行目の手動確認項目が同じ 2 定数に絞られ、同じ判定基準を使い、TS-13 を引用している。
- [ ] AC-4（FR3）: `tests/test_recycled_task_id_consistency.py` を `reader` で大文字小文字を区別せず検索しても、モジュール docstring に読み取り箇所数の主張が見つからない。
- [ ] AC-5（FR4、NFR1、NFR2）: base との差分で変わるのは、`feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行と 89 行目の項目、および `feature-docs/recycled-carveout-reader-count-claims/` 配下のファイルだけである。
- [ ] AC-6（NFR3）: `python3 -m unittest discover -s tests` が終了コード 0 で終わる。

## Assumptions

- **A1:** 読み取り箇所は定義行以外のコード上の参照とし、コメントと docstring は数えない。requirement.ts13-scope の回答による定義である。この定義でも、task0004 AC-5 の定義（値によって振る舞いが変わるアサーションまたは導出）でも、`HOOK_FILENAMES` の読み取り箇所は同じ 3 つになる。
- **A2:** 測定値は、統合ワークツリーの base_revision d8e6d30 時点の `tests/test_recycled_task_id_consistency.py` から取った。このモジュールは recycled-task-id-carveout のマージ後に書き換えられている。その後の変更には recycled-task-id-contract task0001、routeback-admissibility-exits、goal-vs-spec-divergence task0017 が含まれる。
- **A3:** 読み取り箇所が 1 つだけの他の定数は、選んだ TS-13 の範囲外であり変更しない。対象は `_PIN_PATH`、`PLUGIN_ROOT`、`IMPLEMENT_PHASE_PATH`、`STOP_CONDITION_3_PHRASE`、`ABORT_PHASE_TERMINAL_PHRASE`、`STATUS_NEVER_CONSULTED_PHRASE`、`ORCHESTRATOR_ONLY_SCOPE_PHRASE`。
- **A4:** マージ済みの recycled-task-id-carveout の過去の記録は書かれたままにする。対象は `workflow.yaml` の verify のメモ、`task0004.md`、task0001 と task0004 の `tests.yaml`。

## Open Questions

なし（`status: tbd` の要件は無い）。

## Implementation Phases (if applicable)

該当なし。

## References

- `feature-docs/recycled-carveout-reader-count-claims/REQUIREMENTS.md`: 要件定義書
- `feature-docs/recycled-task-id-carveout/VERIFICATION.md`: 変更対象（TS-13 行、89 行目）
- `feature-docs/recycled-task-id-carveout/SPEC.md`: TS-13 の出典 AC-6
- `tests/test_recycled_task_id_consistency.py`: 読み取り箇所の測定対象
