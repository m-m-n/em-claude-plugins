# Plugin Version Bump

プラグインの version は、main への push 時に GitHub Actions
（`.github/workflows/plugin-version-bump.yml`）が上げる。実装では version を触らない。

## Rules

- `<plugin>/` 配下のファイルを変更しても、version は変えない。
    - `<plugin>/.claude-plugin/plugin.json` の `version`
    - リポジトリルート `.claude-plugin/marketplace.json` の該当プラグインの `version`
- main に push されると、Actions が変更のあったプラグインの patch を上げてコミットする。
- 機能追加（minor）や互換性を壊す変更（major）のときだけ、上の 2 箇所を同じ値に手で上げ、
  変更と同じコミットに含める。その push では Actions は patch を上げない。
- SPEC・計画・受け入れ条件に version の変更を書かない。minor / major を上げる場合だけ、
  上げる位置を書く。具体値は書かない。
    - 例: 「em-workflow の version の minor を上げる」
    - 悪い例: 「0.2.12 → 0.3.0 に上げる」
- main に push した後は、Actions のコミットを `git pull` で取り込んでから次の作業に入る。
- 変更をユーザーに報告するときは、反映に Claude Code の再起動が要ることを添える。
- 詳細は `plugin-dev` プラグインの `plugin-dev` スキルを参照する。

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
