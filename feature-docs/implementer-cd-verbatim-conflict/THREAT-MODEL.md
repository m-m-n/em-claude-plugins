# Threat Model: implementer-cd-verbatim-conflict

## Verdict
threats-identified

## Rationale

調べたもの: REQUIREMENTS.md と SPEC.md（tier: full）、`em-workflow/hooks/bash_guard.py` の現在の判定、変更対象の文書（implementer.md、worktree-task-workflow/SKILL.md、command-execution-protocol.md、README.md、workflow-schema.md）。

信頼境界は 1 つ。エージェント（LLM）が組み立てた Bash コマンド文字列が PreToolUse hook に渡り、hook が allow を返すとユーザーの確認なしに実行される。この機能はその allow の経路を 1 つ増やすので、境界をまたいで権限が広がる危険がある。task0001 が `auth`（allow / deny の権限判定）と `input-handling`（コマンド文字列の分解）を宣言しているため、この境界は deep で分析した。

文書の変更（task0002、task0003）は、エージェントにどの形で実行するかを指示するだけで、新しい信頼境界をまたがない。指示がどう書かれていても、確認なしの実行を許すかどうかは hook が決める。task0002・task0003 は `config-infra` だけを宣言しており、深さを上げる 4 つのドメインを持たない。

hook のテストが一時ディレクトリに git リポジトリを作って git を起動するのはテストの中だけで、利用者の環境に信頼境界を足さない。

## Trust Boundaries

### TB-1: エージェントの Bash コマンド文字列 → bash_guard の allow 判定
Crossing: エージェント（プロンプトインジェクションを受けうる LLM）が組み立てたコマンド文字列と、Claude Code が渡す hook 入力の cwd。hook が allow を返すと、ユーザーの permission 確認を経ずにコマンドが実行される（権限の変化）。
Boundary files: `em-workflow/hooks/bash_guard.py`
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | 前置部に別のコマンドや展開を混ぜた文字列（セミコロン・パイプ・コマンド置換・バッククォート・改行・`cd` のオプション・引用なしや一重引用のパス・2 つ目のパス引数）や、残りの後ろにコマンドを足した文字列が、承認済み文字列を含むことを理由に allow され、未承認のコマンドが確認なしで実行される（FR1 (a)〜(d)・(f)、NFR2） | TM-1 | 構文条件（IMPLEMENTATION.md C1 の 1〜4）をすべて満たし、残り全体が承認済み文字列と完全一致するときだけ C1 の候補にする。外れた形は C1 の対象外として文字列全体に変更前の判定表を当て、新しい allow を出さない | task0001 AC-2 | VERIFICATION.md Performance / Security Verification の TM-1 |
| Elevation of privilege | 承認はこのリポジトリでのコマンド文字列に対するもの。`..`、シンボリックリンク、別リポジトリの `.claude/worktrees/em-workflow/` 配下、worktrees ディレクトリそのもの、名前が前方一致する兄弟ディレクトリへの `cd` で、承認済み文字列を想定外の場所（別リポジトリのコードを読む場所や worktree 領域の外）で確認なしに実行させる（FR1 (e)、NFR2） | TM-2 | P の realpath が「hook の cwd から求めた git common dir の親の直下にある `.claude/worktrees/em-workflow` の realpath」より深い既存ディレクトリのときだけ許す。比較はパスの区切りごとの要素で行い、基準の場所そのものは含めない。git common dir を求められないときは許さない。P は realpath で解決するだけで、P を作業ディレクトリや引数にした子プロセスを起動しない | task0001 AC-3 | VERIFICATION.md Performance / Security Verification の TM-2 |
| Elevation of privilege | 禁止パターンを含む文字列が承認ストアに入っている場合（ストアの直接編集）に、新しい allow の経路が「禁止パターンは承認済みでも deny」の規則をすり抜ける（FR2） | TM-3 | C1 の候補には、allow を返す前にコマンド全体へ禁止パターンの判定を当て、一致したら deny する | task0001 AC-4 | VERIFICATION.md Performance / Security Verification の TM-3 |
