# em-workflow

SDD・並列実装・多観点レビューを統合した開発ワークフロープラグイン。`/em-workflow:develop` 一本で spec 作成からタスク分割・worktree 並列実装・動的レビュー・統合検証・ふりかえり収集までを自走させる。

## フロー

```
/em-workflow:develop
    │
    ├─ create-spec   要件定義・仕様書の対話作成 (REQUIREMENTS.md / SPEC.md / workflow.yaml)
    ├─ design        デザイン決定を完全自律で実施 (DESIGN.md / HTML モック /
    │                  design-system/ の tokens.yaml + tokens.html ビジュアルトークンシート)
    │                  create-spec が要否を判定（不要なら skipped）。確認では止まらず「まず動くものを」
    │                  implementer はデザインを発明しない — 決定は planner 経由でタスク計画に降ろし、
    │                  詰めは実機確認後の /em-workflow:design で行う
    ├─ create-plan   横断設計判断 (IMPLEMENTATION.md) + タスク分割 (tasks/taskNNNN.md)
    │                  各タスクに files / skills / domains / complexity を宣言
    ├─ implement     ワークキューで implementer を最大並列数までバックグラウンド起動
    │                  各エージェントが実装 → コミット → merge-task.sh でマージ完了まで自走
    │                  （コンフリクトは本人が親側採用で再実装）
    │                  進捗は journal.jsonl（機械書き込み専用の追記ログ）で追跡し、
    │                  workflow.yaml（LLM 管理の要約 SSOT）と役割を分離する
    ├─ review        機械層 (review-rules.yaml × タスク宣言) + 裁量層で観点を動的選択
    │                  各観点は primary_chain 先頭の利用可能な非 Claude レビュアーを 1 体だけ起動
    │                  （チェーン全滅時のみ Claude reviewer にフォールバック）
    │                  全観点確定後、Opus 評価者が 1 体でラウンド全体を評価 → 次アクションはオーケストレーターが決定
    │                  bounded auto-fix (≤ 3 ループ) → reviews/roundN.yaml に記録
    ├─ verify        VERIFICATION.md に基づく統合検証（ビルド / テスト / E2E）
    └─ retrospect    つまずきの痕跡を retrospect.yaml へ自動収集（判断は手動コマンドで）
```

- develop 開始時（Step 0）に git-setup ゲートが走る: gitleaks の存在を確認し、gitleaks pre-commit hook を冪等セットアップする。gitleaks が無ければワークフローはその場で中断する（自動コミット中のシークレット混入をコミット時点で止めるため）。
- ライセンス整合はワークフロー横断の制約として扱う: create-spec が既存 LICENSE を `project.license`（SPDX id、無ければ `none`）として workflow.yaml に記録し、create-plan は新規ライブラリ選定をこの制約と突き合わせる（矛盾したら「差し替え / ライセンス変更」をユーザーに確認）。diff が依存マニフェストに触れたら review が license 観点を裁量層で追加する。互換性判定の SSOT は `references/license-compat.md`。LICENSE が無いプロジェクトでは完了報告で `/em-workflow:gen-license` を提案する。
- 進捗の SSOT は `feature-docs/{feature}/workflow.yaml`（step 状態 + tasks メタデータ + review plan/サマリ + requirements マッピング）。スキーマは `references/workflow-schema.md`。書き込むのはオーケストレーターのみ — Task dispatch される各 worker（requirements-analyst / spec-writer / implementation-planner / rework-planner / designer）は read-only で、必要な変更は構造化された結果（2 種の planner は workflow patch）として返す。
- 各 phase（create-spec / create-plan / rework 合成）の対話履歴と worker 実行状態は `feature-docs/{feature}/phase-state/`（create-spec.yaml / create-plan.yaml / rework.yaml）に置き、`workflow.yaml` には持たせない（`references/phase-state.md`）。
- ワークフロー成果物（REQUIREMENTS.md / SPEC.md / DESIGN.md / IMPLEMENTATION.md / VERIFICATION.md / tasks/ / reviews/ / retrospect.yaml を含む feature-docs/{feature}/ 一式、および test/README.md・design-system/）は integration worktree にのみ存在し、更新のたびに `commit-docs.sh` で integration ブランチへコミットされる。メインの作業ツリーは最終マージまで変更されない — 唯一の例外は `.claude/worktrees/` を無視させる gitignore-guard 相当の `.gitignore` 追記（create-spec Phase 3 または implement Step I.1 で発生）で、それ以外は `git status` が常にクリーンに保たれる。
- 再開は feature 名の明示起点: `/em-workflow:develop <feature 名>` で `em-workflow/{feature}/integration` ブランチを解決し、そのブランチの workflow.yaml から状態を復元する。worktree が失われていてもブランチさえ残っていれば `git worktree add` で再作成して続行する。feature 名を渡さない起動は常に新規 feature（create-spec から開始）で、既存ブランチの列挙・推測はしない — 対話ではメインコンテキストの議論が、`--batch` ではタスク記述引数が create-spec の入力になる。
- ユーザーのブランチには一切コミットしない。全ワークフローコミットは専用の `em-workflow/{feature}/integration` ブランチに載り、完了時に「base_branch にマージ / ブランチを残す / push + PR 作成」の三択を確認する（デフォルトはマージ。--batch は確認なしで「ブランチを残す」）。いずれの分岐でも integration worktree は片付ける — マージ時はブランチも削除し、それ以外はブランチを残してメイン作業ツリーから `git switch` できる状態にする。
- 軽い変更もタスク 1 個として同じフローを通す（従来型モードは持たない）。
- `--batch` で無人実行モードになる: 外部タスク管理サービス起点のヘッドレス起動（例: `claude -p "/em-workflow:develop --batch <タスク記述>"`）向けに、全ての AskUserQuestion ゲートを機械的既定値へ置き換えて完走する。要件の不明点は Codex 相談（最大 5 ターン、結論は Claude）で確定し、コマンド承認は自動記録（refusal パターンは従来どおり拒否）、review 残存 critical/high と verify 失敗はそれぞれ上限 1 回の自動 rework、完了時はマージも PR 作成もせず integration worktree だけ片付けてブランチを残す（worktree が消えることで checkout ロックが外れ、メイン作業ツリーから `git switch` で取り込み — ローカルマージまたは push + PR 作成 — できる）。各ゲートの既定回答は question packet の `gate_id` をキーに `references/batch-policies.yaml`（gate ごとの決定表 SSOT）を引く。policy に無い `gate_id` は `references/question-resolution.md` の未収載ゲート fallback（同じ Codex 相談ループ、決まらなければ副作用の小さい側を選択）に従うが、仕様変更・セキュリティ・ライセンス・不可逆判断のゲートは未収載なら安全側で中断する（fail-closed）。gate_id を経由しない残りの batch 判断（git-setup 失敗、feature 解決、レビュー diff サイズゲート、コマンド承認 hook のフォールバック等）は `references/batch-mode.md` に残る。失敗時は隠さず停止して報告する — 差し戻しは外部サービス側で新タスクを切る運用。

## コマンド

| コマンド | 用途 |
|---------|------|
| `/em-workflow:develop [feature-path] [--report-only] [--batch] [タスク記述]` | 統合開発フローの自走実行・再開（`--batch` は無人実行モード） |
| `/em-workflow:design [feature-name]` | 実機確認後のデザイン詰め（tokens / モック / DESIGN.md を合意ループで対話更新。コードには触れない。引数なしはシステム全体がデフォルト） |
| `/em-workflow:review [--report-only]` | SDD を通さない日常レビュー（workflow.yaml 不在時は baseline + 裁量層で観点選択） |
| `/em-workflow:retrospect [feature ...]` | retrospect.yaml の横断分析 → 承認付きで feature-docs/LESSONS.md / プロジェクト CLAUDE.md へ還元（プラグイン改善は報告のみ） |
| `/em-workflow:git-setup` | git ローカル設定の冪等セットアップ（gitleaks pre-commit hook）。develop の Step 0 と同じ手順を単体実行する |
| `/em-workflow:gen-license [ライセンスID] [--analyze-only]` | 依存ライセンス分析 → 互換ライセンス選定 → LICENSE 生成。既存 LICENSE の変更（relicense）にも使い、workflow.yaml の `project.license` があれば同期する |

## アーキテクチャ: エージェント 11 枚 + スキル注入

エージェント markdown を減らし、知識はスキルとして注入する（「規律は静的プリロード、ドメイン知識は動的注入」）。オーケストレーターが唯一の状態書き込み者・唯一の AskUserQuestion 呼び出し元であり、それ以外の worker はすべて Task dispatch され、構造化された結果（question packet または workflow patch）を返すのみで workflow.yaml を直接書かない。

### エージェント

| エージェント | 役割 | 静的プリロード |
|-------------|------|---------------|
| requirements-analyst | create-spec の調査・質問候補生成（プロジェクト規約・ライセンス・デザインシステム候補検出） | — |
| spec-writer | requirements-analyst の確定結果と 2 種のテンプレートから REQUIREMENTS.md / SPEC.md を執筆 | — |
| designer | design ステップを完全自律実行（tokens.yaml / HTML モック / DESIGN.md を生成） | — |
| implementation-planner | タスク分割 + domains / complexity / skills 割当。workflow patch を提案（workflow.yaml へ直接書き込まない） | plan-writing |
| rework-planner | review findings / verify failed_items から追加タスクのみを計画。既存計画は書き換えず、workflow patch（`append_rework`）を提案 | — |
| implementer | 1 タスク = 1 worktree。TDD 実装からマージ完了まで自走 | worktree-task-workflow, tdd-testing |
| reviewer | 汎用 Claude レビュアー（フォールバック専用 — 観点の primary_chain が全滅したときだけ起動） | — |
| codex-reviewer | 汎用 GPT/Codex レビュアー（観点の primary reviewer。`primary_chain` の先頭から選ばれる） | codex-prompting |
| review-editor | auto-fix 適用専用（Read/Edit のみの最小権限） | — |
| review-evaluator | 1 ラウンド分の reviewer 出力をまとめて評価する Opus サブエージェント（findings 評価 + `recommended_action` を返す。決定はオーケストレーター） | — |

`primary_chain` の litellm ハーネス種別のエントリを起動する際は、上記に加えて `vertex-review:vertex-reviewer` も使われる。em-workflow 本体ではなく、別途インストールする `vertex-review` プラグインが提供するエージェントで、`codex exec -p litellm -m <model>` 経由で Vertex AI MaaS と Meta Muse を 1 本の LiteLLM proxy の裏に束ねる。未インストールでもチェーンの次エントリに進むだけで、em-workflow は変わらず動作する（後述）。
| gitignore-guard | implement 前処理。`.claude/worktrees/` の ignore を確認・追記（haiku） | — |
| git-setup-guard | develop の Step 0。gitleaks の存在確認 + gitleaks pre-commit hook の冪等設置。gitleaks 不在なら中断を報告（haiku） | — |

### 動的注入スキル

- 実装（レイヤー軸のみ・レジストリ `references/impl-skills.yaml`）: `design-impl` / `frontend-impl` / `backend-impl` / `infra-impl`。どれにも該当しないタスクは注入なしで実行。
- レビュー観点（レジストリ `references/reviewers.yaml`）: `review-security` / `review-performance` / `review-architecture` / `review-spec` / `review-comprehensive` / `review-license`（license のみ裁量層専用 — 機械層のルール入力に依存マニフェストの信号が無いため）。

## 動的レビュー選択（2 層）

1. **機械層**: workflow.yaml の tasks 宣言（domains / complexity）だけを入力に `references/review-rules.yaml` を決定的に評価し、必須観点セット（フロア）を出す。comprehensive は常時、spec は SDD 経由なら常時。
2. **裁量層**: オーケストレーターが統合 diff を見て観点を**追加のみ**できる（削除不可）。追加理由は review plan に記録され、retrospect でルール表育成の材料になる。diff が依存マニフェスト / lockfile に触れる、または vendored コードを追加する場合の `license` 観点の追加は必須（license は裁量層でのみ選択される）。

選択された各観点には、その観点の `primary_chain`（`reviewers.yaml`）先頭から利用可能な最初のエントリを非 Claude レビュアーとして 1 体だけ起動する。チェーンの全エントリが利用不可のときだけ、その観点は Claude 汎用レビュアーにフォールバックする。両者は排他 — Claude レビュアーが非 Claude レビュアーと並行に同一観点を二重実行することはない。全観点の結果が確定した後、Opus 評価者サブエージェントが 1 体、ラウンド全体を横断評価する。評価結果（`recommended_action` を含む）は次アクション（auto-fix / もう1ラウンド / rework / 完了）の参考情報であり、決定は常にオーケストレーターが行う。

ハーネス（どのモデルが存在し、どう到達するか）は vertex-review 側の責務、**観点ごとのモデル選択は em-workflow 側の責務**。`reviewers.yaml` が渡した `model` をレビュアーはそのまま `-m` に流す。

### primary-reviewer チェーン表

| 観点 | チェーン（1st → 2nd → 3rd） |
|------|------------------------------|
| security | codex → litellm `muse-spark` |
| performance / spec | litellm `vertex-deepseek-v3.2` → litellm `muse-spark` → codex |
| architecture | litellm `vertex-glm-5` → litellm `muse-spark` → codex |
| comprehensive | codex → litellm `vertex-glm-5` → litellm `muse-spark` |
| license | codex → litellm `vertex-deepseek-v3.2` → litellm `muse-spark` |

R2b はスキップ理由が retryable なときだけチェーンを進める。`rate_limited` は次のエントリへ、`budget_exhausted` / `harness_unavailable` は**別ハーネス**の次エントリへ飛ぶ（litellm のエントリは仮想キー 1 本の月次予算を共有するため、モデルを変えても同じく落ちる）。フォールバックは 1 観点につき最大 2 ホップ。

## マージ戦略（worktree 並列）

- 最大並列数（`max_parallel_implementers`、デフォルト 6）を上限に、完了通知駆動のワークキューとして全タスクを並列実行する（一括起動してまとめて待ち合わせるチャンク方式は廃止）。タスク間の順序制御は持たず、タスク間で使うコンポーネントの契約は IMPLEMENTATION.md に固定して両側が契約に対して独立に実装する。
- 「実装完了 = 親ブランチへのマージ完了」。implementer 自身が `scripts/merge-task.sh`（flock 排他 + `merge-tree`/`commit-tree`/`update-ref` の checkout 不要マージ、exit code 0=完了 / 1=コンフリクト / 2=エラー）でマージまで行う。
- files の重複は許容し、コンフリクトは通常パスとして扱う: 親側採用（`git checkout --theirs`）で本人が再実装 → 再マージ（1 タスクにつき最大 3 サイクル、超過は failed 報告）。
- 進捗の実体は `journal.jsonl`（`launched`/`merged`/`failed` を機械が追記する raw ログ、追記専用で削除されない）。`workflow.yaml` は LLM が管理する要約 SSOT であり、スクリプト・hook が書き込むことはない。同ループの規律違反（起動漏れ・二重起動・失敗の見逃し）は、複数のフェイルオープンなガード hook が機械的に検知するネットとして働く（一覧・詳細: `references/implement-phase.md`）。オーケストレーターが `TaskStop` で implementer を明示的に停止させた場合も、その停止は journal に `failed` イベントとして記録される。

## レビュー記録と自己改善

- 各ラウンドの findings と処理結果（fixed / declined / deferred + 理由）を `feature-docs/{feature}/reviews/roundN.yaml` に永続化。次ラウンド・次セッション・CI レビュアーへの引き継ぎと nit 蒸し返し防止に使う。
- Critical/High が未修正のままワークフローを完了させないゲートあり。
- develop の最終フェーズが `retrospect.yaml` に痕跡（レビュー Critical/High、コンフリクトやり直し、files 予測ミス、裁量層の観点追加、declined findings）を自動収集し、`/em-workflow:retrospect` が横断分析 → **ユーザー承認付きで**プロジェクト側（feature-docs/LESSONS.md / CLAUDE.md）へ還元する。プラグイン本体のファイルには書き込まない（プラグイン改善候補は報告のみ）。自動追記はしない。

## コマンド実行ガード（workflow.yaml 由来のシェル文字列）

workflow.yaml の build / test / format / e2e コマンドはリポジトリ管理の自由記述シェルであり、悪意あるリポジトリでは RCE の入口になりうる。em-workflow は「LLM が提案し、hook が裁く」の分離で守る（詳細: `references/command-execution-protocol.md`）:

1. **事前一括承認**: create-spec（または develop の Step A.5）が全コマンド文字列を出典フィールド・実体の説明つきで提示し、AskUserQuestion で一括承認。承認は `~/.claude/em-workflow/approvals.json`（リポジトリ外・ユーザー管理。git common dir をキーに同一リポジトリの全 worktree で共有）へ記録する
2. **実行時強制**: プラグイン同梱の PreToolUse hook（`hooks/bash_guard.py`）が全 Bash コールを機械的に検査する — 承認済み文字列と完全一致 → allow、workflow.yaml 記載かつ未承認 → deny、禁止パターン（sudo / curl-pipe-shell / プロジェクト外 rm 等）→ 承認済みでも deny。hook は LLM ではなくコードなので、プロンプトインジェクションで判定を曲げられない
3. workflow.yaml と無関係なコマンドには判定を出さない（Claude Code 標準の権限フローのまま）

これにより develop 実行中の確認プロンプトは、開発するプロダクトに関する質問だけになる。

## ガードレール hook（同梱・インストールしただけで全セッションに効く）

このプラグインは上記のコマンド実行ガードとは別に、PreToolUse ガード hook を 4 本同梱している。em-workflow の外側でも、プラグインが有効な全セッションの Bash / Write / Edit / MultiEdit に対して動く。

| hook | イベント | 役割 |
|------|---------|------|
| `hooks/gitleaks-precommit.sh` | PreToolUse(Bash) | `git commit` を含むコマンドの前に staged / unstaged の diff と、git の追跡対象外の新規ファイル（新規 `.env` 等）を gitleaks でスキャンし、検出したらコミットをブロックする |
| `hooks/kill-guard.py` | PreToolUse(Bash) | `kill` / `pkill` / `killall` の対象プロセスを解決し、claude プロセスの祖先なら常に拒否、子孫なら許可、それ以外は確認に回す（無人実行では拒否に降格） |
| `hooks/bash_guard.py` | PreToolUse(Bash) | 前節のコマンド実行ガード（workflow.yaml 由来のシェル文字列のみ判断） |
| `hooks/failed-run-cleanup-guard.py` | PreToolUse(Bash) | 対象 feature の workflow.yaml が failed ステップを含む em-workflow run に対する worktree 削除・integration ブランチ削除・pull request 作成を拒否し、無人実行が報告して停止できるよう理由を返す。対象を解決できない場合は確認に回り、無人実行では拒否に降格する |
| `hooks/destructive-guard.py` | PreToolUse(Bash) | 破壊的コマンドの静的ブロックリスト。**マッチしないコマンドは `allow` で返す** |
| `hooks/gitleaks-write-guard.sh` | PreToolUse(Write\|Edit\|MultiEdit) | 書き込む内容を gitleaks でスキャンし、シークレットを含むなら書き込みをブロックする |

PreToolUse(Bash) の 5 本は `hooks.json` の配列順（gitleaks → kill-guard → bash_guard → failed-run-cleanup-guard → destructive-guard）で実行される。`destructive-guard.py` は広域 `allow` を返すため必ず最後に置く — 先に allow が確定すると `bash_guard.py` の承認ゲートが働くべき経路を潰しかねない。

gitleaks 系 2 本はバイナリを `command -v gitleaks` → `$HOME/.local/share/mise/shims/gitleaks` の順で解決し、どちらにも無ければスキャンせず通す（fail-open）。gitleaks 未インストール環境で全コミット・全書き込みがブロックされるのを避けるため。develop の Step 0（git-setup ゲート）が gitleaks 不在で workflow ごと中断するのとは判断が異なる — この hook は develop の外でも動くため。

### 副作用: Bash の auto mode 分類器が無効になる

`destructive-guard.py` はブロックリストにマッチしなかったコマンドを `permissionDecision: "allow"` で返す。Claude Code はこの経路で **auto mode の分類器（classifier）を丸ごとスキップする**。つまりこのプラグインを入れると、Bash に対する適応的な判定が静的ブロックリストに置き換わる。

- **代償**: ブロックリストが唯一の防波堤になる。リストが知らない破壊的パターンは素通りする。
- **実例**: `gcloud projects add-iam-policy-binding` は classifier が止めたが、当時のリストは知らなかった。hook 内のクラウド / IaC セクションはこの隙間を狭めるために書かれたもので、塞ぎ切ってはいない。
- **hook の判定は `permissions.deny` より優先される**。後から deny ルールを足しても、この hook が allow したコマンドには効かない。

**なぜこの設計なのか**: 無人実行（`--batch`）で classifier の誤検知が run を止めるため。classifier は毎回新規に判定する LLM で、実測の誤検知率は 0.2〜0.8% ある。同一リポジトリで `commit-docs.sh` が 251 回 allow・2 回 deny され、その deny のペアが claude-batch を 11 時間凍らせた実例がある。

**無効化を止めたい場合**: `hooks/destructive-guard.py` の `ALLOW_NON_DESTRUCTIVE` を `False` にする。ブロック機能だけが残り、未判定のコマンドは classifier に戻る。

## 要件

- git ≥ 2.40（`git merge-tree --write-tree --name-only`；2.38/2.39 は事前チェックで弾かれる）
- flock（util-linux）— stock macOS には無いため別途インストールが必要
- gitleaks — develop 開始時の git-setup ゲートが存在チェックし、無ければワークフローを中断する（pre-commit hook でのシークレットスキャンに使用）。同梱の gitleaks ガード hook も同じバイナリを使うが、そちらは不在なら fail-open で素通りする
- jq — 同梱の gitleaks ガード hook 2 本が hook 入力の JSON を読むのに使う。無い環境ではスキャンされずに素通りする（fail-open）
- python3 — コマンド実行ガードの hook。無い環境では hook が非ブロッキングで抜け、コマンドごとの AskUserQuestion フォールバックゲートに切り替わる
- python3 + PyYAML — 同梱の検証スクリプト（`scripts/validate-worker-output.py` / `scripts/check-plugin-invariants.py`）が使う実行時依存。テストコードはこの依存を使わず標準ライブラリのみで動く（`test/README.md`）。環境によっては `python3` の非対話実行に `Bash(python3:*)` 権限エントリの追加が必要
- Codex CLI（任意 — ただし litellm ハーネスも `codex exec` を使うため、無ければそれを使うチェーンエントリが利用不可になる。観点の `primary_chain` が全滅したときはその観点だけ Claude フォールバックが動き、em-workflow はそのまま最後まで走る）
- `vertex-review` プラグイン + LiteLLM ハーネス（任意 — 別リポジトリからインストールする独立プラグイン。`LITELLM_API_KEY` と `~/.codex/litellm.config.toml` が揃って初めて `litellm_available` になる。無ければ litellm 種別のチェーンエントリが利用不可になる。観点の `primary_chain` が全滅したときはその観点だけ Claude フォールバックが動き、em-workflow はそのまま最後まで走る）
