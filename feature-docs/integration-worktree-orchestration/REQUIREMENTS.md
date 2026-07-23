---
title: "integration worktree 完結化"
created_date: 2026-07-23
status: draft
---

# integration worktree 完結化 - 要件定義書

## 1. 概要

### 1.1 背景

現行の em-workflow develop は、実行中の状態 SSOT（workflow.yaml）と各フェーズの
成果物（feature-docs/{feature}/、test/README.md、design-system/）を main 作業
ツリーに git 未追跡のまま置く。コミットが base_branch に載ることはないが、
ワークフロー実行中〜中断時に main 作業ツリーが untracked ファイルで汚染される。
検討経緯は `tmp/report-integration-worktree-orchestrator-20260723-175049.md` を参照。

### 1.2 目的

ワークフローの全成果物を integration worktree 内で生成・コミット管理し、
main 作業ツリーをワークフロー起因の変更・untracked ゼロに保つ。

### 1.3 スコープ

- 対象: em-workflow プラグインの develop オーケストレーションが扱う全成果物の
  配置とライフサイクル（対話モード・batch モードの両方）
- 対象外: 旧レイアウト（feature-docs が main 作業ツリーに untracked）で作成
  された既存 feature の互換サポート。gitignore-guard の除外方式変更
  （.gitignore 追記のまま維持）

## 2. ビジネス要件

### 2.1 目標

- ワークフロー実行中の `git status`（main 作業ツリー）が汚れない
- クラッシュ・中断時に main 作業ツリーへ後始末が不要
- Step C の untracked 同一確認・ゴミ箱退避ロジックの削除による安全性向上

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow 利用者 | main ブランチ上で /em-workflow:develop（--batch 含む）を実行する開発者 |

### 2.3 期待される効果

- main 作業ツリーの untracked 汚染ゼロ
- 状態更新が常にコミット済みとなり、クラッシュ時のロストゼロ
- Step C から誤削除リスクが最も高い退避ロジックが消える

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | main から develop を完走し main を汚さない | 利用者 | 高 |
| UC02 | 中断後の resume（worktree 消失時の再構成含む） | 利用者 | 高 |
| UC03 | implement 中の状態コミットとタスクマージの並行 | オーケストレーター / implementer | 高 |

### 3.2 ユースケース詳細

#### UC01: main から develop を完走し main を汚さない

**アクター**: 利用者

**事前条件**:
- main ブランチがクリーン

**基本フロー**:
1. 利用者が /em-workflow:develop（または --batch）を実行する
2. create-spec で feature 名が確定した時点で integration ブランチ + worktree が作成される
3. REQUIREMENTS.md / SPEC.md / workflow.yaml 以降の全成果物が worktree 配下に書かれ、都度コミットされる
4. 全フェーズが worktree 内の成果物を参照して完走する
5. Step C で integration ブランチを main へマージする（または PR 作成）

**事後条件**:
- マージ前の main 作業ツリーにワークフロー起因の変更・untracked が存在しない

#### UC02: 中断後の resume

**アクター**: 利用者

**基本フロー**:
1. 利用者が引数なしで /em-workflow:develop を再実行する
2. オーケストレーターが `em-workflow/*/integration` ブランチを列挙して feature を検出する
3. worktree が存在しなければ `git worktree add` で再構成する
4. worktree 内の workflow.yaml から次の pending step を再開する

**代替フロー**:
- ブランチが複数: AskUserQuestion で選択（batch: 中断報告）
- ブランチ 0 件: 新規 feature として create-spec から開始

#### UC03: implement 中の状態コミットとタスクマージの並行

**アクター**: オーケストレーター / implementer

**基本フロー**:
1. implementer が merge-task.sh で integration ブランチを進める（flock 下）
2. オーケストレーターが状態更新を同一 flock 下でコミットする
3. reconcile の `reset --hard` 後も、コミット済みの状態が worktree に保たれる

**事後条件**:
- ドキュメントコミットとタスクマージが直列化され、どちらも失われない

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| F01 | integration worktree の前倒し作成 | create-spec の feature 名確定時点でブランチ + worktree を作成 | 高 |
| F02 | 全成果物の worktree 配置 | feature-docs / test/README.md / design-system/ を worktree 配下に生成 | 高 |
| F03 | 状態更新の都度コミット | 専用スクリプトで flock を取ってコミット | 高 |
| F04 | resume 探索のブランチベース化 | Step A を feature-docs スキャンからブランチ / worktree 列挙へ変更 | 高 |
| F05 | Step C の簡素化 | untracked 同一確認・退避ロジックを削除 | 高 |
| F06 | フェーズプロトコル・エージェント指示のパス更新 | 各 .md の成果物パスを worktree 基準に変更 | 高 |
| F07 | ドキュメント更新とバージョン bump | README / plugin.json / workflow-schema.md | 中 |

### 4.2 機能詳細

#### F01: integration worktree の前倒し作成

**説明**: create-spec の Phase 3（ディレクトリ作成）を「integration ブランチ +
worktree の作成」に変更する。worktree パスは従来どおり
`{project_root}/.claude/worktrees/em-workflow/{feature}/integration`。
ブランチは base_branch の HEAD から作成する。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 同名ブランチが既存 | 前回の残骸 | resume として扱うか、ユーザー確認（batch: 中断報告） |
| create-spec 中断 | ドキュメント完成前の中断 | ブランチ・worktree は残し、resume で継続 |

#### F02: 全成果物の worktree 配置

**説明**: feature-docs/{feature}/ 一式・test/README.md・design-system/ を
worktree 配下の同相対パスに生成する。main 作業ツリーには一切書かない。
implement Step I.1 の「main → integration へのコピー + コミット」および
Step C.1 の最終 sync は不要になり削除する。

#### F03: 状態更新の都度コミット

**説明**: workflow.yaml・feature-docs 配下の更新のたびに、専用スクリプト
（scripts/commit-docs.sh）でコミットする。スクリプトは merge-task.sh と同一の
ロックファイル（`$(git rev-parse --git-common-dir)/em-workflow-merge.lock`）で
排他し、integration worktree 内で add + commit する。

**ビジネスルール**:
- flock 取得なしで integration ブランチの ref を進める操作を追加しない
- コミットメッセージは `docs({feature}): {summary}` 形式

#### F04: resume 探索のブランチベース化

**説明**: Step A の探索を `git branch --list 'em-workflow/*/integration'` +
`git worktree list` に変更する。ブランチはあるが worktree が無い場合は
`git worktree add` で再構成する。旧形式（main 作業ツリーの feature-docs）は
検出対象にしない。

#### F05: Step C の簡素化

**説明**: main 作業ツリーが常にクリーンである前提で、Step C から untracked
同一確認・`gio trash` / `mv` 退避ロジックを削除する。クリーン確認 →
`git merge`（batch の PR variant は従来どおり push + `gh pr create`）のみとする。
`.gitignore` の gitignore-guard 追記行のみ dirty 例外として維持する。

#### F06: フェーズプロトコル・エージェント指示のパス更新

**説明**: develop SKILL.md / implement-phase.md / review-phase.md /
batch-mode.md / workflow-schema.md / requirements-spec-creator.md /
implementation-planner.md / designer.md の成果物参照パスを worktree 基準に
更新し、二層構造（main 側 live copy + integration 側スナップショット）の
記述を削除する。

## 5. 非機能要件

### 5.1 セキュリティ要件

- 入力検証: feature 名・タスク ID の fail-closed 検証（既存の
  `^[a-z0-9][a-z0-9-]*$` / `^task[0-9]+$`）を worktree パス構成前に適用する
  （既存規律の維持）

### 5.2 可用性要件

- クラッシュ耐性: 状態更新は常にコミット済みであり、`reset --hard` や
  セッション中断で失われない

### 5.3 保守性要件

- テスト: 新規スクリプト・変更スクリプトは tests/ 配下の stdlib unittest で
  検証する（既存規約: `python3 -m unittest discover -s tests`）
- ドキュメント: ブランチ / worktree モデルの記述を一元化する

## 6. UI/UX要件

なし（プロトコル文書 / スクリプトの変更のみ。design step は skip）。

## 7. データ要件

なし（新規データ構造の追加なし。workflow.yaml スキーマは配置場所のみ変更）。

## 8. 外部連携

なし。

## 9. 制約条件

### 9.1 技術的制約

- util-linux `flock` に依存（merge-task.sh の既存制約と同一）
- worktree の物理配置は `{project_root}/.claude/worktrees/` 配下
  （`.claude/worktrees/` は gitignore 済みが前提。未カバー時は既存の
  gitignore-guard が .gitignore へ追記する — 現状維持）
- base_branch（ユーザーのブランチ）へのコミット禁止（既存規律の維持）

## 10. 想定される課題とリスク

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| ドキュメントコミットと merge-task.sh の ref 更新の競合 | 高 | 同一ロックファイルでの flock 直列化（F03） |
| 高頻度コミットによる integration ブランチの履歴肥大 | 低 | 許容する（docs コミットとして追跡可能） |
| worktree 消失時の resume 失敗 | 中 | ブランチからの再 materialize（F04） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] develop 実行中〜完了（マージ前）の任意の時点で、main 作業ツリーに
  ワークフロー起因の変更・untracked が存在しない
- [ ] 中断 → 引数なし再実行で resume できる（worktree 消失時も含む）
- [ ] implement 並列実行中に状態コミットとタスクマージが両立する
- [ ] Step C に退避ロジックが存在しない
- [ ] 既存テストと新規テストが全て pass する

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: commit-docs.sh が flock 下で add + commit し ref が進む
- [ ] 異常系: ロック取得不能・worktree 不在時のエラー終了
- [ ] 並行系: merge-task.sh と commit-docs.sh の同時実行で両コミットが残る
- [ ] resume: ブランチのみ残存状態からの worktree 再構成

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| integration worktree | `em-workflow/{feature}/integration` ブランチを checkout した専用 worktree |
| 旧レイアウト | feature-docs 等を main 作業ツリーに untracked で置く現行方式 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 適用範囲: 対話モードと batch モードの両方に適用する
- [x] コミット粒度: 状態更新の都度コミット
- [x] 旧形式互換: サポートしない（新形式のみ。未完の旧形式 feature は存在しない）
- [x] worktree 除外方式: gitignore-guard の .gitignore 追記を現状維持

### 14.2 未確認・保留事項

なし。

## 15. 参考資料

- 検討レポート: tmp/report-integration-worktree-orchestrator-20260723-175049.md
- 現行ブランチモデル: em-workflow/references/implement-phase.md
