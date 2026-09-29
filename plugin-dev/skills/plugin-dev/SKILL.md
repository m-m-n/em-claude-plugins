---
name: plugin-dev
description: Claude Code プラグインを新しく作るとき、または既存プラグインの中身（skills / agents / hooks / scripts / references / plugin.json など）を変更するときに使う。新規作成なら構成・マーケットプレイス登録・version 自動更新の GitHub Actions の置き方を、更新なら version を手で上げないことと例外を示す。
---

# Plugin Dev

作業の種類を判定し、対応する資料だけを読む。

| 作業 | 読む資料 |
| --- | --- |
| プラグインを新しく作る（`.claude-plugin/plugin.json` がまだ無い） | [references/create.md](references/create.md) |
| 既存プラグインの中身を変える | [references/update.md](references/update.md) |

## 判定

1. 作業対象のディレクトリに `.claude-plugin/plugin.json` があるかを見る。
    - 無い → 新規作成
    - ある → 更新
2. 更新でも、リポジトリルートに `.github/workflows/plugin-version-bump.yml` が無いときは、
   先に create.md の「version 自動更新の Actions」を行う。

## 同梱ファイル

- `templates/plugin-version-bump.yml` — version 自動更新の Actions ワークフロー
