# プラグインを新しく作る

## 1. ディレクトリを作る

マーケットプレイスのリポジトリルート直下に `<plugin-name>/` を作る。ディレクトリ名が
プラグイン名になり、スラッシュコマンドのネームスペースになる（`/<plugin-name>:<skill>`）。

```
<plugin-name>/
├── .claude-plugin/
│   └── plugin.json
├── skills/<skill-name>/SKILL.md
├── agents/
├── hooks/
└── references/
```

- 使わないディレクトリは作らない。
- スラッシュコマンドは `commands/` ではなく `skills/<name>/SKILL.md` に置く。
- `<plugin-name>/` 配下の全ファイルが利用者の環境に配られる。git の追跡対象かどうかは
  関係ない。

## 2. plugin.json を書く

```json
{
  "name": "<plugin-name>",
  "description": "<説明>",
  "author": {
    "name": "<作者>"
  },
  "version": "0.1.0"
}
```

## 3. marketplace.json に登録する

リポジトリルートの `.claude-plugin/marketplace.json` の `plugins[]` に追加する。

```json
{
  "name": "<plugin-name>",
  "description": "<説明>",
  "author": {
    "name": "<作者>"
  },
  "category": "<分類>",
  "source": "./<plugin-name>",
  "version": "0.1.0"
}
```

`version` は plugin.json と同じ値にする。

## 4. version 自動更新の Actions

リポジトリルートに `.github/workflows/plugin-version-bump.yml` が無ければ置く。
中身はこのスキルの `templates/plugin-version-bump.yml` をそのままコピーする。

### 動き

- main への push で発火する。
- push 前後の差分に含まれるプラグイン（`.claude-plugin/plugin.json` を持つディレクトリ）
  ごとに、plugin.json と marketplace.json の `version` の patch を 1 上げてコミットし、
  PR を作って main にマージする。
- 次のプラグインは上げない。
    - その push で新しく追加されたプラグイン
    - その push の中で `version` が手で変えられたプラグイン
    - `version` が `MAJOR.MINOR.PATCH` の形でないプラグイン
- Actions 自身のコミットはワークフローを再発火させない。

### 前提

- リポジトリ設定の Settings → Actions → General で
  「Allow GitHub Actions to create and approve pull requests」を有効にする。
- main の保護ルールで PR の承認を必須にしていると、マージできない。
- 置いた後のプラグイン変更は [update.md](update.md) に従う。
