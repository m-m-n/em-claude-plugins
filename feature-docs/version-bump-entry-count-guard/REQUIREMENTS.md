---
title: "version-bump-entry-count-guard"
created_date: 2026-09-25
status: draft
---

# version-bump-entry-count-guard - 要件定義書

## 1. 概要

### 1.1 背景
version bump 検証モジュール `tests/test_recycled_task_id_contract_version_bump.py` は、`.claude-plugin/marketplace.json` の `plugins[]` のエントリ数と、全エントリの name/source を固定値と比較している。このため、マーケットプレイスにプラグインを追加すると同モジュールが落ちる。

### 1.2 目的
- マーケットプレイスへのプラグイン追加（`.claude-plugin/marketplace.json` の `plugins[]` へのエントリ追加）で、`tests/test_recycled_task_id_contract_version_bump.py` が落ちないようにする
- 同モジュールの AC-3（このタスクが触らないフィールドが変わっていないこと）の検証を em-workflow エントリに限定する

### 1.3 スコープ
対象:
- `tests/test_recycled_task_id_contract_version_bump.py`
- `test-docs/recycled-task-id-contract/task0002.tests.yaml`

対象外:
- `tests/test_batch_policy_option_id_version_bump.py`、`tests/test_goal_vs_spec_divergence_version_bump.py`、`tests/test_rework_contract_drift_version_bump.py` にある marketplace エントリ数の固定（batch_policy は並び順の比較も含む）。この機能では実装せず、別タスクとして起票する対象とする
- `em-workflow/` 配下のファイルと `.claude-plugin/marketplace.json`

## 2. ビジネス要件

### 2.1 ビジネス目標
- マーケットプレイスへのプラグイン追加（`.claude-plugin/marketplace.json` の `plugins[]` へのエントリ追加）で、version bump 検証モジュール `tests/test_recycled_task_id_contract_version_bump.py` が落ちないようにする
- 同モジュールの AC-3（このタスクが触らないフィールドが変わっていないこと）の検証を em-workflow エントリに限定する

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| 該当なし | — |

### 2.3 期待される効果
- `.claude-plugin/marketplace.json` の `plugins[]` に 3 つ目のエントリがあっても `tests/test_recycled_task_id_contract_version_bump.py` は落ちない
- em-workflow エントリの `name` または `source` が変わると同モジュールが落ちる

## 3. ユースケース

### 3.1 ユースケース一覧
該当なし（テストコードとテスト対応表だけの修正）

### 3.2 ユースケース詳細
該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 件数ガードとエントリ全体スナップショットの撤去 | `TestMarketplaceOtherFieldsUnchanged` の 2 テストと `MARKETPLACE_NAME_SOURCE_BASELINE` を削除し、AC-3 の検証を `test_em_workflow_entry_name_and_source_unchanged` に一本化する | — |
| FR2 | em-workflow エントリの name / source 検査の維持 | em-workflow エントリの `name` または `source` が変わった場合に同モジュールが落ちる状態を維持する | — |
| FR3 | モジュール内の記述の整合 | 同モジュールの docstring を em-workflow エントリに限定した検証内容に合わせる | — |
| FR4 | テスト対応表の更新 | `task0002.tests.yaml` の AC-3 の tests と red_reason を削除後の内容に合わせる | — |
| FR5 | テスト内で作った値による確認 | 3 エントリのデータで通ること、source / name が変わったデータで落ちることをテスト内の値で示す | — |

### 4.2 機能詳細

#### FR1: 件数ガードとエントリ全体スナップショットの撤去

**説明**: `tests/test_recycled_task_id_contract_version_bump.py` から `TestMarketplaceOtherFieldsUnchanged` の 2 テスト（`test_entry_count_unchanged` / `test_every_entry_name_and_source_matches_baseline`）と、それらだけが参照する定数 `MARKETPLACE_NAME_SOURCE_BASELINE` を削除する。AC-3 の検証は既存の `TestMarketplaceEntryVersion.test_em_workflow_entry_name_and_source_unchanged` に一本化する（レビュー提案 (b)）。

#### FR2: em-workflow エントリの name / source 検査の維持

**説明**: em-workflow エントリの `name` または `source` が変わった場合に同モジュールが落ちる状態を維持する。`test_em_workflow_entry_name_and_source_unchanged` は削除も弱体化もしない。

#### FR3: モジュール内の記述の整合

**説明**: 同モジュールの docstring（モジュール先頭の AC-3 の説明にある「the marketplace `plugins` array gains or loses no entry」、および全エントリの name/source を検査するという記述）を、em-workflow エントリに限定した検証内容に合わせる。

#### FR4: テスト対応表の更新

**説明**: `test-docs/recycled-task-id-contract/task0002.tests.yaml` の `acceptance_tests.AC-3.tests` から削除した 2 テストの ID を除き、`test_em_workflow_entry_name_and_source_unchanged` だけを残す。同じ AC-3 の `red_reason` にある件数（entry count）への言及も削除後の内容に合わせる。

#### FR5: テスト内で作った値による確認

**説明**: 次の 2 点を、テスト内で作った値で示す。リポジトリ上のファイルを書き換えて確かめる方法は取らない。

1. em-workflow 以外に 3 つ目のエントリを持つ marketplace データで、em-workflow エントリの検査が通ること
2. em-workflow エントリの `source` が変わったデータ、および `name` が変わって em-workflow エントリが見つからないデータでは、検査が落ちること

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR1: 変更するファイルは `tests/test_recycled_task_id_contract_version_bump.py` と `test-docs/recycled-task-id-contract/task0002.tests.yaml` の 2 つだけとする。
- NFR2: テストコードは標準ライブラリ（unittest / json / re / pathlib）だけを import し、JSON は必ずパースして読む（パターンマッチでは読まない）。
- NFR3: `em-workflow/` 配下のファイルと `.claude-plugin/marketplace.json` は変更しない。このためプラグインの version は上げない。
- NFR4: `python3 -m unittest discover -s tests` をリポジトリルートで実行し、全体が通る。

### 5.5 互換性要件
該当なし

## 6. UI/UX要件

該当なし（デザインステップはスキップ）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 変更対象は `tests/test_recycled_task_id_contract_version_bump.py` と `test-docs/recycled-task-id-contract/task0002.tests.yaml` の 2 ファイルに限る（NFR1）
- テストコードの import は標準ライブラリ（unittest / json / re / pathlib）に限る。JSON はパースして読む（NFR2）
- `em-workflow/` 配下のファイルと `.claude-plugin/marketplace.json` は変更せず、プラグインの version は上げない（NFR3）

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/version-bump-entry-count-guard/**`
- `test-docs/version-bump-entry-count-guard/**`

`feature-docs/version-bump-entry-count-guard/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/version-bump-entry-count-guard/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/version-bump-entry-count-guard/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 3 つ目のプラグインを追加すると、`tests/test_batch_policy_option_id_version_bump.py`、`tests/test_goal_vs_spec_divergence_version_bump.py`、`tests/test_rework_contract_drift_version_bump.py` の 3 モジュールは引き続き落ちる | — | この機能の範囲外。別タスクとして起票する対象 |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR1, FR5）: `.claude-plugin/marketplace.json` の `plugins[]` に 3 つ目のエントリがあっても `tests/test_recycled_task_id_contract_version_bump.py` は落ちない。FR5(1) のテスト内の値による確認で示す。
- [ ] AC-2（FR2, FR5）: em-workflow エントリの `name` または `source` が変わると同モジュールが落ちる。既存の `test_em_workflow_entry_name_and_source_unchanged` が残っていることと、FR5(2) のテスト内の値による確認で示す。
- [ ] AC-3（FR1, FR3）: 同モジュールに `MARKETPLACE_NAME_SOURCE_BASELINE`、`test_entry_count_unchanged`、`test_every_entry_name_and_source_matches_baseline` が残っていない。docstring に、エントリ数やエントリ全体の name/source を検査するという記述が残っていない。
- [ ] AC-4（FR4）: `task0002.tests.yaml` の AC-3 の tests に書かれているテスト ID はすべてモジュールに実在し、削除した 2 テストの ID は含まれない。
- [ ] AC-5（NFR1, NFR2, NFR3, NFR4）: `python3 -m unittest discover -s tests` が全体で通り、変更は NFR1 の 2 ファイルだけに収まっている。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系（TS-1 / AC-1）: em-review / em-workflow に 3 つ目のエントリを加えた marketplace の dict をテスト内で作り、em-workflow エントリの name/source 検査に渡す。検査が通る
- [ ] 異常系（TS-2 / AC-2）: em-workflow エントリの source を `./em-workflow` 以外にした dict をテスト内で作り、同じ検査に渡す。AssertionError になる
- [ ] 異常系（TS-3 / AC-2）: em-workflow エントリの name を別名にした（em-workflow エントリが無い）dict をテスト内で作り、同じ検査に渡す。AssertionError になる
- [ ] 削除確認（TS-4 / AC-3, AC-4）: モジュールと `task0002.tests.yaml` から `MARKETPLACE_NAME_SOURCE_BASELINE` / `test_entry_count_unchanged` / `test_every_entry_name_and_source_matches_baseline` / `TestMarketplaceOtherFieldsUnchanged` を検索する。どれも見つからない
- [ ] スイート全体（TS-5 / AC-5）: リポジトリルートで `python3 -m unittest discover -s tests` を実行する。失敗が 0 件。現在の marketplace.json（em-review / em-workflow の 2 件）で em-workflow の検査も通る

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 同モジュール | `tests/test_recycled_task_id_contract_version_bump.py` |
| task0002 の AC-3 | `test-docs/recycled-task-id-contract/task0002.tests.yaml` の `acceptance_tests.AC-3`。このタスクが触らないフィールドが変わっていないことの検証 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] ほかの 3 モジュールの件数固定の扱い（requirement.scope.other-count-guards）: target_module_only。修正範囲は `tests/test_recycled_task_id_contract_version_bump.py` と `test-docs/recycled-task-id-contract/task0002.tests.yaml` に限る
- [x] デザインステップ（design-step.recommendation）: skip

前提（assumptions）:

- A-1: 修正範囲は `tests/test_recycled_task_id_contract_version_bump.py` と `test-docs/recycled-task-id-contract/task0002.tests.yaml` に限る。ほかの 3 モジュール（`tests/test_batch_policy_option_id_version_bump.py` の `OTHER_PLUGIN_ENTRIES_BASELINE` による件数・並び順の比較、`tests/test_goal_vs_spec_divergence_version_bump.py` / `tests/test_rework_contract_drift_version_bump.py` の `test_plugins_list_length_unchanged`）の件数固定はこの機能の範囲外とし、直さない。3 つ目のプラグインを追加すると、この 3 モジュールは引き続き落ちる。
- A-2: レビュー提案のうち (b)（2 テストを削除して `test_em_workflow_entry_name_and_source_unchanged` に一本化）を採る。(a)（`assertGreaterEqual` に緩める）は em-review エントリの name/source 検査を残してしまい、「em-workflow エントリに限定して検証する」という期待する挙動に合わないため採らない。
- A-3: `task0002.tests.yaml` の AC-4 の `red_reason` にあるテスト件数（「10 tests」「1462 tests」）は task0002 当時の実行記録として変更しない。タスク本文が更新を求めているのは AC-3 の tests 一覧だけである。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- なし
