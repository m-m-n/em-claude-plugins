# em-claude-plugins

このリポジトリは Claude Code プラグインを管理するマーケットプレイスです。各プラグインはルート直下のサブディレクトリとして配置されています。

## 構成

```
.
├── .claude-plugin/
│   └── marketplace.json    # マーケットプレイス定義（plugins[].source で各プラグインを参照）
├── <plugin-name>/          # 各プラグインのルート（サブディレクトリ単位）
│   ├── .claude-plugin/
│   │   └── plugin.json     # プラグイン定義（name / version / description）
│   ├── agents/             # サブエージェント定義
│   ├── skills/             # スキル定義
│   └── references/         # プラグイン内 SSOT（プロトコル / スキーマ / レジストリ等）
└── README.md
```

## プラグインを追加するときのルール

- ルート直下に `<plugin-name>/` ディレクトリを作る（プラグイン名 = ディレクトリ名）
- そのディレクトリ内に `.claude-plugin/plugin.json` を置く
- `.claude-plugin/marketplace.json` の `plugins[]` にエントリを追加し、`source` は `./<plugin-name>` を指す
- プラグイン名がスラッシュコマンドのネームスペースになる（例: `em-review` → `/em-review:<skill>`）

## バージョン管理

- 各プラグインの `version` は `<plugin>/.claude-plugin/plugin.json` で個別に管理する
- パッチ単位での bump を基本とする（例: 0.1.5 → 0.1.6）

## 個別プラグインの仕様

各プラグイン固有の仕様・設計判断は、そのプラグインディレクトリ配下のドキュメント / `references/` / agent prompt を参照すること。ルートではプラグイン横断の構造ルールのみを扱う。
