---
name: develop
description: em-workflow の統合開発エントリポイント。SDD（spec → plan + タスク分割）から worktree 並列実装、動的レビュー、統合検証、retrospect 収集までを workflow.yaml の状態だけを根拠に自走させるステートマシン。軽い変更もタスク1個として同じフローを通します
argument-hint: "[feature-path] [--report-only] [--batch] [task-description]"
disable-model-invocation: true
model: best
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
3. ある step の status が `failed` / `needs_update`（= ユーザー介入が必要）
4. workflow.yaml の YAML parse エラー（= リカバリ不能）
5. implement フェーズでバックグラウンド implementer の完了通知を待つとき
   （= キューループが定める正常な待機。次の 2 形がある:
   (a) 起動/補充した直後、(b) failed 発生後のドレイン中 — 新規投入は
   止めて in-flight の完了通知だけを待ち、全て回収してからユーザー三択を
   出す（batch: 三択の代わりにタスクごと 1 回だけ自動 retry、2 回目の
   failed で中断 — batch-mode.md 決定表）。通知で起こされたら reconcile
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

## 引数処理

- `--report-only`（別名 `--no-auto-fix`, `--no-fix`）: review フェーズの
  auto-fix をスキップするフラグとして保持し、review フェーズに引き渡す
- `--batch`: 無人実行モード。**最初に**
  `${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md` を Read し、以降の全
  ゲート（Step A / A.5 / 各フェーズ / Step C）にその決定表を適用する。
  batch モード中は AskUserQuestion を一切呼ばない。workflow.yaml が存在
  するのに `batch` ブロックが無ければ作成する（カウンタ永続化のみ —
  モード判定は常にこのフラグ）
- パス引数（存在するディレクトリ、または feature 名の文字列）: 末尾要素を
  feature 名として扱う。main 作業ツリーのディレクトリとして中身を読むこと
  はしない — Step A の Discovery でその feature 名に対応する
  `em-workflow/{feature}/integration` ブランチ + worktree に解決する
- 存在するファイルを指す引数（--batch 時）: Read してタスク記述として扱う
- その他の自由テキスト（--batch 時）: そのままタスク記述として扱う
  （feature 未存在時の batch create-spec の入力になる）
- 引数なし: Step A の探索へ

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

## Step A: feature の決定（Discovery）

feature-docs はもう main 作業ツリーを走査しない。存在する feature は
`em-workflow/{feature}/integration` ブランチの有無で判定する（Discovery
セマンティクス）。プロジェクトルートは最初にシェル変数へ捕捉する
（`PROJECT_ROOT="$(git rev-parse --show-toplevel)"` —
requirements-spec-creator.md Phase 3 と同じ安全なパターン。以降このステップの
コマンド文字列は `$PROJECT_ROOT` を参照し、`{project_root}` をコマンド文字列に
直接埋め込まない）。

1. **feature 名の決定**
   - パス引数（引数処理参照）があれば、その末尾要素を feature 名とする
   - **fail-closed 識別子ゲート**: feature 名（パス引数由来・ブランチ由来を
     問わず）は `^[a-z0-9][a-z0-9-]*$` にマッチしなければならない。
     マッチしない場合はサニタイズや暗黙の変換をせず、明確なエラーで
     **中断**する（この後の worktree 操作を含む、いかなるシェルコマンドへの
     補間より前に検証する）
   - 無ければ `em-workflow/*/integration` にマッチするブランチを列挙する
     （`git branch --list 'em-workflow/*/integration'`）
     - 1件: そのブランチの feature を使う（ブートストラップ状態は
       2./3. で判定する）
     - 複数: AskUserQuestion で選択（batch: 推測せず中断報告 —
       batch-mode.md 決定表）
     - 0件: 新規 feature。create-spec フェーズから開始（workflow.yaml は
       create-spec が生成する）。完了後に再探索して確定（batch: タスク
       記述引数を create-spec の入力にする。タスク記述も無ければ中断報告）
2. **worktree の確保**（既存 feature のときのみ）: `git worktree list` で
   `"$PROJECT_ROOT/.claude/worktrees/em-workflow/{feature}/integration"` が
   存在するか確認する
   - 存在する: そのまま使う
   - 存在しない（ブランチはあるが worktree が片付けられている —
     前回セッションの手動クリーンアップ後の再開等）: 再マテリアライズは
     対応する `em-workflow/{feature}/integration` ブランチが実在すると
     確認できた場合のみ行う。パス引数由来の feature 名で対応ブランチが
     存在しない場合は再マテリアライズせず、新規 feature として
     create-spec フェーズに回す（上記 1. の「0件」ルート）。
     再マテリアライズするコマンドは引数を必ずクォートする:
     `git worktree add "$PROJECT_ROOT/.claude/worktrees/em-workflow/{feature}/integration" "em-workflow/{feature}/integration"`
3. **ブートストラップ状態の判定**（1. で 1 件マッチした既存 feature のみ対象。
   複数/0件は上記で解決済み）: 確保した worktree 内の
   `feature-docs/{feature}/workflow.yaml` の有無で分岐する:
   - **存在する**（通常の再開）: そのまま Step A.5 → Step B へ進む
   - **存在しない**（ブランチ + worktree だけが作られ、create-spec が
     workflow.yaml を書き切る前に中断された状態）: 新規 feature 扱いには
     せず、この既存ブランチ/worktree に対して create-spec フェーズへ直接
     再突入する（requirements-spec-creator.md Phase 3 は既存ブランチの
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
   fail。自動承認した文字列は終了報告に列挙する — batch-mode.md 決定表）
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
`skipped` でもない step を特定 → 下表のフェーズを実行 → workflow.yaml を
Read し直して次へ。step 実行前に
その step を `in_progress` に更新し、フェーズ完了時に `completed`（+
`completed_at_commit`）へ更新するのはあなた（オーケストレーター）の責務
（`skipped` は create-spec が設定する。design 以外の step に `skipped` が
あったら YAML エラー扱いで停止）。

workflow.yaml か feature-docs/ 配下のドキュメントを Write/Edit するたび
（`in_progress` / `completed` への status 更新を含む）、その場で
`${CLAUDE_PLUGIN_ROOT}/scripts/commit-docs.sh {integration worktree の絶対パス}
"docs({feature}): {更新内容の要約}"` を実行してコミットする。状態の根拠は
変わらず **workflow.yaml の status のみ**（保存場所が main ツリーから
worktree に移っただけ）。

**exit-4 リカバリ**（commit-docs.sh の全呼び出し箇所で共通 — Step B のこの
ドキュメントコミット、および下記の verify / retrospect フェーズのコミットを
含む）: 戻り値 4（stale worktree — 並行する merge-task.sh がこの worktree の
直近の refresh より後にブランチ ref を進めた）を受けたら、
`git -C {integration worktree の絶対パス} reset --hard
em-workflow/{feature}/integration` で最新 tip に refresh し、直前に書こう
とした状態遷移（status 更新やドキュメント内容）を最新ツリーの上に
re-derive して書き直し、`commit-docs.sh` を 1 回だけ再試行する。2 回目も
exit 4 ならそこでフェーズを中断し、状況をユーザーに報告する（無限リトライ
しない）。

| step | 実行方法 |
|------|----------|
| create-spec | `${CLAUDE_PLUGIN_ROOT}/agents/requirements-spec-creator.md` を Read してその指示にインラインで従う（対話フェーズ。batch: 同ファイルの Batch Mode セクションに従い、ユーザー対話の代わりにタスク記述 + Codex 相談で書き切る） |
| design | `${CLAUDE_PLUGIN_ROOT}/agents/designer.md` を Read してその指示にインラインで従う（完全自律フェーズ — ユーザー確認なしで走り切り、迷ったら決めて DESIGN.md に根拠を記録。詰めは実機確認後の `/em-workflow:design`。`status: skipped` の場合はこの表に来ない） |
| create-plan | `${CLAUDE_PLUGIN_ROOT}/agents/implementation-planner.md` を Read してその指示にインラインで従う。frontmatter の `skills:` にある `plan-writing` スキル（`${CLAUDE_PLUGIN_ROOT}/skills/plan-writing/SKILL.md`）も先に Read する |
| implement | `${CLAUDE_PLUGIN_ROOT}/references/implement-phase.md` を Read してインライン実行（ワークキュー方式: 最大 6 タスクをバックグラウンド Task 起動 → ターンを終えて完了通知を待つ → journal + git 実状態から reconcile して空きスロットへ補充。同期 fan-out でのバリア待ちはしない） |
| review | `${CLAUDE_PLUGIN_ROOT}/references/review-phase.md` を Read してインライン実行（develop-駆動モード、`--report-only` / `--batch` を伝播） |
| verify | 下記「verify フェーズ」をインライン実行 |
| retrospect | 下記「retrospect フェーズ」をインライン実行 |

`${CLAUDE_PLUGIN_ROOT}` が解決しない場合は `$HOME/.claude/plugins` /
`$HOME/.claude/skills` 配下のみを Glob（`**/em-workflow/*/references/...`）で
探索する。cwd からは決して読まない。

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
   （implement へ rework / review へ / 中断）。pass → `completed`
   （batch: 確認せず自動 rework。`batch.verify_rework_count == 0` なら
   failed_items から rework タスクを合成して implement / verify を
   `pending` に戻しカウンタを +1、既に 1 以上なら `failed` のまま報告して
   停止 — batch-mode.md「Rework task synthesis」）。いずれの分岐も
   workflow.yaml 更新後に commit-docs.sh でコミットする

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

1. **マージ提案**: AskUserQuestion —
   「integration ブランチ `em-workflow/{feature}/integration` を
   `{base_branch}` にマージする？」
   （batch: 提案せず自動で「マージする」を選ぶ。クリーン確認規律は
   下記と同一で、dirty なら中断報告。ただしタスク記述または SPEC.md が
   PR 作成を明示している場合はローカルマージせず、integration ブランチを
   push して `gh pr create` で `{base_branch}` への PR を作成し、
   ブランチと worktree は残す — batch-mode.md 決定表）
   - **マージする**: メイン作業ツリーがクリーンか確認する。workflow.yaml
     も feature-docs/ 配下のドキュメントも worktree にのみコミットされ、
     main 作業ツリーには存在しない（Step A/B 参照）ため、退避も
     untracked の同一性チェックも不要。唯一許容する例外は
     gitignore-guard が追記した `.gitignore` の未コミット行
     （`.claude/worktrees/`）のみ: diff がその行だけなら許容してそのまま
     `git merge em-workflow/{feature}/integration` する（integration 側が
     `.gitignore` に触れる場合は git 自身が中断するので安全）。それ以外の
     dirty（未コミットの変更・untracked ファイルを問わず）は退避を試みず
     報告して中断する
   - **しない**: ブランチを残す旨と手動マージ手順を 1-2 行で案内
2. **worktree / ブランチ掃除**: `git worktree remove` で integration
   worktree を削除。Step 1 でマージした場合は続けて
   `git branch -d "em-workflow/{feature}/integration"` でブランチも削除する
   （マージしなかった場合はブランチを残す）
3. 終了報告: `em-workflow 完了: {feature}`（タスク数 / レビュー
   ラウンド数 / 残存 findings を 1-3 行で添える）。workflow.yaml
   `project.license` が `none` の場合は
   `LICENSE が無いから /em-workflow:gen-license の実行をおすすめするよ`
   を 1 行添える。batch: batch-mode.md「Reporting」の監査項目
   （自動承認コマンド / 記録した仮定 / rework 消費 / deferred findings）
   を必ず含める — 外部サービス経由で人間の評価者に届く唯一の確認面

## 停止時の報告（停止条件 2-4 のみ）

- スタック: `{step} が {status} のままだよ。フェーズ出力を確認してね`
- 中断: `{step} が {status} のため中断。再開するには /em-workflow:develop を実行してね`
- YAML エラー: 内容と `git restore` 等のリカバリ案を報告

$ARGUMENTS
