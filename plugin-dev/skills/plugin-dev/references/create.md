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

- main への push と workflow_dispatch で発火する。workflow_dispatch は ref が main の
  ときだけ version を更新する。

#### push のとき

- 比較の基点を次の順で決める。BEFORE は push 前の main の commit、AFTER は push された
  commit。
    1. BEFORE が 40 桁の 16 進数で、全部が 0 ではなく、clone にあれば、BEFORE を基点にする。
    2. BEFORE が同じ形で clone に無ければ、origin から BEFORE を 1 回だけ fetch する。
       取れたら BEFORE を基点にする。
    3. fetch が失敗したとき、BEFORE が全部 0 のとき、BEFORE が 40 桁の 16 進数でない
       ときは、AFTER の第 1 親を基点にし、`::warning::` で始まる行でその旨を出す。
       処理は続ける。
    4. AFTER に第 1 親も無いときは、ファイルを変えずに非 0 で終了する。
- 基点と AFTER の差分に含まれる各ファイルについて、そのファイルから上へ辿って最初に
  `.claude-plugin/plugin.json` を持つディレクトリを、変更のあったプラグインとする。
- 変更のあったプラグインごとに、基点と AFTER の plugin.json の `version` を
  `MAJOR.MINOR.PATCH` の整数の組として比べる。
    - AFTER が基点以下: 2 つのうち大きい方の patch を 1 上げた値を、plugin.json と、
      同じ名前の marketplace.json のエントリに書く。
    - AFTER が基点より大きい（minor や major を手で上げた）: 変えない。
    - 次のプラグインは上げない。
        - 基点に plugin.json が無いプラグイン（その push で新しく追加されたもの）
        - 基点か AFTER の `version` が `MAJOR.MINOR.PATCH` の形でないプラグイン
    - marketplace.json のエントリに `version` が無いときは、そのエントリを書き換えない。

#### workflow_dispatch のとき

- 入力は 2 つで、どちらも必須。
    - `plugin`: marketplace.json に登録済みのプラグイン名
    - `min_version`: `MAJOR.MINOR.PATCH`（各項は 0 以上の整数）
- 結果は次のとおり。
    - 現在の `version` が `min_version` 以下で、major と minor が同じ: `min_version` の
      patch を 1 上げた値を、plugin.json と、同じ名前の marketplace.json のエントリ
      （`version` を持つとき）に書く。
    - 現在の `version` が `min_version` を超える: ファイルを変えず、成功で終わる。
      `bumped` は空になる。
    - `plugin` が未登録: ファイルを変えずに非 0 で終了する。
    - `min_version` が `MAJOR.MINOR.PATCH` の形でない: ファイルを変えずに非 0 で終了する。
    - 現在の `version` が `min_version` 以下だが、major か minor が違う:
      ファイルを変えずに非 0 で終了する。

#### 出力と取り込み

- 非 0 で終了するときは、理由を示すメッセージを出す。
- 上げたプラグインを `name@version` のカンマ区切りで GITHUB_OUTPUT の `bumped` に書く。
  上げなかったときは空にする。
- push と workflow_dispatch のどちらでも、`bumped` が空でなければ、コミットして PR を
  作り、main にマージする。
- Actions 自身のコミットはワークフローを再発火させない。

### 前提

- リポジトリ設定の Settings → Actions → General で
  「Allow GitHub Actions to create and approve pull requests」を有効にする。
- main の保護ルールで PR の承認を必須にしていると、マージできない。
- 置いた後のプラグイン変更は [update.md](update.md) に従う。
