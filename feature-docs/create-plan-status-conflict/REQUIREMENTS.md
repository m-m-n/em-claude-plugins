---
title: "create-plan-status-conflict"
created_date: 2026-08-13
status: draft
---

# create-plan-status-conflict - 要件定義書

## 1. 概要

### 1.1 背景

create-plan フェーズを protocol どおりに実行すると、必ず `replace-all-not-permitted` で落ちる。`skills/develop/SKILL.md` Step B は step 実行前に status を `in_progress` へ更新することを求める一方、`references/workflow-patch.md` の application rule 5 は `replace_all` を create-plan が `pending` または `needs_update` のときだけ許可する。さらに `scripts/validate-worker-output.py` の `_validate_dry_run_apply` 内 replace_all チェック（現行 1168-1176 行、`current_status not in ("pending", "needs_update")`）が同じ条件で拒否するため、protocol どおりの実行が validator に弾かれる。

### 1.2 目的

- create-plan フェーズが protocol どおりに実行すると必ず `replace-all-not-permitted` で落ちる矛盾を解消し、無人実行が create-plan を通過できるようにする。
- `skills/develop/SKILL.md` Step B / `references/workflow-patch.md` rule 5 / `scripts/validate-worker-output.py` の三者が、`in_progress` の create-plan step に対する `replace_planning` patch の扱いについて一意の仕様を共有する状態にする。

### 1.3 スコープ

対象は em-workflow プラグイン内の SSOT ドキュメント（`skills/develop/SKILL.md` Step B、`references/phases/create-plan-phase.md`）、リポジトリルート `tests/` のテスト、および `em-workflow/.claude-plugin/plugin.json` の version。

スコープ外:

- `append_rework`（rework-planner 経路）の permission conditions
- validator の `mode == "append"` 分岐
- `references/rework-task-synthesis.md`
- `references/workflow-patch.md` の rule 5 本文（無変更）
- `scripts/validate-worker-output.py` の判定ロジック、hooks、shell スクリプトの挙動（無変更）

## 2. ビジネス要件

### 2.1 ビジネス目標

- create-plan フェーズが protocol どおりに実行すると必ず `replace-all-not-permitted` で落ちる矛盾を解消し、無人実行が create-plan を通過できるようにする。
- `skills/develop/SKILL.md` Step B / `references/workflow-patch.md` rule 5 / `scripts/validate-worker-output.py` の三者が、`in_progress` の create-plan step に対する `replace_planning` patch の扱いについて一意の仕様を共有する状態にする。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| `/em-workflow:develop` の利用者 | create-plan フェーズを手動介入なしに完了させたい |
| 無人実行（`--batch`） | ユーザー対話なしに create-plan を `completed` へ到達させる必要がある |

### 2.3 期待される効果

- `--batch` 実行の create-plan フェーズがユーザー対話なしに `completed` へ到達できる。
- `in_progress` の create-plan step に対する `replace_planning` patch の扱いが、三者のドキュメント・実装で一意に定まる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 初回計画（`pending` で create-plan に入る） | `/em-workflow:develop` | 高 |
| UC02 | 明示的な再計画（`needs_update` で create-plan に入る） | `/em-workflow:develop` | 高 |
| UC03 | `in_progress` で中断した feature の復旧 | `/em-workflow:develop` | 高 |

### 3.2 ユースケース詳細

#### UC01: 初回計画（`pending` で create-plan に入る）

**アクター**: `/em-workflow:develop`

**事前条件**:
- workflow.yaml の create-plan step が `pending`

**基本フロー**:
1. Step B に入るが、create-plan は pre-dispatch `in_progress` 更新の例外のため status を変更しない。
2. `pending` のまま planner を dispatch する。
3. planner が `replace_planning`（`replace_all`）patch を提案する。
4. rule 5 の 1 つ目の分岐（create-plan が `pending`）により patch が許可され、適用とコミットが成功する。
5. create-plan を `completed`（+ `completed_at_commit`、規則 R2）へ直接進める。

**代替フロー**:
- patch の適用またはコミットが失敗した場合、`completed` へは進めない。

**事後条件**:
- create-plan step が `completed` になっている。

#### UC02: 明示的な再計画（`needs_update` で create-plan に入る）

**アクター**: `/em-workflow:develop`

**事前条件**:
- workflow.yaml の create-plan step が `needs_update`

**基本フロー**:
1. 例外は入口 status を上書きしないため、`needs_update` のまま planner を dispatch する。
2. rule 5 の 2 つ目の分岐（create-plan が `needs_update`）により patch が許可される。
3. 適用とコミットの成功後、create-plan を `completed` へ進める。

**事後条件**:
- create-plan step が `completed` になっている。

#### UC03: `in_progress` で中断した feature の復旧

**アクター**: `/em-workflow:develop`

**事前条件**:
- workflow.yaml の create-plan step が `in_progress`

**基本フロー**:
1. `references/phases/create-plan-phase.md` の「3. Reconcile on entry」で、提案済み patch が未適用かを判定する。
2. 未適用の場合、planner を dispatch する前に create-plan を `pending` へ戻し、Step B の規律どおり `commit-docs.sh` でコミットする。
3. `pending` として UC01 の流れで実行する。

**代替フロー**:
- patch が既に適用済みの場合はリセットを行わず、既存の §11 / `references/phase-state.md` Resume 決定表（`applying_patch`(applied) 行）に従って `completed` への遷移だけを実行する。

**事後条件**:
- create-plan step が `pending` から再実行されるか、`completed` へ遷移している。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | create-plan を Step B の pre-dispatch `in_progress` 更新から除外する | create-plan は dispatch 前に status を変更せず、フェーズ完了後に `completed` へ直接進める | 高 |
| FR2 | 例外は入口 status を保存し、`needs_update` 分岐を到達可能に保つ | `pending` / `needs_update` の入口 status をそのまま維持する | 高 |
| FR3 | 例外の根拠を Step B に明記する | 既存 backfill 節と同じ体裁で理由を添える | 高 |
| FR4 | workflow-patch.md rule 5 は変更しない | `replace_all` permission conditions と rule 5 を現状の文言のまま維持する | 高 |
| FR5 | validator の許可条件は変更しない | 現行実装が更新後仕様と一致するため機能変更なし、退行テストのみ追加 | 高 |
| FR6 | 中断復旧規則を create-plan-phase.md の Reconcile on entry に追加する | `in_progress` かつ patch 未適用なら `pending` へ戻す | 高 |
| FR7 | プラグイン内の記述整合 | FR1 の例外と矛盾する記述を残さない | 中 |
| FR8 | テストの更新・追加 | doc assertion テストと validator 退行テストを追加する | 高 |
| FR9 | プラグイン version bump | plugin.json の version を 0.1.34 → 0.1.35 へ patch bump | 中 |

### 4.2 機能詳細

#### FR1: create-plan を Step B の pre-dispatch `in_progress` 更新から除外する

**説明**: `skills/develop/SKILL.md` Step B は、create-plan step に限り「step 実行前に `in_progress` へ更新する」規則の例外とする。create-plan は dispatch 前に status を変更せず、フェーズ完了（patch の適用とコミットの成功）後に `completed`（+ `completed_at_commit`、規則 R2）へ直接進める。

**ビジネスルール**:
- pre-dispatch の status 更新を行わない。
- `completed` への遷移は patch の適用とコミットの成功後に限る。

#### FR2: 例外は入口 status を保存し、`needs_update` 分岐を到達可能に保つ

**説明**: 例外は create-plan の入口 status を上書きしない。`pending`（初回計画）で入れば `pending` のまま、`needs_update`（明示的な再計画）で入れば `needs_update` のまま planner を dispatch する。これにより rule 5 が許可する 2 つの分岐が両方とも実際に到達可能になる。

**ビジネスルール**:
- 入口 status を書き換えない。

#### FR3: 例外の根拠を Step B に明記する

**説明**: Step B の例外記述には理由を添える。

**ビジネスルール**:
- (a) `replace_all` は create-plan が `pending` / `needs_update` のときだけ許可される（`references/workflow-patch.md` rule 5 を参照するのみで、条件本文は複製しない）。
- (b) create-plan の中断復旧は `phase-state/create-plan.yaml` が担うため `in_progress` マーカーを必要としない。
- 記述形式は既存の design-system backfill の「**`in_progress` へ先に更新しない理由**」節と同じ体裁に揃える。

#### FR4: workflow-patch.md rule 5 は変更しない

**説明**: `references/workflow-patch.md` の「`replace_all` permission conditions」節および application rule 5 は現状の文言のまま変更しない（create-plan が `pending` または `needs_update` のときのみ許可）。

#### FR5: validator の許可条件は変更しない（挙動は更新後の仕様と一致済み）

**説明**: `scripts/validate-worker-output.py` の `_validate_dry_run_apply` 内 replace_all チェック（現行 1168-1176 行、`current_status not in ("pending", "needs_update")`）は機能変更しない。FR1/FR2 の下では planner dispatch 時の create-plan status が常に `pending` か `needs_update` になるため、現行実装がそのまま更新後仕様と一致する。変更は退行テストの追加のみ（FR8）。

#### FR6: 中断復旧規則を create-plan-phase.md の Reconcile on entry に追加する

**説明**: `references/phases/create-plan-phase.md` の「3. Reconcile on entry」に規則を 1 つ追加する。

**ビジネスルール**:
- 入口で `workflow.yaml` の create-plan step が `in_progress` であり、かつ提案済み patch が未適用の場合、planner を dispatch する前に create-plan を `pending` へ戻し、Step B の規律どおり `commit-docs.sh` でコミットする。
- patch が既に適用済みの場合はこのリセットを行わず、既存の §11 / `references/phase-state.md` Resume 決定表（`applying_patch`(applied) 行）に従って `completed` への遷移だけを実行する。

#### FR7: プラグイン内の記述整合

**説明**: `references/phase-state.md`（Resume 決定表・legacy compatibility 表・backfill 節）をはじめとする他の SSOT に、FR1 の例外と矛盾する「全 step を実行前に `in_progress` にする」旨の記述が残らないようにする。Resume 決定表は phase-state の `status` をキーにしており workflow step status に依存しないため、本 feature の既定では `phase-state.md` の変更は不要と判断する。変更が必要な箇所が見つかった場合は同一変更内で更新する。

#### FR8: テストの更新・追加

**説明**: リポジトリルート `tests/` に以下を検証する assertion を追加する。

- (a) develop SKILL.md Step B に create-plan 例外とその根拠が記述されていること
- (b) create-plan-phase.md §3 に in_progress → pending リセット規則が記述されていること
- (c) workflow-patch.md の rule 5 が `pending` / `needs_update` のままであること
- (d) validator が `in_progress` の create-plan に対する `replace_all` を引き続き拒否すること

既存の `tests/test_develop_skill_rewiring.py`（Step B 文字列と backfill 順序）、`tests/test_phase_protocols.py`（create-plan-phase.md セクション構成）、`tests/test_workflow_patch_doc.py`、`tests/test_validate_worker_output.py` が引き続き通ることを保証し、必要なら同一変更内で更新する。

#### FR9: プラグイン version bump

**説明**: `em-workflow/.claude-plugin/plugin.json` の `version` を 0.1.34 → 0.1.35 へ patch bump する。ルート `.claude-plugin/marketplace.json` の em-workflow エントリは `version` フィールドを持たない（name / description / author / category / source のみ）ため、変更は不要。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし。

### 5.2 セキュリティ要件

- `replace_all` の第 1 条件（tasks が空、または全 task が pending）は緩めない。
- `completed` / `failed` の create-plan に対する `replace_all` は引き続き拒否されること。
- worker が workflow.yaml を直接書かない所有境界（workflow-schema.md の Write ownership）は変更しない。

### 5.3 可用性要件

- **NFR4 - 無人実行での完走**: 変更後、`--batch` 実行の create-plan フェーズがユーザー対話なしに `completed` へ到達できること。

### 5.4 保守性要件

- **NFR1 - スコープ外の維持**: `append_rework`（rework-planner 経路）の permission conditions、validator の `mode == "append"` 分岐、`references/rework-task-synthesis.md` は一切変更しない。
- **NFR2 - 実行時ロジックの非変更**: 変更はドキュメント（SSOT prose）+ テスト + version のみ。`validate-worker-output.py` の判定ロジック、hooks、shell スクリプトの挙動は変更しない。
- **NFR3 - SSOT 所有境界の保持**: develop SKILL.md は rule 5 の条件本文を複製せず参照に留める。各ドキュメントは既存の「restate しない」規律（`tests/test_phase_protocols.py` の must-not-restate assertions）を破らない。

### 5.5 互換性要件

- phase-state が存在しない legacy feature で create-plan が `in_progress` のケースについて、`references/phase-state.md` の legacy compatibility 表（該当フェーズを新フローで再開）と FR6 のリセット規則が同じ結論（pending から再実行）に落ちること。

## 6. UI/UX要件

この feature に UI は無い。ユーザーから見える挙動は `/em-workflow:develop` の create-plan フェーズが手動介入なしに完了すること。

### 6.1 画面設計要件

該当なし。

### 6.2 画面遷移

該当なし。

### 6.3 レスポンシブ対応

該当なし。

## 7. データ要件

該当なし（変更対象はドキュメント・テスト・version のみ）。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 変更はドキュメント（SSOT prose）+ テスト + version のみ。実行時ロジック（validator の判定、hooks、shell スクリプト）は変更しない（NFR2）。
- develop SKILL.md は rule 5 の条件本文を複製せず参照に留める（NFR3）。
- `references/workflow-patch.md` rule 5 と validator の許可条件は変更しない（FR4 / FR5）。

### 9.2 ビジネス上の制約

- `append_rework` 経路および `references/rework-task-synthesis.md` はスコープ外（NFR1）。

### 9.3 スケジュール制約

該当なし。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `in_progress` で中断済みの既存 feature が復旧できない | 高 | FR6 の Reconcile on entry リセット規則で `pending` へ戻してから dispatch する |
| 停止条件 2（同じ step を 2 回連続実行しても status が進まない = スタック）との相互作用 | 中 | create-plan は `in_progress` を経由しなくなるため、スタック判定は `pending`（または `needs_update`）が 2 回続くかで行われる。正常な 1 回の実行では `completed` へ到達するため誤検知しないことを確認する（EC4） |
| create-plan step が `in_progress` であることを前提にする他の機構の存在 | 中 | queue 系 hook は implement step / tasks status のみを参照する想定であることを確認する（EC5） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 無人実行が create-plan で停止し続ける | 高 | 高 | FR1 / FR2 / FR6 により `pending` / `needs_update` のみで dispatch されるようにする |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `in_progress` の create-plan step に対する `replace_planning` patch の扱いが一意に決まっている — 「そもそも dispatch 時に create-plan が `in_progress` にならない。もし `in_progress` で中断していた場合は Reconcile on entry が `pending` へ戻してから dispatch する。`in_progress` のまま提出された patch は rule 5 により拒否される」。
- [ ] AC2: `skills/develop/SKILL.md` Step B と `references/workflow-patch.md` rule 5 が矛盾しない（Step B が create-plan を例外化し、rule 5 は無変更）。
- [ ] AC3: `scripts/validate-worker-output.py` の挙動が更新後の仕様と一致する（機能変更なしで一致し、その一致が退行テストで固定されている）。
- [ ] AC4: `references/phases/create-plan-phase.md` の Reconcile on entry を読んだだけで、`in_progress` で中断した既存 feature の復旧手順が決定的にたどれる。
- [ ] AC5: `python3 -m unittest discover -s tests` が全て pass する。
- [ ] AC6: `em-workflow/.claude-plugin/plugin.json` の version が bump されている。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系（TS-1）: develop SKILL.md Step B のテキストに create-plan 例外と根拠が含まれ、既存の backfill 順序 assertion（backfill 記述が汎用 `in_progress` 更新文より前）も同時に成立することを検証する doc assertion テスト。
- [ ] 正常系（TS-2）: create-plan-phase.md §3 に「create-plan が `in_progress` かつ patch 未適用なら `pending` へ戻してから dispatch」規則が存在し、patch 適用済みの場合はリセットしない旨も併記されていることを検証する doc assertion テスト。
- [ ] 正常系（TS-3）: workflow-patch.md の `replace_all` permission conditions 節が `pending` / `needs_update` の 2 条件を保持していることを検証する（既存 `tests/test_workflow_patch_doc.py` の拡張または新規）。
- [ ] 異常系（TS-4）: create-plan step が `in_progress` の workflow.yaml に対して `replace_all` patch を `--dry-run-apply` で検証すると exit 1 かつ `replace-all-not-permitted` を返すこと、`pending` および `needs_update` では通ることを検証する validator 退行テスト。
- [ ] 統合（TS-5）: `python3 -m unittest discover -s tests` の全体実行。

### 12.2 エッジケース

- [ ] EC1: 再計画で create-plan が `needs_update` の状態で Step B に入るケース。例外は status を書き換えないため `needs_update` のまま planner が dispatch され、rule 5 の 2 つ目の分岐で許可される。
- [ ] EC2: `in_progress` で中断したが patch は既に適用済みのケース。Reconcile はリセットせず、§11 と `references/phase-state.md` Resume 決定表の `applying_patch`(applied) 行に従って `completed` 遷移だけを実行する。
- [ ] EC3: phase-state が存在しない legacy feature で create-plan が `in_progress` のケース。`references/phase-state.md` の legacy compatibility 表（該当フェーズを新フローで再開）と FR6 のリセット規則が同じ結論（pending から再実行）に落ちることを確認する。
- [ ] EC4: 停止条件 2（同じ step を 2 回連続実行しても status が進まない = スタック）との相互作用。create-plan は成功しても途中で `in_progress` を経由しなくなるため、スタック判定は `pending`（または `needs_update`）が 2 回続くかで行われる。正常な 1 回の実行では `completed` へ到達するため誤検知しないことを確認する。
- [ ] EC5: create-plan step が `in_progress` であることを前提にしている他の機構が無いことの確認（queue 系 hook は implement step / tasks status のみを参照する想定）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| Step B | `skills/develop/SKILL.md` の step 実行手順。step 実行前に status を `in_progress` へ更新する規則を持つ |
| rule 5 | `references/workflow-patch.md` の application rule 5。`replace_all` を create-plan が `pending` または `needs_update` のときだけ許可する |
| `replace_planning` | create-plan が提案する workflow patch。`replace_all` モードで適用される |
| `replace-all-not-permitted` | rule 5 の条件を満たさない `replace_all` patch に対して validator が返すエラー |
| Reconcile on entry | `references/phases/create-plan-phase.md` の「3. Reconcile on entry」節。フェーズ入口の状態整合手順 |
| 規則 R2 | `completed` への遷移時に `completed_at_commit` を併せて記録する規則 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: status conflict の解消方向 — develop SKILL.md Step B を例外化する方向を採用する。create-plan は dispatch 前に `in_progress` にせず pending のまま実行し、patch 適用後に completed へ進める。workflow-patch.md rule 5 と validator の許可条件は変更しない。
      - 根拠: gate `create-spec.requirement-clarification` を batch-policies.yaml の `codex_consultation` で解決（source: batch-codex-consultation、selected_option_id: exempt-create-plan、record_as_assumption: true）。Codex は `in_progress` の意味づけを保ちつつ rule 5 の `pending` / `needs_update` 両分岐が到達可能になる点を根拠とした。タスク記述の申し送り（案(b)を優先検討）とも一致。
- [x] A2: 既存の `in_progress` 中断 feature の復旧方法 — create-plan-phase.md の Reconcile on entry に「patch 未適用のまま `in_progress` で中断していた場合は create-plan を `pending` に戻してから dispatch する」規則を追加して扱う。
      - 根拠: gate `create-spec.requirement-clarification` を batch-policies.yaml の `codex_consultation` で解決（source: batch-codex-consultation、selected_option_id: reconcile-resets、record_as_assumption: true）。Codex は validator を恒久的に緩めずに無人実行へ決定的な復旧経路を与える点を根拠とした。
- [x] A3: version bump の対象範囲 — `.claude-plugin/marketplace.json` は em-workflow エントリに `version` フィールドを持たないため、version bump の対象は plugin.json のみ。
      - 根拠: marketplace.json の実ファイル確認（plugins[] エントリは name / description / author / category / source のみ）。

### 14.2 未確認・保留事項

なし（すべての要件が `status: ok`）。

## 15. 参考資料

- `skills/develop/SKILL.md`: Step B（pre-dispatch status 更新規則、design-system backfill の「`in_progress` へ先に更新しない理由」節）
- `references/workflow-patch.md`: `replace_all` permission conditions / application rule 5
- `references/phases/create-plan-phase.md`: 3. Reconcile on entry、§11
- `references/phase-state.md`: Resume 決定表、legacy compatibility 表、backfill 節
- `scripts/validate-worker-output.py`: `_validate_dry_run_apply` の replace_all チェック（現行 1168-1176 行）
- `tests/test_develop_skill_rewiring.py` / `tests/test_phase_protocols.py` / `tests/test_workflow_patch_doc.py` / `tests/test_validate_worker_output.py`
- `em-workflow/.claude-plugin/plugin.json`: version（0.1.34 → 0.1.35）
