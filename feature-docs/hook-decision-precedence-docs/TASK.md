# Task Document: hook-decision-precedence-docs — フック文書の判定優先順位の記述を公式仕様に合わせる

## Change

`em-workflow/hooks/destructive-guard.py` のコメント・docstring と `em-workflow/README.md` の文章のうち、「hook の allow が別フックの判定を上書きする」「hook の判定が `permissions.deny` より優先される」という趣旨の記述を、公式仕様（複数 PreToolUse フックの判定優先順位は deny > defer > ask > allow。hook が allow を返しても settings の deny / ask ルールは評価される）と食い違わない記述に直す。対象は次の 7 か所。

1. `destructive-guard.py` 30-31 行（モジュール docstring）: 「hook の判定が `permissions.deny` より優先され、後から足した deny ルールはこの hook が allow したコマンドに効かない」を、この hook が allow を返しても settings.json の deny / ask ルールは引き続き評価される（一致する deny は実行を拒否し、一致する ask は確認を求める）という記述に置き換える。
2. `destructive-guard.py` 349-354 行（KILL_WORDS 前のコメント）: プロセス終了コマンドの判定は kill-guard.py が担当し、この hook は自身の破壊的操作の検査を続けたうえで、該当時は main() 末尾の allow だけを返さない、という記述にする。「allow が kill-guard の deny を上書きしてしまうため」という理由は削除する。
3. `destructive-guard.py` 8855-8857 行（matches_target_shape() の docstring）: True になる対象でもこの hook 自身の検査は続け、末尾の allow は返さない、という記述にする。「allow が他 hook の deny を上書きするため」という理由は削除し、別の設計理由は補わない。
4. `destructive-guard.py` 8981-8985 行（main() 内 defer_to_kill_guard 前のコメント）: コマンド文字列が KILL_WORDS の検索条件に一致すると末尾の allow を返さないが、複合コマンド中の他の破壊的操作の検査は続ける、という記述にする。「kill-guard の deny/ask が上書きされないように」という理由は削除する。
5. `destructive-guard.py` 9137-9139 行（_OUTCOME_RANK 前のコメント）: allow が他のガードの判定を奪うという含意を持たない記述にする。
6. `README.md` 139 行: PreToolUse(Bash) の hook の並びを hooks.json の登録順として記載し、複数 hook の判定の優先順位を deny > defer > ask > allow と記載する。「先に allow が確定すると bash_guard.py の承認ゲートが働くべき経路を潰しかねない」という、allow が他 hook の判定を上書きすることを前提とした理由は削除する。
7. `README.md` 149 行: 「hook の判定は `permissions.deny` より優先される。後から deny ルールを足しても、この hook が allow したコマンドには効かない。」を、1. と同じ趣旨の記述に置き換える。

destructive-guard.py の判定処理（コード）、hooks.json、tests、他の feature-docs は変更しない。置き換える記述の言語は各箇所の周辺に合わせる（destructive-guard.py は英語、README.md は日本語）。

## Expected Result

- 上記 7 か所に、hook の allow が別 hook の deny / ask を上書きする、または hook の判定が `permissions.deny` より優先される、という趣旨の記述が残っていない。
- `README.md` と `destructive-guard.py` のモジュール docstring が、hook が allow を返しても settings.json の deny / ask ルールは引き続き評価される旨を記載している。`README.md` は複数 hook の判定の優先順位を deny > defer > ask > allow と記載している。
- `destructive-guard.py` の差分はコメントと docstring の文言だけで、docstring を除いた AST は変更前と一致する。
- `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` が通る。
- 差分のあるファイルは `em-workflow/hooks/destructive-guard.py`、`em-workflow/README.md`、この feature の feature-docs だけである。
