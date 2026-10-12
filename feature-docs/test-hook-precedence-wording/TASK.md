# Task Document: test-hook-precedence-wording — テストに残る「blanket allow が判定を終わらせる」記述を判定優先順位に合わせる

## Change

テストのコメント・docstring・アサーションメッセージのうち、「`destructive-guard.py` の blanket allow が判定を終わらせる（ends the decision）」「ask / deny を出すガードは blanket allow より前に走らなければならない」「hooks.json の配列順が実行順である」という前提の記述を、公式仕様（複数 PreToolUse フックの判定優先順位は deny > defer > ask > allow。後の hook の allow が先の hook の deny / ask を上書きすることはない。一致する hook は並列に実行される）と食い違わない記述に直す。登録順は「hooks.json で宣言した順序（declared order）をテストで固定している」という事実として書く。記述は英語のまま。

1. `tests/test_guardrail_hooks_migration.py` モジュール docstring の性質 1「Order」（10-17 行）: テストが hooks.json で宣言した PreToolUse(Bash) の順序を固定していることを書く。「配列順が実行順である」「blanket allow が判定を終わらせる」「前に置くと bash_guard.py のゲートが黙って無効になる」という主張は削除する。判定の優先順位 deny > defer > ask > allow と、後の hook の allow が先の hook の deny / ask を上書きしないことを、ここに 1 回だけ書く。
2. 同 docstring の heredoc-stdin-guard / loop-command-guard / cross-repo-write-guard の段落（35-66 行）: 各 hook の位置の説明と、`EXPECTED_BASH_GUARD_ORDER`・テストメソッド名への参照は残す。「blanket allow が判定を終わらせる」「blanket allow より前に走らなければならない」に依拠する理由は、その位置が `EXPECTED_BASH_GUARD_ORDER` により宣言順で固定されている、という事実に置き換える。heredoc-stdin-guard.py は判定を返さない（updatedInput を返すか何も返さない）ことは残す。
3. `EXPECTED_BASH_GUARD_ORDER` 前のコメント（93-114 行）: 「実行順」ではなく、PreToolUse(Bash) ガードの宣言順として説明する。出典の引用（failed-run-cleanup-guard D1、muse-spark-contributor-consent task0001 Registration、loop-command-guard task0001 Registration、cross-repo-write-guard C1、heredoc-stdin-guard task0001 D3）は残す。ガードが blanket allow より前に走らなければならない、blanket allow が判定を打ち切りうる、という理由は削除する。heredoc-stdin-guard.py は `em-workflow/README.md` 139 行と同じ趣旨（判定を返さず updatedInput の書き換えのみなので宣言順の最後に置く）で書き、末尾配置が実行順を保証する、または他のガードが書き換え後のコマンドを見ない、とは書かない。
4. `TestPreToolUseBashGuardOrder` のクラス docstring（298-299 行）とテスト内コメント（310-315 行）: クラス docstring は「destructive-guard.py が宣言順で判定を返す Bash ガードの最後にある」と書く。テスト内コメントは、heredoc-stdin-guard.py は判定を返さないのでこの検査から除外する、と書き、「このテストが守るゲートを再び開く」という表現は削除する。
5. 同ファイルのアサーションメッセージ: 322-323 行は `destructive-guard.py must stay last among the decision-capable Bash guards in the declared order; order is {names}`（f-string の補間は残す）、331-332 行は `bash_guard.py must precede destructive-guard.py in the declared order`、356 行は `cross-repo-write-guard.py must precede destructive-guard.py in the declared order` にする。
6. `tests/test_muse_guard_registration.py`: `TestEmWorkflowOrderingAgainstDestructiveGuard` の docstring（99-102 行）は muse_guard.py が宣言順で destructive-guard.py より前にあることを書き（task0001 Design「Registration」の引用は残す）、destructive-guard.py の末尾 allow が先に判定を終わらせる、という節は削除する。117 行のメッセージは `muse_guard.py must precede destructive-guard.py in the declared order; order={self.order}`（補間は残す）にする。121-125 行のコメントは、heredoc-stdin-guard.py は判定を返さないのでこの検査から除外する、と書き、「blanket allow ends the decision」ゲートの表現は削除する。
7. `tests/test_hooks_registration.py` モジュール docstring（67-70 行）: 相対順序の不変条件を「destructive-guard.py は宣言順で判定を返す Bash ガードの最後にある」と書き直す。この不変条件は `tests/test_guardrail_hooks_migration.py` だけが扱い、ここでは重複させない、という記述は残す。

`tests/test_guard_deferral_parity.py`（「blanket allow must survive / intact」は destructive-guard.py 単体の出力が allow であることを指す）と `em-workflow/hooks/destructive-guard.py`（353・8855・8883・8981・8992 行付近は、この hook 自身が末尾の allow を返すかどうかを述べている）は、上書きの前提を含まないので変更しない。アサーションの式・期待値・`EXPECTED_BASH_GUARD_ORDER` の名前と値・`decision_capable` の絞り込み・位置の比較、テストのモジュール名・クラス名・メソッド名（`blanket_allow` を含むものも）は変更しない。`em-workflow/hooks/hooks.json`、`em-workflow/README.md`、プラグインの version は変更しない。

## Expected Result

- 上記 1-7 の箇所に、destructive-guard.py の blanket allow が判定を終わらせる・打ち切る、ガードが blanket allow より前に走らなければならない、hooks.json の配列順が実行順である、並べ替えるとゲートが黙って無効になる、という趣旨の記述が残っていない。4 つのテストファイルのコメント・docstring・メッセージに `ends the decision`、`IS the execution order`、`before the blanket allow`、`blanket allow must run`、`reopen`、`silently disable` が現れない（テストメソッド名は対象外）。
- `deny > defer > ask > allow` と「後の hook の allow が先の hook の deny / ask を上書きしない」旨の記述は、`tests/test_guardrail_hooks_migration.py` のモジュール docstring に 1 回だけあり、他の変更ファイルには繰り返されない。
- 変更した各 .py ファイルは、docstring とアサーション呼び出しの msg 引数を除いた AST が変更前と一致する。テスト名は変わっていない。
- 差分のあるファイルは `tests/test_guardrail_hooks_migration.py`、`tests/test_muse_guard_registration.py`、`tests/test_hooks_registration.py` と、この feature の feature-docs だけである。
- `python3 -m unittest discover -s tests` と `python3 em-workflow/hooks/tests/run-destructive-guard.py` がリポジトリルートで通る。
