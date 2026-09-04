# Feature: llm-led-review

要件の一次情報は `feature-docs/llm-led-review/REQUIREMENTS.md`。本書はそれを実装観点で表現したもので、FR/NFR の ID は両文書で一致する。

## Overview

em-workflow の review 段のメインレビューを、Claude ではない LLM（codex ハーネス / litellm ハーネス）に移す。Claude(Opus) は個別観点のレビュアーではなく、1 ラウンド分の全レビュアー出力を横断して評価する役に置き直す。評価結果はオーケストレーターに返り、次の行動（auto-fix / 追加ラウンド / rework / 完了）はオーケストレーターが決める。

## Objectives

- em-workflow の review 段のメインレビューを Claude 以外の LLM に移し、Claude(Opus) は個別観点のレビュアーではなく、結果を横断して評価する役に置き直す。
- 評価結果をオーケストレーターに返し、次の行動（auto-fix / 追加ラウンド / rework / 完了）はオーケストレーターが決める、という責務分離を review 段でも成立させる。
- 既存の Claude + Codex 並列レビューと突合という構成を、上記の構成で置き換える。

## User Stories

### US1: 主レビューを他 LLM に任せ、Opus は横断評価に回す

em-workflow の develop フローを実行する利用者として、選択された各観点の主レビューを Claude 以外の LLM に実行させ、Claude(Opus) には全レビュアー出力をまとめた横断評価をさせたい。個別観点のレビューと、その結果の評価が別の役に分かれるため。

**Acceptance Criteria:**

- [ ] 選択された各観点の主レビューを、Claude ではない LLM（codex ハーネスまたは litellm ハーネス）が実行する。（FR1, FR2）
- [ ] 全レビュアー結果が出揃った後、Opus のサブエージェント 1 本がそれらをまとめて評価する。（FR4, FR9）
- [ ] 評価役の評価がオーケストレーターに返る。（FR7）
- [ ] オーケストレーターがその評価に基づいて次の行動（auto-fix / 追加ラウンド / rework / 完了）を決める。（FR8）
- [ ] Claude と Codex を並列起動して突合する現行の流れが、上記構成に置き換わっている（review-phase.md Phase R2 / R3 と reviewers.yaml から並列突合前提の記述が消えている）。（FR3, FR13）

### US2: 他 LLM 出力を安全に取り込む

同じ利用者として、他 LLM のレビュー出力に含まれる指示文が命令として実行されないことを保証したい。injection の洗浄経路を作らないため。

**Acceptance Criteria:**

- [ ] 他 LLM 出力の untrusted 扱いを評価役が担い、かつオーケストレーターが評価役出力に対して機械的検査（file 字句・存在・severity 語彙・category 一致 drop・source 上書き・サイズ上限）を適用する旨が文書に明記されている。（FR5, FR6, NFR1）

### US3: ハーネスが無い環境でも壊れない

vertex-review を導入していない利用者として、ハーネスが 1 つも使えない観点があっても review 段が最後まで走ってほしい。em-workflow 単体で動く現行の性質を保つため。

**Acceptance Criteria:**

- [ ] ハーネスが 1 つも利用可能でない観点があってもフェーズが abort せず、Claude フォールバックで完走する。（FR3, FR10, NFR2）
- [ ] `/em-workflow:review` の standalone 実行も同じ構成になる。（FR11）

### US4: 下流の記録読み取りと不変条件を壊さない

同じ利用者として、review 段の改修が既存のラウンド記録読み取り・テスト・プラグイン不変条件を壊さないことを求める。

**Acceptance Criteria:**

- [ ] reviews/roundN.yaml の場所と、round_context / retrospect signals が読むフィールド名・意味が維持されている。（FR12）
- [ ] `python3 -m unittest discover -s tests` が通り、check-plugin-invariants.py の agent_dispatch_parity / stale_references / gate_id coverage が通る。（FR15, NFR3, NFR6）
- [ ] `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version が同じ値に上がっている。（FR14）
- [ ] em-review 配下のファイルが 1 つも変更されていない。

## Technical Requirements

### Functional Requirements

- **FR1 — 主レビューを他 LLM が実行する:** 選択された各観点について、review-phase.md Phase R2 は Claude ではないレビュアーを 1 本だけ dispatch する。どのハーネス／モデルを使うかは `references/reviewers.yaml` のその観点のチェーンの先頭から、ハーネスが利用可能な最初のエントリを取る（`{harness: codex}` → `em-workflow:codex-reviewer`、`{harness: litellm, model: M}` → `vertex-review:vertex-reviewer` に `model: M` を verbatim で渡す）。可用性判定は現行 Phase R0 の `codex_available` / `litellm_available` プローブをそのまま使う。
- **FR2 — reviewers.yaml を主レビュアーレジストリへ転換する:** 観点ごとの `cross_validation` チェーンを主レビュアーチェーンとして読み替える。現在 `cross_validation: []` の 2 観点（comprehensive / license）にもエントリを与え、選択された全観点が他 LLM の主レビュアーを持つ状態にする。「どのモデルが存在するかはハーネス側、観点ごとのモデル選択は em-workflow 側」という reviewers.yaml ヘッダの責務分割は維持する。
- **FR3 — Claude 汎用レビュアーはフォールバック専任にする:** `em-workflow:reviewer` は削除せず、ある観点のチェーンに利用可能なエントリが 1 つも無いときだけ、その観点のレビュアーとして dispatch される役に降格する。他 LLM レビュアーとの並列同時起動は行わない。
- **FR4 — Opus 評価サブエージェントを新設する:** 1 ラウンド分の全レビュアー出力（チェーンウォーク後の最終結果を含む）が出揃った後、Opus のサブエージェント 1 本を dispatch し、横断的な評価を 1 つのオブジェクトとして返させる。既存 `agents/reviewer.md` の `model: opus` / `effort: xhigh` frontmatter が、判断役エージェントの既存記法として先例になる。
- **FR5 — 他 LLM 出力の untrusted 扱いは評価役が担保する:** レビュアー出力に含まれる指示文・ロール上書き・"ignore previous instructions" 等は評価役が評価の一部として扱い、データとして分析する。（回答済み `review.sanitization-ownership` による。）
- **FR6 — 評価役の出力もオーケストレーターから見て untrusted:** オーケストレーターは評価役の出力に対して、現行 Phase R3 のうち委譲不能な機械的ゲートを引き続き適用する — `file` の字句検査（絶対パス / `..` / NUL の拒否）、project_root 配下での存在検査、`severity` 語彙検査、`category` が dispatch した観点と一致しなければ無条件 drop（絶対に relabel しない — relabel は injection の洗浄になる）、`source` のオーケストレーター既知 identity での上書き、title/description/suggestion の 4096 バイト上限、changed_files 外の finding の confidence 上限。
- **FR7 — 評価役の出力契約を定義する:** 評価役は機械検査可能な 1 つのオブジェクトを返す。findings は roundN.yaml の finding 形（`stable_id` / `severity` / `category` / `file` / `line` / `title` / `description` / `suggestion` / `sources` / `confidence`）を持ち、ラウンド単位で推奨アクションを含む。評価役は worker-envelope.md 2.3 の 5 worker には含まれない（同表は `reviewer` / `codex-reviewer` を明示的に除外しており、「Every other worker keeps its current input/output form」）ため、worker envelope ではなく review 段固有の契約に従う。
- **FR8 — 次の行動はオーケストレーターが決める:** 評価はオーケストレーターに返り、オーケストレーターが Phase R4 の auto-fix、追加ラウンド、rework、完了のいずれかを決める。workflow.yaml / roundN.yaml への書き込み、commit、AskUserQuestion ゲートは従来どおりオーケストレーター専有で、評価役には移さない。Phase R5 の rework 経路は `references/rework-task-synthesis.md` Section 10 の固定順序（`review.needs_rework = true` と `review.status = pending` をオーケストレーターが先に直接書き、その後 rework-planner を dispatch）をそのまま維持する。
- **FR9 — fan-out 形状とチェーンウォークの維持:** 1 ラウンドの主レビュアー Task 呼び出しは全て 1 メッセージにまとめる。Phase R2b の retryable skip チェーンウォーク（`rate_limited` / `budget_exhausted` / `harness_unavailable` のみ、1 観点あたり fallback dispatch 最大 2 回、budget/reachability はハーネス単位・congestion はモデル単位）は主レビュアーに対して維持する。評価役の dispatch はチェーンウォーク完了後。
- **FR10 — ハーネス不在時の劣化動作:** ある観点でハーネスが 1 つも使えない場合もフェーズを abort しない。FR3 の Claude フォールバックに落ち、評価役は通常どおり走る。ラウンド記録にはその観点の source がフォールバックであることが残る。vertex-review 未導入環境でも em-workflow が動く、という現行の性質を壊さない。
- **FR11 — standalone レビューも同じ構成になる:** review-phase.md は develop 駆動と standalone の 2 実行文脈を持つ 1 本のプロトコルで、`skills/review/SKILL.md` はそれを standalone モードでインライン実行するだけなので、`/em-workflow:review` も自動的に新構成になる。スコープ外は em-review の `/em-review:multi-review` のみで、em-workflow の standalone review はスコープ内。
- **FR12 — ラウンド記録の後方互換:** `feature-docs/{feature}/reviews/roundN.yaml` はファイル名・配置・下流が読むフィールド名と意味を維持する — Phase R0 の `round_context` が読む `stable_id` / `file` / `line` / `resolution`、および `skills/develop/SKILL.md` の retrospect signals が読む `severity` / `category` / `resolution_reason` / review plan の Layer-2 追加理由。`perspective_runs` は評価役の run を記録できるよう拡張し、`source: claude` はフォールバック実行を意味するようになる。
- **FR13 — confidence モデルの再定義:** 現行の confidence は claude と cross-model の same_site 一致（95 / 60 / 50 / 70 / 65）を入力にしているが、Claude 並列レビューが無くなるとその入力自体が消える。confidence は評価役が付与する値とし、オーケストレーターは機械的な補正のみ残す（2 観点以上が同一サイトを指摘したときの +15・上限 100、changed_files 外の finding の 50 上限）。
- **FR14 — プラグインバージョンと説明文の更新:** `.claude/rules/core-plugin-version-bump.md` に従い `em-workflow/.claude-plugin/plugin.json` とリポジトリルート `.claude-plugin/marketplace.json` の version を同じ値へ上げる（現行 0.1.58）。両ファイルの description、および `em-workflow/README.md` のエージェント表とレビュー節が現行構成を文章で述べているため、同じ変更で更新する。
- **FR15 — プラグイン不変条件の維持:** `em-workflow/scripts/check-plugin-invariants.py` の `agent_dispatch_parity` は `em-workflow/agents/*.md` の各定義がどこかから dispatch されていることを要求するため、新設する評価役エージェントは review-phase.md から dispatch され、`agents/reviewer.md` も dispatch 元を失ってはならない。`check_gate_id_coverage` により、新しい `gate_id` を導入する場合は `references/batch-policies.yaml` に対応エントリが必要。

### Non-Functional Requirements

- **NFR1 — Security（injection 洗浄の防止を維持する）:** 評価役の導入によって「category を relabel しない」「source を自己申告に依らずオーケストレーターが上書きする」という現行の injection 洗浄防止が失われてはならない。FR6 がこれを担保する。
- **NFR2 — Compatibility（外部依存を増やさない）:** litellm ハーネス（vertex-review プラグイン）は任意のままとし、未導入環境で動作が壊れないこと。codex は同梱ラッパー `scripts/run_codex_exec.sh` + `command -v codex` の可用性判定のまま。
- **NFR3 — Usability（batch モードで停止しない）:** 新経路のどこでも AskUserQuestion を増やさない。Phase R4/R5 の 3 ゲート（`review.auto-fix-conflict` / `review.auto-fix-judgment` / `review.residual-critical-high`）は `references/batch-mode.md` の Non-packet gates 表に載っており、挙動を変える場合は同表と `references/batch-policies.yaml` ヘッダの除外コメントを同時に直す。
- **NFR4 — Maintainability（review-protocol.md の SSOT 性を壊さない）:** review-protocol.md は別途インストールされる vertex-review プラグインのレビュアーも直接読む唯一の SSOT（同プラグインは `references/` を持たない）。入力フィールド・出力スキーマ・skip 語彙の変更は、このリポジトリから編集もテストもできない外部プラグインの挙動を変える。既存の入力名・`skip_reason` 文字列・出力スキーマは可能な限り保つ。
- **NFR5 — Security（レビューは read-only のまま）:** レビュアーおよび評価役は working tree を変更しない（commit / branch 切替 / formatter 実行 / Write / Edit の禁止）。ファイル変更は Phase R4 の review-editor のみが行う。
- **NFR6 — Compatibility（既存テストの前提を壊さない）:** `tests/test_review_implement_develop_lock_contracts.py` は review-phase.md の fix-commit ブロックが共有 flock を取ることと、コミットメッセージ `fix({feature}): review round ` のリテラルをそのまま検査する。Phase R4 のコミット節を編集する場合は同テストと整合させる。

## Implementation Approach

### Architecture

**System Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│ オーケストレーター (review-phase.md)                     │
│  - 次アクション決定 / 書き込み / commit / ゲート (FR8)   │
│  - 評価役出力への機械的検査 (FR6, NFR1)                  │
├─────────────────────────────────────────────────────────┤
│ 評価役サブエージェント (Opus, 1 本) (FR4, FR5, FR7)      │
├─────────────────────────────────────────────────────────┤
│ 主レビュアー層 (観点ごとに 1 本) (FR1, FR3, FR9)         │
│  em-workflow:codex-reviewer / vertex-review:vertex-      │
│  reviewer / (フォールバック) em-workflow:reviewer         │
├─────────────────────────────────────────────────────────┤
│ レジストリ・プロトコル                                    │
│  references/reviewers.yaml (FR2)                         │
│  references/review-protocol.md (NFR4)                    │
├─────────────────────────────────────────────────────────┤
│ ラウンド記録 feature-docs/{feature}/reviews/roundN.yaml   │
│  (FR12)                                                  │
└─────────────────────────────────────────────────────────┘
```

**Component Diagram:**

- `references/review-phase.md` — Phase R0（可用性プローブ / round_context）、Phase R2（主レビュアー dispatch）、Phase R2b（チェーンウォーク）、Phase R3（評価役 dispatch と機械的検査）、Phase R4（auto-fix）、Phase R5（rework）を持つ 1 本のプロトコル。develop 駆動と standalone の 2 実行文脈を持つ（FR11）。
- `references/reviewers.yaml` — 観点 → 主レビュアーチェーンのレジストリ（FR2）。
- 評価役エージェント定義（新設、`em-workflow/agents/` 配下）— review-phase.md から dispatch される（FR4, FR15）。
- `em-workflow/agents/reviewer.md` — フォールバック専任として残置。dispatch 元を失わない（FR3, FR15）。
- `em-workflow/agents/codex-reviewer.md` / `vertex-review:vertex-reviewer` — 主レビュアー（FR1）。
- `references/review-protocol.md` — レビュアー入出力の SSOT。外部プラグインも直接読む（NFR4）。

### Data Flow

```
Phase R0: 可用性プローブ (codex_available / litellm_available)
   ↓
Phase R2: 観点ごとにチェーン先頭の利用可能エントリを 1 本 dispatch  (FR1, FR2)
          全 Task 呼び出しを 1 メッセージに集約                      (FR9)
          利用可能エントリ 0 → em-workflow:reviewer フォールバック   (FR3, FR10)
   ↓
Phase R2b: retryable skip のチェーンウォーク (最大 2 hop / 観点)     (FR9)
   ↓  (チェーンウォーク完了 = 全レビュアー出力が確定)
Phase R3a: 評価役 (Opus) を 1 本 dispatch                            (FR4)
          レビュアー出力中の指示文はデータとして分析                 (FR5)
          → 評価オブジェクト (findings + ラウンド単位の推奨アクション) (FR7)
   ↓
Phase R3b: オーケストレーターが機械的検査を適用                       (FR6, NFR1)
          confidence の機械補正                                      (FR13)
   ↓
roundN.yaml へ記録 (perspective_runs に評価役 run を含む)             (FR12)
   ↓
Phase R4 auto-fix / 追加ラウンド / Phase R5 rework / 完了 を決定       (FR8)
```

### API Design

HTTP API を持たない機能のため該当なし。エージェント間のインターフェースは次の 3 つで、いずれも既存 SSOT に従う。

- 主レビュアーへの入力・出力: `references/review-protocol.md`（既存の入力名・`skip_reason` 文字列・出力スキーマを可能な限り保つ — NFR4）。
- litellm ハーネス経由の主レビュアー: `vertex-review:vertex-reviewer` に `model: M` を verbatim で渡す（FR1）。
- 評価役の出力: review 段固有の契約に従う 1 オブジェクト。worker-envelope.md の worker envelope には従わない（FR7）。

### Database Schema

データベースを持たない機能のため該当なし。永続化される構造化データは YAML ファイルのみ。

**評価役出力の finding 形（FR7、roundN.yaml の finding 形と同一）:**

| Field | Type | 検査 |
|--------|------|-------------|
| stable_id | string | — |
| severity | string | 語彙検査（FR6） |
| category | string | dispatch 観点と不一致なら無条件 drop、relabel しない（FR6, NFR1） |
| file | string | 絶対パス / `..` / NUL 拒否、project_root 配下での存在検査（FR6） |
| line | int | — |
| title | string | 4096 バイト上限（FR6） |
| description | string | 4096 バイト上限（FR6） |
| suggestion | string | 4096 バイト上限（FR6） |
| sources | list | オーケストレーター既知 identity で上書き（FR6, NFR1） |
| confidence | int | 評価役付与値 + 機械補正（複数観点一致 +15 上限 100、changed_files 外は 50 上限）（FR13, FR6） |

**roundN.yaml（FR12）:** ファイル名・配置は不変。`round_context` が読む `stable_id` / `file` / `line` / `resolution`、retrospect signals が読む `severity` / `category` / `resolution_reason` / review plan の Layer-2 追加理由は名前も意味も不変。`perspective_runs` は評価役の run を記録できるよう拡張し、`source: claude` はフォールバック実行を意味する。

### Dependencies

**Internal Dependencies:**

- `references/review-phase.md`: 主レビュアー dispatch / チェーンウォーク / 評価役 dispatch / 機械的検査の実装先（FR1, FR3, FR4, FR6, FR8, FR9, FR10）。
- `references/reviewers.yaml`: 主レビュアーチェーンのレジストリ（FR2）。
- `references/review-protocol.md`: レビュアー入出力の SSOT（NFR4）。
- `references/rework-task-synthesis.md` Section 10: rework 経路の固定順序（FR8）。
- `references/batch-mode.md` / `references/batch-policies.yaml`: Non-packet gates と gate_id ごとの batch 既定（NFR3, FR15）。
- `skills/review/SKILL.md`: standalone 実行文脈（FR11）。
- `skills/develop/SKILL.md`: retrospect signals の読み手（FR12）。
- `scripts/check-plugin-invariants.py`: agent_dispatch_parity / stale_references / gate_id coverage（FR15）。

**External Dependencies:**

- codex ハーネス: 同梱ラッパー `scripts/run_codex_exec.sh`、可用性判定は `command -v codex`（NFR2）。
- litellm ハーネス（vertex-review プラグイン）: 任意。未導入環境で壊れないこと（NFR2, FR10）。

### File Structure

```
em-workflow/
├── references/
│   ├── review-phase.md          # Phase R0/R2/R2b/R3/R4/R5 (FR1,FR3,FR4,FR6,FR8,FR9,FR10)
│   ├── review-protocol.md       # レビュアー入出力 SSOT (NFR4)
│   ├── reviewers.yaml           # 主レビュアーチェーン (FR2)
│   ├── review-rules.yaml        # レビュー規則
│   └── batch-policies.yaml      # gate_id ごとの batch 既定 (FR15,NFR3)
├── agents/
│   ├── reviewer.md              # フォールバック専任へ降格 (FR3)
│   ├── codex-reviewer.md        # 主レビュアー (FR1)
│   └── <評価役>.md               # 新設 (FR4,FR15)
├── skills/review/SKILL.md       # standalone 実行文脈 (FR11)
├── README.md                    # エージェント表 / レビュー節 (FR14)
└── .claude-plugin/plugin.json   # version / description (FR14)
.claude-plugin/marketplace.json  # version / description (FR14)
tests/                           # 構造アサーション + 回帰 (TS1..TS6)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/llm-led-review/**`
- `test-docs/llm-led-review/**`

`feature-docs/llm-led-review/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/llm-led-review/**` covers `test-docs/llm-led-review/{T}.tests.yaml`,
the per-task test record. It is generated and owned by
`implement-phase.md`; this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/llm-led-review/` directory at all; the declared
`test-docs/llm-led-review/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1: `tests/` に unittest 形式の構造アサーションテストを追加し、review-phase.md / reviewers.yaml / review-protocol.md が新構成の必須要素（主レビュアー dispatch、評価役 dispatch、評価役出力への機械的検査、フォールバック規定）を含むことを検査する。このリポジトリでは仕様文書の検証を構造アサーションで行う先例が既にある（`tests/test_worker_contract_docs.py`）。— 対象要件: FR1, FR2, FR3, FR4, FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR13, NFR1, NFR3, NFR5
- [ ] TS4: flock 契約回帰 — `tests/test_review_implement_develop_lock_contracts.py` が引き続き通ることを確認する。— 対象要件: NFR6
- [ ] TS5: codex-reviewer の mktemp 分離契約回帰 — `tests/test_codex_reviewer_temp_file_isolation.py` が引き続き通ることを確認する（主レビュアー化で同一メッセージ内の並列インスタンス数が増えるため、この不変条件の重要度は上がる）。— 対象要件: FR1, FR9, NFR2
- [ ] TS6: version bump 回帰 — 既存の version bump 検査テストが引き続き通ることを確認する。— 対象要件: FR14

### Integration Tests

- [ ] TS2: agent_dispatch_parity 回帰 — 新設の評価役エージェント定義が review-phase.md から dispatch されており、`agents/reviewer.md` も dispatch 元を保っていることを check-plugin-invariants.py で確認する。— 対象要件: FR3, FR4, FR15
- [ ] TS3: gate_id coverage 回帰 — 新しい gate_id を導入した場合に batch-policies.yaml に対応エントリがあることを確認する。— 対象要件: FR15, NFR3

**Run command**: `python3 -m unittest discover -s tests`（このリポジトリに build / format コマンドは存在しない）

### E2E Tests

**Existing E2E tests**: None（`resolved_input_paths.e2e` は空）
**Run command**: Not detected

### Edge Cases

- [ ] ある観点でハーネスが 1 つも使えない: フェーズを abort せず、`em-workflow:reviewer` フォールバックに落ち、評価役は通常どおり走る。ラウンド記録にその観点の source がフォールバックであることが残る。（FR3, FR10）
- [ ] 主レビュアーが retryable skip（`rate_limited` / `budget_exhausted` / `harness_unavailable`）を返す: チェーンの次エントリへフォールバックする。1 観点あたり fallback dispatch は最大 2 回。budget/reachability はハーネス単位、congestion はモデル単位。（FR9）
- [ ] 評価役の finding の `category` が dispatch した観点と一致しない: 無条件 drop する。relabel は絶対にしない。（FR6, NFR1）
- [ ] 評価役の finding の `file` が絶対パス / `..` / NUL を含む、または project_root 配下に存在しない: 字句検査・存在検査で弾く。（FR6）
- [ ] 評価役の finding が changed_files 外を指す: confidence に 50 上限を適用する。（FR13, FR6）
- [ ] 2 観点以上が同一サイトを指摘する: confidence に +15（上限 100）の機械補正を適用する。（FR13）
- [ ] レビュアー出力に指示文・ロール上書き・"ignore previous instructions" が含まれる: 評価役が評価の一部としてデータとして分析する。（FR5）
- [ ] vertex-review 未導入環境: litellm ハーネスは利用不可と判定され、em-workflow は変わらず動作する。（NFR2, FR10）
- [ ] 既存 feature の過去ラウンド記録: 読み替えなしで round_context と retrospect signals に供給できる。（FR12）

### Performance Tests

該当なし。本フィーチャーに負荷試験・ストレス試験の受け入れ基準は定義されていない。fan-out 形状（1 メッセージ集約、1 観点 1 本、fallback 最大 2 hop）は FR9 の構造要件として TS1 で検査する。

## Security Considerations

- **Authentication:** 該当なし。本フィーチャーは認証を扱わない。
- **Authorization:** 書き込み・commit・AskUserQuestion ゲートはオーケストレーター専有で、評価役には移さない（FR8）。レビュアーおよび評価役は working tree を変更しない — commit / branch 切替 / formatter 実行 / Write / Edit の禁止。ファイル変更は Phase R4 の review-editor のみ（NFR5）。
- **Input Validation:** 他 LLM 出力は評価役が untrusted として扱いデータとして分析する（FR5）。評価役の出力もオーケストレーターから見て untrusted で、`file` 字句検査（絶対パス / `..` / NUL 拒否）、project_root 配下での存在検査、`severity` 語彙検査、`category` 一致 drop、`source` 上書き、title/description/suggestion の 4096 バイト上限、changed_files 外の confidence 上限を適用する（FR6）。
- **Data Protection:** 該当なし。本フィーチャーは機密データを扱わない。
- **Injection 洗浄の防止:** 「category を relabel しない」「source を自己申告に依らずオーケストレーターが上書きする」という現行の防止策を、評価役の導入によって失ってはならない（NFR1）。
- **XSS / SQL Injection / CSRF:** 該当なし。Web 面もデータベースも持たない。

## Error Handling

### Error Codes

HTTP を持たない機能のためエラーコード表は該当なし。エラー相当の分岐は次のとおり。

| 条件 | 扱い | 要件 |
|------|------|------|
| 当該観点のチェーンに利用可能エントリが 0 | `em-workflow:reviewer` フォールバック。abort しない | FR3, FR10 |
| 主レビュアーが `rate_limited` / `budget_exhausted` / `harness_unavailable` | チェーンの次エントリへ（最大 2 hop） | FR9 |
| 評価役 finding の `category` 不一致 | 無条件 drop（relabel しない） | FR6, NFR1 |
| 評価役 finding の `file` が字句検査 / 存在検査に失敗 | 当該 finding を弾く | FR6 |
| 評価役 finding の `severity` が語彙外 | 語彙検査で弾く | FR6 |

`skip_reason` 文字列は既存のものを可能な限り保つ（NFR4）。

### Error Flow

```
主レビュアー skip → retryable か判定 → チェーン次エントリ (最大 2 hop) → 尽きたらフォールバック
評価役出力      → 機械的検査 → 不適合 finding を drop → 残りを roundN.yaml へ
```

## Performance Optimization

該当なし。本フィーチャーにレスポンスタイム・スループット・キャッシュの目標値は定義されていない。

## Success Criteria

- [ ] All functional requirements (FR1–FR15) are implemented and reflected in the affected documents.
- [ ] All test scenarios (TS1–TS6) pass.
- [ ] Security requirements are satisfied: FR5 / FR6 / NFR1 / NFR5。
- [ ] Documentation is complete: review-phase.md / review-protocol.md / reviewers.yaml / README.md（FR14）。
- [ ] `python3 -m unittest discover -s tests` が通り、check-plugin-invariants.py の agent_dispatch_parity / stale_references / gate_id coverage が通る。
- [ ] `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version が同じ値に上がっている（現行 0.1.58）。
- [ ] em-review 配下のファイルが 1 つも変更されていない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。FR1–FR15 と NFR1–NFR6 の全てが `status: resolved`。

なお、次の 2 つは resolved だがリスクを伴う仮定として記録されている（詳細は REQUIREMENTS.md 14.1）。

- A-3（FR2 の根拠）: comprehensive / license の 2 観点は他 LLM 単独実行の実績が無い。妥当性は実装段で再確認の余地がある。
- A-6（FR13 の根拠）: 現行の「Mechanical counting, not judgment」という明示的な設計方針を部分的に変える。本仕様中で最もリスクの高い仮定。

## Implementation Phases (if applicable)

該当なし。フェーズ分割は create-plan で `workflow.yaml` のタスクとして決まる。

## References

- 要件定義書: `feature-docs/llm-led-review/REQUIREMENTS.md`
- レビュー段プロトコル: `em-workflow/references/review-phase.md`
- レビュアー入出力 SSOT: `em-workflow/references/review-protocol.md`
- レビュアーレジストリ: `em-workflow/references/reviewers.yaml`
- rework 経路の固定順序: `em-workflow/references/rework-task-synthesis.md` Section 10
- worker envelope の適用表: `em-workflow/references/contracts/worker-envelope.md` 2.3
- Non-packet gates: `em-workflow/references/batch-mode.md`
- gate_id ごとの batch 既定: `em-workflow/references/batch-policies.yaml`
- プラグイン不変条件: `em-workflow/scripts/check-plugin-invariants.py`
- version bump ルール: `.claude/rules/core-plugin-version-bump.md`
- 構造アサーションの先例: `tests/test_worker_contract_docs.py`
- flock 契約テスト: `tests/test_review_implement_develop_lock_contracts.py`
- mktemp 分離契約テスト: `tests/test_codex_reviewer_temp_file_isolation.py`
