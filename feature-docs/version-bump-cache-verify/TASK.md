# Task Document: version-bump-cache-verify — push 後のキャッシュ反映を Claude が確かめる形に core-plugin-version-bump ルールを変える

## Change

`.claude/rules/core-plugin-version-bump.md` の `## Rules` を次のとおり変える。

1. 「main に push した後は、Actions のコミットを `git pull` で取り込んでから次の作業に入る。」の項目を、次の内容に置き換える。
    - main に push した後、Actions のコミットを `git pull` で取り込み、`~/.claude/plugins/cache/<marketplace>/<plugin>/<新しい version>/` に変更が入っていることを確かめる。
    - 確かめる対象は、その push でファイルが変わったプラグイン。
    - 新しい version のキャッシュが無いか、中身がリポジトリと一致しないときは、`claude plugin update <plugin>` でキャッシュを更新して確かめ直す。それでも確かめられなければ、原因を調べて報告する。
    - Actions が version を上げなかったときは、その原因を調べて報告する。
2. 「変更をユーザーに報告するときは、反映に Claude Code の再起動が要ることを添える。」の項目を削り、次の内容に置き換える。
    - 再起動が要るのは、今開いている対話セッションへの反映だけ。新しく起動するセッション（無人実行を含む）には、再起動なしで反映される。

ファイル名、level-1 見出し「# Plugin Version Bump」、他の項目、`## Rationale` と `## 由来` の節は変えない。他のファイルは変えない。

## Expected Result

- `.claude/rules/core-plugin-version-bump.md` に、main に push した後、Actions のコミットを `git pull` で取り込み、`~/.claude/plugins/cache/<marketplace>/<plugin>/<新しい version>/` に変更が入っていることを確かめる、と書かれている。
- Actions が version を上げなかったときは、その原因を調べて報告する、と書かれている。
- 新しい version のキャッシュが無いか中身が一致しないときは `claude plugin update <plugin>` で更新して確かめ直し、それでも確かめられなければ原因を調べて報告する、と書かれている。
- 再起動が要るのは今開いている対話セッションへの反映だけで、新しく起動するセッションには再起動なしで反映される、と書かれている。「反映に Claude Code の再起動が要ることを添える」の項目は残っていない。
- base からの差分は `.claude/rules/core-plugin-version-bump.md` と、この feature の feature-docs・test-docs だけである。
- リポジトリルートで `python3 -m unittest tests.test_guardrail_hooks_migration` が通る。
