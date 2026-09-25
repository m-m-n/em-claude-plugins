# Feature: task-id-allocation-ssot

## 概要

task id の割当規則を `em-workflow/references/workflow-patch.md` の 'Re-planning task-id allocation' だけで定義し、他の文書はそれを引用するだけにする。`em-workflow/references/implement-phase.md` I.2.c から task id の再利用・再採番の前提を除き、既存の recycled-task-id 対策の挙動は維持したまま根拠を書き直す。要件の詳細は `feature-docs/task-id-allocation-ssot/REQUIREMENTS.md` を参照する。

## 目的

- task id の割当規則を定義する文書は workflow-patch.md の 'Re-planning task-id allocation' だけとし、他の文書はすべて引用のみとする。
- task id が再発行されないこと、したがって他タスクの journal 終端イベントを継承するタスクは存在しないことが、文書から一意に読み取れる。
- 既存の recycled-task-id 対策をこの規則の下で判定し直し、その結果を記録する。

## ユーザーストーリー

該当なし

## 技術要件

### 機能要件
- **FR1:** task id 割当の所有 SSOT を 1 つにする。workflow-patch.md の 'Re-planning task-id allocation' だけが task id の割当を定義する（id を再発行しない、新規 id は登録済みの最大 id より上から採番する、登録済み id は `tasks_patch.carried_task_ids` でそのまま保持する）。implement-phase.md、implementation-planner.md、planner-contract.md、create-plan-phase.md はこの節を引用し、規則を再掲しない。workflow-patch.md の同節の内容は変更しない。
- **FR2:** I.2.c から再利用・再採番の前提を除く。implement-phase.md I.2.c に、`replace_all` が task id を再利用・再採番・再発行するという記述を残さない。対象は 'the planner's `replace_all` recycles every id, not only the failed ones'、'a renumbered task id inheriting such an event could never be launched'、'only the failed one leaves a recycled id launchable'、'no recycled id can ever inherit a journal `merged` the launch guard denies through this phase's own write set' の各文。I.2.c で割当規則が必要な箇所では workflow-patch.md の 'Re-planning task-id allocation' を引用する。
- **FR3:** 継承が起こり得ないことを明記する。implement-phase.md I.2.c に、I.2.a と同様、task id は再発行されない（所有 SSOT を引用する）と書く。したがって他タスクの journal 終端イベントを持つタスクは存在しない。タスクが持つ終端イベントはそのタスク自身のものである。
- **FR4:** 対策の挙動を維持し、根拠を書き直す。`queue_launch_guard.py` の `deny_already_merged`、I.2.c の route-back gate の第三条件（journal の最終イベント `merged` を直接読む）、failed+pending carve-out の 3 つの挙動は変更しない。根拠をタスク自身の id が自身の終端イベントを持つという観点で書き直す。
    - 第三条件: タスク自身の journal 最終イベントが `merged` で祖先確認が失敗した場合、第三条件が無ければそのタスクは `pending` に戻され、launch guard がその再起動を拒否する。
    - carve-out: route-back はタスク自身の `failed` 状態を `pending` に戻し、再計画の `replace_all` はその id をそのまま保持する。
    - `deny_already_merged`: タスク自身の merged id に対する二重起動の防止であり、id の再利用とは無関係である。
    - 3 つすべてが所有規則の下でも引き続き必要であることを文書に記録する。
- **FR5:** I.2.c の再スコープ文を carried-verbatim 規則に揃える。implement-phase.md I.2.c の 'The planner re-scopes the failed task (split it, change the approach)' を、保持規則に合わせて書き直す。リセットされた失敗タスクの id はそのまま保持され、plan、files、`pending` 状態も保持される。planner は新規タスクを最大 id より上の新しい id で追加する。要件そのものを外す必要がある場合は、これまでどおり先に通常の SPEC.md 更新の経路を通す。説明は workflow-patch.md の 'Re-planning task-id allocation' の引用で行い、規則を再掲しない。挙動を広げない。
- **FR6:** carve-out の名称を維持し、前提だけを直す。'recycled-task-id carve-out' と 'recycled-task-id rule' の名称は、既存のすべての箇所（implement-phase.md、skills/develop/SKILL.md:563、queue_stop_guard.py）で参照ラベルとして維持する。id が再利用・再採番されると述べる文だけを直す。`queue_stop_guard.py` のモジュール docstring（16〜19 行）を、pending+failed の例外を「route-back によって `pending` に戻されたタスク自身の id」として説明する形に直し、'a recycled task id left behind by a route-back re-plan' とは書かない。hook のコードは変更しない。
- **FR7:** validator のコメントを揃える。`em-workflow/scripts/validate-worker-output.py:1492-1494` のコメントは、再計画の `replace_all` の `entries` が登録済み id をすべて再宣言しなければならないと述べている。これを、その下のコードが強制している carried_task_ids 規則の説明に直す。コードは変更しない。
- **FR8:** version bump。em-workflow の version を、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの両方で、同じ値に patch bump する。同じ変更に含める。

### 非機能要件
- **NFR1 - テストスイートが通る:** `python3 -m unittest discover -s tests` が通る。
- **NFR2 - 実行時の挙動を変えない:** hook（`queue_launch_guard.py`、`queue_stop_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py`）と `validate-worker-output.py` の実行時の挙動は変えない。これらのファイルで変更するのは docstring とコメントのみ。
- **NFR3 - テストの決まりごと:** 新規・更新するテストは Python 標準ライブラリのみを使い、test/README.md に従う。新しい文言のマッチャーには、既存の文書文言テストと同様に、変更前に取得したサンプルに対する否定の証明を必ず対にする。
- **NFR4 - 引用し、再掲しない:** workflow-patch.md 以外の文書は、割当の式や carried-verbatim のフィールド一覧を再掲しない。他の文書は節名で引用する。

## 実装方針

### アーキテクチャ

該当なし（変更は参照文書の文章、hook の docstring、スクリプトのコメント、テスト、version フィールドのみ）

### 変更対象

| 対象 | 変更内容 | 要件 |
|------|----------|------|
| `em-workflow/references/implement-phase.md` I.2.c | 再利用・再採番の前提の文を除き、所有 SSOT の引用、自身の終端イベントの記述、3 つの対策の根拠と再判定の記録、再スコープ文の書き直しを行う | FR2, FR3, FR4, FR5, FR6 |
| `em-workflow/references/workflow-patch.md` 'Re-planning task-id allocation' | 変更しない | FR1 |
| implementation-planner.md、planner-contract.md、create-plan-phase.md | 引用を維持し、規則を再掲しない | FR1, NFR4 |
| `queue_stop_guard.py` | モジュール docstring（16〜19 行）のみ修正 | FR6, NFR2 |
| `em-workflow/scripts/validate-worker-output.py:1492-1494` | コメントのみ修正 | FR7, NFR2 |
| `em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json` | em-workflow の version を patch bump | FR8 |
| tests/test_implement_routeback_gate.py | 削除する I.2.c の文言を固定しているリテラルとアンカーテストを更新 | NFR1, NFR3 |
| tests 配下の新規テスト | 新しい文言の検証と version bump の検証 | NFR1, NFR3 |

### 依存関係

**内部依存:**
- workflow-patch.md の 'Re-planning task-id allocation': task id 割当規則の所有 SSOT。他の文書はこの節を引用する。
- `validate-worker-output.py`: 所有 SSOT の規則を機械的に強制している。コードは変更しない。

**外部依存:**
- なし

## 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリをデフォルトで宣言する。

- `feature-docs/task-id-allocation-ssot/**`
- `test-docs/task-id-allocation-ssot/**`

`feature-docs/task-id-allocation-ssot/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。これらの生成主体は各フェーズドキュメントと `references/phase-state.md` であり、この節は引用のみでルールを再掲しない。

`test-docs/task-id-allocation-ssot/**` に含まれるもの: タスクごとのテスト記録 `test-docs/task-id-allocation-ssot/{T}.tests.yaml`。生成主体は `implement-phase.md` であり、この節は引用のみでルールを再掲しない。

この 2 つのデフォルトエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさず、除外は意図的で明示的な絞り込みである。

この宣言はスーパーセット（superset）の主張であり、検証時に観測される実際の変更集合は宣言された集合に含まれる（CONTAINED IN）必要がある。一致は求めない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/task-id-allocation-ssot/` ディレクトリを生成しないが、その場合も宣言された `test-docs/task-id-allocation-ssot/**` は正しい。生成されなかった宣言パスは違反ではない。

## テストシナリオ

### ユニットテスト
- [ ] TS-1（AC-1）: implement-phase.md を読み、I.2.c を切り出して空白を正規化し、削除した再利用・再採番の各文言が含まれないことを確認する。否定の証明として、同じマッチャーが変更前に取得した I.2.c のサンプルを検出することを示す。
- [ ] TS-2（AC-2）: I.2.c に workflow-patch.md の 'Re-planning task-id allocation' の引用と、自身の終端イベントについての記述が含まれることを確認する。否定の証明は変更前のサンプルに対して行う。
- [ ] TS-3（AC-3, AC-4）: 第三条件のアンカーが残っていること、書き直した根拠の文言があること、3 つの対策すべての再判定の記述があることを確認する。THIRD_CONJUNCT_NARROWING_PHRASE、NO_RECYCLED_ID_INHERITS_MERGED_VIA_WRITE_SET_PHRASE、tests/test_implement_routeback_gate.py:2276 のアンカーテストを新しい文言に更新し、否定の証明を付ける。
- [ ] TS-4（AC-5）: 旧来の再スコープ文が I.2.c に無いこと、引用付きの carried-verbatim の置き換え文があることを確認する。否定の証明は変更前のサンプルに対して行う。
- [ ] TS-5（AC-6）: 'recycled-task-id carve-out' の語が既存の箇所に残っていることを確認する（tests/test_recycled_task_id_consistency.py、tests/test_routeback_reset_scope_consistency.py、tests/test_failed_kind_resume_reentry.py がすでに固定している保持リテラルが引き続き通る）。`queue_stop_guard.py` の docstring に 'a recycled task id left behind by a route-back re-plan' が無いことを確認する。既存の hook 挙動テスト（tests/test_queue_stop_guard.py）が変更なしで通る。
- [ ] TS-6（AC-7）: 既存の tests/test_workflow_patch_doc.py の割当規則テストと、tests/test_replanning_producer_alignment.py の引用テストが変更なしで通る。
- [ ] TS-7（AC-8）: replace-all-task-id-reused ブロック付近の validator コメントが、`entries` で登録済み id を再宣言すると主張していないことを確認する。既存の tests/test_validate_worker_output.py のフィクスチャが変更なしで通る。
- [ ] TS-8（AC-9）: version bump のテストモジュールが、plugin.json と marketplace.json の em-workflow の version が一致し、tests/*_version_bump.py が固定している既存の基準値の最大より厳密に大きいことを確認する。

### 結合テスト
- [ ] TS-9（AC-10）: `python3 -m unittest discover -s tests` を実行し、すべてのテストが通る。

### E2E テスト
**既存の E2E テスト**: なし
**実行コマンド**: 未検出

### エッジケース
該当なし

### 性能テスト
該当なし

## セキュリティ上の考慮

該当なし

## エラー処理

該当なし

## 性能最適化

該当なし

## 成功基準

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

## 未解決事項

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## 仮定

- A1: validate-worker-output.py:1492-1494 の古いコメントを carried_task_ids 規則に合わせて直す。コードは変更しない（FR7）。
- A2: em-workflow の version を plugin.json と marketplace.json の両方で、同じ変更の中で patch bump する（FR8）。
- A3: 削除する I.2.c の文言を固定しているテストのリテラル（tests/test_implement_routeback_gate.py の THIRD_CONJUNCT_NARROWING_PHRASE、NO_RECYCLED_ID_INHERITS_MERGED_VIA_WRITE_SET_PHRASE、2276 行のアンカーテスト）を同じ変更で更新する。
- A4: workflow-patch.md の 'Re-planning task-id allocation'（再発行しない、最大 id より上から採番、carried_task_ids でそのまま保持）が唯一の所有 SSOT である。implement-phase.md は引用のみ。
- A5: `deny_already_merged`、I.2.c の第三条件、failed+pending carve-out は挙動を維持する。書き直すのは根拠のみで、タスク自身の id の観点で書く。
- A6: 'recycled-task-id carve-out' の語はラベルとして維持する。直すのは I.2.c の前提の文と `queue_stop_guard.py` の docstring のみ。
- A7: I.2.c の 'The planner re-scopes the failed task (split it, change the approach)' を、この feature の中で carried-verbatim 規則に合わせ、所有 SSOT を引用して書き直す。
- A8: design step は skip する。

## 参照

- 要件定義書: `feature-docs/task-id-allocation-ssot/REQUIREMENTS.md`
- task id 割当の所有 SSOT: `em-workflow/references/workflow-patch.md`（'Re-planning task-id allocation'）
- 変更対象の主文書: `em-workflow/references/implement-phase.md`（I.2.a、I.2.c）
