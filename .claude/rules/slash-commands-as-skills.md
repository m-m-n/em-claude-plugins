# Slash Commands as Skills

スラッシュコマンドはスキルに統合されているため、コマンドを `commands/` ディレクトリに作らない。

## Rules

- スラッシュコマンドを新規作成するときは、スキル（`skills/<name>/SKILL.md`）として作成する。
- プラグイン内でも同様: `plugins/<plugin>/commands/` は使わず `plugins/<plugin>/skills/<name>/SKILL.md` に置く。
- プロジェクト/ユーザー設定でも同様: `.claude/commands/` や `~/.claude/commands/` に新規ファイルを作らない。
- 既存の `commands/*.md` を見つけても、新規作成時の形式の参考にしない。
