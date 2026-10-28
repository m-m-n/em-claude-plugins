# Implementation Plan: implementer-cd-verbatim-conflict

## Overview

`em-workflow/hooks/bash_guard.py` に、implementer が `cd "{worktree_path}" && <承認文字列>` の 1 回の Bash 呼び出しで承認済みコマンドを実行する形の許可を足し、implementer・スキル・参照文書の指示と説明をこの形に合わせる。

## Technology Stack

- **Language**: Python 3（hook とテスト。標準ライブラリのみ、NFR1・NFR8）
- **Test framework**: 標準ライブラリの unittest（`python3 -m unittest discover -s tests`）
- **Documents**: Markdown（エージェント定義・スキル・参照文書・README）
- **New dependencies**: なし（`project.license: none`。記録するライセンスなし）

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| 実行時強制 | `em-workflow/hooks/bash_guard.py` | Bash 呼び出しごとに allow / deny / 判定なしを決める。文書を読まない |
| implementer 向け指示 | `em-workflow/agents/implementer.md`、`em-workflow/skills/worktree-task-workflow/SKILL.md` | implementer がコマンドをどの形で実行するかを指示する |
| 参照文書 | `em-workflow/references/command-execution-protocol.md`（プロトコルの SSOT）、`em-workflow/README.md`、`em-workflow/references/workflow-schema.md`（要約と参照） | hook の判定と役割ごとの実行規則を説明する |
| テスト | `tests/` | hook の挙動（subprocess で起動）と文書の文言を確かめる |

依存の向き: 文書は hook の挙動を説明する側で、hook は文書に依存しない。README.md と workflow-schema.md は詳細を command-execution-protocol.md に委ね、規則を重複して定義しない。

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1: cd 前置形の許可規則 | hook が新しく allow する形と、その判定順を定める | 下の「C1 の定義」のとおり。task0001 が実装し、task0002・task0003 の文書はこの定義と食い違う記述をしない | task0001, task0002, task0003 |
| C2: 役割ごとの実行形 | implementer とオーケストレーターが承認済みコマンドを実行する形を定める | 下の「C2 の定義」のとおり。task0001 の deny 時の案内、task0002 の指示、task0003 の説明はすべてこの定義に従う | task0001, task0002, task0003 |

### C1 の定義（FR1・FR2・FR3）

対象: hook に渡されたコマンド文字列（前後の空白を取り除いたもの）と、hook 入力の cwd。

構文条件（すべて満たすとき「cd 前置形」と呼ぶ）:

1. 文字列は `cd` で始まり、1 つ以上のスペースまたはタブを挟んで、二重引用符で囲んだパス P が 1 つだけ続く。`cd` にオプションは付かず、パス引数は 1 つ。
2. P は `/` で始まる絶対パスで、空ではなく、`"`・`$`・バッククォート・バックスラッシュ・改行を含まない。
3. 閉じ引用符の直後から最初の `&&` までは、スペースまたはタブだけ（0 個でもよい）。改行やそれ以外の文字があれば構文条件を満たさない。
4. 残り = その最初の `&&` より後ろ全体。残りの前後の空白は取り除いて比べる。

パス条件:

5. メイン作業ツリー = hook の cwd から求めた git common dir の親ディレクトリ。git common dir を求められないときは、パス条件を満たさないものとする。
6. P の realpath が存在するディレクトリで、「メイン作業ツリー直下の `.claude/worktrees/em-workflow` の realpath」より深い場所にある。比較はパスの区切りごとの要素で行い、文字列の前方一致では比べない。基準の場所そのものは含めない。
7. P は realpath で解決するだけで、P を作業ディレクトリや引数にして git などの子プロセスを起動しない。

承認条件:

8. 残りが、project_key(cwd) の承認済み文字列のどれかと完全一致する。

判定順:

- 構文条件・パス条件・承認条件をすべて満たすコマンドを「C1 の候補」とする。C1 の候補は workflow に関係するコマンドとして扱う。
- C1 の候補には、まずコマンド全体に禁止パターンの判定を当て、一致したら deny（既存の禁止パターンの理由文）。一致しなければ allow。
- C1 の候補でないコマンドは、変更前とまったく同じ流れで判定する（文字列全体が承認済み → allow、workflow.yaml に宣言済みで未承認 → deny、それ以外 → 判定なし）。新しく deny を返す条件は足さない。
- 承認文字列そのものが `cd` や `&&` を含む場合も、承認条件は残り全体の完全一致だけで判定する。構文条件の「cd は 1 つ」は前置部（先頭から最初の `&&` まで）についての条件である。

### C2 の定義（FR4〜FR7）

| 役割 | 実行形 | cwd |
|------|--------|-----|
| implementer（サブエージェント） | テスト・ビルド・フォーマット・merge_script を `cd "{worktree_path}" && <コマンド>` の 1 回の Bash 呼び出しで実行する。git の操作は `git -C "{worktree_path}"` を使う | Bash の呼び出し間で残らない |
| オーケストレーター（メインセッション） | 単独の `cd` で移動してから承認文字列をそのまま実行し、実行後に単独の `cd` でプロジェクトルートへ戻る（変更しない） | Bash の呼び出し間で残る |

- どちらの役割でも、環境変数の代入を前置するなど、承認文字列そのものを変形しない。implementer に許される前置は同じ呼び出し内の `cd "{worktree_path}" && ` だけ。
- 文書と hook の案内では、implementer の形を `cd "{worktree_path}" && <承認文字列>`（または `<コマンド>`）と表記する。
- AskUserQuestion を持たないサブエージェントは、deny された後に再試行せず notes で報告する（変更しない）。

## Conventions

- **テスト**: 標準ライブラリの unittest だけを使う。リポジトリルートはテストモジュール自身のパスから求める。各タスクは自分のテストを新しいファイルに書き、タスク間で同じテストファイルを編集しない（task0002 が既存の固定文字列を直す 1 ファイルを除く）。
- **hook のテスト**: hook を subprocess で起動し、hook 入力の JSON を標準入力で渡す。承認ストアは `EM_WORKFLOW_APPROVALS` で一時ファイルに分け、一時的な git リポジトリを使う。実行環境の `CLAUDE_PROJECT_DIR` が実リポジトリの workflow.yaml を読ませないよう、subprocess の環境では取り除くか一時リポジトリを指す。
- **文書契約テスト**: 文言は見出しと安定した語句で探し、行番号に頼らない。空白（改行の折り返しを含む）は 1 つのスペースに正規化して比べる。比べる範囲は見出しから、同じかそれより上の階層の次の見出しまで。
- **文書の言語**: 各文書の既存の言語を保つ（エージェント定義・スキル・command-execution-protocol.md・workflow-schema.md は英語、README.md は日本語）。
- **AskUserQuestion の出現数**: `em-workflow/references/` と `em-workflow/skills/` の文書に `AskUserQuestion` の語を新しく書き足さない（`tests/test_muse_consent_no_new_questions.py` がファイルごとの出現数の上限を固定している）。
- **version**: プラグインの version（plugin.json、marketplace.json）はどのタスクでも扱わない（NFR7）。

## Cross-task Design Decisions

### D1: 実行形を役割で分ける

- 決定: implementer は連結形の 1 呼び出し、オーケストレーターは単独 `cd` のまま（C2）。
- 理由: サブエージェントでは単独の `cd` が次の呼び出しに残らない。メインセッションでは `cd … &&` の移動が残る。
- 影響: task0001（deny 時の案内）、task0002、task0003。

### D2: 許可は hook の構文判定で行い、承認ストアは変えない

- 決定: 承認ストアには今までどおり承認文字列だけを記録し、cd 前置形の文字列は記録しない。cd 前置形は hook が C1 で分解して判定する。
- 理由: worktree のパスはタスクごとに変わる。承認はパスに依存しない文字列のまま保つ。
- 影響: task0001、task0003（説明）。

### D3: 「cd は 1 つ」は前置部についての条件とする

- 決定: C1 の構文条件は前置部だけに当てる。承認文字列そのものに `cd` が含まれていても、残り全体が完全一致すれば allow する。
- 理由: 承認文字列はユーザーが承認した文字列そのもので、FR1 (f) の完全一致で判定する。前置部に 2 つ目の `cd` を足した形は、残りが承認文字列と一致しないため allow にならない。
- 影響: task0001（判定とテスト）、task0002・task0003（「コマンド全体で cd は 1 つ」と書かない）。

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 文書に `AskUserQuestion` を書き足して、出現数を固定したテストが落ちる | 中 | 中 | Conventions のとおり書き足さない。task0002・task0003 の受け入れ条件で全テストの通過を確かめる |
| SKILL.md の gate 節に `byte` などの語を書き足して NFR6 の固定が落ちる | 中 | 中 | task0002 の受け入れ条件で、gate 節の語の制約を確かめる |
| bash_guard.py の実行コードに部分文字列 `status` が入り、hook 分類テストが落ちる | 低 | 中 | task0001 の受け入れ条件で、`tests/test_hook_classification_pin.py` の通過を確かめる |
| hook のテストが実行環境の `CLAUDE_PROJECT_DIR` や実在の承認ストアの影響を受ける | 中 | 中 | Conventions の hook のテストの決まりに従う |
| worktree_path に `$` などの C1 で許さない文字が入り、implementer の実行が allow にならない | 低 | 低 | 対応しない。C1 の対象外は変更前の判定（多くは判定なし）になり、通常の permission フローに戻る |

## Open Questions

- [ ] `.claude/rules/hook-tests.md` に bash_guard のテスト実行コマンドの節を足すかは SPEC の範囲外。今回は足さない。
- [ ] D3（承認文字列そのものに `cd` が含まれる場合も残り全体の完全一致で allow）は SPEC の FR1 (c) の読み方を決めたもの。
