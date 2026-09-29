# 既存プラグインを変更する

リポジトリルートに `.github/workflows/plugin-version-bump.yml` があることが前提。
無ければ [create.md](create.md) の「version 自動更新の Actions」を先に行う。

## version は触らない

- プラグインの中身を変えても、plugin.json と marketplace.json の `version` は変えない。
- main にマージ（push）されると、Actions が変更のあったプラグインの patch を上げて
  コミットする。
- SPEC・計画・受け入れ条件に version の変更を書かない。

## minor / major を上げるとき

機能追加（minor）や互換性を壊す変更（major）のときだけ、手で上げる。

- plugin.json と marketplace.json の `version` を同じ値にして、変更と同じコミットに含める。
- その push では Actions は patch を上げない。

## マージ後

- Actions が main にコミットを足すので、次の作業の前に `git pull` する。
- インストール済みのプラグインに反映するには、マーケットプレイスの更新と
  Claude Code の再起動が要る。
