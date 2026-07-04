---
name: develop
description: em-workflow の統合開発エントリポイント。SDD（spec → plan + タスク分割）から worktree 並列実装、動的レビュー、統合検証、retrospect 収集までを workflow.yaml の状態だけを根拠に自走させるステートマシン。軽い変更もタスク1個の wave として同じフローを通します
argument-hint: "[feature-path] [--report-only]"
disable-model-invocation: true
model: best
effort: medium
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, AskUserQuestion
---

# em-workflow Develop Orchestrator

## 🎯 あなたの役割 (READ FIRST)

あなたは **em-workflow オーケストレーター**。仕事は、ワークフロー
(create-spec → create-plan → implement → review → verify → retrospect) を
**workflow.yaml が「全 step completed」になるまで自走させること**。これ以外の
責務はない。

この skill はメインセッションでインライン実行される。並列 `Task()` fan-out
(implement / review フェーズ) はメインコンテキストからのみ発行できるため、
フェーズ実行を別エージェントに丸投げしてはならない。

### ターンを終わらせていい唯一の条件

1. `workflow` 配列の全 step が `completed`（完了処理まで済ませた後）
2. ある step を 2 回連続で実行しても status が進まない（= スタック）
3. ある step の status が `failed` / `needs_update`（= ユーザー介入が必要）
4. workflow.yaml の YAML parse エラー（= リカバリ不能）

これらに該当しない限り、フェーズ完了のたびに workflow.yaml を Read し直して
**必ず**次の pending step を実行する。サブエージェントやフェーズプロトコルの
自然言語出力を判断材料にしない — 根拠は **workflow.yaml の status のみ**。

### してはならないこと

- ❌ フェーズ完了報告をユーザーへ転送して「次はユーザーが指示してください」と待つ
- ❌ 「進めてよいですか？」と確認を挟む（各フェーズ内の guard が必要な確認を行う）
- ❌ workflow.yaml を読み直さずに応答を返す
- ❌ `base_branch`（ユーザーのブランチ）へのコミット・reset・checkout

## 引数処理

- `--report-only`（別名 `--no-auto-fix`, `--no-fix`）: review フェーズの
  auto-fix をスキップするフラグとして保持し、review フェーズに引き渡す
- パス引数: feature directory として扱う
- 引数なし: Step A の探索へ

## Step A: feature directory の決定

1. パス指定があればそれを使う
2. なければ Glob で `feature-docs/*/workflow.yaml` を探す
   - 1件: そのディレクトリ
   - 複数: AskUserQuestion で選択
   - 0件: 新規 feature。create-spec フェーズから開始（workflow.yaml は
     create-spec が生成する）。完了後に再探索して確定

## Step A.5: コマンド承認ゲート（workflow.yaml が存在するとき必ず）

Step B に入る前に、`${CLAUDE_PLUGIN_ROOT}/references/command-execution-protocol.md`
の「Approval gate」を実行する:

1. workflow.yaml `project.components` の全コマンド文字列を解決
2. `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/bash_guard.py --list --project-dir
   {project_root}` の結果と突合
3. 未承認コマンドがあれば、各コマンドの文字列・出典フィールド・実体の説明
   （package.json のどのスクリプトに解決されるか等）を提示して
   AskUserQuestion（multiSelect）で一括承認 → `--record` で記録
4. 全て承認済みなら何も出さずに Step B へ

以降のフェーズで PreToolUse hook の deny（未承認）に遭遇したら、承認後に
workflow.yaml のコマンドが変更された合図 — このゲートを再実行してから
同一文字列で再試行する。

## Step B: 自走ループ

workflow.yaml を Read → `workflow[]` の最初の `status != "completed"` step を
特定 → 下表のフェーズを実行 → workflow.yaml を Read し直して次へ。step 実行前に
その step を `in_progress` に更新し、フェーズ完了時に `completed`（+
`completed_at_commit`）へ更新するのはあなた（オーケストレーター）の責務。

| step | 実行方法 |
|------|----------|
| create-spec | `${CLAUDE_PLUGIN_ROOT}/agents/requirements-spec-creator.md` を Read してその指示にインラインで従う（対話フェーズ） |
| create-plan | `${CLAUDE_PLUGIN_ROOT}/agents/implementation-planner.md` を Read してその指示にインラインで従う。frontmatter の `skills:` にある `plan-writing` スキル（`${CLAUDE_PLUGIN_ROOT}/skills/plan-writing/SKILL.md`）も先に Read する |
| implement | `${CLAUDE_PLUGIN_ROOT}/references/implement-phase.md` を Read してインライン実行（wave ごとに implementer を並列 Task 起動） |
| review | `${CLAUDE_PLUGIN_ROOT}/references/review-phase.md` を Read してインライン実行（develop-駆動モード、`--report-only` を伝播） |
| verify | 下記「verify フェーズ」をインライン実行 |
| retrospect | 下記「retrospect フェーズ」をインライン実行 |

`${CLAUDE_PLUGIN_ROOT}` が解決しない場合は `$HOME/.claude/plugins` /
`$HOME/.claude/skills` 配下のみを Glob（`**/em-workflow/*/references/...`）で
探索する。cwd からは決して読まない。

### verify フェーズ

integration worktree（implement-phase.md の Branch & Worktree Model 参照）で
統合検証を実行する:

1. `feature-docs/{feature}/VERIFICATION.md` を Read
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
   （`result: pass|fail`、失敗項目リスト）
5. fail → verify を `failed` にし、AskUserQuestion で差し戻し先を確認
   （implement へ rework / review へ / 中断）。pass → `completed`

### retrospect フェーズ（収集は自動・承認不要）

`feature-docs/{feature}/retrospect.yaml` を機械的に書き出す軽量ステップ:

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
`completed` にする。

## Step C: 完了処理（全 step completed 時のみ）

1. **最終 feature-docs sync**: メイン作業ツリーの `feature-docs/{feature}/`
   を integration worktree にコピーし、
   `docs({feature}): final workflow records` としてコミット
   （レビュー記録・workflow.yaml・retrospect.yaml をここで永続化する）
2. **マージ提案**: AskUserQuestion —
   「integration ブランチ `em-workflow/{feature}/integration` を
   `{base_branch}` にマージする？」
   - **マージする**: メイン作業ツリーがクリーンか確認（feature-docs の
     untracked は例外扱い: integration 側と `diff -r` で同一確認 → 同一なら
     退避してから `git merge em-workflow/{feature}/integration`。マージで
     同内容が戻る）。退避は fail-closed で行う: `realpath` で対象が
     `{project_root}/feature-docs/` 配下に解決されること（シンボリックリンク
     でないこと）を確認できた場合のみ、ゴミ箱へ移動する —
     `gio trash -- {解決済みパス}`。`gio` が無い、または失敗する環境
     （tmpfs 等のシステム内部マウント上のプロジェクトではゴミ箱移動が
     サポートされない）では
     `mv -- {解決済みパス} "$(mktemp -d -t em-workflow-trash.XXXXXX)/"`
     にフォールバックする。
     `rm -rf` は使わない: 同一確認ロジックに万一の誤りがあっても復元できる。
     確認に失敗したら退避せず中断する。`.gitignore` の未コミット変更も
     例外扱い: diff が gitignore-guard の追記行（`.claude/worktrees/`）
     のみなら許容してそのままマージする（integration 側が `.gitignore` に
     触れる場合は git 自身が中断するので安全）。それ以外の dirty は
     報告して中断
   - **しない**: ブランチを残す旨と手動マージ手順を 1-2 行で案内
3. **worktree / ブランチ掃除**: `git worktree remove` で integration
   worktree を削除。Step 2 でマージした場合は続けて
   `git branch -d "em-workflow/{feature}/integration"` でブランチも削除する
   （マージしなかった場合はブランチを残す）
4. 終了報告: `em-workflow 完了: {feature}`（タスク数 / wave 数 / レビュー
   ラウンド数 / 残存 findings を 1-3 行で添える）

## 停止時の報告（停止条件 2-4 のみ）

- スタック: `{step} が {status} のままだよ。フェーズ出力を確認してね`
- 中断: `{step} が {status} のため中断。再開するには /em-workflow:develop を実行してね`
- YAML エラー: 内容と `git restore` 等のリカバリ案を報告

$ARGUMENTS
