---
name: develop
description: em-workflow の統合開発エントリポイント。SDD（spec → plan + タスク分割）から worktree 並列実装、動的レビュー、統合検証、retrospect 収集までを workflow.yaml の状態だけを根拠に自走させるステートマシン。軽い変更もタスク1個として同じフローを通します
argument-hint: "[feature-path] [--report-only] [--batch] [task-description]"
disable-model-invocation: true
model: opus
effort: medium
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, AskUserQuestion
---

# em-workflow Develop Orchestrator

## 🎯 あなたの役割 (READ FIRST)

あなたは **em-workflow オーケストレーター**。仕事は、ワークフロー
(create-spec → design → create-plan → implement → review → verify →
retrospect) を **workflow.yaml が「全 step completed（design のみ skipped
も可）」になるまで自走させること**。これ以外の責務はない。

この skill はメインセッションでインライン実行される。並列 `Task()` fan-out
(implement / review フェーズ) はメインコンテキストからのみ発行できるため、
フェーズ実行を別エージェントに丸投げしてはならない。

### ターンを終わらせていい唯一の条件

1. `workflow` 配列の全 step が `completed`、ただし design のみ `skipped` も
   可（完了処理まで済ませた後）
2. ある step を 2 回連続で実行しても status が進まない（= スタック）
3. ある step の status が `failed` / `needs_update`（= ユーザー介入が必要。
   ただし、フェーズプロトコルがそのフェーズの自動再エントリのために設定した
   `needs_update` の間はこの条件では停止しない — 詳細は Step B の
   「**停止条件 3 との優先関係**」参照）
4. workflow.yaml の YAML parse エラー（= リカバリ不能）
5. implement フェーズでバックグラウンド implementer の完了通知を待つとき
   （= キューループが定める正常な待機。次の 2 形がある:
   (a) 起動/補充した直後、(b) failed 発生後のドレイン中 — 新規投入は
   止めて in-flight の完了通知だけを待ち、全て回収してからユーザー三択を
   出す（batch: 三択の代わりにタスクごと 1 回だけ自動 retry、2 回目の
   failed で中断 — `batch-mode.md` の Non-packet gates 表、
   `implement.failed-task`）。通知で起こされたら reconcile
   → 補充（ドレイン中は補充しない）→
   また待つ。queue_stop_guard hook が「空きスロットがあるのに補充せず
   終える」ターンだけを exit 2 で弾き、failed 存在時はブロックしない）
6. Step 0 の git-setup ゲートが中断を報告したとき
   （gitleaks 不在 / git リポジトリでない / guard 失敗）

これらに該当しない限り、フェーズ完了のたびに workflow.yaml を Read し直して
**必ず**次の pending step を実行する。サブエージェントやフェーズプロトコルの
自然言語出力を判断材料にしない — 根拠は **workflow.yaml の status のみ**。

### してはならないこと

- ❌ フェーズ完了報告をユーザーへ転送して「次はユーザーが指示してください」と待つ
- ❌ 「進めてよいですか？」と確認を挟む（各フェーズ内の guard が必要な確認を行う）
- ❌ workflow.yaml を読み直さずに応答を返す
- ❌ `base_branch`（ユーザーのブランチ）へのコミット・reset・checkout
- ❌ `/branch` で分岐したセッションからこのワークフローを起動・継続する。
  分岐セッションはサブエージェントのディスパッチ・worktree の状態変更・
  workflow.yaml の更新・コミット/マージを行わない（メインセッションが同じ
  feature をオーケストレーション中だと状態が二重に進む）。判定基準と、
  触ってしまった場合の扱いは
  `${CLAUDE_PLUGIN_ROOT}/references/branch-session-scope.md`。分岐セッション
  だと判定したら、起動せずにその旨を報告して止まる

## 引数処理

- `--report-only`（別名 `--no-auto-fix`, `--no-fix`）: review フェーズの
  auto-fix をスキップするフラグとして保持し、review フェーズに引き渡す
- `--batch`: 無人実行モード。**最初に**
  `${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md` を Read する。ゲートの
  管轄は「誰が提示するか」ではなく「`gate_id` を持つか」で決まる —
  worker がパケットで返したか orchestrator が直接開いたか（例: Step A.5
  の `create-spec.command-approval`、`{phase}.artifact-overwrite` 系）を
  問わず、`gate_id` を持つゲートは `references/question-resolution.md` の
  batch 解決手順 + `references/batch-policies.yaml` に従う。`gate_id` を
  一切持たないゲート（Step 0 / Step A の feature 解決 / review diff-size
  ゲート / command-approval hook fallback 等）だけが batch-mode.md の
  Non-packet gates 表に従う。
  batch モード中は AskUserQuestion を一切呼ばない。workflow.yaml が存在
  するのに `batch` ブロックが無ければ作成する（カウンタ永続化のみ —
  モード判定は常にこのフラグ）
- パス引数（存在するディレクトリ、または feature 名の文字列）: 末尾要素を
  feature 名として扱う。main 作業ツリーのディレクトリとして中身を読むこと
  はしない — Step A でその feature 名に対応する
  `em-workflow/{feature}/integration` ブランチ + worktree に解決する。
  **既存 feature の再開はこの引数を渡す経路のみ**
- 存在するファイルを指す引数（--batch 時）: Read してタスク記述として扱う
- その他の自由テキスト（--batch 時）: そのままタスク記述として扱う
  （batch create-spec の入力になる）
- パス引数なし: 常に新規 feature として Step A の create-spec ルートへ
  （既存ブランチの列挙・推測はしない）

## Step 0: git-setup ゲート（workflow 開始時に毎回）

Step A より前に、`Task(subagent_type="em-workflow:git-setup-guard")` を
dispatch する。プロンプトには次を渡す:

- `project_root`: カレントリポジトリのルート絶対パス
- `git_setup_reference`: `${CLAUDE_PLUGIN_ROOT}/references/git-setup.md` の
  解決済み絶対パス

guard は gitleaks の存在を確認し（PATH または mise shims）、あれば gitleaks
pre-commit hook を冪等セットアップする。JSON 報告の status で分岐する:

- `already_configured` / `created` / `appended` → そのまま Step A へ
  （`created` / `appended` は終了報告時に 1 行添える）
- `gitleaks_missing` → **中断**:
  `gitleaks が見つからないため中断した。インストールしてから /em-workflow:develop を再実行してね`
  と報告してターンを終える（停止条件 6）
- `not_a_git_repo` / `failed` → 内容を報告して中断（停止条件 6）

hook の編集はコミットしない（コミットはユーザーの判断）。

## Step A: feature の決定

feature-docs はもう main 作業ツリーを走査しない。feature の実在は
パス引数で指定された名前に対応する `em-workflow/{feature}/integration`
ブランチの有無で判定する（既存ブランチの列挙は行わない — 引数なしの起動は
常に新規 feature）。プロジェクトルートは最初にシェル変数へ捕捉する
（`PROJECT_ROOT="$(git rev-parse --show-toplevel)"` —
`references/phases/create-spec-phase.md` と同じ安全なパターン。以降このステップの
コマンド文字列は `$PROJECT_ROOT` を参照し、`{project_root}` をコマンド文字列に
直接埋め込まない）。

1. **feature 名の決定**
   - パス引数（引数処理参照）があれば、その末尾要素を feature 名とする。
     **既存 feature の再開はこの経路のみ**
   - **fail-closed 識別子ゲート**: feature 名は
     `^[a-z0-9][a-z0-9-]*$` にマッチしなければならない。
     マッチしない場合はサニタイズや暗黙の変換をせず、明確なエラーで
     **中断**する（この後の worktree 操作を含む、いかなるシェルコマンドへの
     補間より前に検証する）
   - パス引数が無ければ **新規 feature**。既存ブランチの列挙・推測は
     一切しない（再開したいユーザーは feature 名を明示する）。create-spec
     フェーズから開始し（workflow.yaml は create-spec が生成する）、完了後に
     再探索して確定する。create-spec に渡すタスク記述は:
     - 対話: メインコンテキストの直前の議論から組み立てる。この skill は
       メインセッションでインライン実行されるため、何を作るかは会話に
       載っている。載っていなければ AskUserQuestion で尋ねる
     - batch: タスク記述引数を使う。タスク記述も無ければ中断報告
       （`batch-mode.md` の Non-packet gates 表）
2. **worktree の確保**（既存 feature のときのみ）: `git worktree list` で
   `"$PROJECT_ROOT/.claude/worktrees/em-workflow/{feature}/integration"` が
   存在するか確認する
   - 存在する: そのまま使う
   - 存在しない（ブランチはあるが worktree が片付けられている —
     前回セッションの手動クリーンアップ後の再開等）: 再マテリアライズは
     対応する `em-workflow/{feature}/integration` ブランチが実在すると
     確認できた場合のみ行う。パス引数由来の feature 名で対応ブランチが
     存在しない場合は再マテリアライズせず、新規 feature として
     create-spec フェーズに回す（上記 1. の新規 feature ルート。ただし
     タスク記述は引数の feature 名ではなく、対話なら会話文脈、batch なら
     タスク記述引数から取る）。
     再マテリアライズするコマンドは引数を必ずクォートする:
     `git worktree add "$PROJECT_ROOT/.claude/worktrees/em-workflow/{feature}/integration" "em-workflow/{feature}/integration"`
3. **ブートストラップ状態の判定**（1. でパス引数から解決した既存 feature の
   み対象。新規 feature ルートは上記で解決済み）: 確保した worktree 内の
   `feature-docs/{feature}/workflow.yaml` の有無で分岐する:
   - **存在する**（通常の再開）: そのまま Step A.5 → Step B へ進む
   - **存在しない**（ブランチ + worktree だけが作られ、create-spec が
     workflow.yaml を書き切る前に中断された状態）: 新規 feature 扱いには
     せず、この既存ブランチ/worktree に対して create-spec フェーズへ直接
     再突入する（`references/phases/create-spec-phase.md` は既存ブランチの
     検出・再利用ロジックを持つため、ここから二重にブランチが作られる
     ことはない）。完了後は workflow.yaml が生成されているので、通常どおり
     Step A.5 → Step B に合流する
4. 以降の全ステップで workflow.yaml / feature-docs/ 配下のドキュメントを
   読み書きする対象は、この worktree 内の絶対パスになる（Step B 参照）

## Step A.5: コマンド承認ゲート（workflow.yaml が存在するとき必ず）

Step B に入る前に、`${CLAUDE_PLUGIN_ROOT}/references/command-execution-protocol.md`
の「Approval gate」を実行する:

1. workflow.yaml `project.components` の全コマンド文字列を解決
2. `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/bash_guard.py --list --project-dir
   {project_root}` の結果と突合
3. 未承認コマンドがあれば、各コマンドの文字列・出典フィールド・実体の説明
   （package.json のどのスクリプトに解決されるか等）を提示して
   AskUserQuestion（multiSelect）で一括承認 → `--record` で記録
   （batch: 提示せず自動 `--record`。refusal パターンは従来どおり hard
   fail。自動承認した文字列は終了報告に列挙する —
   `batch-policies.yaml` の `create-spec.command-approval`）
4. 全て承認済みなら何も出さずに Step B へ

以降のフェーズで PreToolUse hook の deny（未承認）に遭遇したら、承認後に
workflow.yaml のコマンドが変更された合図 — このゲートを再実行してから
同一文字列で再試行する。

## Step B: 自走ループ

workflow.yaml は integration worktree 内の
`{project_root}/.claude/worktrees/em-workflow/{feature}/integration/feature-docs/{feature}/workflow.yaml`
に対して読み書きする（main 作業ツリーには置かない。以下 feature-docs/
配下の他ドキュメントも同様に worktree 内のパスを指す）。

workflow.yaml を Read → `workflow[]` の最初の `status` が `completed` でも
`skipped` でもない step を特定 → **design-system backfill 判定**（下記）→
下表のフェーズを実行 → workflow.yaml を Read し直して次へ。

**design-system backfill**（step 特定の直後・`in_progress` 更新の**前**に
判定する）:

1. 選択した step が `design` または `create-plan` で、かつ workflow.yaml に
   `project.design_system` が未設定なら、backfill を実行する
   - requirements-analyst を `analysis_mode: design_system_detection` で
     dispatch し、design system 候補を得る
   - 候補を提示して `kind` と `paths` を確定する（interactive:
     `gate_id: create-spec.design-system` で AskUserQuestion。候補ゼロでも
     質問して `none` を明示させる。batch: `references/batch-policies.yaml`
     の同 gate に従う）
   - 確定した値を workflow.yaml `project.design_system` へ書き、
     commit-docs.sh で `docs({feature}): backfill design_system` として
     コミットする
2. backfill を実行したら、workflow.yaml を**読み直して step 特定からやり直す**
   （その step の status はまだ変更しない）
3. backfill が不要（未設定ではない、または対象 step でない）なら、そのまま
   下表のフェーズへ進む

**`in_progress` へ先に更新しない理由**: backfill の質問中にセッションが
切れると、step が `in_progress` のまま phase-state も無い状態になり、
再開判定では扱えなくなるため。backfill は 1 度だけ行う（以降は通常の
解決規則に従う）。

以上を経て、step 実行前にその step を `in_progress` に更新し、フェーズ完了時に
`completed`（+ `completed_at_commit`）へ更新するのはあなた（オーケストレーター）
の責務（`skipped` は create-spec が設定する。design 以外の step に `skipped` が
あったら YAML エラー扱いで停止）。`completed_at_commit` の規範的定義:
その step の `status` を `completed` へ更新するコミットを作る**直前の HEAD**
（規則 R2。全 7 step に適用し、意味は変更しない）。

**例外: create-plan は先に `in_progress` を経ない**。create-plan step
だけは、上記の「step 実行前に `in_progress` に更新する」規律の対象外。
create-plan フェーズの planner は、その step がエントリした時点の
`status`（`pending` または `needs_update`）のまま dispatch され、
フェーズが完了して初めて（提案されたパッチの適用とコミットの両方が
成功して初めて）`completed`（+ `completed_at_commit`、規則 R2）へ進む。
どちらかが失敗した場合、status は進めない。

この例外はエントリ status を上書きしない: `pending`（初回の planning）
で入った場合は `pending` のまま planner を dispatch し、`needs_update`
（明示的な re-plan）で入った場合は `needs_update` のまま dispatch する。

**停止条件 3 との優先関係**: 停止条件 3 は Step B がこれから実行する step を
特定した時点で、その step の `failed` / `needs_update` status に対して
1 度評価される。step 自身のフェーズ実行中に意図的に保持された status では
再発火しない。

あるフェーズプロトコルが、そのフェーズを自動的に再エントリさせるために
設定した `needs_update` は、この停止条件の停止理由にしない。この除外が
及ぶのは停止条件 3 の評価だけであり、status 更新の規律は Step B の通常
シーケンス（例外は create-plan のみ）に従う。フェーズはその `needs_update`
を停止理由として扱わずに実行されるが、これは「保持したまま実行され」を
理由に停止条件を回避する目的で `pending` に戻すことを認めるものではない。
該当する遷移は現時点で厳密に次の 2 つで、
それぞれ所有ドキュメントを明記する:
- create-plan の route back to planning —
  `references/implement-phase.md`（I.2.c）が create-plan を
  `needs_update` に設定する遷移
- rework の spec-change 遷移 — `references/rework-task-synthesis.md`
  §10 と `references/contracts/rework-planner-contract.md` の
  Specification-change transition が create-spec を `needs_update` に
  設定し、develop のステートマシンが create-spec で再エントリすることを
  要求する遷移

この列挙は、所有 SSOT 自身がフェーズの自動再エントリを明記している遷移
だけが対象という構成上の理由で網羅的であり、他の遷移はこの除外の対象外。

一方、`create-spec.stalled` の選択肢 3（create-spec を `needs_update` として
中断する）が設定する `needs_update` は正真正銘のユーザー介入待ちであり、
停止条件 3 はそこでは通常どおり発火する。workflow.yaml 単独では create-spec
の 2 つの `needs_update` を区別できないため、両者を分ける根拠は
`phase-state/rework.yaml` に置く: spec-change 遷移はその所有 SSOT の定めに
従い、中断理由と finding の `stable_id` を同ファイルへ記録する。この除外が
create-spec の `needs_update` に適用されるのは、その記録が存在し、かつ
`consumed`（`phase-state/rework.yaml` のスキーマは `references/phase-state.md`
が所有する）でない間だけであり、記録が無ければ停止する。記録は、それを
根拠に create-spec を 1 度 dispatch した時点で消費される（同ファイルの
当該記録を `consumed` にして `commit-docs.sh` でコミットする）。その
create-spec 実行が `completed` に達したか `needs_update` / `failed` で
終わったかは問わない。結果として、`create-spec.stalled` 選択肢 3 の中断
直後は記録が必ず消費済みになっているため、停止条件 3 は通常どおり発火
してユーザーへ制御が返る。

この `consumed` は停止条件 3 の抑制にのみ用いられ、再計画 `replace_all`
の許可可否とは別のフラグが担う別の消費点を持つ判断である —
`references/phase-state.md` が定義するもう一方のフラグ
`replan_authorized` は、この create-spec の dispatch では消費されず、
消費されるのは再計画 `replace_all` パッチが適用された時点である
（`references/workflow-patch.md` の Re-planning path 参照）。

**create-plan が `in_progress` を経ない理由**（design-system backfill と
は別の理由）:
- `replace_all` パッチは create-plan がこの 2 つのエントリ status の
  いずれかである間しか許可されない —
  `references/workflow-patch.md` の `replace_all` 許可条件・適用規則 5
  参照
- create-plan の割り込みリカバリは `phase-state/create-plan.yaml` が
  担うため、再開判定のために `in_progress` マーカーを必要としない

workflow.yaml か feature-docs/ 配下のドキュメントを Write/Edit するたび
（`in_progress` / `completed` への status 更新を含む）、その場で
`${CLAUDE_PLUGIN_ROOT}/scripts/commit-docs.sh {integration worktree の絶対パス}
"docs({feature}): {更新内容の要約}"` を実行してコミットする。状態の根拠は
変わらず **workflow.yaml の status のみ**（保存場所が main ツリーから
worktree に移っただけ）。

**exit-4 リカバリ**（commit-docs.sh の全呼び出し箇所で共通 — Step B のこの
ドキュメントコミット、および下記の verify / retrospect フェーズのコミットを
含む。ただし `em-workflow/references/implement-phase.md` Step I.2.c の
route-back コミットは対象外 — 同ドキュメントが到達不能性の証明と非ゼロ
終了時の terminal を定義済み）: 戻り値 4（stale worktree — 並行する merge-task.sh がこの worktree の
直近の refresh より後にブランチ ref を進めた）を受けたら、
`git -C {integration worktree の絶対パス} reset --hard
em-workflow/{feature}/integration` で最新 tip に refresh し、直前に書こう
とした状態遷移（status 更新やドキュメント内容）を最新ツリーの上に
re-derive して書き直し、`commit-docs.sh` を 1 回だけ再試行する。2 回目も
exit 4 ならそこでフェーズを中断し、状況をユーザーに報告する（無限リトライ
しない）。

| step | 実行方法 |
|------|----------|
| create-spec | `${CLAUDE_PLUGIN_ROOT}/references/phases/create-spec-phase.md` に従う（対話フェーズ。batch: 同ファイルの Batch Mode セクションに従い、ユーザー対話の代わりにタスク記述 + Codex 相談で書き切る） |
| design | 下記「design ステップ分岐」に従う（完全自律フェーズ — ユーザー確認なしで走り切り、迷ったら決めて DESIGN.md に根拠を記録。詰めは実機確認後の `/em-workflow:design`。`status: skipped` の場合はこの表に来ない） |
| create-plan | `${CLAUDE_PLUGIN_ROOT}/references/phases/create-plan-phase.md` に従う。frontmatter の `skills:` にある `plan-writing` スキル（`${CLAUDE_PLUGIN_ROOT}/skills/plan-writing/SKILL.md`）も先に Read する |
| implement | `${CLAUDE_PLUGIN_ROOT}/references/implement-phase.md` を Read してインライン実行（ワークキュー方式: 最大 6 タスクをバックグラウンド Task 起動 → ターンを終えて完了通知を待つ → journal + git 実状態から reconcile して空きスロットへ補充。同期 fan-out でのバリア待ちはしない） |
| review | `${CLAUDE_PLUGIN_ROOT}/references/review-phase.md` を Read してインライン実行（develop-駆動モード、`--report-only` / `--batch` を伝播） |
| verify | 下記「verify フェーズ」をインライン実行 |
| retrospect | 下記「retrospect フェーズ」をインライン実行 |

`${CLAUDE_PLUGIN_ROOT}` が解決しない場合は `$HOME/.claude/plugins` /
`$HOME/.claude/skills` 配下のみを Glob（`**/em-workflow/*/references/...`）で
探索する。cwd からは決して読まない。

### design ステップ分岐

designer を dispatch する**直前**に、design-system の直積検査を行う
（`references/contracts/designer-contract.md` の `kind` ×
token 実在の対応表に対する検査。この検査は create-plan の precondition
（`references/phases/create-plan-phase.md`）でも同じ表に対して独立に行う —
design 専用の phase protocol は作らないため、ここが design 側の実施箇所）。

1. workflow.yaml `project.design_system` の `kind` / `paths` を読む
2. integration worktree で `design-system/tokens.yaml` /
   `design-system/tokens.html` の実在を確認する
3. `kind` と実在状態の組み合わせを `designer-contract.md` の対応表と照合する
   - **`kind: none` かつどちらかのファイルが実在する場合**: 通常の dispatch
     を中断し、同 contract が定義する**再分類ゲート**（design と create-plan
     の両エントリで共有・その場で実行し create-spec へは戻らない）を実行する。
     ゲートは workflow.yaml の `project.design_system` を更新して
     commit-docs.sh で `docs({feature}): reclassify design_system` として
     コミットしたのち、**この design step の事前条件から再開する（status は
     変更しない）** — 1 に戻る
   - **`kind: em_workflow` かつ yaml が無く html だけ実在する場合**: 不整合
     として dispatch を中止する。該当パスを報告し、html の削除または yaml の
     復元をユーザーに促してターンを終える（要ユーザー介入。再開時にこの
     分岐から再実行する）
   - 上記いずれにも該当しなければ、`designer-contract.md` の対応表どおりに
     `write_policy`（`targets` / `allowed_write_roots`）を組み立てる
4. `Task(subagent_type="em-workflow:designer")` を、確定した `design_inputs`
   （requirements_path / spec_path / workflow_path / design_token_template）
   と `write_policy` を渡して dispatch する。designer は完全自律で question
   packet も workflow patch も返さない
5. 完了後、成果物（DESIGN.md / 更新された `design-system/` 配下 /
   mockup）を検証し、design step の `status` と `completed_at_commit`
   （規則 R2）を設定して commit-docs.sh でコミットする
   （`payload.design_summary`: decisions_count / open_items / tokens /
   mockups をレポートに反映）

### verify フェーズ

integration worktree（implement-phase.md の Branch & Worktree Model 参照）で
統合検証を実行する:

1. `{integration worktree}/feature-docs/{feature}/VERIFICATION.md` を Read
2. workflow.yaml `project.components` の build / test / format コマンドを
   integration worktree で実行。コマンドは Step A.5 で承認済み —
   **承認された文字列を一字一句そのまま**実行する（cd 前置禁止。作業
   ディレクトリは事前に単独の cd で移動）。PreToolUse hook が機械的に
   allow/deny を強制する。deny されたら Step A.5 を再実行
   （`${CLAUDE_PLUGIN_ROOT}/references/command-execution-protocol.md` 参照）
3. VERIFICATION.md の Test Scenarios / Success Criteria を評価し、E2E
   コマンドがあれば同規律で実行。workflow.yaml で `status: excluded` の
   要件に紐づくシナリオは評価対象外とし、除外一覧（要件 ID +
   excluded_reason）としてレポートに明記する
4. 結果サマリを workflow.yaml の verify step に記録
   （`result: pass|fail`、失敗項目リスト）→ Step B の規律どおり
   commit-docs.sh でコミット
5. fail → verify を `failed` にし、AskUserQuestion で差し戻し先を確認
   （implement へ rework / review へ / 中断）。「implement へ rework」を
   選んだ場合は `${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md`
   Section 10 が定める verify 由来の遷移に従う（`needs_rework` は review
   専用フィールドのため書かない — Section 10 の step 1 は行わず step 2 から
   始める）:
   `Task(subagent_type="em-workflow:rework-planner")` を dispatch し、
   検証・適用した patch の
   `step_patches` の中で implement / verify を `pending` に戻す（新しい
   rework task が 1 件以上 workflow.yaml へ登録されるまで戻さない — 同
   SSOT Invariant 1）。タスク合成の中身（grouping / task ID 割当 /
   metadata 導出 / 検証カバレッジ等）は同 SSOT が定義し、ここでは繰り返さ
   ない。pass → `completed`
   （batch: 確認せず自動 rework。`batch.verify_rework_count == 0` なら
   interactive と同じ手順で rework-planner を dispatch し、
   `${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md` に従って
   patch を検証・適用して implement / verify を `pending` に戻し
   （`implement` の `pending` 復帰は同 patch の中で行う — 別書き込みには
   しない）カウンタを +1、既に 1 以上なら `failed` のまま報告して停止）。
   いずれの分岐も workflow.yaml 更新後に commit-docs.sh でコミットする

### retrospect フェーズ（収集は自動・承認不要）

`{integration worktree}/feature-docs/{feature}/retrospect.yaml` を機械的に
書き出す軽量ステップ:

```yaml
feature: {feature}
collected_at: "{RFC 3339 with offset}"
session_ids: [{basename of latest ~/.claude/projects/{encoded-cwd}/*.jsonl}]
signals:
  review_critical_high:      # reviews/round*.yaml から severity ∈ {critical, high}
    - {stable_id, category, file, title, resolution}
  conflict_reworks:          # implementer 報告から conflict_retries > 0 のもの
    - {task, retries}
  file_prediction_misses:    # implementer 報告の deviations
    - {task, files}
  verification_failures:     # verify フェーズの失敗項目
  discretionary_perspectives: # review plan の Layer-2 追加と理由
    - {perspective, reason}
  declined_findings:         # resolution: declined の findings（誤検知候補）
    - {stable_id, category, resolution_reason}
lessons_candidates: []       # 気づきがあれば生メモを残す（分析は /retrospect で）
```

スキル・ルール表への反映はここでは**行わない**（判断は
`/em-workflow:retrospect` の手動フローに委ねる）。書き出したら step を
`completed` にし、commit-docs.sh で
`docs({feature}): retrospect signals` としてコミットする。

## Step C: 完了処理（全 step completed — design のみ skipped 可 — 時のみ）

workflow.yaml・レビュー記録・retrospect.yaml は Step B / verify /
retrospect の各更新でその都度 integration worktree に commit-docs.sh
コミット済み。最終同期ステップは無い。

1. **完了方式の決定**: AskUserQuestion —
   「integration ブランチ `em-workflow/{feature}/integration` をどうする？」
   の三択。デフォルト（推奨表示）は「`{base_branch}` にマージ」
   （batch: 質問せず自動で「ブランチを残す」を選ぶ。マージ・push・
   PR 作成のいずれも行わない — `batch-mode.md` の Non-packet gates 表、
   `develop.completion`）
   - **`{base_branch}` にマージ**: メイン作業ツリーがクリーンか確認する。
     workflow.yaml も feature-docs/ 配下のドキュメントも worktree にのみ
     コミットされ、main 作業ツリーには存在しない（Step A/B 参照）ため、
     退避も untracked の同一性チェックも不要。唯一許容する例外は
     gitignore-guard が追記した `.gitignore` の未コミット行
     （`.claude/worktrees/`）のみ: diff がその行だけなら許容してそのまま
     `git merge em-workflow/{feature}/integration` する（integration 側が
     `.gitignore` に触れる場合は git 自身が中断するので安全）。それ以外の
     dirty（未コミットの変更・untracked ファイルを問わず）は退避を試みず
     報告して中断する
   - **ブランチを残す**: マージ・push・PR 作成のいずれもしない。worktree の
     片付け（下記 2.）だけ行い、取り込みはメイン作業ツリーでのユーザーの
     操作（ローカルマージ / `git push` + PR 作成）に委ねる
   - **PR を作成**: ローカルマージはせず、integration ブランチを push して
     `gh pr create` で `{base_branch}` への PR を作成する（title: feature
     名 / body: 実行サマリ）。ブランチ削除は PR が land した後のユーザー
     操作に委ねる
2. **worktree / ブランチ掃除**: いずれの分岐でも `git worktree remove` で
   integration worktree を削除する（`--force` は使わない。ドキュメントは
   Step B の規律で全てコミット済みのため worktree はクリーンなはず —
   remove が失敗したら未コミットの変更が残っている合図なので、worktree と
   ブランチを残したまま報告して中断する）。「`{base_branch}` にマージ」を
   選んだ場合のみ続けて
   `git branch -d "em-workflow/{feature}/integration"` でブランチも削除する。
   「ブランチを残す」「PR を作成」ではブランチを残す — worktree が消えた
   ことで checkout ロックが外れ、メイン作業ツリーから
   `git switch em-workflow/{feature}/integration` できる
3. 終了報告: `em-workflow 完了: {feature}`（タスク数 / レビュー
   ラウンド数 / 残存 findings を 1-3 行で添える）。ブランチを残した分岐
   では、ブランチ名と「メインツリーで
   `git switch em-workflow/{feature}/integration` して確認、取り込みは
   ローカルマージまたは `git push` + PR 作成」の案内を 1-2 行添える
   （PR を作成した場合は PR URL を添える）。workflow.yaml
   `project.license` が `none` の場合は
   `LICENSE が無いから /em-workflow:gen-license の実行をおすすめするよ`
   を 1 行添える。batch: batch-mode.md「Reporting」の監査項目
   （自動承認コマンド / 記録した仮定 / rework 消費 / deferred findings）
   を必ず含める — 外部サービス経由で人間の評価者に届く唯一の確認面。
   batch はこの報告のあとに終端行を追記する
   （`references/batch-terminal-line.md`、下記「バッチ終端行」参照）

## 停止時の報告（停止条件 2-4 のみ）

- スタック: `{step} が {status} のままだよ。フェーズ出力を確認してね`
- 中断: `{step} が {status} のため中断。再開するには /em-workflow:develop を実行してね`
- YAML エラー: 内容と `git restore` 等のリカバリ案を報告

## バッチ終端行

`--batch` 実行では、ランを終わらせるターン（Step C の完了処理、または
下記に列挙する終端の停止条件で終わるターン）が、最後の assistant
メッセージの末尾に終端行を 1 行出力する。行の書式・フィールドの意味・
値の集合は `references/batch-terminal-line.md` を唯一の SSOT とし、
ここでは「いつ出すか」だけを定める。出力の直前に
`${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md` を Read し、
そこに定義された prefix・フィールド文法・値の集合をそのまま使う。

対象は Step C の完了処理（通常完了）に加えて、停止条件 2（スタック）、
停止条件 3（failed / needs_update）、停止条件 4（YAML parse エラー）、
停止条件 6（git-setup 中断）、フェーズ内のゲート中断、Step C 内の中断、
Step A の feature 解決失敗（fail-closed 識別子ゲート、またはパス引数も
タスク記述も無い batch 起動による中断）、commit-docs.sh の 2 回目の
exit 4 によるフェーズ中断、そして implement / verify フェーズが定める
終端停止 — 同 SSOT が列挙する停止点のすべてを含む。

ターンが終わる時点でランが終端状態（同 SSOT が定める 2 つの終端状態の
いずれか）に達していない場合は、終端行を出力しない。停止条件 5
（implementer の完了通知待ち）はこの規則のインスタンスであり、implement
フェーズの launch ターン（起動直後にターンを終える）と wake ターン
（補充後にターンを終える）も同様である。

$ARGUMENTS
