---
name: retrospect
description: 自己改善ループの手動判断コマンド（em-workflow）。溜まった feature-docs/*/retrospect.yaml を横断分析し、再発性のある教訓候補を抽出して帰属先（feature-docs/LESSONS.md の audience セクション / プロジェクト CLAUDE.md / プラグイン改善候補=報告のみ）に分類、既存記述との重複チェックとユーザー承認を経てプロジェクト側に追記します。プラグイン本体のファイルには書き込みません。承認なしの自動追記は絶対にしません
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
2. **帰属先の分類**（書き込み先はプロジェクト側の 2 系統のみ）:
   - **プロジェクト教訓 → `feature-docs/LESSONS.md`**（このプロジェクトの
     次回 develop 実行で効かせる。audience セクション式、書式は下記）:
     - タスク分割・計画のつまずき（コンフリクトやり直し・files 予測ミス・
       配線所有者の不在等） → `## planner`
     - レビューで Critical/High が繰り返し出る実装領域 → `## implementer`
       （全タスク共通）または `## implementer:{layer}`（layer は
       impl-skills.yaml のスキル名から `-impl` を除いたもの: backend /
       frontend / design / infra）
     - declined findings の繰り返し（誤検知パターン: What NOT to flag） →
       `## reviewer:{perspective}`（comprehensive / spec / security /
       performance / architecture）
   - **ワークフロー外でも効くべき普遍事項 → プロジェクト CLAUDE.md**
   - **プラグイン改善候補 → ファイルには書かず Step 4 の報告のみ**:
     プロトコル・スキル・ルール表そのものの欠陥（review-rules.yaml への
     ルール昇格、worktree-task-workflow の手順不備、実装/レビュースキルの
     汎用チェックリスト不足等）。`${CLAUDE_PLUGIN_ROOT}` はインストール
     実体（更新で入れ替わる cache 等）を指すため、そこへの Edit は永続
     しない — プラグイン原本の修正は retrospect の外（プラグイン開発
     リポジトリでの作業）で行う。
3. **重複チェック**: 帰属先（LESSONS.md の該当セクション / CLAUDE.md）を
   Read し、既に同等の記述がないか確認。既存記述で防げたはずなら「記述は
   あるのに効かなかった」問題として別途報告（文言の強化候補）。

### LESSONS.md の書式

`feature-docs/LESSONS.md`（feature 横断・プロジェクト所有・git 管理は
ユーザー任せ）。無ければ作成し、セクションは必要になったときだけ足す:

```markdown
# em-workflow Lessons

## planner
- {教訓本文}（{feature} {date}, 根拠: {stable_id 等}）

## implementer:backend
- ...

## reviewer:security
- ...
```

読み手の配線（各フェーズ側が実装済み）: planner は `## planner` を、
implementer は `## implementer` と自レイヤーの `## implementer:{layer}` を、
レビューオーケストレーターは `## reviewer:{perspective}` を各実行時に
取り込む。ここにない audience 語彙を発明しない。

## Step 3: Propose and apply (approval REQUIRED)

採用候補ごとに AskUserQuestion で提示する: 教訓の内容、根拠事例（feature 名・
日付・stable_id 等へのリンク）、帰属先（LESSONS.md のセクション / CLAUDE.md /
プラグイン改善候補）、追記の具体文面。選択肢:
`適用する / 文面を調整する / 見送る`。

- 承認されたものだけを Edit で反映する。**承認なしの自動追記は絶対にしない。**
- Edit の対象は `feature-docs/LESSONS.md` とプロジェクト CLAUDE.md のみ。
  プラグイン配下（`${CLAUDE_PLUGIN_ROOT}` 等）のファイルは承認の有無に
  かかわらず Edit しない。
- 追記する教訓には根拠事例（feature 名・日付）を併記し、後で見直せるようにする。

## Step 4: Report

日本語で: 分析した feature 数 / 候補数 / 適用数 / 見送り数（理由付き）、
更新したファイル一覧。**プラグイン改善候補**があれば、内容・根拠・提案文面を
列挙する（プラグイン開発リポジトリで直すか issue にする材料）。LESSONS.md に
追記した場合、プロジェクトが git 管理下ならコミットを促す（プロジェクトの
恒久資産として残すため。ワークフロー各フェーズは main ツリーの絶対パスで
読むので、コミット前でも次回実行には効く）。定期棚卸し（溜まった教訓の監査）が
必要そうなら一言添える。

$ARGUMENTS
