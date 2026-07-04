# em-workflow

em-sdd（SDD ワークフロー）と em-review（並列多観点レビュー）を統合した後継プラグイン。`/em-workflow:develop` 一本で spec 作成からタスク分割・worktree 並列実装・動的レビュー・統合検証・ふりかえり収集までを自走させる。

## フロー

```
/em-workflow:develop
    │
    ├─ create-spec   要件定義・仕様書の対話作成 (REQUIREMENTS.md / SPEC.md / workflow.yaml)
    ├─ create-plan   横断設計判断 (IMPLEMENTATION.md) + タスク分割 (tasks/taskNNNN.md)
    │                  各タスクに files / wave / skills / domains / complexity を宣言
    ├─ implement     wave ごとに implementer を worktree 並列起動
    │                  各エージェントが実装 → コミット → merge-task.sh でマージ完了まで自走
    │                  （コンフリクトは本人が親側採用で再実装）
    ├─ review        機械層 (review-rules.yaml × タスク宣言) + 裁量層で観点を動的選択
    │                  観点スキル注入型の汎用レビュアーを並列起動（条件により Codex 二重化）
    │                  bounded auto-fix (≤ 3 ループ) → reviews/roundN.yaml に記録
    ├─ verify        VERIFICATION.md に基づく統合検証（ビルド / テスト / E2E）
    └─ retrospect    つまずきの痕跡を retrospect.yaml へ自動収集（判断は手動コマンドで）
```

- 進捗の SSOT は `feature-docs/{feature}/workflow.yaml`（step 状態 + tasks メタデータ + review plan/サマリ + requirements マッピング）。スキーマは `references/workflow-schema.md`。
- ユーザーのブランチには一切コミットしない。全ワークフローコミットは専用の `em-workflow/{feature}/integration` ブランチに載り、完了時にマージを提案する。
- 軽い変更もタスク 1 個 × wave 1 個として同じフローを通す（従来型モードは持たない）。

## コマンド

| コマンド | 用途 |
|---------|------|
| `/em-workflow:develop [feature-path] [--report-only]` | 統合開発フローの自走実行・再開 |
| `/em-workflow:review [--report-only]` | SDD を通さない日常レビュー（workflow.yaml 不在時は baseline + 裁量層で観点選択） |
| `/em-workflow:retrospect [feature ...]` | retrospect.yaml の横断分析 → 承認付きでスキル / ルール表へ還元 |

## アーキテクチャ: エージェント 6 枚 + スキル注入

エージェント markdown を減らし、知識はスキルとして注入する（「規律は静的プリロード、ドメイン知識は動的注入」）。

### エージェント

| エージェント | 役割 | 静的プリロード |
|-------------|------|---------------|
| requirements-spec-creator | 対話で REQUIREMENTS.md / SPEC.md / workflow.yaml を作成 | — |
| implementation-planner | タスク分割 + wave / domains / complexity / skills 割当 | plan-writing |
| implementer | 1 タスク = 1 worktree。TDD 実装からマージ完了まで自走 | worktree-task-workflow, tdd-testing |
| reviewer | 汎用 Claude レビュアー（観点はスキル注入） | — |
| codex-reviewer | 汎用 GPT/Codex レビュアー（クロスバリデーション用） | codex-prompting |
| review-editor | auto-fix 適用専用（Read/Edit のみの最小権限） | — |

### 動的注入スキル

- 実装（レイヤー軸のみ・レジストリ `references/impl-skills.yaml`）: `design-impl` / `frontend-impl` / `backend-impl` / `infra-impl`。どれにも該当しないタスクは注入なしで実行。
- レビュー観点（レジストリ `references/reviewers.yaml`）: `review-security` / `review-performance` / `review-architecture` / `review-spec` / `review-comprehensive`。

## 動的レビュー選択（2 層）

1. **機械層**: workflow.yaml の tasks 宣言（domains / complexity）だけを入力に `references/review-rules.yaml` を決定的に評価し、必須観点セット（フロア）を出す。comprehensive は常時、spec は SDD 経由なら常時。
2. **裁量層**: オーケストレーターが統合 diff を見て観点を**追加のみ**できる（削除不可）。追加理由は review plan に記録され、retrospect でルール表育成の材料になる。

Codex クロスバリデーションは強度の軸として分離: complexity high のタスクを含む、または security が選ばれた場合に発動。

## マージ戦略（worktree 並列）

- タスク分割時に `files`（触る予定ファイル）と `wave` を宣言し、files が重複するタスクは同じ wave に入れない（オーケストレーターが機械的に再検証）。
- 「実装完了 = 親ブランチへのマージ完了」。implementer 自身が `scripts/merge-task.sh`（flock 排他 + `merge-tree`/`commit-tree`/`update-ref` の checkout 不要マージ、exit code 0=完了 / 1=コンフリクト / 2=エラー）でマージまで行う。
- コンフリクト時は親側採用（`git checkout --theirs`）で本人が再実装 → 再マージ。やり直しは最大タスク数-1 回で収束する。

## レビュー記録と自己改善

- 各ラウンドの findings と処理結果（fixed / declined / deferred + 理由）を `feature-docs/{feature}/reviews/roundN.yaml` に永続化。次ラウンド・次セッション・CI レビュアーへの引き継ぎと nit 蒸し返し防止に使う。
- Critical/High が未修正のままワークフローを完了させないゲートあり。
- develop の最終フェーズが `retrospect.yaml` に痕跡（レビュー Critical/High、コンフリクトやり直し、files 予測ミス、裁量層の観点追加、declined findings）を自動収集し、`/em-workflow:retrospect` が横断分析 → **ユーザー承認付きで**スキル / ルール表へ還元する。自動追記はしない。

## コマンド実行ガード（workflow.yaml 由来のシェル文字列）

workflow.yaml の build / test / format / e2e コマンドはリポジトリ管理の自由記述シェルであり、悪意あるリポジトリでは RCE の入口になりうる。em-workflow は「LLM が提案し、hook が裁く」の分離で守る（詳細: `references/command-execution-protocol.md`）:

1. **事前一括承認**: create-spec（または develop の Step A.5）が全コマンド文字列を出典フィールド・実体の説明つきで提示し、AskUserQuestion で一括承認。承認は `~/.claude/em-workflow/approvals.json`（リポジトリ外・ユーザー管理。git common dir をキーに同一リポジトリの全 worktree で共有）へ記録する
2. **実行時強制**: プラグイン同梱の PreToolUse hook（`hooks/bash_guard.py`）が全 Bash コールを機械的に検査する — 承認済み文字列と完全一致 → allow、workflow.yaml 記載かつ未承認 → deny、禁止パターン（sudo / curl-pipe-shell / プロジェクト外 rm 等）→ 承認済みでも deny。hook は LLM ではなくコードなので、プロンプトインジェクションで判定を曲げられない
3. workflow.yaml と無関係なコマンドには判定を出さない（Claude Code 標準の権限フローのまま）

これにより develop 実行中の確認プロンプトは、開発するプロダクトに関する質問だけになる。

## 要件

- git ≥ 2.40（`git merge-tree --write-tree --name-only`；2.38/2.39 は事前チェックで弾かれる）
- flock（util-linux）— stock macOS には無いため別途インストールが必要
- python3 — コマンド実行ガードの hook。無い環境では hook が非ブロッキングで抜け、コマンドごとの AskUserQuestion フォールバックゲートに切り替わる
- Codex CLI（任意 — 無ければ GPT クロスバリデーションはクリーンにスキップ）

## 既存プラグインとの関係

- em-sdd / em-review からのコピーで独立（fork）。名前空間・状態ファイル（workflow.yaml vs sdd.yaml）・成果物ディレクトリ（feature-docs/ vs doc/tasks/）を分けてあり、併存しても干渉しない。
- 機能進化は em-workflow に一本化し、既存 2 プラグインはバグ修正のみ → 安定後に deprecated 化予定。
