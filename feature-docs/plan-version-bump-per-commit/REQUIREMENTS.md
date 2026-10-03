---
title: "plan-version-bump-per-commit"
created_date: 2026-10-03
status: draft
---

# plan-version-bump-per-commit - 要件定義書

## 1. 概要

### 1.1 背景
create-plan / rework の計画が示すプラグインの version の扱いが、plugin-version-guard のコミット単位の判定と矛盾しうる。同じプラグインを触るタスクが複数ある batch 実行では、version 起因の git commit 拒否により implement フェーズが中断しうる。

### 1.2 目的
- create-plan / rework の計画が plugin-version-guard のコミット単位の判定と矛盾しない version の扱いを定め、implementer が guard と矛盾する指示を受けないようにする
- 同じプラグインを触るタスクが複数ある batch 実行で、version 起因の git commit 拒否により implement フェーズが中断しないようにする

### 1.3 スコープ
対象:
- plan-writing スキルの計画規則（非免除リポジトリ・免除リポジトリでの version の扱い）
- rework-planner.md / rework-planner-contract.md / rework-task-synthesis.md からの plan-writing 規則の参照
- 免除判定とプラグイン位置の dispatch 時解決（planner-contract.md / rework-planner-contract.md / create-plan-phase.md / rework の dispatch 手順）
- worktree-task-workflow スキルの親側採用プロトコル
- 上記を検出する tests/ 配下のテスト

対象外:
- `~/.claude/hooks/plugin-version-guard.py` 自体の変更（A5）
- 中断中の feature destructive-guard-heredoc-reset-hard（IMPLEMENTATION.md D3 の書き換え・task0003 の再開）（A4）

## 2. ビジネス要件

### 2.1 ビジネス目標
- create-plan / rework の計画が plugin-version-guard のコミット単位の判定と矛盾しない version の扱いを定め、implementer が guard と矛盾する指示を受けないようにする
- 同じプラグインを触るタスクが複数ある batch 実行で、version 起因の git commit 拒否により implement フェーズが中断しないようにする

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| implementation-planner / rework-planner | 計画規則に従って計画・追加タスクを作る |
| implementer | 計画の指示に従ってコミットする |
| orchestrator | create-plan / rework の dispatch で免除判定とプラグイン位置を解決して渡す |

### 2.3 期待される効果
- implementer が plugin-version-guard と矛盾する指示を受けない
- 同じプラグインを触るタスクが複数ある batch 実行で、version 起因の git commit 拒否により implement フェーズが中断しない

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 非免除リポジトリで同一プラグインを触る複数タスクを計画する | implementation-planner | 高 |
| UC02 | 免除リポジトリで計画する | implementation-planner | 高 |
| UC03 | rework の追加タスクを合成する | rework-planner | 高 |

### 3.2 ユースケース詳細

#### UC01: 非免除リポジトリで同一プラグインを触る複数タスクを計画する

**アクター**: implementation-planner

**事前条件**:
- リポジトリルートに `.github/workflows/plugin-version-bump.yml` が無い
- 同一プラグインを触るタスクが 2 つ以上ある

**基本フロー**:
1. orchestrator が免除判定とプラグイン位置を解決し、planning_inputs に値として渡す（FR5）
2. planner がプラグイン配下を変える全コミットでの version 上げを指示する（FR1）
3. planner は据え置きを指示せず、該当タスクの files に plugin.json と（version を持つ項目がある場合）marketplace.json を含める（FR2）

**事後条件**:
- 計画はプラグイン配下を変える全コミットでの version 上げを指示し、据え置きを指示しない（AC1）

#### UC02: 免除リポジトリで計画する

**アクター**: implementation-planner

**事前条件**:
- リポジトリルートに `.github/workflows/plugin-version-bump.yml` がある

**基本フロー**:
1. orchestrator が免除判定を解決し、planning_inputs に値として渡す（FR5）
2. planner は version の変更をタスクに指示しない。minor / major を上げる場合だけ上げる位置を書き、具体値は書かない（FR3）

**事後条件**:
- 計画は version 変更を指示しない（AC2）

#### UC03: rework の追加タスクを合成する

**アクター**: rework-planner

**事前条件**:
- orchestrator が rework の dispatch で免除判定とプラグイン位置を入力に渡している（FR5）

**基本フロー**:
1. rework-planner が plan-writing の version 規則（FR1〜FR3）を追加タスクに適用する（FR4）

**事後条件**:
- 追加タスクに同じ規則が適用される（AC3）

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 | 状態 |
|----|--------|------|--------|------|
| FR1 | 非免除リポジトリでのコミット単位の version 上げ規則 | プラグイン配下を変える全コミットが同じコミットで patch を上げる | 高 | assumed |
| FR2 | guard と矛盾する計画指示の禁止 | version 据え置きの指示を含めず、files に plugin.json / marketplace.json を含める | 高 | confirmed |
| FR3 | 免除リポジトリでの扱い | version の変更をタスクに指示しない | 高 | confirmed |
| FR4 | rework-planner への同一規則の適用 | rework 側文書から plan-writing の規則を参照する | 高 | confirmed |
| FR5 | 免除判定とプラグイン位置の dispatch 時解決 | orchestrator が dispatch ごとに解決し planner 入力に値として渡す | 高 | assumed |
| FR6 | 競合プロトコルでの version | 親側採用コミット・再実装コミットの version 規則 | 高 | assumed |
| FR7 | 再発検出テスト | FR1〜FR6 の記載と据え置き許容記述の不在を検出する | 高 | confirmed |

### 4.2 機能詳細

#### FR1: 非免除リポジトリでのコミット単位の version 上げ規則

**説明**: plan-writing スキルの計画規則に次を定める。非免除リポジトリ（リポジトリルートに `.github/workflows/plugin-version-bump.yml` が無い）では、プラグイン配下（`.claude-plugin/plugin.json` を持つディレクトリ配下）のファイルを変更する全コミットが、同じコミットでそのプラグインの plugin.json の version の patch を上げる。`.claude-plugin/marketplace.json` の同名プラグイン項目が version を持つ場合は同じ値に揃える。1 タスク内に該当コミットが複数あれば version はコミットごとに進む。上げた値は直前の HEAD の値より大きい（per-component の数値比較で厳密に大きい）。

**状態**: assumed（A1）

**ビジネスルール**:
- 新規追加のプラグイン（base に plugin.json が無い）と、version を持たない marketplace 項目は上げ・揃えの対象にしない（A7）

#### FR2: guard と矛盾する計画指示の禁止

**説明**: 非免除リポジトリの計画（IMPLEMENTATION.md / タスク計画）は「最初のタスクだけが version を上げる」「後続タスク・rework タスクは version を上げない」のように、プラグイン配下を変えるコミットで version を据え置く指示を含めない。プラグイン配下を変えるタスクの files には、そのプラグインの plugin.json と（version を持つ項目がある場合）marketplace.json を含める。

**状態**: confirmed

#### FR3: 免除リポジトリでの扱い

**説明**: 免除リポジトリ（`.github/workflows/plugin-version-bump.yml` がある）では、計画は version の変更をタスクに指示しない。minor / major を上げる場合だけ上げる位置を書き、具体値は書かない。

**状態**: confirmed

#### FR4: rework-planner への同一規則の適用

**説明**: rework-planner が合成する追加タスクにも FR1〜FR3 と同じ version の扱いを適用する。rework-planner.md / rework-planner-contract.md / rework-task-synthesis.md から plan-writing の規則を参照し、規則本文は再記述しない。

**状態**: confirmed

#### FR5: 免除判定とプラグイン位置の dispatch 時解決

**説明**: orchestrator が create-plan と rework の dispatch ごとに、対象 worktree のリポジトリが免除か（`.github/workflows/plugin-version-bump.yml` の有無）と、プラグインの位置（`.claude-plugin/plugin.json` を持つディレクトリと marketplace.json の version を持つ項目）を解決し、implementation-planner の planning_inputs と rework-planner の入力に値として渡す。この値は両 worker の input_digest の value_inputs に含める。planner-contract.md の「planner には value_inputs が無い」という記述はこれに合わせて改める。create-plan-phase.md の Planner dispatch と rework の dispatch 手順に、この値を渡すことを記す。

**状態**: assumed（A3）

#### FR6: 競合プロトコルでの version

**説明**: worktree-task-workflow スキルの親側採用プロトコルに、非免除リポジトリでの例外を加える。親側採用コミット（`{task_id}: resolve via parent-side adoption`）がプラグイン配下を変える場合、そのコミットの version は親側の値とタスク側 HEAD の値の両方より大きくする。再実装コミット（`{task_id}: re-implement on updated parent`）は採用後の HEAD の値より大きくする。marketplace.json の対応項目も同じ値に揃える。免除リポジトリでは追加の手順を行わない。

**状態**: assumed（A2）

#### FR7: 再発検出テスト

**説明**: tests/ に、FR1〜FR6 の規則が該当文書に記載されていること、および非免除リポジトリで version を据え置く指示を許す記述が無いことを検出するテストを置く。

**状態**: confirmed

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR1（SSOT）: version の扱いの規則本文は plan-writing スキル（計画側）と worktree-task-workflow スキル（競合時の実装側）に置き、contract / agent / phase 文書は参照で示し再記述しない
- NFR2（計画にコードを書かない）: plan-writing の No Concrete Code 規則に従い、追加する規則は振る舞いの記述にとどめる
- NFR3（テストの依存）: テストは Python 標準ライブラリの unittest のみを使い、`python3 -m unittest discover -s tests` で走る。実環境の `~/.claude` 配下を読まない・書かない
- NFR4（本リポジトリでの version）: 本リポジトリは免除リポジトリのため、この feature の実装タスクは em-workflow の plugin.json / marketplace.json の version を変更しない。SPEC・計画・受け入れ条件に version の具体値を書かない

### 5.5 互換性要件
該当なし

## 6. UI/UX要件

該当なし（デザインステップは skip: UI を持たない文書・計画規則の変更のため）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- `~/.claude/hooks/plugin-version-guard.py` 自体は変更しない。guard は値の不一致だけを拒否し増加は検証しないため、増加の要求は計画規則側で定める（A5）
- 本リポジトリは免除リポジトリのため、実装タスクは em-workflow の plugin.json / marketplace.json の version を変更しない（NFR4）

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/plan-version-bump-per-commit/**`
- `test-docs/plan-version-bump-per-commit/**`

`feature-docs/plan-version-bump-per-commit/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/plan-version-bump-per-commit/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/plan-version-bump-per-commit/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/plan-version-bump-per-commit/` ディレクトリを生成しないが、宣言された `test-docs/plan-version-bump-per-commit/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| merge-task.sh は commit-tree で合成するため、2 タスクが同じ値に上げた場合は競合せずにマージされる | 低 | 統合ブランチの version は base より進んでおり、追加の対処は求めない（A6） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 非免除リポジトリで同一プラグインを触るタスクを 2 つ以上計画したとき、計画はプラグイン配下を変える全コミットでの version 上げを指示し、据え置きを指示しない（FR1, FR2）
- [ ] AC2: 免除リポジトリでの計画は version 変更を指示しない（FR3）
- [ ] AC3: rework-planner の追加タスクに同じ規則が適用されることが rework 側文書から参照されている（FR4）
- [ ] AC4: implementation-planner と rework-planner の入力に免除判定とプラグイン位置が値として定義され、input_digest の value_inputs に含まれ、create-plan / rework の dispatch 手順に記載されている（FR5）
- [ ] AC5: worktree-task-workflow の競合プロトコルに、非免除リポジトリでの採用コミット・再実装コミットの version 規則が記載されている（FR6）
- [ ] AC6: 上記を検出するテストが tests/ にあり、`python3 -m unittest discover -s tests` が通る（FR7, NFR3）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
| ID | シナリオ | 期待結果 | 種別 | 要件 |
|----|----------|----------|------|------|
| TS-1 | plan-writing SKILL.md に非免除リポジトリのコミット単位の version 上げ規則（marketplace.json の揃え、1 タスク内の複数回上げ、厳密に大きい値）がある | 記載がありテストが通る | Unit | FR1 |
| TS-2 | plan-writing SKILL.md に据え置き指示の禁止と、プラグイン配下を変えるタスクの files に plugin.json / marketplace.json を含める規則がある | 記載がありテストが通る | Unit | FR2 |
| TS-3 | plan-writing SKILL.md に免除リポジトリでは version を指示しない規則と判定基準（`.github/workflows/plugin-version-bump.yml` の有無）がある | 記載がありテストが通る | Unit | FR3 |
| TS-4 | rework-planner.md / rework-planner-contract.md / rework-task-synthesis.md が plan-writing の version 規則を参照している | 参照がありテストが通る | Unit | FR4 |
| TS-5 | planner-contract.md と rework-planner-contract.md に免除判定・プラグイン位置の入力と value_inputs への算入が定義され、create-plan-phase.md と rework の dispatch 手順に渡す記載がある | 記載がありテストが通る | Unit | FR5 |
| TS-6 | worktree-task-workflow SKILL.md の競合プロトコルに、採用コミットは親側とタスク側 HEAD の両方を上回る値、再実装コミットは採用後 HEAD を上回る値にする非免除リポジトリの規則がある | 記載がありテストが通る | Unit | FR6 |
| TS-7 | `python3 -m unittest discover -s tests` を実行する | exit 0 | Integration | FR7, NFR3 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 免除リポジトリ | リポジトリルートに `.github/workflows/plugin-version-bump.yml` があるリポジトリ |
| 非免除リポジトリ | リポジトリルートに `.github/workflows/plugin-version-bump.yml` が無いリポジトリ |
| プラグイン配下 | `.claude-plugin/plugin.json` を持つディレクトリ配下 |
| 親側採用コミット | `{task_id}: resolve via parent-side adoption` のコミット |
| 再実装コミット | `{task_id}: re-implement on updated parent` のコミット |

## 14. 確認事項

### 14.1 確認済み事項

status: confirmed の要件は FR2 / FR3 / FR4 / FR7。

前提（requirements-analyst の assumptions。いずれも可逆）:

- A1: 非免除リポジトリでは、プラグイン配下を変える全コミットが同じコミットで patch を上げる（create-spec-q0001: per_commit_bump）
- A2: worktree-task-workflow の競合プロトコルも本 feature で改める（create-spec-q0001: include_worktree_task_workflow）
- A3: 免除判定とプラグイン位置は orchestrator が dispatch ごとに解決して planner 入力に値として渡す（create-spec-q0001: orchestrator_resolves_per_dispatch）
- A4: 中断中の feature destructive-guard-heredoc-reset-hard（IMPLEMENTATION.md D3 の書き換え・task0003 の再開）は本 feature の範囲外（create-spec-q0001: out_of_scope）
- A5: `~/.claude/hooks/plugin-version-guard.py` 自体は変更しない。guard は値の不一致だけを拒否し増加は検証しないため、増加の要求は計画規則側で定める
- A6: merge-task.sh は commit-tree で合成するため、2 タスクが同じ値に上げた場合は競合せずにマージされる。この場合も統合ブランチの version は base より進んでおり、追加の対処は求めない
- A7: 新規追加のプラグイン（base に plugin.json が無い）と、version を持たない marketplace 項目は guard の対象外であり、上げ・揃えの対象にしない

### 14.2 未確認・保留事項
- status: tbd の要件は無い
- status: assumed の要件: FR1（A1）、FR5（A3）、FR6（A2）

## 15. 参考資料

- SPEC.md: `feature-docs/plan-version-bump-per-commit/SPEC.md`
