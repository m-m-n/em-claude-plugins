---
title: "recycled-carveout-reader-count-claims"
created_date: 2026-09-25
status: draft
---

# recycled-carveout-reader-count-claims - 要件定義書

## 1. 概要

### 1.1 背景

`feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 は出典に SPEC AC-6 を挙げている。AC-6 が対象とするのは、`ORCHESTRATOR_ONLY_SCOPE_PHRASE` の改訂で読み取り箇所を失った定数（`HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES`）だけである。一方、TS-13 の行と 89 行目の手動確認項目は、モジュールレベルの全定数を対象とする文言になっている。

### 1.2 目的

- `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 の主張を、出典である SPEC AC-6 の範囲に合わせる。対象は `ORCHESTRATOR_ONLY_SCOPE_PHRASE` の改訂で読み取り箇所を失った定数（`HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES`）だけとする。
- recycled-task-id-carveout の検証記録と `tests/test_recycled_task_id_consistency.py` のモジュール docstring に、モジュールから数えた実数と食い違う読み取り箇所数の主張を残さない。

### 1.3 スコープ

対象:
- `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行（36 行目）
- 同ファイルの Manual Testing 項目（89 行目）
- `tests/test_recycled_task_id_consistency.py` の docstring の確認（編集はしない）

対象外:
- 上記 2 箇所以外の `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の行
- NFR2 に挙げたファイル
- 読み取り箇所が 1 つだけの他の定数（14.1 の A3 を参照）

## 2. ビジネス要件

### 2.1 ビジネス目標

1.2 の目的と同じ。

### 2.2 対象ユーザー

該当なし。

### 2.3 期待される効果

該当なし。

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | TS-13 行を AC-6 の対象定数に絞る | TS-13 行の Scenario と Expected Result を `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけに絞る | - |
| FR2 | TS-13 の手動確認項目を同じく絞る | 89 行目の手動確認項目を同じ 2 定数に絞る | - |
| FR3 | モジュール docstring に誤った読み取り箇所数の主張が無いことを確認する | docstring を確認する。テストモジュールは変更しない | - |
| FR4 | 変更を VERIFICATION.md の 2 箇所に限る | TS-13 行と 89 行目の項目、およびこのフィーチャー自身の生成文書以外は変更しない | - |

### 4.2 機能詳細

#### FR1: TS-13 行を AC-6 の対象定数に絞る

**説明**: `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行（36 行目）を書き換え、Scenario と Expected Result の対象を `tests/test_recycled_task_id_consistency.py` の `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけにする。

**ビジネスルール**:
- 判定基準: 各定数は、すべての参照とともに削除されている（定義なし・読み取り箇所 0）か、読み取り箇所が 2 以上あるかのどちらかである。
- 読み取り箇所は、定義行以外にあるコード上の参照とする。コメントと docstring は数えない。
- 次の全称の文言を削除する。
    - `No module-level constant ... is left with fewer than two reader sites`
    - `every constant has 0 (retired with its readers) or >= 2`
- ID `TS-13`、出典表記 `(SPEC AC-6)`、Test Type `Inspection` は変えない。

#### FR2: TS-13 の手動確認項目を同じく絞る

**説明**: 同じ `VERIFICATION.md` の Manual Testing 項目（89 行目）を書き換える。現在の文言は次のとおり。

> Count the reader sites of every module-level constant in that module and confirm none is left with exactly one (TS-13).

**ビジネスルール**:
- 確認対象は `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけとする。
- FR1 の判定基準と読み取り箇所の定義で確認する内容にする。
- TS-13 の引用は残す。

#### FR3: モジュール docstring に誤った読み取り箇所数の主張が無いことを確認する

**説明**: `tests/test_recycled_task_id_consistency.py` の docstring に、実数と食い違う読み取り箇所数の主張を含めない。

**ビジネスルール**:
- base_revision 時点で、docstring に読み取り箇所数の主張は無い。
    - `leaving no module-level constant in this module with fewer than two reader sites` という文は存在しない。
    - モジュール内を `reader` で大文字小文字を区別せず検索しても何も見つからない。
- この要件は編集ではなく確認で満たす。
- テストモジュールは変更しない。

#### FR4: 変更を VERIFICATION.md の 2 箇所に限る

**説明**: 変更するのは `feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行と 89 行目の手動確認項目、およびこのフィーチャー自身のワークフロー生成文書だけとする。

**ビジネスルール**:
- `VERIFICATION.md` の他の行はバイト単位で変えない。TS-12、TS-14、Verification Summary、105 行目もこれに含む。

## 5. 非機能要件

| ID | 要件名 | 内容 |
|----|--------|------|
| NFR1 | プラグインの version を上げない | `em-workflow/` 配下のファイルは変更しない。よって `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は現在の値のままとする。 |
| NFR2 | 過去の記録を変更しない | 次のファイルは変更しない: `feature-docs/recycled-task-id-carveout/workflow.yaml`（verify のメモを含む）、`feature-docs/recycled-task-id-carveout/SPEC.md`、`feature-docs/recycled-task-id-carveout/tasks/task0004.md`、`test-docs/recycled-task-id-carveout/task0001.tests.yaml`、`test-docs/recycled-task-id-carveout/task0004.tests.yaml`、`tests/test_recycled_task_id_consistency.py` |
| NFR3 | テストスイートが通る | リポジトリルートで `python3 -m unittest discover -s tests` が終了コード 0 で終わる。 |

### 5.1 パフォーマンス要件

該当なし。

### 5.2 セキュリティ要件

該当なし。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

該当なし。

### 5.5 互換性要件

該当なし。

## 6. UI/UX要件

該当なし。検証文書のテキスト編集のみで、利用者から見える画面は無い。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 5 章の NFR1、NFR2 に従う。

### 9.2 ビジネス上の制約

該当なし。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/recycled-carveout-reader-count-claims/**`
- `test-docs/recycled-carveout-reader-count-claims/**`

`feature-docs/recycled-carveout-reader-count-claims/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/recycled-carveout-reader-count-claims/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/recycled-carveout-reader-count-claims/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/recycled-carveout-reader-count-claims/` ディレクトリを生成しないが、宣言された `test-docs/recycled-carveout-reader-count-claims/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1（FR1）: TS-13 行が挙げる定数は `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけである。Expected Result に判定基準「すべての参照とともに削除（定義なし・読み取り箇所 0）、または読み取り箇所 2 以上」と、読み取り箇所の定義（定義行以外のコード上の参照。コメントと docstring は除く）が書かれている。行内に「モジュールレベルの全定数」を指す全称の文言が残っていない。
- [ ] AC-2（FR1）: 統合後の `tests/test_recycled_task_id_consistency.py` で測って TS-13 の判定基準が成り立つ。`HOOK_FILENAMES` の読み取り箇所は 3 つ（base 時点で 1290、1291、1429 行目）。`JOURNAL_ONLY_HOOK_FILENAMES` は定義も参照も無い。
- [ ] AC-3（FR2）: 89 行目の手動確認項目が同じ 2 定数に絞られ、同じ判定基準を使い、TS-13 を引用している。
- [ ] AC-4（FR3）: `tests/test_recycled_task_id_consistency.py` を `reader` で大文字小文字を区別せず検索しても、モジュール docstring に読み取り箇所数の主張が見つからない。
- [ ] AC-5（FR4、NFR1、NFR2）: base との差分で変わるのは、`feature-docs/recycled-task-id-carveout/VERIFICATION.md` の TS-13 行と 89 行目の項目、および `feature-docs/recycled-carveout-reader-count-claims/` 配下のファイルだけである。
- [ ] AC-6（NFR3）: `python3 -m unittest discover -s tests` が終了コード 0 で終わる。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1（AC-1、AC-3）: 目視確認。TS-13 行と 89 行目の項目を読む。どちらも `HOOK_FILENAMES` と `JOURNAL_ONLY_HOOK_FILENAMES` だけを挙げ、読み取り箇所の定義つきで「削除済み、または 2 以上」の判定基準を書いており、全定数を指す全称の文言を含まない。
- [ ] TS-2（AC-2）: 目視確認。`tests/test_recycled_task_id_consistency.py` で、`HOOK_FILENAMES` の定義行以外の参照を、コメントと docstring を除いて数える（2 以上であること。base 時点では 3）。`JOURNAL_ONLY_HOOK_FILENAMES` に定義も参照も無いことを確かめる。
- [ ] TS-3（AC-4）: 目視確認。モジュール docstring に読み取り箇所数の主張が無い。
- [ ] TS-4（AC-5）: 目視確認。base に対する `git diff --stat` に出るのが `feature-docs/recycled-task-id-carveout/VERIFICATION.md` と `feature-docs/recycled-carveout-reader-count-claims/` 配下のファイルだけである。`VERIFICATION.md` の差分が触れるのは 36 行目と 89 行目だけである。
- [ ] TS-5（AC-6）: リポジトリルートで `python3 -m unittest discover -s tests` を実行し、終了コード 0 で終わる。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 読み取り箇所（reader site） | 定数の定義行以外にある、コード上の参照。コメントと docstring は数えない。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1 読み取り箇所の定義: 定義行以外のコード上の参照とし、コメントと docstring は数えない。requirement.ts13-scope の回答による定義である。この定義でも、task0004 AC-5 の定義（値によって振る舞いが変わるアサーションまたは導出）でも、`HOOK_FILENAMES` の読み取り箇所は同じ 3 つになる。
- [x] A2 測定の基準: 測定値は、統合ワークツリーの base_revision d8e6d30 時点の `tests/test_recycled_task_id_consistency.py` から取った。このモジュールは recycled-task-id-carveout のマージ後に書き換えられている。その後の変更には recycled-task-id-contract task0001、routeback-admissibility-exits、goal-vs-spec-divergence task0017 が含まれる。
- [x] A3 他の定数の扱い: 読み取り箇所が 1 つだけの他の定数は、選んだ TS-13 の範囲外であり変更しない。対象は `_PIN_PATH`、`PLUGIN_ROOT`、`IMPLEMENT_PHASE_PATH`、`STOP_CONDITION_3_PHRASE`、`ABORT_PHASE_TERMINAL_PHRASE`、`STATUS_NEVER_CONSULTED_PHRASE`、`ORCHESTRATOR_ONLY_SCOPE_PHRASE`。
- [x] A4 過去の記録の扱い: マージ済みの recycled-task-id-carveout の過去の記録は書かれたままにする。対象は `workflow.yaml` の verify のメモ、`task0004.md`、task0001 と task0004 の `tests.yaml`。

### 14.2 未確認・保留事項

なし。

## 15. 参考資料

- `feature-docs/recycled-task-id-carveout/VERIFICATION.md`: 変更対象（TS-13 行、89 行目）
- `feature-docs/recycled-task-id-carveout/SPEC.md`: TS-13 の出典 AC-6
- `tests/test_recycled_task_id_consistency.py`: 読み取り箇所の測定対象
