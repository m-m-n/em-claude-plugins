# プラグインの配置と構造

各プラグインはリポジトリのルート直下に 1 ディレクトリとして置く。ディレクトリ名が
そのままプラグイン名になり、スラッシュコマンドのネームスペースにもなる
（`em-review/` → `/em-review:<skill>`）。

## 構成

```
.
├── .claude/
│   └── rules/              # このリポジトリの作業ルール
├── .claude-plugin/
│   └── marketplace.json    # マーケットプレイス定義（plugins[].source で各プラグインを参照）
├── <plugin-name>/          # 各プラグインのルート
│   ├── .claude-plugin/
│   │   └── plugin.json     # プラグイン定義（name / version / description）
│   ├── agents/             # サブエージェント定義
│   ├── skills/             # スキル定義
│   ├── hooks/              # フック（hooks.json + スクリプト）
│   ├── scripts/            # プラグインが実行するスクリプト
│   └── references/         # プラグイン内 SSOT（プロトコル / スキーマ / レジストリ等）
└── README.md
```

## プラグインを追加するとき

- ルート直下に `<plugin-name>/` を作る。
- その中に `.claude-plugin/plugin.json` を置く（`name` / `version` / `description`）。
- `.claude-plugin/marketplace.json` の `plugins[]` にエントリを追加し、`source` を
  `./<plugin-name>` にする。

## 配布されるもの

インストール時は `<plugin-name>/` **配下の全ファイル**が
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` にコピーされる。git の
追跡対象かどうかは関係なく、`__pycache__` のような生成物もそのまま入る。同梱対象を
選ぶフィールドは plugin.json に無い。テストや開発用ファイルを置くときは、それが
利用者の環境にも配られることを前提にする。

## 個別プラグインの仕様

プラグイン固有の仕様・設計判断は、そのプラグインの `references/` / agent prompt /
README を参照する。ルート側で扱うのはプラグイン横断の構造ルールだけ。
