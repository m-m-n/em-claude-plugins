---
title: "task-tier-reduction"
created_date: 2026-09-21
status: draft
---

# task-tier-reduction - 要件定義書

## 1. 概要

### 1.1 背景

背景として個別に確定した事項は無い。本要件は 2.1 のビジネス目標に基づく。

### 1.2 目的

- 走行前にタスクの重さを判定し、em-workflow の走行段を full / reduced / minimal の 3 段階で軽減する。
- 判定を Codex の事前調査と Jev（System One）で行い、判定コストに Claude の週間枠を使わない。
- 判定不能・判定材料欠落時は常に full に倒す（fail-open ではなく fail-safe）。

### 1.3 スコープ

対象:

- tier 判定の規則・閾値・入出力スキーマの新設（FR1、FR4、FR5、FR6）
- `workflow.yaml` と関連文書への tier / tier_decision の導入（FR2、FR3、FR15）
- reduced / minimal の引き算内容と、それに伴う既存規定の緩和（FR9〜FR11、FR16〜FR18、FR21）
- 昇格経路と停止表現（FR7、FR12、FR19、FR24）
- 既存の固定アサーションと不変条件チェックへの整合（FR22、FR23、NFR3、NFR4）

対象外:

- 閾値の自動調整・学習（FR20）
- 外部タスク管理サービスのステータス・本文の操作（FR8）
- 外部コンシューマの受理語彙との歩調合わせ（FR7。新コードを文書化するところまでが対象）
- `validate-worker-output.py` の `WORKER_CAPABILITIES['requirements-analyst']['full'].required_payload` に関する既存の契約ドリフト（AS-11）

## 2. ビジネス要件

### 2.1 ビジネス目標

- 走行前にタスクの重さを判定し、em-workflow の走行段を full / reduced / minimal の 3 段階で軽減する。
- 判定を Codex の事前調査と Jev（System One）で行い、判定コストに Claude の週間枠を使わない。
- 判定不能・判定材料欠落時は常に full に倒す（fail-open ではなく fail-safe）。

### 2.2 対象ユーザー

対象ユーザーは個別に確定していない。

### 2.3 期待される効果

2.1 のビジネス目標の達成をもって効果とする。個別の効果は確定していない。

## 3. ユースケース

個別のユースケースは確定していない。機能の一覧は 4 章を参照。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 |
|----|--------|
| FR1 | tier-rules.yaml の新設 |
| FR2 | workflow.yaml の tier / tier_decision |
| FR3 | design 以外の step への skipped 許可 |
| FR4 | Jev 判定の入力と閾値 |
| FR5 | Codex 事前調査 |
| FR6 | 見積もりの Jev state への合流 |
| FR7 | work_still_required: false の停止表現 |
| FR8 | 外部タスク管理サービスに触れない |
| FR9 | reduced の引き算 |
| FR10 | minimal の引き算 |
| FR11 | minimal でもテストは全部走る |
| FR12 | 昇格のみ（降格禁止） |
| FR13 | フォールバック |
| FR14 | スタンドアロン経路 |
| FR15 | tier 判定結果の永続化と転記 |
| FR16 | minimal の requirements / tasks |
| FR17 | develop 駆動経路の spec 観点除外条件 |
| FR18 | create-plan 前提条件の tier 対応 |
| FR19 | 昇格時の再走行手順 |
| FR20 | retrospect への記録 |
| FR21 | 並列 worktree を引くの範囲 |
| FR22 | 既存の固定アサーションの更新 |
| FR23 | gate_id 双方向チェックへの整合 |
| FR24 | minimal からの rework 経路の明示 |

### 4.2 機能詳細

#### FR1: tier-rules.yaml の新設

`em-workflow/references/tier-rules.yaml` を新設し、Jev へ送る質問、閾値、Codex 出力スキーマを 1 箇所に集める。Jev スキル（`~/.claude/skills/jev`）と `typesafe:typesafe-ai` の内容は書き写さず参照に留める。

#### FR2: workflow.yaml の tier / tier_decision

`workflow.yaml` に `tier` と `tier_decision`（`by` / `confidence` / `at` / `reductions`）を追加し、`references/workflow-schema.md` にフィールド定義を書く。書き手はオーケストレーター単独（既存の単一書き手規則を変えない）。

#### FR3: design 以外の step への skipped 許可

`workflow[]` の `status: skipped` を design 以外の step にも許す。`references/workflow-schema.md` の Status semantics（`skipped` is valid ONLY for the `design` step）、`skills/develop/SKILL.md` の停止条件 1・Step B の status 規律（design 以外に skipped があれば YAML エラー扱いで停止）・Step C の入場条件・完了判定表を、tier による skip を認める形に改める。`skipped_reason` の必須性は維持する。

#### FR4: Jev 判定の入力と閾値

判定は Jev の `score` の `probabilities` を使い、`confidence` 単体で閾値を切らない。初期閾値は `P(0) >= 0.80` かつ `expectation_clear >= 0.5` で minimal、`P(0) >= 0.40` かつ `P(0) + P(1) >= 0.85` で reduced、それ以外は full。Jev は `--json-input` / `--json-output` で呼ぶ。

#### FR5: Codex 事前調査

走行開始前に `codex-harness:codex-cli` の `run_codex_exec.sh`（`readonly`）で変更範囲を見積もる。`codex exec` は直接呼ばない。出力は構造化スキーマで受け、触るファイルと変更行数の概算、新規の関数・ファイル・依存の要否、既存テストの有無、他モジュールへの波及、`work_still_required` を含む。

#### FR6: 見積もりの Jev state への合流

Codex の見積もり結果を Jev の `state` に足して判定する。記述のみの判定と、Codex 見積もりを足した判定の両方を `tier_decision` の根拠として残す。

#### FR7: work_still_required: false の停止表現

`work_still_required: false` のときは走行を始めず、`references/batch-terminal-line.md` の構造化結果で終端する。同文書の閉じた stop reason code 集合に新コードを 1 件追加し（`no_work_required`）、`## Stop point coverage` 表にも対応する 1 行を追加する。報告は `state: "stopped"` / `step: "no-step"`（workflow.yaml step が未発効の停止点）とし、`resume_conditions` は空にできない規定があるため「再開不要である」旨を非空文字列で明記する。既存コードの流用はしない（`completed` は retrospect 到達を意味するため意味が歪む）。stop-recovery に Codex の根拠を入れる。外部コンシューマの受理語彙との歩調合わせは本フィーチャでは「新コードを文書化するところまで」がスコープ。

#### FR8: 外部タスク管理サービスに触れない

Notion のステータス・本文は触らない。「中断」への遷移はディスパッチャの責務。`references/batch-terminal-line.md` の `## Responsibility boundary` を変えない。

#### FR9: reduced の引き算

`reduced` は `full` から REQUIREMENTS.md / IMPLEMENTATION.md / design を引く。

#### FR10: minimal の引き算

`minimal` は `reduced` からさらに SPEC.md（`TASK.md` に置き換え）/ `tasks/` の分割 / VERIFICATION.md / 並列 worktree を引く。`TASK.md` は「変更点」と「期待結果」の 2 つだけを持つ。

#### FR11: minimal でもテストは全部走る

`minimal` でも既存テストスイートは全部実行する。引くのは VERIFICATION.md という文書だけ。Step 0 の git-setup（gitleaks pre-commit）も全段階で走る。

#### FR12: 昇格のみ（降格禁止）

tier の変更は昇格のみ許す。review で critical が出た場合、verify が落ちた場合に tier を上げて再走行できる。降格は許さない。

#### FR13: フォールバック

Jev と Codex の両方が使えるときは記述 + 実コードで判定する。Jev だけのときは記述ベースで判定し、割れたら `full` に倒す。どちらも使えないときは `full`。Jev の終了コード（0 成功 / 1 その他 / 2 HTTP 401 / 75 HTTP 429 または 529）のうち非 0 はすべて「Jev 使用不可」として扱う。

#### FR14: スタンドアロン経路

スタンドアロン（`workflow.yaml` 起点・Notion 不在）でも同じ規則で動く。

#### FR15: tier 判定結果の永続化と転記

判定は Step A の feature 決定直後、workflow.yaml 構築前に起きる。判定直後に integration worktree の `feature-docs/{feature}/phase-state/` 配下へ保存して `commit-docs.sh` でコミットする（`phase-state.md` の `backfill.yaml` と同じ「どのフェーズにも属さない派生値」の先例に従う）。create-spec が workflow.yaml を構築する時点でオーケストレーターがそこへ転記し、workflow.yaml 単一書き手規則を保つ。構築後は workflow.yaml 側の `tier` を正とし、再開時の再転記で tier を降格させない。メモリ保持にしない理由は `skills/develop/SKILL.md` Step A の「ブートストラップ状態の判定」（workflow.yaml 未作成のまま中断・再開する経路）が実在するため。

#### FR16: minimal の requirements / tasks

`minimal` では `requirements: {}`（空）を正当な状態として認める。一方 `tasks` には TASK.md を参照する実タスクを 1 件残す。`tasks` はレビュー属性だけでなく実行状態（`status`）とブランチ（`branch`）も持ち、タスク完了は統合ブランチへのマージで定義されるため、`tasks/` の分割を省くこととタスクエントリ自体を省くことは別物。

#### FR17: develop 駆動経路の spec 観点除外条件

`references/review-rules.yaml` の `spec_review: always` は spec 観点を無条件に含める規定であり、SPEC.md 不在時に spec が落ちる規定は現状スタンドアロン `/em-workflow:review` にしか無い（同ファイルのヘッダコメントと `references/review-phase.md` の入力解決 4 番・Layer 1）。したがって「SPEC.md を作らなければ floor が自然に comprehensive + security に落ちる」は成り立たない。既存の「SPEC.md が無ければ spec 観点は skip notice 付きで落とす」規定を develop 駆動経路へ拡張し、`review-phase.md` の develop 駆動側「must exist; SDD guarantees it」を tier 条件下で緩める。これは tier による観点除去の分岐ではなく、既存規定の経路拡張である。

#### FR18: create-plan 前提条件の tier 対応

`references/phases/create-plan-phase.md` の前提「REQUIREMENTS.md と SPEC.md が存在する」「workflow.yaml の `requirements` が SPEC.md の FR/NFR 集合と一致する」を tier に応じて緩める。`reduced` は REQUIREMENTS.md 不在、`minimal` は SPEC.md 不在（TASK.md 参照）かつ `requirements: {}` を許す。

#### FR19: 昇格時の再走行手順

昇格は `skipped` の step を `pending` に戻すことで実現し、新しい status 値は導入しない。ただし `minimal` で TASK.md を作って `completed` になった create-spec は `skipped` 解除だけでは SPEC.md を補えないため、昇格手順に「完了済み step の再実行」を含める。あわせて `skills/develop/SKILL.md` の停止条件 3 自動再エントリ carve-out（現在「厳密に次の 2 つ」と網羅性を宣言している列挙: implement-phase.md I.2.c の create-plan route back、rework の spec-change 遷移）に、tier 昇格による再エントリを加えて列挙と網羅性宣言を更新する。

#### FR20: retrospect への記録

判定内容（tier、根拠、Jev の probabilities、Codex 見積もり）と実際の結果を retrospect に残す。閾値の自動調整・学習はスコープ外。

#### FR21: 並列 worktree を引くの範囲

`minimal` の「並列 worktree を引く」は integration worktree を残したまま、implement を単一タスク・単一タスク worktree で実行することを意味する。workflow.yaml と feature-docs 配下の文書は integration worktree にしか置かれず、verify / retrospect / Step C がその配置を前提にしているため、integration worktree は引かない。

#### FR22: 既存の固定アサーションの更新

stop reason code を 11 個から 12 個へ増やす変更は、個数を固定アサートしている既存テストを同じ変更で更新する。対象は `tests/test_failed_kind_batch_docs.py` の reason code 表アサーション、`tests/test_batch_quiet_output_discipline.py` の stop point coverage 行数・キー数アサーション（現在 11）、`tests/test_batch_stop_contract_skill_wiring.py` の REASON_CODES タプル。SSOT 表から動的抽出する `tests/test_structured_result_conformance.py` と `tests/test_structured_result_consumer_constraints.py` は自動追随するため回帰確認に留める。

#### FR23: gate_id 双方向チェックへの整合

tier 関連で新しい `gate_id` を導入する場合は、同じ変更で `references/batch-policies.yaml` に対応エントリを追加する。`scripts/check-plugin-invariants.py` の `gate_id_coverage` がプラグイン配下で使われる gate_id と batch-policies.yaml の双方向一致を検査するため。新しい `gate_id` を導入しない選択も許す。

#### FR24: minimal からの rework 経路の明示

`minimal`（VERIFICATION.md 不在）から rework 経路に入った場合の挙動を明示する。`scripts/validate-worker-output.py` の rework-planner 検証は VERIFICATION.md の diff を前提にしているため、昇格を経ずに rework が発火する経路が存在するなら、その経路での扱いを定める。

## 5. 非機能要件

### 5.1 非機能要件一覧

| ID | 名称 |
|----|------|
| NFR1 | 判定に Claude を使わない |
| NFR2 | security 観点は引けない |
| NFR3 | SSOT 分割の維持 |
| NFR4 | プラグイン version bump |
| NFR5 | 外部スキルの内容を複製しない |
| NFR6 | 無人実行を止めない |
| NFR7 | テストの依存制約 |

### 5.2 非機能要件詳細

#### NFR1: 判定に Claude を使わない

tier 判定の経路で Claude の推論を使わない。Codex（readonly）と Jev のみ。

#### NFR2: security 観点は引けない

`review-rules.yaml` の `baseline` に `security` が入っており、全 run・全粒度で選択され、どのルールも除去しない。tier 側で観点を引く分岐を作らない。

#### NFR3: SSOT 分割の維持

stop reason code の所有者は `references/batch-terminal-line.md` 単独であり、`references/batch-mode.md` と `skills/develop/SKILL.md` は文書を指すだけでコード文字列を restate しない（この不変条件は `tests/test_batch_stop_contract_skill_wiring.py` と `tests/test_batch_quiet_output_discipline.py` が機械検査している）。

#### NFR4: プラグイン version bump

`em-workflow/` 配下を変更するため、同じ変更で `em-workflow/.claude-plugin/plugin.json` と ルート `.claude-plugin/marketplace.json` の version を同値で上げる。機能追加のため minor。

#### NFR5: 外部スキルの内容を複製しない

Jev の呼び出し方（`~/.claude/skills/jev`）とモデル特性・質問設計（`typesafe:typesafe-ai`）は参照に留め、実装側・tier-rules.yaml に書き写さない。

#### NFR6: 無人実行を止めない

判定・停止経路のいずれも batch 実行で確認プロンプトを発生させない。

#### NFR7: テストの依存制約

追加・更新するテストはリポジトリルート `tests/` に `test_*.py` として置き、標準ライブラリ `unittest`（Python 3.14）のみを使う。テストコードは第三者パッケージを import しない。

## 6. UI/UX要件

該当なし。本フィーチャは em-workflow プラグインの文書・プロトコル変更のみで、UI 面・視覚要素を一切持たない。

## 7. データ要件

永続化する派生値は tier 判定結果のみで、保存先は `feature-docs/{feature}/phase-state/` 配下（FR15、AS-2）。データモデル・保持期間として個別に確定した事項は無い。

## 8. 外部連携

| システム名 | 連携方法 | 扱い |
|------------|----------|------|
| Jev（System One） | `~/.claude/skills/jev` を `--json-input` / `--json-output` で呼ぶ | 判定入力に `score` の `probabilities` を使う（FR4）。非 0 終了はすべて使用不可として扱う（FR13） |
| Codex | `codex-harness:codex-cli` の `run_codex_exec.sh`（`readonly`） | 変更範囲の事前見積もり。`codex exec` は直接呼ばない（FR5） |
| Notion | 連携しない | ステータス・本文を触らない。「中断」への遷移はディスパッチャの責務（FR8） |

## 9. 制約条件

### 9.1 技術的制約

- tier 判定の経路で Claude の推論を使わない（NFR1）。
- 判定不能・判定材料欠落時は full に倒す（ビジネス目標 3、FR13）。
- stop reason code の所有者は `references/batch-terminal-line.md` 単独。他文書はコード文字列を restate しない（NFR3）。
- Jev と `typesafe:typesafe-ai` の内容は参照に留め、書き写さない（FR1、NFR5）。
- batch 実行で確認プロンプトを発生させない（NFR6）。
- テストは `tests/test_*.py` に置き、標準ライブラリ `unittest`（Python 3.14）のみを使う（NFR7）。
- `workflow.yaml` の単一書き手規則（書き手はオーケストレーター単独）を変えない（FR2、FR15）。
- security 観点は tier に関係なく floor に残る（NFR2、AS-7）。
- integration worktree は全 tier で維持する（FR21、AS-5）。

### 9.2 ビジネス上の制約

- 外部タスク管理サービス（Notion）のステータス・本文を操作しない（FR8）。

### 9.3 スケジュール制約

確定した制約は無い。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/task-tier-reduction/**`
- `test-docs/task-tier-reduction/**`

`feature-docs/task-tier-reduction/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/task-tier-reduction/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/task-tier-reduction/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/task-tier-reduction/` ディレクトリを生成しないが、宣言された `test-docs/task-tier-reduction/**` は依然として正しい。

## 10. 想定される課題とリスク

個別の課題・リスクとして確定した事項は無い。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: `em-workflow/references/tier-rules.yaml` が存在し、Jev 質問・閾値・Codex 出力スキーマの 3 つを含む。
- [ ] AC-2: `references/workflow-schema.md` に `tier` と `tier_decision`（4 サブフィールド）の定義がある。
- [ ] AC-3: `references/workflow-schema.md` の Status semantics が design 以外の step の `skipped` を認め、`skills/develop/SKILL.md` の停止条件 1・Step B 規律・Step C 入場条件・完了判定表がそれに整合する。
- [ ] AC-4: 閾値判定が `probabilities` を入力とし、`confidence` 単体の閾値がどこにも書かれていない。
- [ ] AC-5: `references/batch-terminal-line.md` の stop reason code 表に新コードが 1 行、`## Stop point coverage` に対応 1 行が追加され、集合サイズを述べる文言（現在「eleven」）が更新されている。
- [ ] AC-6: 新コードの停止が `state: stopped` / `step: no-step` / 非空 `resume_conditions` を満たす。
- [ ] AC-7: `reduced` / `minimal` の引き算対象が文書化され、create-plan の前提条件が tier 対応に改められている。
- [ ] AC-8: `minimal` で `requirements: {}` と TASK.md 参照の実タスク 1 件が正当な状態として文書化されている。
- [ ] AC-9: develop 駆動経路で SPEC.md 不在時に spec 観点が skip notice 付きで落ちる規定が `review-phase.md` にある。
- [ ] AC-10: 昇格が `skipped → pending` だけで表現され、新 status 値が導入されていない。完了済み create-spec の再実行手順と carve-out 列挙の更新が入っている。
- [ ] AC-11: integration worktree を引く記述がどこにも無い。
- [ ] AC-12: `python3 -m unittest discover -s tests` が全通過する（11 件固定アサーションの更新を含む）。
- [ ] AC-13: `python3 em-workflow/scripts/check-plugin-invariants.py` が全チェック PASS。
- [ ] AC-14: plugin.json と marketplace.json の version が同値で上がっている。
- [ ] AC-15: `minimal` から rework 経路に入ったときの扱いが文書化されている。

### 11.2 KPI

確定した KPI は無い。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1: 既存 `tests/test_failed_kind_batch_docs.py` の reason code 表アサーションを新コード込みに更新し、追加・削除の negative proof が引き続き機能する。
- [ ] TS-2: 既存 `tests/test_batch_quiet_output_discipline.py` の stop point 行数・キー数アサーション（現在 11）を更新する。
- [ ] TS-3: `tests/test_structured_result_conformance.py` / `test_structured_result_consumer_constraints.py` は SSOT 表から reason code を動的抽出するため、新コード追加で自動追随することを確認する（回帰確認のみ）。
- [ ] TS-4: `state: stopped` / `reason: no_work_required` / `step: no-step` / 非空 `resume_conditions` の結果が consumer constraints チェッカを通る。
- [ ] TS-5: design 以外の step に `skipped` を持つ workflow.yaml が YAML エラー扱いにならず、Step B の次 step 選択で正しくスキップされる。
- [ ] TS-6: `requirements: {}` と `requirements: []` を持つ単一タスクの workflow patch が `validate-worker-output.py` を通る。
- [ ] TS-7: SPEC.md 不在の develop 駆動 review で floor から spec が落ち、security と comprehensive が残る。
- [ ] TS-8: workflow.yaml 未作成のまま中断 → 再開したとき phase-state の tier 判定が復元され、再転記で降格しない。
- [ ] TS-9: Jev 非 0 終了 / Codex 不在の各組み合わせで tier が仕様どおり full に倒れる。
- [ ] TS-10: 閾値関数が (P0=0.81, expectation_clear=0.6) → minimal、(P0=0.37, P1=0.59) → full、(P0=0.50, P1=0.40) → reduced を返す。
- [ ] TS-11: `references/tier-rules.yaml` が実在し、プラグイン内から同ファイルを指す参照がすべて解決する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| tier | 走行段。full / reduced / minimal の 3 段階を取る |
| full | 引き算を行わない走行段。reduced / minimal の基準となる |
| reduced | full から REQUIREMENTS.md / IMPLEMENTATION.md / design を引いた段（FR9） |
| minimal | reduced からさらに SPEC.md（TASK.md に置き換え）/ `tasks/` の分割 / VERIFICATION.md / 並列 worktree を引いた段（FR10、FR21） |
| TASK.md | minimal で SPEC.md の代わりに置く文書。「変更点」と「期待結果」の 2 つだけを持つ（FR10） |
| 昇格 | tier を上げること。`skipped` の step を `pending` に戻して表現する（FR12、FR19） |
| Jev | System One。`~/.claude/skills/jev` 経由で呼び、`score` の `probabilities` を判定入力に使う（FR4） |
| tier_decision | tier 判定の記録。`by` / `confidence` / `at` / `reductions` を持つ（FR2） |

## 14. 確認事項

### 14.1 確認済み事項

以下は requirements-analyst が確定として扱う前提（いずれも可逆）。

- [x] AS-1: 新 stop reason code の名前は `no_work_required` を採用する（オーケストレーターが Codex 相談の結果として提示した案）。
- [x] AS-2: tier 判定の永続先は `feature-docs/{feature}/phase-state/tier.yaml`（仮名）とし、`references/phase-state.md` の `backfill.yaml` と同じ「どのフェーズにも属さない派生値を phase-state 配下に置く」先例に従う。`commit-docs.sh` の `ARTIFACT_PATHS` が feature-docs 全体をステージするため、スクリプト変更は不要。
- [x] AS-3: `validate-worker-output.py` の `validate_task_entry` は `requirements` 空リストを許容し（下限チェックなし）、列挙された id のみ workflow.yaml 側の存在を要求する。したがって `requirements: {}` + `requirements: []` の単一タスクは既存バリデータを素通りする。`complexity` は必須で low|medium|high のいずれかが要る。
- [x] AS-4: 昇格は `skipped → pending` のみで表現し、新 status 値を導入しない。`minimal` からの昇格では完了済み create-spec を再実行し、`skills/develop/SKILL.md` の自動再エントリ carve-out 列挙（現在 2 遷移、網羅性を明示）を 3 遷移へ更新する。
- [x] AS-5: integration worktree は全 tier で維持する（既存の verify / retrospect / Step C / implement の wake reconcile がその配置を前提にしている保存制約）。
- [x] AS-6: 新 stop reason code は `batch-mode.md` と `skills/develop/SKILL.md` に literal として書かない。両文書は `batch-terminal-line.md` を指すだけという SSOT 分割が既存テストで機械検査されている。
- [x] AS-7: security 観点は tier に関係なく floor に残る（`review-rules.yaml` の `baseline` が保証する既存不変条件）。
- [x] AS-8: テストコマンドは `python3 -m unittest discover -s tests`（`test/README.md`）。ビルド・フォーマット・E2E コマンドはこのリポジトリに存在しない。
- [x] AS-9: ルート LICENSE ファイルが存在しないため `project.license` は `none`。
- [x] AS-10: design step は skip 対象（UI 面の変更が無く、design-system 候補も 0 件）。
- [x] AS-11: `validate-worker-output.py` の `WORKER_CAPABILITIES['requirements-analyst']['full'].required_payload` が `reference_impact` を含んでいない契約ドリフトは既存の不整合であり、本フィーチャのスコープ外とする。

### 14.2 未確認・保留事項

未確認・保留の要件は無い（`status: tbd` の要件は 0 件）。

## 15. 参考資料

- `em-workflow/references/tier-rules.yaml`: 本フィーチャで新設する tier 判定規則（FR1）
- `references/workflow-schema.md`: `tier` / `tier_decision` の定義と Status semantics（FR2、FR3）
- `references/batch-terminal-line.md`: stop reason code と Stop point coverage の SSOT（FR7、NFR3）
- `references/review-rules.yaml` / `references/review-phase.md`: spec 観点の選択規定（FR17、NFR2）
- `references/phases/create-plan-phase.md`: create-plan の前提条件（FR18）
- `references/phase-state.md`: phase-state 配下の派生値の先例（FR15、AS-2）
- `skills/develop/SKILL.md`: 停止条件・Step A/B/C の規律と carve-out 列挙（FR3、FR15、FR19）
- `references/batch-policies.yaml` / `scripts/check-plugin-invariants.py`: gate_id 双方向チェック（FR23）
- `scripts/validate-worker-output.py`: タスクエントリ検証と rework-planner 検証（FR16、FR24、AS-3）
- `~/.claude/skills/jev`: Jev の呼び出し方（FR1、NFR5）
- `typesafe:typesafe-ai`: モデル特性・質問設計（FR1、NFR5）
- `codex-harness:codex-cli` の `run_codex_exec.sh`: Codex 事前調査の実行経路（FR5）
