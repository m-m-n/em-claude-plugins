# フックのテスト

`em-workflow/hooks/destructive-guard.py` を変更したら、同じ変更の中でテストを走らせる。

```
python3 em-workflow/hooks/tests/run-destructive-guard.py
```

引数にパスを渡すと別のコピーを検査できる。インストール済みのキャッシュが古くないか
確かめるときに使う。

```
python3 em-workflow/hooks/tests/run-destructive-guard.py \
  ~/.claude/plugins/cache/em-claude-plugins/em-workflow/<version>/hooks/destructive-guard.py
```

## Rules

- ケースは `em-workflow/hooks/tests/destructive-guard-cases.json` に
  `[期待する判定, ラベル, コマンド]` の 3 要素で並べる。
- 誤爆（本来 allow なのに ask / deny になった）を見つけたら、直す前にケースを足す。
  見逃し（deny すべきものが allow になった）も同じ。
- 既存の deny / ask ケースは消さない。誤爆を潰す修正が検知力を削っていないことを
  示すのがこのスイートの半分の役割。

## Rationale

このフックの誤爆は無人実行をその場で止める。`ask` は `claude-batch` 下で `deny` に
降格されるので、誰も答えられないまま走行が終わる。誤爆 1 件のコストが、見逃し 1 件の
コストと同じ桁にある。

判定はコマンド文字列の静的解析なので、シェルの引用規則を読み違えた瞬間に誤爆する。
クォートの中に書いた `rm -rf` を実行と誤認する、ヒアドキュメントの本文を 1 行ずつ
コマンドとして読む、`> /dev/null` を削除対象として数える——いずれも実際に起きて、
allow 側のケースとして残してある。
