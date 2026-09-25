---
title: "task-id-allocation-ssot"
created_date: 2026-09-25
status: draft
---

# task-id-allocation-ssot - 要件定義書

## 1. 概要

### 1.1 背景
task id の割当規則が 2 つの文書で食い違っている。

- `em-workflow/references/implement-phase.md` は、planner の `replace_all` が task id を再採番する前提で記述されている（I.2.c）。
- `em-workflow/references/workflow-patch.md` の 'Re-planning task-id allocation' は、id を再発行せず、登録済みの最大 id より上から採番し、登録済み id を `tasks_patch.carried_task_ids` でそのまま保持すると定めている。

どちらが正かが文面から一意に決まらず、recycled-task-id 継承が起こり得るのか否かも決まらない。

### 1.2 目的
- task id の割当規則を workflow-patch.md の 'Re-planning task-id allocation' の 1 箇所だけで定義し、他の文書はそれを引用するだけにする。
- task id が再発行されないこと、したがって他タスクの journal 終端イベントを継承するタスクは存在しないことを、文面から一意に読み取れるようにする。
- 既存の recycled-task-id 対策をこの規則の下で判定し直し、その結果を記録する。

### 1.3 スコープ
- `em-workflow/references/implement-phase.md` I.2.c の文言修正
- implementation-planner.md、planner-contract.md、create-plan-phase.md の引用の確認（規則を再掲しない）
- `queue_stop_guard.py` のモジュール docstring の修正（コードは変更しない）
- `em-workflow/scripts/validate-worker-output.py` の該当コメントの修正（コードは変更しない）
- 関連テストの更新と追加
- em-workflow の version の patch bump

workflow-patch.md の 'Re-planning task-id allocation' 節の内容は変更しない。

## 2. ビジネス要件

### 2.1 ビジネス目標
- task id の割当規則を定義する文書は workflow-patch.md の 'Re-planning task-id allocation' だけとし、他の文書はすべて引用のみとする。
- task id が再発行されないこと、したがって他タスクの journal 終端イベントを継承するタスクは存在しないことが、文書から一意に読み取れる。
- 既存の recycled-task-id 対策をこの規則の下で判定し直し、その結果を記録する。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 2.1 のビジネス目標と同じ

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | task id 割当の所有 SSOT を 1 つにする | workflow-patch.md の 'Re-planning task-id allocation' だけが割当規則を定義し、他の文書は引用する |
| FR2 | I.2.c から再利用・再採番の前提を除く | I.2.c に、`replace_all` が task id を再利用・再採番・再発行するという記述を残さない |
| FR3 | 継承が起こり得ないことを明記する | I.2.c に、task id は再発行されず、タスクが持つ終端イベントはそのタスク自身のものであると書く |
| FR4 | 対策の挙動を維持し、根拠を書き直す | 3 つの対策の挙動は変えず、根拠をタスク自身の id と自身の終端イベントの関係で書き直す |
| FR5 | I.2.c の再スコープ文を carried-verbatim 規則に揃える | 失敗 id はそのまま保持し、新規タスクは最大 id より上に追加すると書き直す |
| FR6 | carve-out の名称を維持し、前提だけを直す | 'recycled-task-id carve-out' の名称は維持し、id の再利用・再採番を述べる文だけを直す |
| FR7 | validator のコメントを揃える | validate-worker-output.py:1492-1494 のコメントを carried_task_ids 規則の説明に直す |
| FR8 | version bump | em-workflow の version を plugin.json と marketplace.json の両方で patch bump する |

### 4.2 機能詳細

#### FR1: task id 割当の所有 SSOT を 1 つにする

**説明**: task id の割当規則を定義する文書は workflow-patch.md の 'Re-planning task-id allocation' だけとする。規則の内容は次の 3 点。

- id を再発行しない
- 新規 id は登録済みの最大 id より上から採番する
- 登録済み id は `tasks_patch.carried_task_ids` でそのまま保持する

**ビジネスルール**:
- implement-phase.md、implementation-planner.md、planner-contract.md、create-plan-phase.md はこの節を引用し、規則を再掲しない。
- workflow-patch.md の同節の内容は変更しない。

#### FR2: I.2.c から再利用・再採番の前提を除く

**説明**: implement-phase.md I.2.c に、`replace_all` が task id を再利用・再採番・再発行するという記述を残さない。対象は次の文。

- 'the planner's `replace_all` recycles every id, not only the failed ones'
- 'a renumbered task id inheriting such an event could never be launched'
- 'only the failed one leaves a recycled id launchable'
- 'no recycled id can ever inherit a journal `merged` the launch guard denies through this phase's own write set'

**ビジネスルール**:
- I.2.c で割当規則が必要な箇所では、workflow-patch.md の 'Re-planning task-id allocation' を引用する。

#### FR3: 継承が起こり得ないことを明記する

**説明**: implement-phase.md I.2.c に、I.2.a と同様、task id は再発行されない（所有 SSOT を引用する）と書く。したがって他タスクの journal 終端イベントを持つタスクは存在せず、タスクが持つ終端イベントはそのタスク自身のものである。

#### FR4: 対策の挙動を維持し、根拠を書き直す

**説明**: 次の 3 つの対策の挙動は変更しない。

- `queue_launch_guard.py` の `deny_already_merged`
- I.2.c の route-back gate の第三条件（journal の最終イベント `merged` を直接読む）
- failed+pending carve-out

それぞれの根拠を、タスク自身の id が自身の終端イベントを持つという観点で書き直す。

**ビジネスルール**:
- 第三条件: タスク自身の journal 最終イベントが `merged` で、祖先確認が失敗した場合、第三条件が無ければそのタスクは `pending` に戻され、launch guard がその再起動を拒否する。
- carve-out: route-back はタスク自身の `failed` 状態を `pending` に戻し、再計画の `replace_all` はその id をそのまま保持する。
- `deny_already_merged`: タスク自身の merged id に対する二重起動の防止であり、id の再利用とは無関係である。
- 3 つの対策すべてが所有規則の下でも引き続き必要であることを文書に記録する。

#### FR5: I.2.c の再スコープ文を carried-verbatim 規則に揃える

**説明**: implement-phase.md I.2.c の 'The planner re-scopes the failed task (split it, change the approach)' を、保持規則に合わせて書き直す。

**ビジネスルール**:
- リセットされた失敗タスクの id はそのまま保持され、plan、files、`pending` 状態も保持される。
- planner は新規タスクを最大 id より上の新しい id で追加する。
- 要件そのものを外す必要がある場合は、これまでどおり先に通常の SPEC.md 更新の経路を通す。
- 説明は workflow-patch.md の 'Re-planning task-id allocation' の引用で行い、規則を再掲しない。
- 挙動を広げない。

#### FR6: carve-out の名称を維持し、前提だけを直す

**説明**: 'recycled-task-id carve-out' と 'recycled-task-id rule' の名称は、既存のすべての箇所（implement-phase.md、skills/develop/SKILL.md:563、queue_stop_guard.py）で参照ラベルとして維持する。id が再利用・再採番されると述べる文だけを直す。

**ビジネスルール**:
- `queue_stop_guard.py` のモジュール docstring（16〜19 行）を、pending+failed の例外を「route-back によって `pending` に戻されたタスク自身の id」として説明する形に直す。'a recycled task id left behind by a route-back re-plan' とは書かない。
- hook のコードは変更しない。

#### FR7: validator のコメントを揃える

**説明**: `em-workflow/scripts/validate-worker-output.py:1492-1494` のコメントは、再計画の `replace_all` の `entries` が登録済み id をすべて再宣言しなければならないと述べている。これを、その下のコードが強制している carried_task_ids 規則の説明に直す。

**ビジネスルール**:
- コードは変更しない。

#### FR8: version bump

**説明**: em-workflow の version を、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの両方で、同じ値に patch bump する。同じ変更に含める。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR1（テストスイートが通る）: `python3 -m unittest discover -s tests` が通る。
- NFR3（テストの決まりごと）: 新規・更新するテストは Python 標準ライブラリのみを使い、test/README.md に従う。新しい文言のマッチャーには、既存の文書文言テストと同様に、変更前に取得したサンプルに対する否定の証明を必ず対にする。
- NFR4（引用し、再掲しない）: workflow-patch.md 以外の文書は、割当の式や carried-verbatim のフィールド一覧を再掲しない。他の文書は節名で引用する。

### 5.5 互換性要件
- NFR2（実行時の挙動を変えない）: hook（`queue_launch_guard.py`、`queue_stop_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py`）と `validate-worker-output.py` の実行時の挙動は変えない。これらのファイルで変更するのは docstring とコメントのみ。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- hook と `validate-worker-output.py` は docstring とコメントのみ変更する（NFR2）。
- テストは Python 標準ライブラリのみを使う（NFR3）。

### 9.2 ビジネス上の制約
- 該当なし

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/task-id-allocation-ssot/**`
- `test-docs/task-id-allocation-ssot/**`

`feature-docs/task-id-allocation-ssot/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/task-id-allocation-ssot/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/task-id-allocation-ssot/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/task-id-allocation-ssot/` ディレクトリを生成しないが、宣言された `test-docs/task-id-allocation-ssot/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR2, FR3）: 空白を正規化した implement-phase.md の I.2.c 節に、'recycles every id'、'renumbered task id'、'leaves a recycled id launchable'、'no recycled id can ever inherit' のいずれも含まれない。
- [ ] AC-2（FR1, FR3）: I.2.c 節が workflow-patch.md の 'Re-planning task-id allocation' を引用し、タスクの journal 終端イベントはそのタスク自身のものである（task id は再発行されない）と述べている。
- [ ] AC-3（FR4）: I.2.c の第三条件が残っており、絞り込まれないままである（THIRD_CONJUNCT_OPENING_ANCHOR、THIRD_CONJUNCT_SOURCE_PHRASE、THIRD_CONJUNCT_INDEPENDENCE_PHRASE、THIRD_CONJUNCT_NEVER_NARROWED_PHRASE が残る）。その根拠がタスク自身の `merged` イベントと launch guard の拒否に言及している。
- [ ] AC-4（FR4）: implement-phase.md が再判定の結果を記録している。`deny_already_merged`、第三条件、failed+pending carve-out のそれぞれが所有規則の下でも必要であり、それぞれの理由がタスク自身の id の観点で書かれている。
- [ ] AC-5（FR5）: I.2.c に 'The planner re-scopes the failed task (split it, change the approach)' が含まれない。置き換えた文は、失敗 id がそのまま保持され、新規タスクが最大 id より上に追加されることを、workflow-patch.md の 'Re-planning task-id allocation' を引用して述べている。要件を外す場合の SPEC.md 更新の経路は残っている。
- [ ] AC-6（FR6）: 'recycled-task-id carve-out' の語が既存の箇所（implement-phase.md、skills/develop/SKILL.md:563）に残っている。`queue_stop_guard.py` のモジュール docstring に 'a recycled task id left behind by a route-back re-plan' が含まれない。hook のコードは docstring 以外バイト単位で同一である。
- [ ] AC-7（FR1, NFR4）: workflow-patch.md の 'Re-planning task-id allocation' 節は変更されていない。implementation-planner.md、planner-contract.md、create-plan-phase.md は引き続きこの節を引用し、式を再掲していない。
- [ ] AC-8（FR7）: validate-worker-output.py の再計画割当ブロックのコメントが carried_task_ids を説明している（登録済み id は保持され、`entries` で再宣言されない）。実行コードは変更されていない。
- [ ] AC-9（FR8）: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow の version が同じ値で、変更前の version から patch 1 段上がっている。
- [ ] AC-10（NFR1, NFR3）: `python3 -m unittest discover -s tests` が通る。削除した I.2.c の文言を固定しているテスト（tests/test_implement_routeback_gate.py）が更新され、新しい文言のマッチャーそれぞれに否定の証明がある。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（AC-1）: implement-phase.md を読み、I.2.c を切り出して空白を正規化し、削除した再利用・再採番の各文言が含まれないことを確認する。否定の証明として、同じマッチャーが変更前に取得した I.2.c のサンプルを検出することを示す。
- [ ] TS-2（AC-2）: I.2.c に workflow-patch.md の 'Re-planning task-id allocation' の引用と、自身の終端イベントについての記述が含まれることを確認する。否定の証明は変更前のサンプルに対して行う。
- [ ] TS-3（AC-3, AC-4）: 第三条件のアンカーが残っていること、書き直した根拠の文言があること、3 つの対策すべての再判定の記述があることを確認する。THIRD_CONJUNCT_NARROWING_PHRASE、NO_RECYCLED_ID_INHERITS_MERGED_VIA_WRITE_SET_PHRASE、tests/test_implement_routeback_gate.py:2276 のアンカーテストを新しい文言に更新し、否定の証明を付ける。
- [ ] TS-4（AC-5）: 旧来の再スコープ文が I.2.c に無いこと、引用付きの carried-verbatim の置き換え文があることを確認する。否定の証明は変更前のサンプルに対して行う。
- [ ] TS-5（AC-6）: 'recycled-task-id carve-out' の語が既存の箇所に残っていることを確認する（tests/test_recycled_task_id_consistency.py、tests/test_routeback_reset_scope_consistency.py、tests/test_failed_kind_resume_reentry.py がすでに固定している保持リテラルが引き続き通る）。`queue_stop_guard.py` の docstring に 'a recycled task id left behind by a route-back re-plan' が無いことを確認する。既存の hook 挙動テスト（tests/test_queue_stop_guard.py）が変更なしで通る。
- [ ] TS-6（AC-7）: 既存の tests/test_workflow_patch_doc.py の割当規則テストと、tests/test_replanning_producer_alignment.py の引用テストが変更なしで通る。
- [ ] TS-7（AC-8）: replace-all-task-id-reused ブロック付近の validator コメントが、`entries` で登録済み id を再宣言すると主張していないことを確認する。既存の tests/test_validate_worker_output.py のフィクスチャが変更なしで通る。
- [ ] TS-8（AC-9）: version bump のテストモジュールが、plugin.json と marketplace.json の em-workflow の version が一致し、tests/*_version_bump.py が固定している既存の基準値の最大より厳密に大きいことを確認する。
- [ ] TS-9（AC-10）: `python3 -m unittest discover -s tests` を実行し、すべてのテストが通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 所有 SSOT | task id の割当規則を定義する唯一の文書。workflow-patch.md の 'Re-planning task-id allocation' |
| 最大 id（high-water mark） | 登録済み task id のうち最大のもの。新規 id はこれより上から採番する |
| carried_task_ids | `tasks_patch.carried_task_ids`。再計画で登録済み id をそのまま保持するためのフィールド |
| recycled-task-id carve-out | failed+pending carve-out の参照ラベル。id の再発行を意味しない |
| 第三条件 | I.2.c の route-back gate の第三条件。journal の最終イベント `merged` を直接読む |
| `deny_already_merged` | `queue_launch_guard.py` による、merged 済み id の起動拒否 |

## 14. 確認事項

### 14.1 確認済み事項
- [x] task id 割当規則の所有 SSOT: workflow-patch.md の Re-planning task-id allocation（再発行しない・登録済み最大 id より上から採番・carried_task_ids で既存 id をそのまま保持）。implement-phase.md は引用のみ（`requirement.owning-ssot` = `workflow_patch_no_reissue`）
- [x] 既存対策の扱い: deny_already_merged・I.2.c 第三条件（journal 直読み）・failed+pending carve-out の 3 つは挙動を変えずに維持し、根拠の説明を『タスク自身の id が自身の終端イベントを持つ』に書き直す。再判定の結果を記録する（`requirement.countermeasure-disposition` = `keep_behavior_rewrite_rationale`）
- [x] carve-out の名称: 『recycled-task-id carve-out』の名称は参照ラベルとして維持し、id が再利用・再採番されると述べる文（I.2.c、queue_stop_guard.py docstring）だけを直す（`requirement.carve-out-terminology` = `keep_term_fix_premise`）
- [x] 再スコープ文の扱い: I.2.c の『planner が失敗タスクを再スコープする（分割・方針変更）』の文を、この feature の中で carried-verbatim 規則に合わせて書き直す。所有 SSOT への引用で説明する（`requirement.rescope-sentence-scope` = `in_scope_fix_wording`）
- [x] design step: skip する（`design-step.recommendation` = `decide_autonomously`）

### 14.2 未確認・保留事項
なし

### 14.3 仮定
| ID | 内容 | 影響度 | 可逆 | 関連する質問 |
|----|------|--------|------|--------------|
| A1 | validate-worker-output.py:1492-1494 の古いコメントを carried_task_ids 規則に合わせて直す。コードは変更しない（FR7） | 低 | 可 | `requirement.owning-ssot` |
| A2 | em-workflow の version を plugin.json と marketplace.json の両方で、同じ変更の中で patch bump する（FR8） | 低 | 可 | なし |
| A3 | 削除する I.2.c の文言を固定しているテストのリテラル（tests/test_implement_routeback_gate.py の THIRD_CONJUNCT_NARROWING_PHRASE、NO_RECYCLED_ID_INHERITS_MERGED_VIA_WRITE_SET_PHRASE、2276 行のアンカーテスト）を同じ変更で更新する | 中 | 可 | `requirement.countermeasure-disposition`、`requirement.carve-out-terminology` |
| A4 | workflow-patch.md の 'Re-planning task-id allocation'（再発行しない、最大 id より上から採番、carried_task_ids でそのまま保持）が唯一の所有 SSOT である。implement-phase.md は引用のみ | 高 | 可 | `requirement.owning-ssot` |
| A5 | `deny_already_merged`、I.2.c の第三条件、failed+pending carve-out は挙動を維持する。書き直すのは根拠のみで、タスク自身の id の観点で書く | 中 | 可 | `requirement.countermeasure-disposition` |
| A6 | 'recycled-task-id carve-out' の語はラベルとして維持する。直すのは I.2.c の前提の文と `queue_stop_guard.py` の docstring のみ | 低 | 可 | `requirement.carve-out-terminology` |
| A7 | I.2.c の 'The planner re-scopes the failed task (split it, change the approach)' を、この feature の中で carried-verbatim 規則に合わせ、所有 SSOT を引用して書き直す | 中 | 可 | `requirement.rescope-sentence-scope` |
| A8 | design step は skip する | 低 | 可 | `design-step.recommendation` |

## 15. 参考資料

- `em-workflow/references/workflow-patch.md`: 'Re-planning task-id allocation'（所有 SSOT）
- `em-workflow/references/implement-phase.md`: I.2.a、I.2.c
