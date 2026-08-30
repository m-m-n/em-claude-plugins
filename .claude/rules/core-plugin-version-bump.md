# Plugin Version Bump

Claude Code プラグインの中身を変更したら、同じ変更の中で version を上げる。

## Rules

- `<plugin>/` 配下のファイル（hooks / skills / agents / scripts など）を
  変更したら、その変更に含めて version を上げる。
- 上げる場所は 2 箇所。両方を同じ値にする。
    - `<plugin>/.claude-plugin/plugin.json` の `version`
    - リポジトリルート `.claude-plugin/marketplace.json` の該当プラグインの `version`
- version はプラグインごとに独立している。1 つを上げても他は動かさない。
- 刻み方は semver に従う。挙動の修正は patch、機能追加は minor、互換性を壊す変更は major。
  実際にはほとんどが挙動の修正なので、patch 単位が基本になる。
- 変更をユーザーに報告するときは、反映に Claude Code の再起動が要ることを添える。

## Rationale

インストール済みプラグインは `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`
に展開され、Claude Code はこの version でキャッシュの鮮度を判断する。source が
`directory` で `autoUpdate: true` でも、version が据え置きのままだとキャッシュは
古いファイルを保持し続ける。ソースを直しただけでは実際に動くコードは変わらない。

## 由来

eMterm プラグインの Stop hook を `idle` から `done` に変更してリポジトリにマージ
したが、version が `0.1.0` のままだったためキャッシュが更新されなかった。
`~/.claude/plugins/cache/emterm-plugins/emterm/0.1.0/hooks/hooks.json` は 2 週間前の
`idle` を送り続け、eMterm 側の通知ゲートが `blocked` / `done` しか通さないため、
デスクトップ通知が一切出ない状態が続いた。リポジトリ側のファイルは正しかったので、
コードを読むだけでは原因に辿り着けなかった。
