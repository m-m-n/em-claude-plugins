---
name: retrospect
description: 自己改善ループの手動判断コマンド（em-workflow）。溜まった feature-docs/*/retrospect.yaml を横断分析し、再発性のある教訓候補を抽出して帰属先（実装スキル / レビュー観点スキル / review-rules.yaml / worktree-task-workflow / プロジェクト CLAUDE.md）に分類、既存スキルとの重複チェックとユーザー承認を経てスキル追記またはルール表更新を行います。承認なしの自動追記は絶対にしません
argument-hint: "[feature-name ...]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
---

# em-workflow Retrospect (manual lesson mining)

原則: **収集は自動（develop の最終フェーズ）、スキル化の判断は手動（この
コマンド）**。完了直後の承認はラバースタンプ化するため、develop はこのフローを
自動起動しない。

## Step 1: Collect the raw material

- 引数で feature 名が指定されていればその `feature-docs/{feature}/
  retrospect.yaml` のみ、なければ Glob `feature-docs/*/retrospect.yaml` で
  全件読む。0 件なら「分析対象がないよ」と報告して終了。
- 各 retrospect.yaml の `signals` と `lessons_candidates` を集約する。必要に
  応じて対応する `reviews/round*.yaml` / workflow.yaml も参照して文脈を補う。
- セッション JSONL（`~/.claude/projects/{encoded-cwd}/{session_id}.jsonl`）は
  深掘りが必要な candidate に限って参照する（全部は読まない）。

## Step 2: Cross-feature analysis (recurrence is the bar)

教訓候補ごとに:

1. **再発性**: 同種のシグナルが複数 feature（または同一 feature の複数
   ラウンド）に現れているか。一回きりの事象は原則スキル化しない —
   `見送り（単発）` として記録するだけ。
2. **帰属先の分類**:
   - レビューで Critical/High が繰り返し出る領域 → 該当**実装スキル**の
     チェックリスト不足
   - declined findings の繰り返し（誤検知パターン） → 該当**レビュー観点
     スキル**の What NOT to flag 不足
   - 裁量層の同種の観点追加が繰り返される → **review-rules.yaml** のルール
     不足（機械層に昇格させる）
   - コンフリクトやり直し・files 予測ミスの繰り返し → **plan-writing**
     （タスク分割規則）の不足
   - マージ・worktree 運用のつまずき → **worktree-task-workflow** の不足
   - プロジェクト固有の事情 → **プロジェクト CLAUDE.md**
3. **重複チェック**: 帰属先スキル / ルール表を Read し、既に同等の記述が
   ないか確認。既存記述で防げたはずなら「記述はあるのに効かなかった」問題
   として別途報告（文言の強化候補）。

## Step 3: Propose and apply (approval REQUIRED)

採用候補ごとに AskUserQuestion で提示する: 教訓の内容、根拠事例（feature 名・
日付・stable_id 等へのリンク）、帰属先ファイル、追記/変更の具体文面。選択肢:
`適用する / 文面を調整する / 見送る`。

- 承認されたものだけを Edit で反映する。**承認なしの自動追記は絶対にしない。**
- 追記する教訓には根拠事例（feature 名・日付）を併記し、後で見直せるようにする。
- review-rules.yaml の変更は決定的評価を壊さないこと（domains 8 語彙 /
  complexity 3 段階の外に出ない）。

## Step 4: Report

日本語で: 分析した feature 数 / 候補数 / 適用数 / 見送り数（理由付き）、
更新したファイル一覧。定期棚卸し（溜まったスキルの監査）が必要そうなら一言
添える。

$ARGUMENTS
