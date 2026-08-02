# em-workflow エージェント責務分離 設計書

対象プラグイン: `em-workflow`（リポジトリ `em-claude-plugins`）
現行バージョン: 0.1.27
改訂: rev13（`tmp/codex-design-review.md` 〜 `codex-design-review12.md` の指摘を反映）

この設計書は単独で実装に着手できる自己完結の指示書として書かれている。
検討過程は `tmp/codex-planB-design.md`、レビュー履歴は `tmp/codex-design-review.md` / `tmp/codex-design-review2.md` にあるが、実装に必要な情報は本書に閉じている。

---

## 1. 目的

em-workflow のエージェント責務分離を次の形に統一する。

- オーケストレーター（`/em-workflow:develop`）は、状態遷移・ユーザー対話・workflow.yaml 更新・コミット・承認ゲートだけを持つ
- 調査・分析・文書執筆・計画立案はすべてサブエージェント（worker）が Task dispatch で実行する
- worker はユーザーに質問せず、質問が必要なときは構造化された question packet を返す
- workflow.yaml の変更を伴う worker は、直接書き込みではなく patch を提案する

---

## 2. スコープ

### 2.1 対象

- `create-spec` / `design` / `create-plan` フェーズの Task dispatch 化
- question packet / answer / worker result / workflow patch / phase-state のスキーマ新設
- phase-state による対話状態の永続化と再開
- worker 出力検証スクリプトの同梱
- rework タスク合成の共通 SSOT 化（interactive / batch × review / verify の 4 経路）
- batch モードの gate ID ベース意思決定への移行（question packet で表現されるゲートに限る）

### 2.2 非対象

- `implement` フェーズのワークキュー方式（変更しない。rework 再入場の事前条件のみ追加）
- `review` フェーズの perspective 選択・fan-out・auto-fix ループ（rework 分岐の参照先変更のみ）
- 既存 hook 6 種の判定ロジック（変更不要であることを 6.5 で確認済み）
- `merge-task.sh` / `commit-docs.sh` の実装（呼び出し規約の追加のみ phase protocol 側で行う）
- `completed_at_commit` の意味論（現行を変えない。5.0 R2 参照）
- 既存 worker（implementer / reviewer / codex-reviewer / review-editor / gitignore-guard / git-setup-guard）の入出力形式

### 2.3 共通エンベロープの適用範囲

本書が定義する worker 共通エンベロープ（5.3）は、**新設・改修する 5 worker のみ**に適用する。

| 適用する | 適用しない |
|---|---|
| requirements-analyst（新設） | implementer |
| spec-writer（新設） | reviewer / codex-reviewer |
| rework-planner（新設） | review-editor |
| implementation-planner（改修） | gitignore-guard / git-setup-guard |
| designer（改修） | |

適用しない worker は現行の入出力形式を維持する。`review-editor` は独自 JSON 形式を持つが、現行でも自分では質問せずオーケストレーターが事前に判断を渡す契約になっているため、変更しない。

### 2.4 新規に加わる実行依存

| 依存 | 用途 | 不在時 |
|---|---|---|
| Python 3 + PyYAML | `scripts/validate-worker-output.py` の YAML 入力 parse | 終了コード 2 で「PyYAML が必要」と報告し、フェーズを中断 |
| `gio`（任意） | scope violation で生じた untracked ファイルの退避 | 退避せずフェーズを中断し、対象パスを報告（5.11.3） |

PyYAML は README の前提条件に記載する。`gio` は必須にしない。

---

## 3. 現状の問題

### 3.1 dispatch されないエージェント定義が `agents/` にある

`skills/develop/SKILL.md` の Step B step 表（198-203 行）で、次の 3 つは Task dispatch されず「定義ファイルを Read してインラインで従う」形になっている。

| フェーズ | 定義ファイル | AskUserQuestion |
|---|---|---|
| create-spec | `agents/requirements-spec-creator.md` | 使う（9 箇所） |
| design | `agents/designer.md` | **使わない**（tools に無い） |
| create-plan | `agents/implementation-planner.md` | 使う（TBD / ライセンス衝突 / 既存ファイル） |

実際に `Task(subagent_type=...)` されるのは implementer / reviewer / codex-reviewer / review-editor / gitignore-guard / git-setup-guard の 6 種類のみ。

designer については、インライン実行の根拠が定義側に存在しない。

- frontmatter の tools は `Read, Write, Glob, Grep` のみで AskUserQuestion を持たない
- 本文で「fully autonomously」（11 行）、「Process (autonomous — never ask, never wait)」（70 行）、「Never ask the user anything」（151 行）と自律動作を三重に宣言している
- 「Do not commit — the orchestrator runs commit-docs.sh after this agent returns」（135 行）と、サブエージェントからの return を前提にした契約が書かれている
- frontmatter の `model: best` / `effort: high` は Task dispatch 時にのみ有効で、インライン実行では反映されない

### 3.2 workflow.yaml の書き手が二重定義になっている

`references/workflow-schema.md`「Write ownership」（7-18 行）は次のように書かれている。

```
**Only the orchestrator (the `/em-workflow:develop` main session) writes
workflow.yaml.**
...
Exception: the upstream agents (requirements-spec-creator, implementation-
planner) create/extend the file when dispatched by the orchestrator
```

この例外条項は「when dispatched by the orchestrator」を条件にしているが、当該 2 つは dispatch されない。規則が発動しない条件で書かれている。

### 3.3 rework タスク合成の責務二重化と interactive 側の手順欠落

タスク分割は本来 `agents/implementation-planner.md`「Task decomposition」（95-126 行）の責務であり、`workflow-schema.md` も `tasks` を「written by implementation-planner」（75 行）としている。

しかし rework 時の合成手順は `references/batch-mode.md`「Rework task synthesis」（78-95 行）にあり、「The ONLY case where the orchestrator adds tasks without the planner」と明記されている。planner の責務が batch モード限定でオーケストレーター側に複製されている。

さらに、この手順は batch 専用文書にしか存在しない。`references/review-phase.md`「Completion gate」（380-384 行）の interactive 分岐は次のようにしか書かれていない。

```
Otherwise: offer another round / rework (`needs_rework: true`, route back to
implement) / explicit user acceptance
```

`references/implement-phase.md`「I.2.a: Launch phase」（156-169 行）は「journal に未記録かつ `status != merged`」のタスクだけを起動対象にする。既存タスクが全て merged のまま implement を pending に戻すと、起動できるタスクが存在せず implement フェーズが空回りする。

これは設計論以前の実バグである。

---

## 4. 目標状態

### 4.1 責務の分配

| 主体 | 責務 |
|---|---|
| オーケストレーター | 状態遷移判定、Task dispatch、ユーザー対話（AskUserQuestion の唯一の呼び出し元）、workflow.yaml 更新、コミット、承認ゲート、worker 出力の検証、branch/worktree 操作 |
| worker | 調査、分析、質問候補の生成、成果物の執筆、workflow patch の提案 |

worker の共通制約（2.3 の適用範囲内）:

- workflow.yaml は読み取り専用として扱う
- git commit しない
- AskUserQuestion を持たない
- 最終出力は単一の構造化オブジェクト

### 4.2 実行形態の一覧（目標状態）

| 定義 | 実行形態 | 質問 | workflow.yaml |
|---|---|---|---|
| requirements-analyst | Task | packet を返す | 読むだけ |
| spec-writer | Task | 返さない | 読むだけ |
| designer | Task | 返さない | 読むだけ（patch も返さない） |
| implementation-planner | Task | packet を返す | patch 提案 |
| rework-planner | Task | 条件付きで返す | patch 提案 |
| implementer | Task（現状維持） | 返さない | 触らない |
| reviewer / codex-reviewer | Task（現状維持） | 返さない | 触らない |
| review-editor | Task（現状維持） | 返さない | 触らない |
| gitignore-guard / git-setup-guard | Task（現状維持） | 返さない | 触らない |

designer が patch を返さないのは、成果物だけを返せばオーケストレーターが design step を completed へ進められ、patch を経由しても判断権がオーケストレーターにある以上情報量が増えないため。

`agents/` には Task dispatch される定義のみを置く。オーケストレーター向けのフェーズ手順は `references/phases/` に置く。

---

## 5. 仕様

### 5.0 リビジョン識別の基本規則

git のコミットは、そのコミット自身の SHA を対象ファイルへ事前に書き込めない。本設計では次の 2 つの規則でこれを扱う。

#### 規則 R1: 入力の stale 判定

worker 入力の陳腐化は、**`input_digest` の一致**で判定する。コミット SHA の比較は行わない。

`input_digest` は次を含む正規化 JSON の sha256 とする。

```yaml
digest_source:
  worker: implementation-planner
  mode: interactive
  workflow_blob: 8f17c04...            # git rev-parse HEAD:{workflow.yaml の相対パス}
  digest_inputs:                       # ファイル入力。パス昇順のソート済みマップ
    feature-docs/example/SPEC.md: sha256:...
    feature-docs/example/REQUIREMENTS.md: sha256:...
    feature-docs/example/DESIGN.md: sha256:...
    feature-docs/example/workflow.yaml: sha256:...
    references/impl-skills.yaml: sha256:...
    references/review-rules.yaml: sha256:...
    references/license-compat.md: sha256:...
    references/workflow-schema.md: sha256:...
    references/templates/task-plan.md: sha256:...
    skills/plan-writing/SKILL.md: sha256:...
    references/contracts/planner-contract.md: sha256:...
  value_inputs:                        # ファイルではない入力。キー昇順のソート済みマップ
    task_description: sha256:...       # null 可
    resolved_requirements: sha256:...  # spec-writer のみ
    rework_source: sha256:...          # rework-planner のみ
  answers_digest: sha256:...           # question_id 昇順の answer 正規化 JSON の sha256
  write_policy_digest: sha256:...
```

正規化規則: キーを昇順ソートし、区切りを `(",", ":")`、非 ASCII をエスケープしない JSON にシリアライズしてから sha256 を取る。

存在しないファイルは `digest_inputs` に含めない（キー自体を出さない）。ディレクトリを対象とする場合は、その配下の全ファイルを個別のキーとして展開する。

**`digest_inputs` の対象集合は worker ごとに contract が定義する。**

各 contract（`references/contracts/*.md`）に `digest_inputs` セクションを必須で設け、その worker の判断に影響しうる入力を漏れなく列挙する。オーケストレーターはその一覧に従って digest を構築する。

| worker | digest_inputs（ファイル） | value_inputs |
|---|---|---|
| requirements-analyst（`full`） | `CLAUDE.md`（プロジェクトルート + 該当ディレクトリ）、`LICENSE`、実在するパッケージファイル、`test/README.md`、E2E 探索対象、**design system 候補**、既存 REQUIREMENTS.md / SPEC.md、自身の contract | `task_description` |
| requirements-analyst（`design_system_detection`） | **design system 候補**、自身の contract | — |
| spec-writer | テンプレート 2 件（`requirements-document.md` / `spec-document.md`）、既存 REQUIREMENTS.md / SPEC.md、自身の contract | `resolved_requirements` |
| designer | REQUIREMENTS.md、SPEC.md、`workflow.yaml`、`design-system/tokens.yaml`、`design-system/tokens.html`、`references/templates/design-tokens.yaml`、他 feature の DESIGN.md（`designer.md:85`）、project-native design system の各ファイル、`optional_visual_inputs` の各ファイル、自身の contract | — |
| implementation-planner | REQUIREMENTS.md、SPEC.md、DESIGN.md、LESSONS.md、`workflow.yaml`、`impl-skills.yaml`、`review-rules.yaml`、`license-compat.md`、`workflow-schema.md`、`references/templates/task-plan.md`、`skills/plan-writing/SKILL.md`、`design-system/tokens.yaml`、project-native design system の各ファイル、既存 IMPLEMENTATION.md / VERIFICATION.md / tasks 配下、自身の contract | — |
| rework-planner | SPEC.md、IMPLEMENTATION.md、VERIFICATION.md、`workflow.yaml`、既存 tasks 配下、`impl-skills.yaml`、`review-rules.yaml`、`license-compat.md`、`references/templates/task-plan.md`、`skills/plan-writing/SKILL.md`、自身の contract | `rework_source` |

contract 自身を含めるのは、契約の変更が worker の出力形式を変えるため。

**探索範囲の確定はオーケストレーターが行う。** glob で決まる集合は、worker が独自に探索するのではなく、オーケストレーターが dispatch 前に対象パスを確定し、入力エンベロープの `resolved_input_paths`（5.3）へ列挙する。worker はその一覧の外を読まない。これにより digest の再現性が保証される。

**カテゴリ別の探索規則**

| カテゴリ | 探索 root | glob | 備考 |
|---|---|---|---|
| `e2e` | project root | `e2e-tests/`、`tests/e2e/`、`test/e2e/`、`docker-compose.e2e.yml`、`playwright.config.*`、`cypress.config.*`、`scripts/*e2e*` | 現行 `requirements-spec-creator.md` 71-73 行と同一 |
| `package_files` | project root | `go.mod`、`package.json`、`composer.json`、`Cargo.toml`、`pyproject.toml`、`Gemfile` | 実在するもののみ |
| `design_system_candidates` | project root | 下記「design system 候補の探索」 | requirements-analyst にのみ渡す |
| `project_design_system` | — | 探索しない。workflow.yaml の `project.design_system.paths` をそのまま使う（下記） | designer と implementation-planner に**同一の値**を渡す |
| `other_features_design` | integration worktree | `feature-docs/*/DESIGN.md`（対象 feature 自身を除く） | designer のみ |
| `visual_inputs` | project root `tmp/` | 呼び出しコンテキストで指定されたパスのみ | glob 展開しない |

**design system 候補の探索**（`design_system_candidates`）

requirements-analyst に渡す候補一覧。オーケストレーターが次の glob で解決する。

| 分類 | glob |
|---|---|
| token 定義ファイル | `**/design-tokens.{json,yaml,yml}`、`**/tokens.json` |
| ユーティリティ CSS 設定 | `**/tailwind.config.{js,ts,cjs,mjs}` |
| デザインシステムディレクトリ | `**/design-system/`、`**/ui/theme/` |
| CSS 変数定義 | `**/styles/tokens.{css,scss}`、`**/styles/variables.css` |
| ネイティブ theme | `**/ui/theme/*.kt` |

`node_modules/`、`vendor/`、`.git/`、`.claude/worktrees/`、`.gitignore` 対象は除外する。ディレクトリにマッチした場合は、配下を再帰的に走査し、**対象拡張子（`.yaml` / `.yml` / `.json` / `.css` / `.scss` / `.ts` / `.js` / `.kt`）のファイルだけを列挙する**（画像・フォント・ビルド生成物は候補判定に寄与しないため除外）。

analyst はパス名と、必要ならその内容を見て候補を分類する（判定はせず検出結果のみ返す）。内容を読む対象もこの一覧に限る。

このカテゴリは `analysis_mode` が `full` / `design_system_detection` のどちらでも `digest_inputs` に含める。候補ファイルが変化したら再分析が必要なため。

**探索コストの抑制**

`**/` を含む glob は大規模リポジトリで高コストになる。次を規範とする。

- **1 回の phase run 内では解決結果を再利用する**。create-spec の analyst 反復 dispatch では、初回に解決した一覧と digest を phase-state の `resolved_input_cache` に保存し、以降の dispatch で再利用する
- **失効判定に HEAD は使わない**。phase-state のコミットで HEAD は必ず動くため（`commit-docs.sh`）、HEAD 比較では毎回失効してキャッシュが機能しない。代わりに **`generation_digest`** を使う。これは「候補探索対象として列挙されたパス集合（昇順）と、各パスの blob hash」の正規化 JSON の sha256 とする
- 再探索して `generation_digest` を再計算する契機は次に限る: (a) 新しい phase run の開始（下記）、(b) 前回の解決以降に worker が `written_artifacts` で候補配下のパスを報告した、(c) 直前の `commit-docs.sh` が exit 4 を返し worktree を refresh した（外部コミットが候補を変えた可能性があるため）

  (a)(b)(c) のいずれも起きていなければ、phase-state のコミットが何回入っても再探索しない

- **「新しい phase run」の定義**: phase-state の `status` が `initialized` になった時点、または `generation` が増えた時点。プロセスの再開（同じ `generation` の継続）は新しい phase run ではない
- **ディレクトリ候補は配下を全展開せず、対象拡張子に限定する**（`.yaml` / `.yml` / `.json` / `.css` / `.scss` / `.ts` / `.js` / `.kt`）。それ以外（画像・フォント・ビルド生成物）は候補判定に寄与しないため列挙しない
- 安全上限: 解決結果が **500 ファイルまたは合計 5 MB を超えたら探索を打ち切り**、`truncated: true` を記録する。この場合の扱いは**どの経路でも共通で、経路固有の既定より優先する**。

  | モード | 動作 |
  |---|---|
  | interactive | その経路の gate ID（create-spec 手順 11a と backfill は `create-spec.design-system`、再分類ゲートは `design-system.reclassify`）で「候補が多すぎるため自動検出を断念した」旨を提示し、`kind` と `paths` の手動指定を求める |
  | batch | **中断する**。`batch-policies.yaml` の既定（`top_candidate_or_none` / `em_workflow`）は適用しない。候補一覧が不完全なまま自動判定すると誤分類が永続化するため |

  gate ID は経路ごとに変わるが、動作（interactive は手動指定、batch は中断）は 3 経路すべてで同一とする。

**design system の解決規則**

`project_design_system` の解決は、**workflow.yaml の `project.design_system` を読むだけ**とする。オーケストレーターは dispatch 時に探索を行わない。

```yaml
project:
  design_system:
    kind: project_native        # project_native | em_workflow | none
    paths:
      - src/design-system/tokens.ts
      - src/design-system/theme.ts
```

| `kind` | 意味 | designer の扱い |
|---|---|---|
| `project_native` | プロジェクト固有のデザインシステムが存在する | `paths` を読み取り専用の入力として使う。`design-system/tokens.yaml` / `tokens.html` は**作らない・更新しない**（targets から除外する） |
| `em_workflow` | em-workflow が管理する `design-system/tokens.yaml` を使う | `paths` は `design-system/tokens.yaml` と `tokens.html`。通常どおり `extend_only` / `regenerate` で更新する |
| `none` | デザインシステムが存在せず、em-workflow が新規に起草する | `paths` は空。designer が `design-system/tokens.yaml` と `tokens.html` を新規作成する（targets の `action: create`） |

このフィールドは **create-spec で必ず確定する**（5.7 の手順 11a）。未設定の workflow.yaml を持つ既存 feature の扱いは 5.12 に従う。

dispatch 時に探索しない理由は、探索結果が実行タイミングで変わると `input_digest` の再現性が失われ、designer と planner に別々の結果が渡りうるため。create-spec で 1 度確定してコミットすれば、以降は workflow.yaml の内容として digest に含まれる。

共通規則:

- ディレクトリにマッチした場合は、その配下の全ファイルを個別パスへ展開する（再帰、`.gitignore` 対象は除外）。ただし `design_system_candidates` は例外で、対象拡張子のみを列挙する（上記「design system 候補の探索」）
- symlink はたどらない。symlink 自体も列挙しない
- パスは project root からの相対で正規化し、UTF-8 バイト列の昇順でソートする（locale 依存の照合順序を使わない）
- 解決結果が空のカテゴリは空配列として渡す（キー自体は省略しない）
- `project_design_system` は探索対象ではないため、上記の展開・除外規則は適用しない（workflow.yaml の値をそのまま使う）

- オーケストレーターは dispatch 前に `input_digest` を計算し、入力エンベロープへ入れる
- worker は返却時に受け取った `input_digest` をそのまま `input_revision.input_digest` に複写する
- オーケストレーターは worker 戻り時に `input_digest` を再計算し、dispatch 時の値と一致することを確認する。不一致なら **stale** として扱う

`workflow_blob` を単独で保持するのは、phase-state のみを更新したコミットを無視して workflow.yaml の変化だけを検出できるため。ただし stale 判定の最終根拠は `input_digest` であり、`workflow_blob` はその構成要素の 1 つに過ぎない。

phase-state には参考情報として `base_revision`（phase-state を書き込む直前に取得した HEAD）を記録するが、判定には使わない。

#### 規則 R2: `completed_at_commit`

**現行の意味論を変更しない。**

`completed_at_commit` は「その step の status を `completed` に更新するコミットを作る**直前の HEAD**」である。

現行実装はすでにこの意味で統一されている。

| 箇所 | 実装 |
|---|---|
| `agents/requirements-spec-creator.md:216` | `$(git -C "$WT" rev-parse HEAD)` を workflow.yaml 作成前に評価（= SPEC.md のコミット） |
| `references/implement-phase.md:429` | `$(git rev-parse "em-workflow/{feature}/integration")` を status 更新前に評価 |

**規範的定義**: `completed_at_commit` は「その step の status を `completed` へ更新するコミットを作る直前の HEAD」である。

補足（規範ではない）: 通常はその step の成果を含む最新の tip を指す。ただし step によって「成果」の形は異なる。

- create-spec は REQUIREMENTS.md → SPEC.md → workflow.yaml と複数コミットを作るため、直前の HEAD は最後の成果物コミット
- implement は全 task が merge された後の integration tip（単一の「成果物コミット」ではなく、merge 済み task commit の連なりの先端）
- 成果物を伴わない step では、直前フェーズの終端コミットを指す

したがってコミット列の一般形は次になる。

```
… : その step の成果物コミット（0 個以上）
X  : 上記の最後（成果物が無ければ前フェーズの終端）
Y  : workflow.yaml の status = completed, completed_at_commit = X
```

**完了 status の更新コミットは、それまでの成果物コミットとは常に別コミットになる。** これは現行どおりであり、本設計で変更しない（成果物コミットの個数は step によって変わる）。

適用範囲: `workflow[]` の全 step（create-spec / design / create-plan / implement / review / verify / retrospect）。`references/workflow-schema.md` にこの規範的定義と適用範囲を明記する。

### 5.1 question packet

worker からオーケストレーターへ返す「ユーザー判断要求」。**質問要求専用**であり、質問がない状態を表現しない（worker 全体の状態は worker result の `status` が持つ）。

配置:
- 出力契約（worker prompt と人間向け）: `references/question-packet-schema.md`
- 機械検証: `scripts/validate-worker-output.py`（5.11.1）

```yaml
schema_version: 1
packet_id: create-plan-q0001          # ^[a-z][a-z0-9-]*-q[0-9]{4}$
phase: create-plan                     # create-spec | create-plan | review | verify | rework
worker: implementation-planner         # 5 worker のいずれか
iteration: 1                           # >= 1
input_revision:
  workflow_blob: 8f17c04...            # null 可（workflow.yaml 作成前）
  input_digest: sha256:...
summary: "…"                           # 任意、2000 文字以内
confirmed_facts:                       # 任意
  - fact_id: project.language
    statement: "Go 1.22"
    source: "go.mod"
assumptions:                           # 任意
  - assumption_id: retry.policy
    statement: "…"
    reason: "…"
    impact: medium                     # low | medium | high
    reversible: true
    related_question_ids: []
questions:                             # 1 件以上、32 件以内
  - question_id: requirement.fr4.tbd-resolution   # ^[a-z][a-z0-9._-]*$
    gate_id: create-plan.tbd-resolution           # batch policy との結合キー
    category: tbd-resolution
    priority: high                     # critical | high | normal | low
    blocking: true
    prompt: "FR4 のリトライ回数が未定です。どう扱いますか？"
    header: "FR4 リトライ"             # 12 文字以内
    answer_mode: select_or_freeform    # single_select | multi_select | freeform | select_or_freeform
    options:                           # select 系は 2-4 件、freeform は 0 件
      - option_id: assume
        label: "仮定を置いて進める"
        description: "妥当な既定値を仮定し、SPEC に assumption として記録する"
        recommended: true
      - option_id: exclude
        label: "除外して進める"
        description: "FR4 を status: excluded にし、実装対象から外す"
    why_needed: "リトライ回数がタスク分割と VERIFICATION のシナリオ数を左右するため"
    evidence:
      - path: feature-docs/example/SPEC.md
        line: 42
        detail: "FR4 の記述が TBD"
    depends_on: []
    supersedes: []
    on_unanswered: block               # block | record_tbd | use_batch_policy
```

`category` の語彙: `feature-identity` / `business-objective` / `functional-requirement` / `acceptance-criteria` / `user-experience` / `technical-requirement` / `edge-case` / `security` / `dependency` / `license` / `testing` / `design-step` / `tbd-resolution` / `existing-files` / `artifact-overwrite` / `rework` / `spec-change` / `completion` / `other`

`on_unanswered` に「自動で assumption 化する」値は設けない。interactive で未回答のまま assumption へ落とすことを禁止する。

`options` の `label` / `description` / `recommended` は AskUserQuestion の options にそのまま対応する。`header` は同ツールの header に対応する。

### 5.2 answer

```yaml
question_id: requirement.fr4.tbd-resolution
packet_id: create-plan-q0001
answered_at: "2026-08-02T16:00:00+09:00"    # RFC 3339 オフセット付き
source: user                                 # user | batch-decision-table | batch-codex-consultation | batch-safe-default
answer_mode: select_or_freeform              # 対応する question の値を複写
selected_option_ids: [assume]
freeform: "最大3回、指数バックオフ"
normalized_answer: "FR4は最大3回の指数バックオフを仮定する。"
resolution_note: null
```

`answer_mode` を answer 側にも複写するのは、answer 単体でモード整合を検証できるようにするため。

規則:

1. `single_select` — `selected_option_ids` はちょうど 1 件、`freeform` は null
2. `multi_select` — 1 件以上。ゼロ件を許す場合は「どれも選ばない」option を明示的に置く
3. `freeform` — `selected_option_ids` は空、`freeform` は非空
4. `select_or_freeform` — 選択なら option ID、Other なら `freeform`。両方入ったら freeform を補足説明として扱う
5. `selected_option_ids` の各値が、対応する question の `options[].option_id` に存在すること
6. worker には AskUserQuestion の生の返却値ではなく、この answer オブジェクトを渡す
7. 自由回答の意味が一意でない場合、オーケストレーターは推測して正規化せず、新しい question ID で補足質問を作る

規則 1-5 は `scripts/validate-worker-output.py` が機械検証する。

### 5.3 worker 共通エンベロープ

適用対象は 2.3 の 5 worker のみ。

**入力**

```yaml
schema_version: 1
request_id: create-plan-run-0002
phase: create-plan
mode: interactive             # interactive | batch
project_root: /absolute/main/repository
integration_worktree: /absolute/integration/worktree
feature: example-feature
feature_dir: /absolute/integration/worktree/feature-docs/example-feature
plugin_root: /absolute/plugin/root
workflow_path: /absolute/.../workflow.yaml
input_revision:
  workflow_blob: 8f17c04...
  input_digest: sha256:...    # 規則 R1 の構成
  base_revision: a3c91f2...   # 参考情報
task_description: null
prior_packets:
  - /absolute/.../phase-state/create-plan.yaml
answers: []                   # 5.2 の配列
write_policy: {}              # 5.4.2
resolved_input_paths:         # オーケストレーターが glob を解決した結果（5.0 R1）
  e2e: []
  design_system_candidates: []  # 候補探索の結果（create-spec 11a / backfill / 再分類ゲート用）
  project_design_system: []     # workflow.yaml で確定済みの paths（designer / planner 用）
  package_files: []
  other_features_design: []
  visual_inputs: []
allowed_write_roots:
  - feature-docs/example-feature/design/mockups/
output_contract_path: references/contracts/planner-contract.md
```

`resolved_input_paths` の各カテゴリは、その worker の contract が要求するものだけを埋める（不要なカテゴリは空配列）。

worker は、**エンベロープで明示された固定パス入力**（`workflow_path` / `templates` / `design_inputs` / `planning_inputs` / `output_contract_path` 等）**と `resolved_input_paths` に列挙された動的入力以外を、独自に探索・read してはならない**。各 contract にこの制約を明記する。

**出力**

```yaml
schema_version: 1
request_id: create-plan-run-0002
worker: implementation-planner
status: completed
input_revision:
  workflow_blob: 8f17c04...
  input_digest: sha256:...    # 入力で受け取った値をそのまま複写
question_packet: null
blocking_reason: null
written_artifacts: []
workflow_patch: null
mode_echo: null               # 入力にモード指定を持つ worker のみ必須（requirements-analyst の analysis_mode）
payload: {}                   # worker 固有
warnings: []
report: "計画を作成しました。"
```

`status` の値と制約:

| status | 意味 | 制約 |
|---|---|---|
| `needs_user_input` | 質問が必要 | `question_packet` 必須。成果物・patch・`blocking_reason` は禁止 |
| `completed` | 完了 | worker 固有 `payload` 必須。`question_packet` は禁止 |
| `blocked` | 外部条件の解消が必要 | `blocking_reason` 必須。`question_packet` は禁止 |
| `invalid_input` | 入力不正 | `blocking_reason` 必須。入力を修正せずに再 dispatch してはならない |
| `stale_input` | 入力の陳腐化を worker 側が検出 | 再 dispatch 可能 |
| `failed` | 実行失敗 | `blocking_reason` 必須。同一入力で 1 回だけ再 dispatch 可能 |

成果物を書いた場合は `written_artifacts` に全パスと sha256 digest を列挙する。

`payload` の中身は worker ごとに 5.4 が定義する。共通エンベロープと `payload` の組み合わせ検証は `scripts/validate-worker-output.py` が worker 名で分岐して行う（5.11.1）。

`mode_echo` は、入力にモード指定を持つ worker が受け取った値をそのまま複写する。現状は requirements-analyst の `analysis_mode` のみが該当し、他の worker は null とする。

検証（5.11.1）は `--input-envelope` で受け取った入力の `analysis_mode` と `mode_echo` の一致を確認したうえで、そのモードの payload 排他条件を適用する。**`mode_echo` が無い / 入力と不一致なら検証エラー**とする。

`--kind worker-result` の検証では `--input-envelope` を全 worker で必須とし、省略された場合はスクリプトが終了コード 2（実行エラー）を返す。requirements-analyst 以外では `mode_echo` が null であることの確認に加え、`input_revision` の複写と `write_policy` との整合の検証にも使う。一致の照合を validator に閉じることで、オーケストレーター側の実装漏れが検証をすり抜けない。

### 5.4 各 worker の契約

各 worker の出力契約は `references/` 配下の contract ドキュメントに置き、worker prompt からそれを参照させる。

| worker | contract |
|---|---|
| requirements-analyst | `references/contracts/analyst-contract.md` |
| spec-writer | `references/contracts/spec-writer-contract.md` |
| implementation-planner | `references/contracts/planner-contract.md` |
| rework-planner | `references/contracts/rework-planner-contract.md` |
| designer | `references/contracts/designer-contract.md` |

#### 5.4.1 requirements-analyst（新規）

責務: 現行 `requirements-spec-creator.md` の Phase 0.5 / Phase 1 / Phase 2、および Phase 5.4・5.5 の判断材料収集。質問の実行・ファイル書き込み・branch/worktree 操作は行わない。

追加入力:

```yaml
analysis_mode: full           # full | design_system_detection
analysis_scope:               # 各項目の実体パスは resolved_input_paths（5.3）で渡す
  inspect_claude_md: true
  inspect_test_conventions: true
  inspect_e2e: true
  inspect_project_commands: true
  inspect_license: true
  decide_design_step: true
task_description: |
  ユーザーが指定した機能概要
known_feature_name: example-feature
```

`needs_user_input` 時の `payload.analysis_snapshot`: `feature_name_candidate` / `objectives` / `functional_requirements` / `non_functional_requirements` / `acceptance_criteria` / `user_experience` / `edge_cases` / `security_constraints` / `project_context`（languages / frameworks / existing_test_infrastructure / existing_e2e_infrastructure）/ `detected_commands`（component, field, value, evidence）/ `detected_license`（spdx, confidence）/ `design_step_recommendation`（value, reason）/ `design_system_candidates`（候補パスと分類の一覧。判定はせず検出結果のみ）

`completed` 時の `payload`（`analysis_mode: full`）:

- `resolved_requirements`: `feature_name` / `business_objectives` / `functional_requirements[]`（id, title, statement, status, tbd_reason）/ `non_functional_requirements[]` / `acceptance_criteria` / `test_scenarios` / `assumptions` / `design_step`（status, skipped_reason）
- `project_detection`: license, components
- `design_system_candidates`

**`analysis_mode: design_system_detection`**（5.12 の backfill 専用）

design system の候補検出だけを行う軽量モード。`analysis_scope` は無視する。

| | `full` | `design_system_detection` |
|---|---|---|
| `completed` の必須 payload | `resolved_requirements` / `project_detection` / `design_system_candidates` | `design_system_candidates` のみ |
| `resolved_requirements` / `project_detection` | 必須 | **禁止**（含めたら検証エラー） |
| 返しうる status | 全 6 値 | `completed` / `blocked` / `failed` のみ（question packet を返さない） |
| `digest_inputs` | 5.0 R1 の analyst 行のとおり | design system 候補の探索対象のみ |

この排他条件は `scripts/validate-worker-output.py` が `analysis_mode` で分岐して検証する。

#### 5.4.2 spec-writer（新規）

責務: analyst が確定した構造化要件から REQUIREMENTS.md と SPEC.md を生成する。workflow.yaml は書かない。question packet を返さない。

追加入力:

```yaml
requirements_analysis: {}      # analyst の resolved_requirements
templates:
  requirements: /absolute/.../templates/requirements-document.md
  spec: /absolute/.../templates/spec-document.md
```

**write_policy（path 単位。spec-writer / designer 共通）**

`write_policy.targets` は**特定ファイルの保護**を宣言する。パスが事前に確定しない生成物（mockup HTML など）は targets に列挙せず、`allowed_write_roots`（ディレクトリ許可）と `written_artifacts`（事後報告）で管理する。

**保護の分担（重要）**

| 対象 | 許可の与え方 |
|---|---|
| dispatch 時点で**既に存在する**ファイルの変更・削除 | `write_policy.targets` への明示列挙が**必須**。列挙されていない既存ファイルへの変更は、`allowed_write_roots` 配下であっても scope violation |
| dispatch 時点で**存在しない**ファイルの新規作成 | `allowed_write_roots` 配下であればよい。`written_artifacts` での事後報告が必須 |

`allowed_write_roots` は「新規作成を許すディレクトリ」であって、「配下を自由に書き換えてよいディレクトリ」ではない。この分担により、designer に `feature-docs/{feature}/` を許可しても、既存の SPEC.md / REQUIREMENTS.md / workflow.yaml / phase-state / IMPLEMENTATION.md / tasks 配下は targets に無い限り保護される（現行 `designer.md:143` の責務境界と一致）。

```yaml
write_policy:
  targets:
    - path: feature-docs/example/REQUIREMENTS.md
      action: create                # create | replace_own | replace_authorized | preserve | extend_only
      expect_digest: null           # action ごとに要否が決まる（下表）
      authorization: null
    - path: feature-docs/example/SPEC.md
      action: replace_own
      expect_digest: sha256:abc...
      authorization: null
    - path: feature-docs/example/DESIGN.md
      action: replace_authorized
      expect_digest: sha256:def...  # 承認質問を作った時点の digest
      authorization: create-spec-q0003/overwrite   # packet_id/question_id
    - path: design-system/tokens.yaml
      action: extend_only
      expect_digest: sha256:ghi...
      authorization: null
```

| action | 意味 | `expect_digest` | worker の動作 |
|---|---|---|---|
| `create` | 未作成のはず | 常に null | ファイルが存在したら `blocked` を返す |
| `replace_own` | 同 phase の自分の出力を上書き | 必須 | digest が一致しなければ `blocked` |
| `replace_authorized` | ユーザー承認済みの上書き | **必須**（承認時点の値） | digest が一致しなければ `blocked`（下記参照） |
| `preserve` | 既存を読むだけ | 必須 | 書き込まない。入力として使う |
| `extend_only` | 既存キーを保ったまま追加のみ | 必須 | 既存キーの変更・削除をしない。digest 不一致なら `blocked` |
| `regenerate` | ソースファイルから導出される生成物の再生成 | 必須 | `source` に指定したファイルを同じ dispatch で変更した場合に限り上書きしてよい。source を変更しなかった場合は書き込まない。digest 不一致なら `blocked` |

**`regenerate` はユーザー承認を要さない。** 生成物はソースから機械的に導出されるものであり、ソース側の変更が承認されていれば生成物の更新も同じ承認範囲に含まれる。target には `source` フィールドで導出元を指定する。

```yaml
- path: design-system/tokens.html
  action: regenerate
  source: design-system/tokens.yaml
  expect_digest: sha256:...
```

検証（5.11.1）は次を確認する。

- `written_artifacts` に `regenerate` 対象が含まれるなら、その `source` も含まれること
- `source` が含まれないのに `regenerate` 対象だけ変更されていたら violation

**`replace_authorized` でも digest を検証する。** 承認は「承認質問を作った時点の内容」に対するものであり、その後 dispatch までに別処理が対象を更新した場合、その新しい内容は承認されていない。digest が変わっていたら `blocked` を返し、オーケストレーターは stale として扱い再承認を求める。

`extend_only` は現状 `design-system/tokens.yaml` にのみ適用する。キー比較は YAML を map として parse し、既存の全キーパス（ネストを `.` 連結）の集合と値が保たれていることを確認する。対象ファイルが map でない場合、または YAML alias / merge key を含む場合は、比較不能として `blocked` を返す。

オーケストレーターは dispatch 前に各 target の現在の digest を調べ、action を決める。

- 存在しない → `create`
- 存在し、直前の同 phase worker 出力の digest と一致 → `replace_own`
- 存在し、digest が一致しない → interactive では `gate_id: {phase}.artifact-overwrite` で「上書き / 保持して既存を使う / 中断」を問い、回答に応じて `replace_authorized` / `preserve` / フェーズ中断とする。batch は 5.9 のポリシーに従う

`completed` 時の `payload`:

- `spec_index`: `requirements[]`（id, title, status, tbd_reason）、`test_scenarios[]`（id, requirement_ids）
- `assumptions_written[]`

事後条件:

- FR/NFR ID は重複せず `^(FR|NFR)[1-9][0-9]*$` に合致する
- `spec_index.requirements` と SPEC.md 内の ID が一致する
- `status: tbd` の要件には非空の `tbd_reason` がある
- analyst が出していない要件・assumption を writer が新規追加してはならない

#### 5.4.3 implementation-planner（既存を改修）

責務: 分析、IMPLEMENTATION.md、task plans、VERIFICATION.md の作成。AskUserQuestion と workflow.yaml 更新は行わない。

タスク分割規則の出典（`skills/plan-writing/SKILL.md`）:

| 規則 | 行 |
|---|---|
| タスク分割（one coherent work / files prediction / interface contract） | 60-89 |
| complexity 判定 | 93-106 |
| domains 語彙の解説（語彙の SSOT は `review-rules.yaml`） | 108-117 |

追加入力: `planning_inputs`（requirements_path / spec_path / design_path / lessons_path / impl_skills_registry / review_rules / license_compat）、`write_policy`（5.4.2 の形式）

質問は TBD・license conflict・既存ファイル方針を 1 つの packet にまとめる。ただし license 候補の探索が TBD 回答に依存する場合は別 iteration にしてよい。

`completed` 時の出力: `written_artifacts`（implementation / verification / task-plan）、`workflow_patch`（5.5）、`payload.task_index`

planner は `branch` / `notes` / 実行中 status / `completed_at_commit` を設定しない。

#### 5.4.4 rework-planner（新規）

責務: review findings または verify failed_items から追加タスクだけを計画する。既存計画全体を書き換えない。

追加入力:

```yaml
rework_source:
  type: review                   # review | verify
  review_round: 2
  findings:
    - stable_id: abc123
      severity: high
      category: security
      file: src/auth.go
      title: "…"
      description: "…"
      suggestion: "…"
  failed_items: []
existing_tasks: {}               # workflow.yaml tasks の snapshot
next_task_id: task0007
verification_index:              # VERIFICATION.md の既存シナリオ ID とその対象要件
  TS-1: [FR1]
  TS-2: [NFR1]
implementation_path: /absolute/.../IMPLEMENTATION.md
spec_path: /absolute/.../SPEC.md
verification_path: /absolute/.../VERIFICATION.md
```

グルーピング規則: findings を単純に「1 ファイル 1 タスク」へ変換しない。原因・契約・Acceptance Criteria が同一なら複数ファイルを 1 タスクにまとめる。通常 planner の分割規則（`plan-writing/SKILL.md` 60-89 行）を rework にも適用する。

**計画文書の更新範囲と判定の機械化**

| 文書 | 更新条件 |
|---|---|
| `tasks/taskNNNN.md` | 常に新規作成 |
| `VERIFICATION.md` | 下記の検証カバレッジ規則に従う |
| `IMPLEMENTATION.md` | rework task が既存タスクとの新しい共有契約（インターフェース・データ形式）を生む場合のみ追記 |
| `SPEC.md` / `REQUIREMENTS.md` | 更新しない（SPEC 変更が必要なら下記の遷移へ） |

**検証カバレッジ規則**（機械検証可能にするための必須条件）

rework task ごとに、`payload.rework_index` へ次を必ず出力する。

```yaml
rework_index:
  task0007:
    covered_by_existing: [TS-3]      # 既存シナリオで足りる場合はその ID
    new_scenarios: []                # 新規追加した場合はその ID
    rationale: "TS-3 が認可境界を検証済みで、追加ケースは不要"
```

`covered_by_existing` と `new_scenarios` の**両方が空である rework task を禁止**する。検証スクリプトは次を確認する。

- 各 rework task が `rework_index` に登場する
- `covered_by_existing` の ID がすべて `verification_index` に存在する
- `new_scenarios` の ID が VERIFICATION.md の差分に実在する
- `new_scenarios` が非空なら `requirements_patch` の `tests_append` にも同じ ID が含まれる

`IMPLEMENTATION.md` の更新要否は機械判定できないため、判定根拠を `payload.shared_contract_rationale`（更新した場合は追記内容の要約、しなかった場合はその理由）として必ず出力させ、レビュー時の human-readable な根拠とする。

**SPEC 変更が必要な場合の遷移**

rework が SPEC 変更を必要とすると判断した場合、rework-planner は task を作らず `status: needs_user_input` で `gate_id: rework.spec-change` の question を返す。ユーザーが SPEC 変更を選んだときのオーケストレーターの遷移は次に固定する。

1. `create-spec` step を `needs_update` にする
2. `create-plan` / `implement` / `review` step を `pending` にする
3. `workflow[implement].base_commit` は保持する
4. phase-state `rework.yaml` に中断理由と finding の stable_id を記録する
5. develop 状態機械が create-spec から再入場する

batch では `rework.spec-change` に該当するポリシーを定義しないため unlisted gate fallback（5.9）へ渡り、仕様変更に該当するので中断する。

**その他の質問条件**

次の場合のみ packet を返す。

- 同じ finding に相互排他的な修正方針が残っている
- requirement 除外またはライセンス変更が必要
- review finding だけでは Acceptance Criteria を客観化できない

#### 5.4.5 designer（既存を Task 化）

責務: 現行 `designer.md` の D0〜D4 を Task として実行する。完全自律であり question packet を返さない。workflow patch も返さない（4.2）。

追加入力: `design_inputs`（requirements_path / spec_path / workflow_path / design_token_template）、`write_policy`（5.4.2 の path 単位形式）。project-native design system・他 feature の DESIGN.md・visual input は `resolved_input_paths`（5.3）で渡す

designer は DESIGN.md・`design-system/tokens.yaml` / `tokens.html`・複数の mockup HTML を生成しうる。前 3 者はパスが確定するため `write_policy.targets` に列挙する。mockup は新規作成ならファイル名が designer の判断で決まるため targets に列挙せず、`allowed_write_roots` で許可し `written_artifacts` で事後報告させる。**既存の mockup を更新する場合は、そのパスを targets に列挙する**（5.4.2 の保護の分担）。

```yaml
allowed_write_roots:                          # 新規作成を許すディレクトリ
  - feature-docs/example/design/mockups/
write_policy:
  targets:
    - path: feature-docs/example/DESIGN.md
      action: create
      expect_digest: null
    - path: design-system/tokens.yaml
      action: extend_only
      expect_digest: sha256:...
    - path: design-system/tokens.html
      action: regenerate                       # tokens.yaml を変えたときだけ再生成
      source: design-system/tokens.yaml
      expect_digest: sha256:...
    - path: feature-docs/example/design/mockups/screen-main.html   # 既存 mockup を更新する場合
      action: replace_own
      expect_digest: sha256:...
```

DESIGN.md と `design-system/` 配下の 2 ファイルは `allowed_write_roots` の外にあるが、targets に列挙されているため書き込める。**targets への列挙自体が、その 1 ファイルに対する許可を兼ねる。**

`design-system/` を `allowed_write_roots` に入れない理由: designer が正当に書くのは `tokens.yaml` と `tokens.html` の 2 つだけで（`designer.md` の D0-D4 で確認済み）、どちらもパスが確定しているため targets の `action: create` / `replace_own` / `extend_only` で管理できる。root ごと許可すると `design-system/theme.css` のような責務外の新規ファイルまで通ってしまう。

`allowed_write_roots` を使うのは、mockup のようにファイル名が worker の判断で決まる場合に限る。

`path_prefix` のような前方一致エントリは導入しない。ディレクトリ単位の許可は `allowed_write_roots` が担い、targets は「特定ファイルの保護」だけを担う。両者は役割が重ならない。

**tokens.yaml と tokens.html の連動**: 現行 designer は tokens.yaml を変更したら tokens.html も必ず再生成する（`designer.md:101`）。`tokens.html` の action を `regenerate`（source: `tokens.yaml`）にすることでこれを表現する。検証は双方向で行う。

- `written_artifacts` に `tokens.yaml` があれば `tokens.html` も必須
- `tokens.html` だけが変更されていたら violation

designer は完全自律であり question packet を返さないため、既存 token に対して `replace_authorized`（ユーザー承認が必要）を使うことはない。既存の `tokens.yaml` は常に `extend_only`、`tokens.html` は常に `regenerate` とする。

**`project.design_system.kind` による分岐**（5.0 R1）:

`kind` と、`design-system/tokens.yaml` / `tokens.html` の実在状態の組み合わせで targets を決める。

**この直積検査は design step 専用ではない。** `project.design_system` を `digest_inputs` / `resolved_input_paths` で使う全フェーズ（design / create-plan）が、worker dispatch の前に同じ検査を行う。design が `skipped` で create-plan が次に来る経路でも、不整合を検出できるようにするため。実施箇所は、create-plan が `references/phases/create-plan-phase.md` の preconditions（5.8）、design は design 専用の phase protocol を作らないため `skills/develop/SKILL.md` の design step 分岐（designer を dispatch する直前）とする。

| `kind` | yaml | html | targets（yaml / html） | 備考 |
|---|---|---|---|---|
| `project_native` | 任意 | 任意 | **載せない** | `paths` を読み取り専用入力として使う。targets に無い既存ファイルの変更は 5.11.3 で violation になり、`allowed_write_roots` は `design/mockups/` だけなので新規作成もできない。過去の em-workflow token が残っていても更新されない |
| `em_workflow` | 有 | 有 | `extend_only` / `regenerate` | 通常経路 |
| `em_workflow` | 有 | 無 | `extend_only` / `create` | html は生成物なので、yaml が変われば作られる。`create` は yaml を変更しなかった場合に html を作らなくてもよい（`create` は「存在したら blocked」であって「必ず作れ」ではない） |
| `em_workflow` | 無 | 有 | — | **不整合として dispatch 前に中断する**。ソースなしに生成物だけが存在する状態で、designer に判断させない。原因パスを報告し、ユーザーが html を削除するか yaml を復元してから再開する |
| `em_workflow` | 無 | 無 | `create` / `create` | 新規起草と同じ |
| `none` | 無 | 無 | `create` / `create` | 新規に起草する |
| `none` | 有 or 有 | — | — | **不整合として dispatch 前に中断し、下記の再分類ゲートを実行する** |

`project_native` の場合、designer / planner の `digest_inputs` から `design-system/tokens.yaml` と `tokens.html` を**除外する**（残存していても判断入力として使わせない）。この旨を両 contract に明記する。

**再分類ゲート**（`kind: none` かつ token が実在する場合）

create-spec へ差し戻さず、その場で `project.design_system` を再確定する独立したゲートとして実行する。create-spec は既に `completed` であり、手順 11a はその workflow construction の途中にあるため、戻すと他の確定値まで再実行対象になってしまう。

1. requirements-analyst を `analysis_mode: design_system_detection` で dispatch し、候補を得る
1a. 候補探索が安全上限に達していた場合（`truncated: true`）は、5.0 R1 の上限超過規則を適用する。interactive は `gate_id: design-system.reclassify` で手動指定を求め、batch は**中断する**（下記の既定 `em_workflow` は適用しない）
2. interactive: `gate_id: design-system.reclassify`（phase 非依存の名前。design / create-plan の両方から共用する）で、実在する token を提示したうえで `kind` と `paths` を再確定させる。batch: `batch-policies.yaml` の同 gate に従う（既定は `em_workflow` へ再分類 — token が実在する以上、`none` は誤りだったと解釈する）
3. workflow.yaml の `project.design_system` を更新し、`commit-docs.sh` で `docs({feature}): reclassify design_system` としてコミットする
4. workflow.yaml を読み直し、**同じ step の事前条件から再開する**（step の status は変更しない）
5. 再確定後も直積表の中断ケースに該当する場合（例: `em_workflow` へ再分類したが yaml 無・html 有）は、そのケースの復旧手順に従う

`em_workflow` × (yaml 無 / html 有) の中断からは、ユーザーが html を削除するか yaml を復元して再実行すれば表の別行へ到達できるため、専用ゲートは設けない。

`completed` 時の `payload.design_summary`: decisions_count / open_items / tokens / mockups

オーケストレーターは成果物検証後に design step の status と `completed_at_commit`（規則 R2）を設定する。

### 5.5 workflow patch

配置: `references/workflow-patch.md`

汎用 JSON Patch（RFC 6902 相当）は採用しない。worker が任意の JSON Pointer へ書けると状態機械の所有境界が壊れ、配列 index 指定は step 順序変更に弱いため。

**共通フィールド**

| フィールド | 必須 | 内容 |
|---|---|---|
| `schema_version` | ○ | `1` |
| `patch_id` | ○ | `^[a-z][a-z0-9-]*-p[0-9]{4}$` |
| `base_input_digest` | ○ | 生成元の `input_digest`（規則 R1） |
| `base_workflow_blob` | ○ | 生成時点の workflow.yaml blob hash |
| `operation` | ○ | `replace_planning` \| `append_rework` |
| `tasks_patch` | operation による | 5.5.1 |
| `requirements_patch` | — | 5.5.2 |
| `step_patches` | ○ | 5.5.3（配列） |
| `preserve` | ○ | 5.5.4 |

| operation | tasks_patch.mode | step_patches の対象 | 使用者 |
|---|---|---|---|
| `replace_planning` | `replace_all` | create-plan のみ | implementation-planner |
| `append_rework` | `append` | implement / review / verify | rework-planner |

`project_patch` と `review_patch` は worker patch に存在しない。`project` ブロックと review summary ブロック（`needs_rework` を含む）はオーケストレーターが直接更新する。

#### 5.5.1 tasks_patch

```yaml
tasks_patch:
  mode: replace_all              # replace_all | append
  expected_next_task_id: task0007   # append 時のみ必須
  entries:
    task0001:
      title: ユーザー登録API
      plan: tasks/task0001.md
      files: [src/api/register.go, src/api/register_test.go]
      skills: [backend-impl]
      domains: [input-handling, api-contract]
      complexity: medium
      requirements: [FR1, NFR1]
      initial_status: pending
      provenance:                # append 時のみ必須
        source: review           # review | verify
        source_ids: [abc123]
        review_round: 2
```

task entry は原子的に upsert する。`workflow-schema.md` 75-88 行が task entry に files / skills / domains / complexity / requirements を必須としているため、部分適用で必須集合が欠けた状態を作らない。

**`replace_all` の許可条件**

次をすべて満たすときのみ許可する。満たさない場合は patch を拒否する。

- `tasks` が空、または全 task の `status` が `pending`
- かつ、次のいずれか
  - `create-plan` step が `pending`（初回計画）
  - `create-plan` step が `needs_update`（明示的な再計画）

いずれかの task が `in_progress` / `merged` / `failed` の状態で `replace_all` を受け取った場合は protocol error とする。実装が始まった後の再計画は rework 経路（`append`）で行う。

#### 5.5.2 requirements_patch

```yaml
requirements_patch:
  mode: merge_entries
  entries:
    FR3:
      expected: { tasks_contains: [task0003] }
      set: { tasks_append: [task0007], tests_append: [TS-9] }
```

`set` に使える操作は `tasks` / `tests` の `_append` と、`status` / `tbd_reason` / `excluded_reason` の直接代入に限る。

#### 5.5.3 step_patches（配列）

`workflow` は配列形式のため、step は ID で指定する。仮想フィールド（`implement_status` 等）は使わない。

```yaml
step_patches:
  - step_id: implement
    expected: { status: completed }
    set: { status: pending }
  - step_id: review
    expected: { status: in_progress }
    set: { status: pending }
```

`set` に使えるのは `status` のみ。`base_commit` / `completed_at_commit` は worker patch で設定できない（規則 R2 によりオーケストレーターが設定する）。

#### 5.5.4 preserve と必須 preserve 集合

適用後に値が変わっていないことを検証するパスの一覧。ドット区切りの論理パスで表記し、配列 index は使わない。

許可語彙:

- `workflow.implement.base_commit`
- `workflow.<step_id>.completed_at_commit`
- `project.license`
- `tasks.<task_id>.status`
- `tasks.<task_id>.branch`

**operation ごとの必須 preserve**（不足していれば patch を拒否する）

| operation | 必須 |
|---|---|
| `append_rework` | `workflow.implement.base_commit` |
| `replace_planning` | なし |

`append_rework` は既存 task の状態も保持する必要があるため、`existing_tasks` に含まれる全 task ID について `tasks.<task_id>.status` を preserve に含めることを推奨するが、必須にはしない（5.5.5 の規則 4 が上書きを禁止するため）。

#### 5.5.5 適用規則

1. `base_input_digest` が現在の入力から再計算した digest と一致しなければ適用しない
2. `base_workflow_blob` が現在の workflow.yaml の blob hash と一致しなければ適用しない
3. すべての `expected` が現在値と一致しなければ適用しない
4. `append` は既存 task ID の上書きを禁止し、`expected_next_task_id` が実際の次番号と一致することを要求する
5. `replace_all` は 5.5.1 の許可条件を満たすときのみ
6. task ID は `^task[0-9]+$`
7. `files` は project-relative。絶対パス・`..`・NUL を禁止
8. `skills` は `references/impl-skills.yaml` の登録値のみ
9. `domains` は `references/review-rules.yaml` の語彙のみ（5.5.6）
10. `complexity` は `low | medium | high`
11. `requirements` は workflow.yaml に存在する ID のみ
12. `initial_status` は `pending` のみ
13. operation ごとの必須 preserve（5.5.4）を満たすこと
14. `preserve` に挙げたパスの値が適用前後で変わらないこと
15. 全検証成功後にメモリ上で一括適用し、1 回の Write で workflow.yaml へ書き出す
16. コミット手順は規則 R2 に従う（成果物コミット → status 更新コミット）

#### 5.5.6 domains 語彙の SSOT

`domains` の SSOT は `references/review-rules.yaml` とする。現行の `agents/implementation-planner.md:113` と `references/workflow-schema.md:83` が既にこれを参照しているため、それに揃える。

`skills/plan-writing/SKILL.md` 108-117 行は判定基準の解説であり語彙の SSOT ではない。同スキルに「語彙の SSOT は review-rules.yaml」と明記し、両者の値が一致することを受け入れ条件（8.7）で検証する。

### 5.6 phase-state

workflow.yaml には対話履歴を入れない。対話と worker 実行状態は次に分離する。

```text
feature-docs/{feature}/phase-state/
├── create-spec.yaml
├── create-plan.yaml
└── rework.yaml
```

これらは integration branch にコミットする。`commit-docs.sh` の `ARTIFACT_PATHS`（147 行）は `feature-docs` ディレクトリ全体を許可しているため、スクリプト側の変更は不要。

配置: `references/phase-state.md`

```yaml
schema_version: 1
feature: example-feature
phase: create-plan
status: awaiting_answers      # initialized | dispatching | awaiting_answers | applying_patch | completed | failed
generation: 4
base_revision: a3c91f2...     # phase-state を書き込む直前に取得した HEAD（参考情報）
last_input_digest: sha256:... # 直近 dispatch の input_digest
active_request_id: create-plan-run-0002   # 現在の worker run。null 可（dispatch 前 / 完了後）
packets:
  create-plan-q0001:
    status: answered          # issued | answered | obsolete
    issued_at: "2026-08-02T15:50:00+09:00"
    questions:
      - question_id: requirement.fr4.tbd-resolution
        status: answered
answers:
  requirement.fr4.tbd-resolution:
    packet_id: create-plan-q0001
    answered_at: "2026-08-02T16:00:00+09:00"
    source: user
    answer_mode: select_or_freeform
    selected_option_ids: [assume]
    freeform: "最大3回、指数バックオフ"
    normalized_answer: "FR4は最大3回の指数バックオフを仮定する。"
worker_runs:                   # status: dispatched | needs_user_input | completed | blocked
  - request_id: create-plan-run-0001   #         | invalid_input | stale_input | failed | discarded_stale
    status: needs_user_input
    input_digest: sha256:...
    output_digest: sha256:...
artifacts:
  - path: feature-docs/example/IMPLEMENTATION.md
    sha256: sha256:...
    produced_by: create-plan-run-0002
patches:
  - patch_id: create-plan-p0001
    status: proposed          # proposed | validated | applied | rejected
    base_input_digest: sha256:...
    base_workflow_blob: 8f17c04...
progress_fingerprint: sha256:...
stale_redispatch_count: 0     # 成果物コミット exit 4 による連続再 dispatch 回数（上限 1）
resolved_input_cache:         # 動的入力の解決結果キャッシュ（5.0 R1）。初期値は空 map
  design_system_candidates:
    generation_digest: sha256:...   # パス集合 + 各 blob hash の digest
    resolved_at_generation: 4       # このキャッシュを作った phase-state の generation
    paths:
      - src/design-system/tokens.ts
    digests:
      src/design-system/tokens.ts: sha256:...
    truncated: false                # 500 ファイル / 5 MB 上限に達したか
last_error: null
```

#### 5.6.1 ID の一意性と冪等性

- `packet_id` / `request_id` / `patch_id` は feature 内で一意。同じ ID の再出現は同一実体の再掲とみなし、内容が異なれば protocol error
- `answers` は `question_id` をキーとするマップであり、同じ question への再回答は上書きではなく protocol error（回答を変える場合は新しい question ID と `supersedes` を使う）
- `artifacts` / `patches` への追記は、同じ ID があれば内容比較して一致すれば no-op、不一致なら protocol error
- `worker_runs` も同様だが、**`status` フィールドだけは下記の遷移に限り更新してよい**（他のフィールドが変わっていれば protocol error）

  | 遷移元 | 遷移先 | 契機 |
  |---|---|---|
  | `dispatched` | `needs_user_input` / `completed` / `blocked` / `invalid_input` / `stale_input` / `failed` | worker の返却 |
  | `dispatched` / `completed` | `discarded_stale` | 成果物コミットの exit 4（5.6.2） |

  `discarded_stale` は終端状態であり、そこから他の状態へは遷移しない

- `resolved_input_cache` はカテゴリ名をキーとする map。初期値は空 map（null ではない）。同じカテゴリの再解決は**内容一致でなくても上書きしてよい**（5.6.1 の内容不変規則の対象外。キャッシュは導出値であり記録ではないため）
- `generation` が増えたとき、および phase-state を `initialized` で作り直したときは `resolved_input_cache` を空 map に戻す

- `active_request_id` は、新しい `request_id` で dispatch する直前に更新する。worker run が終端状態（`completed` で成果物コミット済み / `failed`）に達したら null に戻す

  **例外**: `discarded_stale` に達した run は、5.6.2 の手順 2 から次の dispatch（手順 4）までの間、`active_request_id` に**保持したままにする**。再開時にどの run が破棄されたかを識別する唯一の手がかりであるため。手順 4 で新しい `request_id` へ更新される

#### 5.6.2 更新とコミット、exit 4 リカバリ

phase-state の更新は `commit-docs.sh {integration worktree} "{message}" {expected_base_tip}` で行う。第 3 引数は必須とする。

`commit-docs.sh` が exit 4（stale worktree）を返した場合:

1. `git -C {integration worktree} reset --hard em-workflow/{feature}/integration` で最新 tip へ refresh
2. 最新の phase-state を読み直す
3. 書こうとしていた packet / answer / worker_run / artifact / patch を、5.6.1 の冪等規則に従って**再構成した phase-state へ upsert する**（メモリ上の古い phase-state 全体で上書きしない）
3a. `resolved_input_cache` は**最新 phase-state 側の値を採用し、メモリ上の値で上書きしない**。exit 4 は外部コミットが入ったことを意味し、候補が変わった可能性があるため。加えて、この refresh 自体が再探索契機（c）に該当するので、次の dispatch 前に再解決する
4. `base_revision` を refresh 後の HEAD で更新する
5. `commit-docs.sh` を 1 回だけ再試行する
6. 2 回目も exit 4 ならフェーズを中断し、退避した answer object を含めてユーザーへ報告する

回答を受け取ってから phase-state へ書くまでの間に中断した場合、その回答は失われる。これを避けるため、AskUserQuestion の直後に必ず phase-state 更新を行い、worker の再 dispatch はその後にする。

**worker 成果物のコミットで exit 4 を受けた場合は、上記の手順を使わない。**

worker が生成した Markdown / HTML の本文は worker result にも phase-state にも保持されない（digest のみ）。したがって `reset --hard` 後に re-apply できない。次の競合が起こりうる。

1. worker が成果物を書いて返る
2. scope 検証・artifact 検証が成功する
3. 並行する `merge-task.sh` が integration branch を進める
4. 成果物をコミットする `commit-docs.sh` が exit 4 を返す

この場合の手順を次の順序に固定する。**`discarded_stale` の記録とコミットを、再 dispatch より前に行う。**

1. `git -C {integration worktree} reset --hard em-workflow/{feature}/integration` で最新 tip へ同期する（成果物は失われる）
2. 破棄した `request_id` の `worker_runs[]` エントリを `status: discarded_stale` に更新し（5.6.1 の許可遷移）、**同じ更新で `stale_redispatch_count` を +1 する**。この 2 つを 1 回の `commit-docs.sh` で永続化する。phase-state のトップレベル `status` は `dispatching` のまま変えず、`active_request_id` も破棄した ID のまま残す（再開時にどの run が破棄されたか特定するため）
3. `input_digest` と `write_policy` を再計算する
4. `active_request_id` を新しい `request_id` へ更新し、worker を再 dispatch する
5. 通常の検証を経て成果物をコミットする
6. 成果物コミットが成功したら、後続の phase-state 更新で `stale_redispatch_count` を 0 に戻す（成果物コミットとは別のコミット。同一コミットに混ぜない）

手順 2 を再 dispatch の後に回してはならない。`commit-docs.sh` は `feature-docs/` と `design-system/` を丸ごと stage するため（147 行）、phase-state の記録と一緒に**新しい worker の未検証成果物までコミットされる**。

手順 2 のコミット自体が exit 4 になった場合は、上記の phase-state 用 exit 4 リカバリ（1 回再試行）に従う。

**再試行上限**: 成果物コミットの exit 4 による再 dispatch は**連続 1 回まで**。

| 時点 | `stale_redispatch_count` |
|---|---|
| フェーズ開始時 | 0 |
| 1 回目の exit 4（手順 2 で永続化） | 1 |
| 2 回目の exit 4 | 手順 2 を実行せず、値 1 のまま phase を `failed` にして永続化し中断 |
| 成果物コミット成功後（手順 6） | 0 |

手順 2 でカウンタと `discarded_stale` を同一コミットに含めるのは、記録だけ永続化してカウンタが未反映のまま中断すると、再開時に「初回」と誤判定されて上限を回避できてしまうため。

手順 6 のコミットが exit 4 になった場合は、phase-state 用の exit 4 リカバリ（1 回再試行）に従う。それも失敗したらカウンタは 1 のまま残るが、成果物は既にコミット済みなので、再開時は phase-state の `artifacts` と実体の digest 一致から完了を判定できる（5.6.3）。

2 回目の exit 4 でフェーズを `failed` にする際は、並行 merge の頻度が worker 実行時間を上回っている旨を報告する。この上限は phase-state コミットの「1 回再試行」規則と揃えたもの。

成果物を一時領域へ退避して最新 tip へ再適用する方式は採らない（競合検証が別途必要になり、worker の判断根拠が古いままになるため）。

#### 5.6.3 再開判定

再開時は記憶ではなく次を順に読む。

1. integration branch / worktree
2. workflow.yaml の step status
3. phase-state
4. `input_digest` の再計算値と phase-state の `last_input_digest`
5. artifact 実体と digest
6. patch 適用済みか

| phase-state status | 処理 |
|---|---|
| `initialized` | 最初の worker dispatch から |
| `dispatching`（成果物なし、`active_request_id` が指す worker_run が `discarded_stale`） | 手順 2 まで完了して再 dispatch 前に中断した状態。`stale_redispatch_count` が 1 なら、digest と write policy を再計算して**新しい request ID** で再 dispatch する（カウンタは +1 しない）。2 以上ならフェーズを `failed` にする |
| `dispatching`（成果物なし、上記以外） | `input_digest` を再計算し、一致すれば同じ入力で再 dispatch。不一致なら新 request ID |
| `dispatching`（成果物あり、patch 未提案） | artifact を検証して worker へ再 dispatch |
| `awaiting_answers` | 未回答の question だけ再提示 |
| `applying_patch`（未適用） | 5.5.5 の規則 1-2 を満たすときだけ適用。満たさなければ worker へ再 dispatch して patch を作り直す |
| `applying_patch`（適用済み、step 未 completed） | workflow と artifact を検証し、completed 遷移だけ再実行 |
| `completed` | workflow.yaml を優先し、phase-state を reconcile |

workflow.yaml の step が `completed` で phase-state が遅れている場合は、workflow.yaml を正とする。

**再開時の `resolved_input_cache`**: 同じ `generation` を継続する再開では保持して再利用する（プロセスの再開は新しい phase run ではない）。`generation` が増える場合は空 map に戻す。`phase-state` validator は、`resolved_input_cache` の各カテゴリが `generation_digest` / `resolved_at_generation` / `paths` / `digests` / `truncated` を持ち、`resolved_at_generation` が現在の `generation` 以下であることを確認する。

#### 5.6.4 サイズ管理

1 フェーズあたり質問 32 問 × 数 iteration を上限の目安とし、これを超える場合はループ停止条件（5.7）に該当する。

`worker_runs` の `output_digest` は digest のみを保持し、worker 出力の全文は保存しない。

### 5.7 create-spec フェーズプロトコル

配置: `references/phases/create-spec-phase.md`

目次:

1. **Purpose and ownership** — オーケストレーター: 対話 / branch・worktree / phase-state / workflow.yaml / commit / 承認。requirements-analyst: 調査と question packet。spec-writer: REQUIREMENTS.md と SPEC.md
2. **Inputs and preconditions** — task description、batch flag、project root、既存 integration branch/worktree、phase-state の有無、feature identifier 検証、**integration worktree が clean であること**（5.11.3。clean でなければ dispatch せず中断）
3. **Bootstrap and durable-state boundary**
   1. feature 名が入力から一意なら検証後に integration branch/worktree を確保
   2. feature 名自体が未確定なら、それだけをオーケストレーターが先に質問（`gate_id: create-spec.feature-identity`）
   3. feature 確定直後に worktree を作り `phase-state/create-spec.yaml` を初期化
   4. それ以降の質問と回答は毎回永続化（5.6.2）

   現行 Phase 3（`requirements-spec-creator.md` 99-146 行）は詳細 clarification 後に worktree を作るが、再開可能性のため feature 確定直後へ前倒しする
4. **Reconcile on entry** — 5.6.3 の再開判定を適用
5. **Analyst dispatch loop** — `input_digest` を計算 → dispatch → 5.11 の検証 → `needs_user_input` なら packet を正規化 → 重複排除・優先順位付け → AskUserQuestion → 回答を phase-state へ永続化 → 再 dispatch → `completed` まで繰り返す
6. **Question normalization** — 5.9 の共通規則
7. **Interactive answer handling** — 選択肢回答を option ID へ変換、freeform を原文と正規化結果に分離、曖昧な freeform は補足質問、blocking 質問を未回答のまま進めない
8. **Batch answer handling** — 5.9
9. **Spec writer dispatch** — analyst の completed payload を固定入力として渡す。`write_policy` を 5.4.2 の手順で構築する
10. **Artifact validation** — 5.4.2 の事後条件 + テンプレート必須セクション + scope 検証（5.11.3）
11. **workflow.yaml construction** — 現行 Phase 5.5（196-223 行）の項目をここへ移す。オーケストレーターが直接構築する（worker patch は使わない）
11a. **design system の確定**（design step の status に関わらず**必ず実施する**）

    design が `skipped` でも省略しない。現行の design 要否判定は「UI が既存パターンで完全に決まっている」場合も `skipped` にするため（`requirements-spec-creator.md:179`）、`skipped` は「project-native design system が存在するので新しい visual decision が不要」を含む。`skipped` から `kind: none` を導くと、実在する design system を planner へ渡さなくなる。

    ただし design が `skipped` の場合、候補が 1 件も無ければ質問せずに `kind: none` を記録してよい（新規起草の必要が無いため、誤りが下流に影響しない）。候補が 1 件以上あるときは `pending` と同じく確定させる。

    analyst の `analysis_snapshot.design_system_candidates` を材料に、`project.design_system`（`kind` + `paths`）を確定して workflow.yaml へ記録する。

    analyst は次の候補を検出して報告する（検出のみ。判定はしない）。

    | 候補 | 例 |
    |---|---|
    | token 定義ファイル | `design-tokens.json` / `.yaml`、`tokens.json`（任意の階層） |
    | ユーティリティ CSS 設定 | `tailwind.config.{js,ts,cjs,mjs}`（任意の階層） |
    | デザインシステムディレクトリ | `**/design-system/`、`**/ui/theme/` |
    | CSS 変数定義 | `**/styles/tokens.{css,scss}`、`**/styles/variables.css` |
    | ネイティブ theme | `**/ui/theme/Color.kt`、`Theme.kt` 等の Compose theme |
    | em-workflow token | `design-system/tokens.yaml` |

    interactive では `gate_id: create-spec.design-system` で候補を提示し、`project_native`（どの候補を採用するか）/ `em_workflow` / `none` をユーザーに選ばせる。**候補が 1 件も見つからない場合も質問し、`none` を明示的に確定させる**（自動で `none` と決めない）。

    batch では `batch-policies.yaml` の `create-spec.design-system` に従う。既定は「候補が 1 件でもあれば最上位候補を `project_native` として採用、無ければ `none`」とする。

    ここで確定した値は以降の design / create-plan フェーズで探索し直さない。
12. **Command approval gate** — 現行 Phase 5.6（230-241 行）をオーケストレーター責務として実行（`gate_id: create-spec.command-approval`）
13. **Completion** — 成果物をコミット（B）→ workflow.yaml に status = completed と `completed_at_commit = B` を書いてコミット（C）→ design を pending または skipped → phase-state を completed

**終了条件（固定ラウンド数は設けない）**

- analyst が `status: completed` を返す
- blocking question がゼロ
- 全カテゴリが確定・TBD・明示的除外のいずれかに分類されている
- 同一 question が回答後も再生成されていない
- spec-writer 成果物が検証を通る

**ループ停止条件（進捗差分ベース）**

`progress_fingerprint` を「confirmed_facts の fact_id 集合 + 未回答 question_id 集合 + assumptions の assumption_id 集合」の sha256 として毎 iteration 計算し、phase-state に保存する。

- 同じ意味の質問が回答済みにもかかわらず 2 回再生成された
- 2 回連続 dispatch で `progress_fingerprint` が変化しない
- worker が同じ検証エラーを 2 回返した
- ユーザーが「ここで仕様作成を止める」を選んだ
- 外部条件がないと回答不能で、ユーザーが TBD 記録を明示的に選んだ

停止時に未解決事項を自動で assumption 化してはならない。interactive では次を提示する（`gate_id: create-spec.stalled`）。

1. 必要情報を追加して継続
2. 指定項目だけ TBD として記録
3. create-spec を `needs_update` または `failed` にして中断

assumption 化はユーザーが明示的に選んだ場合だけ許可する。

### 5.8 create-plan フェーズプロトコル

配置: `references/phases/create-plan-phase.md`

目次:

1. **Purpose and ownership** — planner: 分析・文書・workflow patch 提案。orchestrator: 質問・patch 適用・workflow.yaml・commit
2. **Preconditions** — create-spec completed、design completed または skipped、SPEC.md / REQUIREMENTS.md 存在、design completed 時は DESIGN.md 必須、workflow requirements が SPEC と一致、**integration worktree が clean であること**（5.11.3）、**`project.design_system` の直積検査に合格すること**（5.4.5）

   直積検査で不整合（`kind: none` かつ token 実在）を検出したら、planner を dispatch せず 5.4.5 の再分類ゲートを実行する。コミット後は create-plan の status を変えないまま、この preconditions から再開する。
3. **Reconcile on entry** — 5.6.3
4. **Planner dispatch** — `input_digest` 計算、workflow snapshot、source documents、prior answers、write_policy、registry paths を渡す
5. **Question loop** — TBD / license conflict / existing files / DESIGN.md open items のうち blocking なもの
6. **Packet normalization and Ask** — create-spec と同じ共通規則
7. **Planner completion output** — written artifacts / task index / tasks_patch / requirements_patch / step_patches / preserve
8. **Validation** — 5.11 の 7 レイヤー
9. **Planning invariants**（検証スクリプトが機械検証する）
   - 全 task plan に Acceptance Criteria がある
   - task の `files` と task plan の Files セクションの union が一致する
   - skills / domains / complexity が語彙に合致する
   - 全 requirement ID が workflow.yaml に存在する
   - task/test mapping の参照整合が取れている
   - parallel task 間の共有契約が IMPLEMENTATION.md にある
   - excluded / tbd requirement に task を割り当てていない
   - design completed 時は manual visual comparison が VERIFICATION.md にある

   出典: 現行 planner の Process 4〜6（95-144 行）と plan-writing checklist（171-183 行）
10. **Atomic patch application** — 5.5.5 の適用規則 → workflow.yaml 書き込み → 規則 R2 のコミット列
11. **Completion or failure** — 成功時のみ create-plan completed。artifact だけ存在し patch 未適用なら部分完了として再開可能にする

### 5.9 question 解決（interactive / batch 共通）

配置: `references/question-resolution.md`

**重複排除**（この順で判定する）

1. 同じ `question_id` は同一質問。回答済みなのに新しい packet で内容が変わっていたら worker protocol violation
2. `supersedes` に既存 question ID があれば旧質問を obsolete にする
3. 同じ `gate_id`・同じ evidence 対象・同じ workflow field へ作用するなら重複候補
4. prompt の文面だけが異なる意味判定はオーケストレーターが行わない。worker へ「stable question ID を再利用せよ」と再 dispatch する
5. 回答済み question は再提示しない。worker が新しい根拠により回答無効を示す場合は、新 question ID と `supersedes` が必須

**優先順位**（安定 sort）

1. `blocking: true`
2. priority: critical → high → normal → low
3. category 順: feature-identity → business-objective → functional-requirement → acceptance-criteria → security → technical-requirement → dependency/license → testing → user-experience/design → edge-case → その他
4. question ID

`depends_on` がある質問は依存先の回答後まで提示しない。1 回の AskUserQuestion 呼び出しには最大 3 問、各問最大 4 option とする（packet 自体は 32 問まで許容し、UI 提示を小分けにする）。

**batch 時の解決手順**

1. worker が `status: needs_user_input` と packet を返す
2. 各 question の `gate_id` を `references/batch-policies.yaml` から検索する
3. policy が見つかれば option ID または action を適用する
4. option ID が question の `options[].option_id` に存在しなければ protocol error として中断する（ラベル一致で代用しない）
5. answer object を作り `source: batch-decision-table` とする
6. 全回答を phase-state へ保存する
7. interactive 時と同じ形式で worker を再 dispatch する

**unlisted gate fallback**

1. `gate_id` が policy にないことを確認
2. question の prompt / options / why_needed / evidence / worker の tentative position を Codex へ渡す
3. Codex の提案を既存 option ID へ写像できるか判断する
4. 写像できれば `source: batch-codex-consultation`
5. 写像できなければ `on_unanswered` を見る
6. `record_tbd` → TBD 回答を生成
7. `block` → 成功経路の単なる選好なら最小副作用 option を選ぶ。**仕様変更・セキュリティ・ライセンス・不可逆操作は中断する**
8. `use_batch_policy` なのに policy がなければ schema/policy 不整合として中断する
9. 判断根拠を `resolution_note` と run report へ記録する

現行 `batch-mode.md` 49-71 行は「未知の gate は成功経路で継続」としている。本設計は上記 7 で仕様・セキュリティ境界を fail-closed に変更する。これは非退行ではなく**意図的な仕様変更**であり、受け入れ条件 8.5 でもその前提で検証する。

**batch policies の対象範囲**

配置: `references/batch-policies.yaml`

このファイルが扱うのは **question packet で表現されるゲートのみ**。question packet を経由しない batch 判断（git-setup 失敗、feature selection、review diff-size gate、command approval hook 不在時の fallback など）は `references/batch-mode.md` に残す。

```yaml
gate_policies:
  create-spec.feature-identity:
    action: select
    option_id: derive_from_task_description
  create-spec.requirement-clarification:
    action: codex_consultation
    record_as_assumption: true
    unresolved: record_tbd
  create-spec.design-step:
    action: select
    option_id: decide_autonomously
  create-spec.design-system:
    action: select
    option_id: top_candidate_or_none    # 候補があれば最上位を project_native、無ければ none
  design-system.reclassify:
    action: select
    option_id: em_workflow              # token 実在なので none は誤りと解釈する
  create-spec.artifact-overwrite:
    action: select
    option_id: preserve_and_reuse
    on_unavailable: abort
  create-spec.command-approval:
    action: auto_record
    refusal_patterns: hard_fail
  create-spec.stalled:
    action: select
    option_id: record_tbd
  create-plan.tbd-resolution:
    action: select
    option_id: assume
  create-plan.license-conflict:
    action: select
    option_id: compatible_alternative
    on_unavailable: abort
  create-plan.existing-files:
    action: select
    option_id: merge
  create-plan.artifact-overwrite:
    action: select
    option_id: preserve_and_reuse
    on_unavailable: abort
  design.artifact-overwrite:
    action: select
    option_id: preserve_and_reuse
    on_unavailable: abort
  implement.failed-task:
    action: retry_once
    on_exhausted: abort
  review.auto-fix-conflict:
    action: select
    option_id: skip_site
  review.auto-fix-judgment:
    action: select
    option_id: apply_as_is
  review.residual-critical-high:
    action: rework_once
    on_exhausted: defer
  verify.failed:
    action: rework_once
    on_exhausted: abort
  develop.completion:
    action: select
    option_id: keep_branch
```

`rework.spec-change` は意図的に定義しない（5.4.4 のとおり fallback で中断させる）。

**`artifact-overwrite` の `preserve_and_reuse` の意味**

batch で既存成果物の digest 不一致を検出した場合、`preserve_and_reuse` は次を意味する。

1. 該当 target の action を `preserve` にして worker を再 dispatch する（worker は既存ファイルを読むだけで書き換えない）
2. worker は既存成果物を入力として扱い、後続の成果物（IMPLEMENTATION.md / workflow patch 等）を生成する
3. 既存成果物が事後条件（5.4.2 の FR/NFR ID 整合など）を満たさない場合、worker は `blocked` を返し、フェーズは中断する

つまり `preserve_and_reuse` は「既存を正として続行する」であり、成功継続と中断のどちらにもなりうる。検証に通れば続行、通らなければ中断する。

`on_unavailable: abort` は、そもそも該当 option が packet に存在しない場合（worker が preserve を選択肢に含めなかった場合）に中断することを指す。

### 5.10 rework タスク合成

配置: `references/rework-task-synthesis.md`

この文書は「誰が文章を考えるか」ではなく「合成結果が満たす契約」を SSOT にする。実行主体（rework-planner）が将来変わっても契約は変わらない。

目次:

1. Purpose
2. Applicable modes — interactive / batch × review / verify の 4 経路
3. Inputs
4. Grouping rules
5. Task ID allocation
6. Task plan requirements
7. Metadata derivation
8. Verification coverage rules（5.4.4 の `rework_index`）
9. Related document updates
10. Workflow state transition
11. Invariants
12. Validation
13. Execution adapter（rework-planner の入出力契約への参照）

**状態遷移の順序**（`needs_rework` の更新時点を固定する）

review 由来の rework は次の順序で行う。

1. review フェーズが `review.needs_rework = true` と `review.status = pending` を workflow.yaml へ直接書く（オーケストレーター責務。worker patch は使わない）
2. rework-planner を dispatch する
3. patch（tasks_patch + step_patches + preserve）を検証して適用する
4. implement を pending に戻すのは 3 の patch 内（`step_patches`）で行う

verify 由来の rework は 1 を行わず、2 から始める（`needs_rework` は review 固有のフィールドのため）。

**不変条件**

1. implement を pending へ戻す前に、新しい rework task が 1 件以上 workflow.yaml へ登録されていること
2. 新規 task の status は pending であること
3. task plan に客観的な Acceptance Criteria があること
4. files / skills / domains / requirements は finding の意味内容から決める。file overlap だけの継承に依存しない
5. `workflow[implement].base_commit` は変更しない（patch の `preserve` に必ず含める。5.5.4 で必須化）
6. review 由来 task は finding の stable_id、verify 由来 task は failed item ID を `provenance` として保持する
7. interactive と batch でタスク合成規則を変えない。変わるのは rework 選択方法と回数上限だけ
8. patch 適用と workflow.yaml 書き込みは常にオーケストレーターが行う
9. rework で SPEC 変更が必要になった場合は task を作らず 5.4.4 の遷移に従う
10. 各 rework task が `rework_index` で検証カバレッジを宣言していること（5.4.4）

参照元（4 経路すべてがこの文書を参照する）:

- `references/review-phase.md` の interactive rework 分岐
- `references/review-phase.md` の batch rework 分岐
- `skills/develop/SKILL.md` の interactive verify rework 分岐
- `skills/develop/SKILL.md` の batch verify rework 分岐

### 5.11 worker 出力検証と失敗処理

#### 5.11.1 検証スクリプト

`scripts/validate-worker-output.py` を同梱する。

**方針: JSON Schema evaluator を実装しない。** 検証したい構造と不変条件を Python で直接記述する。JSON Schema の部分実装は評価意味論（`$ref` 解決、`allOf`/`oneOf` の組み合わせ、`format`、`default` の扱い）を微妙に外すリスクがあり、境界チェックの実装としては不適切なため。

各 worker の出力契約は `references/contracts/*.md` に人間と LLM が読む形で書き、同じ規則を Python 側にも実装する。両者の一致は fixture（5.11.5）で担保する。

**依存**: Python 3 + PyYAML（2.4）。`import yaml` に失敗した場合は終了コード 2 で「PyYAML が必要」と報告する。

```
python3 scripts/validate-worker-output.py \
    --kind worker-result \
    --worker implementation-planner \
    --input /path/to/worker-output.json \
    [--packet /path/to/packet.yaml] \
    [--answers /path/to/answers.yaml] \
    [--workflow /path/to/workflow.yaml] \
    [--registries /path/to/references] \
    [--phase-state /path/to/phase-state/create-plan.yaml] \
    [--input-envelope /path/to/dispatch-input.json] \
    [--digest-source /path/to/digest-source.json] \
    [--feature-dir /path/to/feature-docs/example] \
    [--baseline-dir /path/to/baseline-snapshot] \
    [--dry-run-apply]
```

`--kind` の値: `worker-result` / `question-packet` / `answers` / `workflow-patch` / `phase-state`

補助入力の用途:

| 引数 | 用途 |
|---|---|
| `--input-envelope` | dispatch 時に worker へ渡した入力エンベロープ（5.3）。`mode_echo` と入力の `analysis_mode` の一致、`input_revision` の複写、`write_policy` との整合を検証するために使う。**`--kind worker-result` では全 worker で必須**（`input_revision` と `write_policy` の検証は worker を問わず必要なため）。省略時は終了コード 2 |
| `--digest-source` | 規則 R1 の `digest_source` オブジェクト（オーケストレーターが dispatch 前に構築したもの）。これを正規化・sha256 して `base_input_digest` / `input_revision.input_digest` と突き合わせる。スクリプトは digest 対象ファイルを自分で探索せず、渡された値だけを使う |
| `--feature-dir` | task plan / VERIFICATION.md / IMPLEMENTATION.md の実体を読むため |
| `--baseline-dir` | dispatch 前の VERIFICATION.md 等のコピー。`new_scenarios` が「差分に実在する」ことの比較元 |

入力は JSON / YAML のどちらでも受け付ける（PyYAML の `safe_load` は JSON も読める）。

終了コード: `0` = 合格、`1` = 検証失敗（詳細を stdout に JSON で出力）、`2` = 実行エラー（依存不足・入力読み込み失敗）。

**Markdown 解析の範囲**

Markdown の自由記述を意味解析することはしない。機械検証する項目は、構造マーカーを持つものだけに限定する。

**マーカーは既存のテンプレート構造をそのまま使う。** 新しいマーカーを導入せず、既存資産への変更を避ける。

| 検証項目 | マーカー（既存構造） | 解析方法 |
|---|---|---|
| task plan の Files | `## Scope` 配下の `### Files to Create` と `### Files to Modify` の箇条書き（`references/templates/task-plan.md` 23-33 行）。項目の形式は ``- `{path}` — {responsibility}`` | 両見出しから次の同レベル見出しまでの箇条書きを収集し、各項目の**先頭の backtick 囲みを 1 件だけ path として抽出**して union を取る。backtick 囲みが無い項目・2 件以上含む項目は検証エラー。HTML コメントと fenced code block 内は解析対象外 |
| task plan の Acceptance Criteria | `## Acceptance Criteria (MANDATORY)`（同 41 行） | 見出しの存在と、配下の箇条書きが非空であることを確認 |
| VERIFICATION.md のシナリオ ID | `## Test Verification` 配下 `### Test Scenarios from SPEC.md`（`plan-writing/SKILL.md` 131-139 行）内の `TS-<n>` | 該当セクション内の `TS-\d+` を正規表現で抽出 |
| IMPLEMENTATION.md の共有契約 | `## Shared Components`（同 42 行） | 見出しの存在確認のみ |

**共有契約の判定は近似であることを明示する。** 現行 planner が共有契約を要求する条件は「一方の task が別 task の作るコンポーネントを利用する場合」であり（`plan-writing/SKILL.md` 75 行）、ファイル重複とは一致しない。ファイルが重ならなくても共有 API 契約は必要になりうるし、同一ファイルを触るだけでは不要なこともある。

したがって機械検証は次に限定する。

> **複数の task が同一ファイルを `files` に宣言している場合、IMPLEMENTATION.md に `## Shared Components` セクションが存在すること**

これは近似条件であり、「parallel task 間の共有契約が正しく記述されている」ことの保証ではない。契約の要否と内容の妥当性は human-readable なレビュー対象として残す。

これらのマーカーへの依存は各 contract に明記する。テンプレート側は既存構造を維持するため変更しない。

**検証内容**

構造検証:

- 必須キーの存在、型、enum 値
- ID の正規表現（`packet_id` / `question_id` / `task_id` / `patch_id`）
- 文字列長・配列要素数の上限
- `status` ごとの排他条件（`needs_user_input` なら packet 必須・成果物禁止 など）
- `answer_mode` ごとの `selected_option_ids` / `freeform` の整合（5.2 の規則 1-5）

相互参照検証:

- answer の `selected_option_ids` が対応 question の `options[].option_id` に存在する
- answer の `answer_mode` が対応 question の `answer_mode` と一致する
- patch の `skills` が `impl-skills.yaml` に存在する
- patch の `domains` が `review-rules.yaml` に存在する
- patch の `requirements` が workflow.yaml に存在する
- task の `files` と task plan の Files セクションの union が一致する
- `preserve` のパスが 5.5.4 の許可語彙に含まれ、operation ごとの必須集合を満たす
- rework の `rework_index` が 5.4.4 のカバレッジ規則を満たす
- `written_artifacts` に `design-system/tokens.yaml` が含まれるとき `design-system/tokens.html` も含まれる（5.4.5）

`--dry-run-apply` 指定時の追加検証:

- `base_input_digest` / `base_workflow_blob` の一致
- 全 `expected` の一致
- `replace_all` の許可条件（5.5.1）
- `append` の `expected_next_task_id` 一致と既存 ID 非上書き
- patch 適用後の workflow.yaml が構造検証を通る
- `preserve` 対象の値が適用前後で不変

オーケストレーターはこのスクリプトを Bash で呼び、終了コードで判定する。目視によるスキーマ確認は行わない。

#### 5.11.2 検証レイヤー

| # | レイヤー | 実施主体 |
|---|---|---|
| 1 | 構文検証（JSON/YAML として parse 可能） | スクリプト |
| 2 | 構造検証 | スクリプト |
| 3 | revision 検証（`input_digest` / `base_workflow_blob`） | スクリプト（`--dry-run-apply`） |
| 4 | scope 検証（5.11.3） | オーケストレーター（Bash） |
| 5 | artifact 検証（宣言ファイルの存在と digest 一致） | オーケストレーター（Bash） |
| 6 | cross-artifact 検証（SPEC ID / task metadata / VERIFICATION ID の参照整合） | スクリプト |
| 7 | state-machine 事後条件 | オーケストレーター |

#### 5.11.3 scope 検証

単純な dispatch 前後の `git diff` は使わない。dispatch 中に別の doc commit や task merge が integration branch へ入ると worker 以外の変更が混ざり、逆に dispatch 前から存在した未コミット変更を worker が上書きした場合は name-only diff で検出できないため。

**前提条件: dispatch 前の worktree は clean であること**

worker を dispatch する前に、integration worktree が clean（staged 変更なし・未コミットの tracked 変更なし・想定外の untracked なし）であることを確認する。

**これは「現行フローが clean を保証する」という主張ではなく、dispatch ごとに実施する fail-closed の検査である。**

`commit-docs.sh` が stage するのは `feature-docs/` / `test/README.md` / `design-system/` に限られる（147 行）。したがって次は clean にならない可能性がある。

- build / test / format コマンドが変更した tracked source
- 許可 root 外に作られた untracked byproduct
- 前フェーズの失敗で残った未コミット変更（特に verify 失敗後に rework-planner を dispatch する経路）

clean でなければ **dispatch せず、原因となった path を列挙して中断する**。自動削除や `reset --hard` による強制 clean 化は行わない（ユーザーの作業を破壊しうるため）。

`.gitignore` された build artifact は clean 判定の対象外とする（`git status --porcelain` の既定動作に従い、ignored は列挙しない）。

dirty 状態を snapshot して復元する設計は採らない（stale 時の `reset --hard` と両立しないため）。

**worker 変更集合と外部変更の分離（重要）**

linked worktree の HEAD は branch ref を指す。並行する `merge-task.sh` が integration branch を進めると、worker が何も触っていなくても現在の HEAD tree は新しいコミットを指す。

したがって **HEAD 層の差分を worker の変更集合に含めてはならない**。層ごとに用途を分ける。

| 層 | 用途 |
|---|---|
| HEAD SHA / HEAD tree | **stale 判定のみ**。外部コミットの検出に使う |
| index + working tree | **worker の変更集合の算出**。scope 判定はこの 2 層だけで行う |

dispatch 前の worktree が clean である以上、dispatch 後の index / working tree の差分は worker に帰属する。外部コミットは branch ref を進めるだけで、linked worktree の index / working tree を書き換えないため混入しない（`merge-task.sh` は task worktree 側で作業し、integration の ref だけを更新する）。

**排他前提（規範）**

snapshot 方式では、同じ worktree のファイルを直接触った別プロセスと worker を識別できない。したがって次を前提として明記する。

> worker の dispatch 中、integration worktree のファイルを直接作成・変更・削除してよいのは、オーケストレーターと dispatch 対象の worker だけとする。他のプロセスは integration branch の ref を更新することはできるが、worktree のファイルを直接触ってはならない。

**適用範囲**: この前提が適用されるのは、**2.3 の 5 worker について、scope snapshot の取得開始から検証終了までの区間**に限る。プラグイン全体の恒常的な制約ではない。

review フェーズの auto-fix ループは、複数の review-editor が integration worktree の別ファイルを並行編集する wave-parallel モードを持つ（`review-phase.md` 264 行〜）。これは本設計の scope 検証ではなく、review-phase.md 側の per-wave 検証規則に従う**例外**として扱う。本設計は review フェーズの検証方式を変更しない（2.2）。

**前提が満たされる根拠**（実ファイルで確認済み）:

- `merge-task.sh` は task worktree で tree を作り、integration branch には `update-ref` のみ行う（123 行）
- implementer は個別の task worktree で作業する（`implement-phase.md` 171 行）
- queue hook 群が書くのは feature worktree 群の外にある `journal.jsonl` / `agents.jsonl` であり、integration worktree 内の成果物ではない
- `commit-docs.sh` と `merge-task.sh` の ref 更新は同じ flock で直列化される（`commit-docs.sh` 123 行）

ただし**この排他は lock や hook で強制されていない**。前提が破られた場合の挙動は次のとおりで、常に fail-closed になるわけではない。

| 外部変更の性質 | 結果 |
|---|---|
| 許可範囲外（targets 未列挙の既存ファイル、allowed root 外の新規作成） | violation として拒否される（fail-closed） |
| 許可範囲内で、かつ worker がそのパスを `written_artifacts` に含めた場合 | worker の成果物として受理される。**snapshot 方式では識別できない** |

後者は snapshot 方式の原理的な限界であり、OS レベルの writer 識別を行わない以上は残る。前提の遵守で担保する。

この前提と適用範囲を `references/phases/*.md` と各 contract に記載する。

**dispatch 直前の snapshot**

| 対象 | 取得方法 | 用途 |
|---|---|---|
| HEAD SHA | `git rev-parse HEAD` | stale 判定 |
| index の blob ID と mode | `git ls-files -s -z` | scope 判定 |
| working tree の存在種別と内容 | tracked path を列挙し、通常ファイル・symlink は `git hash-object --` でハッシュ、不在はその種別を記録 | scope 判定 |
| untracked ファイル一覧 | `git status --porcelain -z -uall` | scope 判定 |
| `extend_only` 対象のキー集合 | `design-system/tokens.yaml` を parse | scope 判定 |

symlink は git が blob として格納するため、`git hash-object` はリンク文字列をハッシュする。これでリンク先の変更も検出できる。

**dispatch 後の比較（この順序で実行する）**

1. **worker の変更集合を求める**（HEAD の移動有無に関わらず必ず実行）
   - snapshot の index / working tree / untracked 一覧と現在の状態を比較する
   - 削除・mode 変更・存在種別の変化（file ⇔ symlink ⇔ absent）も差分として扱う
   - HEAD 層は**比較に含めない**
2. **許可範囲を判定する**

   変更 path を snapshot 時点の存在有無で 2 分し、それぞれ別の条件で判定する。

   - 変更 path の集合 **=** `written_artifacts` に列挙されたパスの集合（事後報告との一致）
   - **snapshot 時に存在した path**（変更・削除）: すべて `write_policy.targets` に列挙されていること。列挙が無ければ violation。列挙があれば、その `action` に反する変更を受けていないこと
   - **snapshot 時に存在しなかった path**（新規作成）: `allowed_write_roots` 配下、または targets に列挙されていること
   - `extend_only` 対象は既存キーが変更・削除されていないこと

   **パスの正規化と containment 判定**（全比較で共通）:

   - すべて project root からの相対パスへ正規化する。絶対パスは realpath 解決した結果が project root 配下に containment される場合だけ相対化し、そうでなければ拒否する。相対化後に `..` セグメントが生じるパスも拒否する
   - containment は正規化後のパスセグメント列で判定する（`feature-docs/example2` が `feature-docs/example` に含まれると誤判定しないよう、文字列 prefix 比較は使わない）
   - root 自体および配下の各セグメントが symlink である場合、その path は violation として扱う（symlink 経由の root 外書き込みを防ぐ）
   - 比較は case-sensitive で行う。case-insensitive filesystem 上で正規化後のパスが衝突した場合は violation として扱う
3. **違反があれば除去する**
   - tracked ファイルは snapshot の blob から index と working tree の両方へ復元する（dispatch 前が clean であるため、両者の復元先は同一の blob になる）
   - 新規 untracked の violator は `gio trash --` で退避する。`gio` が使えない場合は**削除も移動もせず**、対象パスを列挙してフェーズを中断する
4. **HEAD が動いていたかを判定する**（stale 判定）
   - 動いていなければ、違反なしなら成功、違反ありなら 3 の後にフェーズ中断
   - 動いていれば 5 へ
5. **stale 処理**
   - worker の成果物も破棄する（違反していなくても、古い tip の上で作られたため）
   - `git -C {integration worktree} reset --hard em-workflow/{feature}/integration` で最新 tip へ同期する（linked worktree は branch ref の外部更新に自動追従しないため必須）
   - `input_digest` と `write_policy` を再計算する
   - 新しい `request_id` で再 dispatch する

手順 1 を HEAD の移動より先に置くことで、worker の許可外変更が次の snapshot の baseline に取り込まれない。手順 1 から HEAD 層を外すことで、外部コミットが worker の違反として誤検出されない。

#### 5.11.4 失敗分類と処理

| 分類 | 例 | 処理 |
|---|---|---|
| transient | Task 失敗、応答途切れ | 同一入力で 1 回再 dispatch |
| stale | `input_digest` 不一致、HEAD 移動、`replace_authorized` の digest 不一致 | 5.11.3 の手順 1-5 を実行し、新 request ID で再 dispatch（digest 不一致の場合は再承認を求める） |
| correctable-schema | 必須フィールド欠落、未知 field | 検証スクリプトのエラー出力だけを添えて 1 回再 dispatch |
| scope violation | 許可外ファイル変更 | 5.11.3 の手順 3 で除去してフェーズ中断 |
| semantic invariant | task plan と files 不一致 | 具体的差分を添えて 1 回再 dispatch |
| repeated failure | 同じ失敗が 2 回 | step を failed または needs_update にし中断 |
| user-decision required | SPEC 変更、license 変更等 | question packet へ変換して Ask |
| irrecoverable | YAML 破損、必須入力消失 | 中断 |

worker 出力をオーケストレーターが黙って修正してはならない。機械的な順序整形と digest 再計算を除き、意味変更は再 dispatch する。

#### 5.11.5 fixture

`references/fixtures/` に、検証スクリプトの自己検証用サンプルを置く。

各 `--kind` について、次の分岐を最低 1 件ずつ通す fixture を用意する。ファイル数は固定しない。

| kind | 網羅すべき分岐 |
|---|---|
| `worker-result` | worker ごとに、その worker（および `mode_echo` の値）で**許可された** status の有効な組み合わせ、および各排他条件の違反例。requirements-analyst は `full`（6 status）と `design_system_detection`（`completed` / `blocked` / `failed` の 3 status）を別々に用意し、`mode_echo` 欠落・入力不一致の invalid も含める |
| `question-packet` | `answer_mode` 4 種 × options 件数の境界、`depends_on` / `supersedes` あり |
| `answers` | `answer_mode` ごとの valid と、option ID 不在・モード不一致の invalid |
| `workflow-patch` | `replace_planning` / `append_rework` の valid、許可条件違反・必須 preserve 欠落・expected mismatch の invalid |
| `phase-state` | 5.6.3 の各 status |

valid fixture は終了コード 0、invalid fixture は終了コード 1 になることを確認する。

### 5.12 既存 feature の互換性

phase-state を持たない既存 workflow.yaml の扱いを次に固定する。

| 上流 step の状態 | phase-state | 動作 |
|---|---|---|
| create-spec / create-plan が `completed` | 無い | **phase-state を要求しない**。implement 以降を新フローで続行する |
| create-spec または create-plan が `in_progress` / `pending` | 無い | 新フローでやり直す。既存の REQUIREMENTS.md / SPEC.md / IMPLEMENTATION.md は `write_policy` の digest 不一致ケース（5.4.2）として扱い、interactive では上書き可否を問い、batch では `preserve_and_reuse`（5.9）で既存を正として続行する |
| 任意 | ある | 通常の再開判定（5.6.3） |

**`project.design_system` の backfill**

`project.design_system` を持たない既存 workflow.yaml は、次の手順で補完する。オーケストレーターは dispatch 時に探索しないため、この backfill 以外に値を得る経路はない。

**実施タイミングと Step B での順序**

develop の Step B は「未完了 step を選択 → `in_progress` へ更新 → フェーズ実行」の順で動く（`develop/SKILL.md` 172-178 行）。backfill はこの**最初と 2 番目の間**に入れる。

1. workflow.yaml を読み、未完了 step を選択する
2. 選択した step が `design` または `create-plan` で、かつ `project.design_system` が未設定なら、**`in_progress` へ更新する前に** backfill を実行する
3. backfill 完了後、workflow.yaml を**読み直して step 選択からやり直す**（1 へ戻る）
4. backfill が不要（または完了済み）なら、通常どおり `in_progress` へ更新してフェーズを実行する

`in_progress` へ先に更新しない理由: backfill の質問中にセッションが切れると、step が `in_progress` のまま phase-state も無い状態になり、5.6.3 の再開判定では扱えないため。

両 step より前に完了している feature（例: implement 以降のみ残っている）では実施しない。

**中断時の扱い**: backfill の質問に回答した後、workflow.yaml へのコミット前に中断した場合、その回答は失われる（phase-state を持たない処理のため）。再開時は同じ質問をやり直す。回答は 1 問の選択のみで再入力の負担が小さいため、専用の永続化は設けない。

手順:

1. requirements-analyst を `analysis_mode: design_system_detection`（5.4.1）で dispatch し、`design_system_candidates` を得る
2. interactive: `gate_id: create-spec.design-system` で候補を提示し、`kind` と `paths` を確定する。候補ゼロでも質問して `none` を明示させる
3. batch: `batch-policies.yaml` の `create-spec.design-system` に従う（候補があれば最上位を `project_native`、無ければ `none`）
4. 確定した値を workflow.yaml へ書き、`commit-docs.sh` で `docs({feature}): backfill design_system` としてコミットする
5. 5.4.5 の直積表で不整合（`kind: none` なのに token が実在する等）になった場合は、2 の質問へ戻して再確定させる

backfill は 1 度だけ行う。以降は通常の解決規則（5.0 R1）に従う。

`schema_version` が未知の値（> 1）の phase-state を見つけた場合は中断し、プラグインのバージョン不整合として報告する。

この規則は `references/phase-state.md` に記載する。リポジトリ内のブランチ確認だけでは他 clone や配布済みプラグインの feature を保証できないため、runtime での互換規則として実装する。

---

## 6. 変更対象ファイル

### 6.1 新規作成（計 21 件 + fixture）

**`references/` 配下: 14 件**

| パス | 概要 |
|---|---|
| `references/rework-task-synthesis.md` | interactive / batch × review / verify 共通の rework 契約 |
| `references/phases/create-spec-phase.md` | 対話ブローカー、analyst/writer dispatch、再開、検証 |
| `references/phases/create-plan-phase.md` | planner dispatch、質問処理、patch 検証・適用 |
| `references/question-packet-schema.md` | question packet と answer の出力契約 |
| `references/question-resolution.md` | interactive / batch 共通の packet 解決手順 |
| `references/phase-state.md` | phase-state の永続化・reconcile・互換規則 |
| `references/workflow-patch.md` | 限定 patch 形式、許可操作、atomic apply 規則 |
| `references/batch-policies.yaml` | gate ID ベースの batch 意思決定 SSOT |
| `references/contracts/analyst-contract.md` | requirements-analyst の入出力契約 |
| `references/contracts/spec-writer-contract.md` | spec-writer の入出力契約 |
| `references/contracts/planner-contract.md` | implementation-planner の入出力契約 |
| `references/contracts/rework-planner-contract.md` | rework-planner の入出力契約 |
| `references/contracts/designer-contract.md` | designer の入出力契約 |
| `references/contracts/worker-envelope.md` | 共通エンベロープ（5.3）の契約 |

加えて `references/fixtures/` に 5.11.5 の fixture を置く（ファイル数は実装時に確定）。

**`agents/` 配下: 3 件**

| パス | 概要 |
|---|---|
| `agents/requirements-analyst.md` | 調査・質問生成 worker |
| `agents/spec-writer.md` | REQUIREMENTS.md / SPEC.md 執筆 worker |
| `agents/rework-planner.md` | review / verify 由来の追加 task 計画 worker |

**`scripts/` 配下: 1 件**

| パス | 概要 |
|---|---|
| `scripts/validate-worker-output.py` | worker 出力・packet・answer・patch・phase-state の検証（Python 3 + PyYAML） |

### 6.2 変更

| パス | 変更概要 |
|---|---|
| `skills/develop/SKILL.md` | create-spec / design / create-plan を phase protocol 経由の Task dispatch へ変更。rework 共通 SSOT を参照。`completed_at_commit` の記述を規則 R2 の表現に統一（意味論は変えない）。Step B の step 選択と `in_progress` 更新の間に design_system backfill の分岐を追加（5.12）。design step 分岐に直積検査と再分類ゲートを追加（5.4.5） |
| `agents/designer.md` | 構造化入力・出力、workflow read-only、patch を返さない、commit 禁止、path 単位 write_policy を明文化 |
| `agents/implementation-planner.md` | AskUserQuestion 削除、question packet と workflow patch proposal 方式へ変更。domains SSOT の記述を review-rules.yaml に統一 |
| `references/batch-mode.md` | question packet 経由のゲートを batch-policies.yaml へ移し、それ以外の判断を残す。rework 手順と Codex fallback 詳細を共通文書へ移す |
| `references/review-phase.md` | interactive / batch 双方から rework 共通 SSOT と rework-planner を参照。`needs_rework` 更新順序（5.10）を明記 |
| `references/implement-phase.md` | rework 再入場時に pending task 必須という事前条件を追加（`completed_at_commit` の意味論は現行のまま） |
| `references/workflow-schema.md` | workflow.yaml の唯一の writer をオーケストレーターへ統一。phase-state sibling を追加。domains SSOT を明記。規則 R2 の定義と適用範囲（全 step）を明記。`project.design_system`（`kind` + `paths`）を追加 |
| `references/command-execution-protocol.md` | question packet との接続、`create-spec.command-approval` gate ID を追加 |
| `references/license-compat.md` | 冒頭 3 行の旧 agent 名参照を更新 |
| `references/impl-skills.yaml` | 冒頭 3 行の旧 agent 名参照を更新 |
| `references/templates/requirements-document.md` | 冒頭 3 行の旧 agent 名参照を spec-writer へ更新 |
| `references/templates/spec-document.md` | 同上 |
| `references/templates/test-readme.md` | 冒頭 3 行の旧 agent 名参照を更新 |
| `references/templates/task-plan.md` | 5 行目の旧 agent 名参照を更新（構造マーカーは既存のまま使うため変更しない） |
| `skills/plan-writing/SKILL.md` | domains 語彙の SSOT が review-rules.yaml であることを明記 |
| `skills/design/SKILL.md` | designer 契約変更に伴う共有 artifact 規則の確認・追随 |
| `README.md` | worker 構成、phase-state、batch policy SSOT、PyYAML 依存を反映 |
| `.claude-plugin/plugin.json` | version bump、description の更新 |

### 6.3 移動（新契約へ移植して参照を切り替えた後に旧記述を削除する）

| 移動元 | 移動先 |
|---|---|
| `agents/requirements-spec-creator.md` の Phase 0〜5.6 の制御部分 | `references/phases/create-spec-phase.md` |
| 同ファイルの調査・質問生成部分 | `agents/requirements-analyst.md` |
| 同ファイルの文書生成部分 | `agents/spec-writer.md` |
| `agents/implementation-planner.md` の対話制御部分 | `references/phases/create-plan-phase.md` |
| `references/batch-mode.md` の Rework task synthesis（78-95 行） | `references/rework-task-synthesis.md` |
| 同文書の Codex fallback 詳細 | `references/question-resolution.md` |

### 6.4 削除

| パス / 箇所 | 条件 |
|---|---|
| `agents/requirements-spec-creator.md` | analyst / writer / create-spec-phase への移行完了後にファイル全体 |
| `batch-mode.md` の「Rework task synthesis」本文 | 共通 SSOT 参照への切替後 |
| `implementation-planner.md` の Batch Mode 内の個別三択処理 | batch-policies.yaml と question-resolution への切替後 |
| `workflow-schema.md` の upstream agent 書き込み例外（14-18 行） | オーケストレーター専有へ移行後 |
| develop step 表の「agent 定義を Read してインラインで従う」記述 | 各 phase protocol への切替後 |

最終状態では、Task dispatch されない定義を `agents/` に残さない。

### 6.5 変更不要（確認済み）

| パス | 根拠 |
|---|---|
| `hooks/queue_stop_guard.py` | workflow.yaml の implement status / tasks / journal のみ参照（84 行） |
| `hooks/queue_launch_guard.py` | implementer のみ対象（82 行） |
| `hooks/queue_agent_index.py` | `em-workflow:implementer` のみ索引化（123 行）。新 agent は無視される |
| `hooks/queue_failure_net.py` | implementer のみ対象（39 行） |
| `hooks/queue_taskstop_net.py` | agents.jsonl と journal のみ |
| `hooks/bash_guard.py` | workflow.yaml 中の command のみ探索（103 行） |
| `scripts/commit-docs.sh` | `ARTIFACT_PATHS` が `feature-docs` 全体を許可（147 行）。phase-state は対象内。呼び出し側で `expected_base_tip` を必ず渡す（5.6.2） |
| `scripts/merge-task.sh` | implement フェーズ専用 |
| `agents/review-editor.md` | 共通エンベロープの適用外（2.3） |

新 worker の prompt には `# Task assignment` という見出しを使わない。`queue_agent_index.py` / `queue_launch_guard.py` は `subagent_type` 欠落時のみこの block を fallback として使うため。

---

## 7. 実装順序

一括実施だが、後続が前段に依存するため次の順で進める。

1. `references/rework-task-synthesis.md` を作成し、4 経路から参照させる（3.3 の実バグ修正。単独で完結する）
2. `references/contracts/` 6 件を作成する（worker-envelope + worker 別 5 件）
3. `scripts/validate-worker-output.py` を実装し、`references/fixtures/` の valid/invalid で自己検証する
4. `references/workflow-patch.md` / `references/phase-state.md` / `references/question-packet-schema.md` / `references/question-resolution.md` を作成する
5. `references/batch-policies.yaml` を作成する
6. `agents/designer.md` を構造化入出力へ改修し、develop の design step を Task dispatch へ変更する
7. `agents/implementation-planner.md` を question packet 方式へ改修する
8. `references/phases/create-plan-phase.md` を作成し、develop の create-plan step を切り替える
9. `agents/requirements-analyst.md` と `agents/spec-writer.md` を作成する
10. `references/phases/create-spec-phase.md` を作成し、develop の create-spec step を切り替える
11. `agents/rework-planner.md` を作成し、rework-task-synthesis の execution adapter を接続する
12. `batch-mode.md` を整理し、重複記述を削除する
13. 参照更新（`workflow-schema.md` / `implement-phase.md` / `review-phase.md` / `command-execution-protocol.md` / `license-compat.md` / `impl-skills.yaml` / templates 4 件 / `plan-writing` / `design` / `README.md` / `plugin.json`）
14. 旧 `agents/requirements-spec-creator.md` を削除する

---

## 8. 受け入れ条件

### 8.1 rework の空回り解消

- `references/rework-task-synthesis.md` が存在し、4 つの参照元すべてがこの文書を参照している
- **4 経路すべて**（interactive review / batch review / interactive verify / batch verify）で、implement を pending に戻す前に pending の rework task が 1 件以上 workflow.yaml へ追加される
- `workflow[implement].base_commit` が rework 再入場で変更されない（`append_rework` の必須 preserve に含まれ、`--dry-run-apply` で欠落が拒否される）
- `references/implement-phase.md` に rework 再入場時の事前条件（pending task 必須）が明記されている
- rework で SPEC 変更が必要になった場合、task が作られず create-spec が `needs_update` に戻る
- 各 rework task が `rework_index` で検証カバレッジを**宣言**し、その参照整合が取れている（`covered_by_existing` の ID が実在し、`new_scenarios` が VERIFICATION.md の差分に実在する）。両方が空の task は拒否される。宣言されたカバレッジが意味的に十分かは機械検証の対象外とし、レビュー対象として残す

### 8.2 エージェント定義と実行形態の一致

- `agents/` 配下のすべての定義が Task dispatch される（agent ファイル名の集合と、リポジトリ内 `subagent_type` 参照の集合が一致する）
- `agents/requirements-spec-creator.md` が存在しない
- `skills/develop/SKILL.md` の step 表に「Read してインラインで従う」記述が残っていない
- design step が `Task(subagent_type="em-workflow:designer")` として dispatch される
- 旧 agent 名（`requirements-spec-creator`）への参照がリポジトリ全体に残っていない

### 8.3 workflow.yaml の書き手の一元化

- `references/workflow-schema.md` の Write ownership に upstream agent の例外条項が存在しない
- どの worker 定義にも workflow.yaml への書き込み指示がない
- workflow.yaml の変更を伴う worker（implementation-planner / rework-planner）が `workflow_patch` を返す形になっている
- 実走後の `git log --name-status` で、workflow.yaml を変更したコミットがすべてオーケストレーター起点である

### 8.4 対話の非退行

- create-spec に固定ラウンド上限が存在しない
- 未解決事項の自動 assumption 化がどのパスにも存在しない（`on_unanswered` の値に該当するものがない）
- ループ停止条件が `progress_fingerprint` の差分で定義されている
- 停止時にユーザーへ 3 択（継続 / TBD 記録 / 中断）が提示される

### 8.5 batch モードの移行後ポリシー整合

これは非退行ではなく、意図的な仕様変更を含む移行の整合確認である。

- `references/batch-policies.yaml` に、question packet で表現されるゲートの全 gate ID が存在する
- question packet を経由しない batch 判断が `batch-mode.md` に残っている
- 両者の和集合が、現行 `batch-mode.md` decision table のゲート集合を漏れなく覆う
- batch 実行時に AskUserQuestion が 1 回も呼ばれない
- unlisted gate で option ID へ写像できない場合、仕様変更・セキュリティ・ライセンス・不可逆操作は中断する
- `artifact-overwrite` の `preserve_and_reuse` で、既存成果物が事後条件を満たさない場合に中断する
- batch report に自動回答の `source` と `resolution_note` が含まれる

### 8.6 再開可能性

- create-spec / create-plan の両方で、途中中断後に phase-state から再開でき、回答済みの質問が再提示されない
- phase-state が integration branch にコミットされている
- workflow.yaml に対話履歴が含まれない
- `commit-docs.sh` の exit 4 を受けた後、退避した回答が最新 phase-state へ冪等に upsert される

### 8.7 検証の機械化

- `scripts/validate-worker-output.py` が Python 3 + PyYAML で動作し、PyYAML 不在時に終了コード 2 で報告する
- `references/fixtures/` の valid fixture が終了コード 0、invalid fixture が終了コード 1 になる
- fixture が 5.11.5 の分岐表を網羅する
- answer mode と `selected_option_ids` / `freeform` の整合が invalid fixture で拒否される
- stale patch（`base_input_digest` / `base_workflow_blob` 不一致）、重複 patch ID、`expected` mismatch が拒否される
- `replace_all` を実装開始後の状態へ適用しようとすると拒否される
- `append_rework` で `workflow.implement.base_commit` が preserve に無いと拒否される
- `review-rules.yaml` の domains 語彙と `plan-writing/SKILL.md` 108-117 行の記載が一致する
- 共有契約の検証が「同一ファイルを宣言した task がある場合の `## Shared Components` 存在確認」に限定され、契約内容の妥当性を機械保証しない旨が明記されている
- 各 contract ドキュメントの規則と Python 実装が fixture 経由で一致することを確認できる

### 8.8 リビジョン識別

- stale 判定が `input_digest` の一致で行われ、コミット SHA の直接比較が使われていない
- `input_digest` の構成要素が 5.0 R1 のとおり（workflow blob / 入力成果物 / registry / answers / write policy）である
- `completed_at_commit` の意味論が現行（status 更新コミットの直前 HEAD）から変わっていない
- `references/workflow-schema.md` に R2 の定義と適用範囲（全 step）が明記されている

### 8.9 scope 検証

- HEAD が移動していても scope 比較が実行される（打ち切られない）
- 違反が検出された場合、次の snapshot を取る前に復元・退避される
- worker の変更集合が index / working tree の 2 層だけから算出され、HEAD 層の差分が含まれない
- 並行する merge-task.sh が integration branch を進めても scope violation として誤検出されない
- dispatch 前に integration worktree が clean であることを確認し、clean でなければ dispatch せず原因パスを報告して中断する（自動 clean 化を行わない）
- snapshot 時に存在した既存ファイルの変更は、`write_policy.targets` に列挙が無ければ `allowed_write_roots` 配下でも violation になる
- パス比較がセグメント単位で行われ、`feature-docs/example2` が `feature-docs/example` の配下と誤判定されない
- symlink を経由した root 外書き込みが violation として検出される
- worker 成果物のコミットで exit 4 を受けた場合、reset → `discarded_stale` の記録とコミット → 再 dispatch の順で処理される（記録を再 dispatch 後に回さない）
- 成果物コミットの exit 4 による再 dispatch が連続 1 回で打ち切られ、2 回目はフェーズが `failed` になる
- `stale_redispatch_count` の +1 が `discarded_stale` の記録と同一コミットで永続化される
- `project_design_system` が dispatch 時に探索されず、workflow.yaml の `project.design_system.paths` から読まれる
- `project.design_system.kind` が create-spec で必ず確定する（design が `skipped` でも、候補が 1 件以上あれば確定させる）
- `project.design_system` を持たない既存 workflow.yaml が、design / create-plan の直前に backfill される
- `kind` と token ファイルの実在状態の全組み合わせが 5.4.5 の表で決まり、不整合の 2 ケースは dispatch 前に中断する
- `active_request_id` が phase-state に存在し、`worker_runs[].status` の許可遷移が定義されている
- `discarded_stale` の run が、手順 2 から次の dispatch までの間 `active_request_id` に保持される（この区間だけ null 化の例外）
- backfill が step の `in_progress` 更新より前に実行され、完了後に step 選択からやり直される
- `analysis_mode: design_system_detection` の completed payload が `design_system_candidates` のみを持ち、`resolved_requirements` を含むと検証エラーになる
- worker 出力の `mode_echo` が入力の `analysis_mode` と一致し、欠落・不一致が検証エラーになる（`--input-envelope` で照合。省略時は終了コード 2）
- design system 候補の解決結果が phase run 内で再利用され、analyst の反復 dispatch ごとに再探索されない
- 候補が 500 ファイル / 5 MB を超えた場合、interactive は手動指定を求め、batch は中断する
- design system 候補が `resolved_input_paths.design_system_candidates` で渡され、両 mode の `digest_inputs` に含まれる
- `project.design_system` の直積検査が design と create-plan の両方の preconditions で実施される
- 再分類ゲートの gate_id が `design-system.reclassify` で、design / create-plan から共用される
- `kind: none` かつ token 実在の場合、create-spec へ戻さず再分類ゲートで解決して同じ step から再開する
- `discarded_stale` が `worker_runs[].status` の値であり、phase-state のトップレベル status に現れない
- 再開時に `discarded_stale` の worker_run を持つ `dispatching` 状態が、新 request ID での再 dispatch へ分岐する
- project-native design system が検出された場合、designer の targets から token 2 ファイルが除外される
- `regenerate` 対象が `written_artifacts` にあるとき、その `source` も含まれる
- `allowed_write_roots` に列挙されるのは、ファイル名が worker の判断で決まるディレクトリだけである（パスが確定するファイルは targets で管理する）
- 絶対パスが realpath 解決で project root 配下に containment される場合だけ受理される
- 削除・mode 変更・file ⇔ symlink の変化が差分として検出される
- `gio` が使えない環境で、untracked violator を削除せずフェーズが中断する
- stale 後に `reset --hard` で linked worktree が最新 tip へ同期される

---

## 9. 検証方法

em-workflow は Markdown プロトコルとプロンプトが中心のため、E2E の完全自動化は難しい。ただし次は自動化できる。

### 9.1 自動検証

| 項目 | 手段 | 対応する受け入れ条件 |
|---|---|---|
| valid / invalid fixture の検証 | `scripts/validate-worker-output.py` を `references/fixtures/` に対して実行 | 8.7 |
| fixture の分岐網羅 | 5.11.5 の表と fixture 一覧の突き合わせ | 8.7 |
| agent 定義と dispatch 参照の対応 | `agents/*.md` のファイル名集合と、リポジトリ内 `subagent_type` 参照の集合を比較 | 8.2 |
| 旧参照の残存 | `grep -rn "requirements-spec-creator\|Read してインラインで従う"` | 8.2 |
| batch gate ID の集合比較 | `batch-policies.yaml` の gate ID と、phase protocol 内の `gate_id` 記述を突き合わせ | 8.5 |
| domains 語彙の一致 | `review-rules.yaml` と `plan-writing/SKILL.md` の値比較 | 8.7 |
| workflow patch の適用テスト | `--dry-run-apply` を fixture に対して実行し、expected mismatch / stale / 重複 ID / 必須 preserve 欠落 / replace_all 許可条件違反を拒否することを確認 | 8.7 |
| phase-state reconcile の状態表テスト | 5.6.3 の各状態を fixture 化し、判定結果を確認 | 8.6 |
| `input_digest` の再現性 | 同じ入力から 2 回計算して一致することを確認 | 8.8 |

### 9.2 実走検証

| # | シナリオ | 確認対象 |
|---|---|---|
| 1 | 小さな feature（1〜2 タスク）を interactive で完走 | 全フェーズの遷移、8.2 / 8.3 |
| 2 | interactive review rework | 8.1（task 追加、implement 起動） |
| 3 | batch review rework | 8.1 / 8.5 |
| 4 | interactive verify rework | 8.1 |
| 5 | batch verify rework | 8.1 / 8.5 |
| 6 | create-spec の質問応答中に中断 → 再開 | 8.6 |
| 7 | create-plan の worker dispatch 中に中断 → 再開 | 8.6 |
| 8 | 同じ feature を `--batch` で完走 | 8.5（AskUserQuestion が 0 回） |
| 9 | rework で SPEC 変更を選択 | 8.1（create-spec へ戻る） |
| 10 | spec-writer に digest 不一致の既存 SPEC.md を渡す | 5.4.2（blocked になる） |
| 11 | batch で digest 不一致の既存成果物に遭遇 | 8.5（`preserve_and_reuse` の分岐） |
| 12 | worker dispatch 中に別プロセスで integration branch を進める | 8.9（scope 比較 → 復元 → refresh の順序） |

実走前後で `git log --name-status` と workflow.yaml のスナップショットを保存し、次を確認する。

- workflow.yaml を変更したコミットがすべてオーケストレーター起点であること（8.3）
- phase-state が実際にコミットされていること（8.6）
- `base_commit` が rework 前後で不変であること（8.1）
- `completed_at_commit` が status 更新コミットの親を指していること（8.8）
- worker の scope violation が検出・報告されていること（8.9）

---

## 10. リスクと留意点

### 10.1 一括実施による不整合期間

段階移行ではないため、実装完了までの間 em-workflow は動作しない前提で進める。実装中にこのプラグイン自身を使って別の作業を回すことはできない。

リリース単位で旧参照が残らないよう、9.1 の「旧参照の残存」検査を完了条件に含める。

### 10.2 既存 feature の互換性

5.12 で規則を確定済み。実装時に `references/phase-state.md` へ記載する。

リポジトリ内のブランチ確認だけでは他 clone や配布済みプラグインの feature を保証できないため、runtime での互換規則として実装する。

### 10.3 ターン境界と hook

implement フェーズは並列 6 本のため「launch → ターン終了 → 通知で wake」という非同期設計になっており、`hooks/queue_stop_guard.py` がターン終了をガードしている。

create-spec / create-plan の worker は 1 本ずつの逐次 dispatch であり、同期的に結果を待つ。ターンをまたぐ設計にはしないため Stop hook の追加は不要。新 worker は implementer 型ではないため queue hooks の対象外（6.5）。

Task が途中で停止した場合は phase-state の `dispatching` 状態から再実行する（5.6.3）。この前提を `references/phases/*.md` に明記する。

### 10.4 検証スクリプトの実行環境

`scripts/validate-worker-output.py` は Python 3 + PyYAML に依存する。README の前提条件に記載する。

オーケストレーターがこのスクリプトを Bash で実行するため、プラグイン利用者の環境によっては `.claude/settings.json` の permissions に `Bash(python3:*)` 相当の許可が必要になる。これも README に記載する。

### 10.5 契約ドキュメントと Python 実装の二重管理

JSON Schema evaluator を実装しない選択（5.11.1）により、同じ規則が `references/contracts/*.md`（worker 向け）と `scripts/validate-worker-output.py`（検証用）の 2 箇所に存在する。

drift を防ぐため、両者の一致は `references/fixtures/` で担保する。contract を変更したら対応する fixture を追加・更新し、検証スクリプトがその fixture を正しく判定することを確認する。

各規則の SSOT は次に固定し、他文書には要約と参照だけを置く。

| 規則 | SSOT |
|---|---|
| worker 入出力の構造 | `references/contracts/*.md` |
| その機械検証 | `scripts/validate-worker-output.py` + `references/fixtures/` |
| workflow patch の許可操作 | `references/workflow-patch.md` |
| phase-state の構造と再開判定 | `references/phase-state.md` |
| batch のゲート解決 | `references/batch-policies.yaml` + `references/question-resolution.md` |
| rework の合成契約 | `references/rework-task-synthesis.md` |
| domains 語彙 | `references/review-rules.yaml` |
| impl skills 語彙 | `references/impl-skills.yaml` |
| `completed_at_commit` の意味論 | `references/workflow-schema.md` |

phase protocol と agent prompt には SSOT へのパス参照のみを書き、値を複写しない。

### 10.6 その他の重大リスク

| リスク | 対策 |
|---|---|
| worker 入力の陳腐化 | 規則 R1 の `input_digest` を dispatch 前後で比較（5.0） |
| `completed_at_commit` の自己参照 | 現行の意味論（status 更新コミットの直前 HEAD）を維持（5.0 R2） |
| worker dispatch 中の branch tip 移動 | 5.11.3 の手順 1-5。scope 比較を先に行い、違反を除去してから refresh。scope 集合は index / working tree の 2 層のみから算出し、外部コミットを誤検出しない |
| linked worktree が branch ref に追従しない | stale 処理で `reset --hard` を明示（5.11.3 手順 5） |
| worker 再 dispatch による成果物の重複・上書き | path 単位 `write_policy` の digest 照合（5.4.2）と `request_id` 単位の冪等性（5.6.1） |
| `allowed_write_roots` 配下の既存ファイルへの意図しない書き込み | 既存ファイルの変更は targets への明示列挙を必須とする（5.4.2 / 5.11.3） |
| 成果物コミット時の exit 4 による成果物消失 | reset して再 dispatch に固定（5.6.2）。成果物の再適用は試みない |
| 並行 merge の高頻度による再 dispatch ループ | 連続 1 回の上限と `stale_redispatch_count` の永続化（5.6.2） |
| 外部プロセスが integration worktree を直接変更 | 排他前提を規範として明記（5.11.3）。許可範囲外の変更は拒否されるが、許可範囲内で worker が `written_artifacts` に含めた変更は識別できない（snapshot 方式の原理的限界） |
| glob 解決結果の worker 間・実行間の不一致 | `resolved_input_paths` をオーケストレーターが 1 度だけ解決し、designer と planner へ同じ一覧を渡す（5.0 R1） |
| packet / question / patch ID の衝突 | 5.6.1 の一意性規則と、内容不一致時の protocol error |
| rework 後の traceability drift | `rework_index` によるカバレッジ宣言の必須化（5.4.4）と cross-artifact 検証 |
| `design-system/` 変更による feature 間競合 | `extend_only` と、既存キー改変の scope violation 判定（5.11.3） |
| phase-state の肥大化 | 5.6.4 のサイズ管理。`worker_runs` は digest のみ保持 |
| 実装開始後の `replace_all` による計画消失 | 5.5.1 の許可条件（全 task が pending のときのみ） |
