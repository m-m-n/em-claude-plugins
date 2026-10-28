---
title: "implementer-cd-verbatim-conflict"
created_date: 2026-10-28
status: draft
---

# implementer-cd-verbatim-conflict - 要件定義書

## 1. 概要

### 1.1 背景
「承認文字列を一字一句そのまま実行する」規則と、「サブエージェントでは単独 `cd` が次の呼び出しに残らない」事実が食い違っている。

### 1.2 目的
- implementer（サブエージェント）が、承認済みの workflow.yaml コマンドを、文字列を変えずに自分の担当 worktree で、1 回の Bash 呼び出しで実行できるようにする。
- 「承認文字列を一字一句そのまま実行する」規則と、「サブエージェントでは単独 `cd` が次の呼び出しに残らない」事実の食い違いをなくす。

### 1.3 スコープ
- `em-workflow/hooks/bash_guard.py` の判定と、deny 時の additionalContext
- `em-workflow/agents/implementer.md`
- `em-workflow/skills/worktree-task-workflow/SKILL.md`
- `em-workflow/references/command-execution-protocol.md`
- `em-workflow/README.md`、`em-workflow/references/workflow-schema.md`
- bash_guard のテストと、`tests/test_worktree_skill_instruction_source.py` の期待文字列

対象外:
- オーケストレーターの単独 `cd` 規則（command-execution-protocol.md、develop/SKILL.md の verify、implement-phase.md の起動前のルート復帰）
- `em-workflow/hooks/queue_launch_guard.py`、`em-workflow/scripts/merge-task.sh`、`em-workflow/hooks/hooks.json`
- プラグインの version

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 の 2 点。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| implementer（サブエージェント） | 承認済みの workflow.yaml コマンドを担当 worktree で実行する |
| オーケストレーター | 単独 `cd` で移動してから承認文字列を実行する（規則は変えない） |

### 2.3 期待される効果
- implementer が承認文字列を変えずに、`cd "{worktree_path}" && <承認文字列>` の 1 回の Bash 呼び出しで実行できる。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 担当 worktree で承認済みコマンドを実行する | implementer | 高 |

### 3.2 ユースケース詳細

#### UC01: 担当 worktree で承認済みコマンドを実行する

**アクター**: implementer

**事前条件**:
- 実行するコマンドが project_key(cwd) の承認ストアに承認済みとして記録されている。
- 担当 worktree がメイン作業ツリー直下の `.claude/worktrees/em-workflow/` より深いところにある。

**基本フロー**:
1. implementer が `cd "{worktree_path}" && <承認文字列>` を 1 回の Bash 呼び出しで実行する。
2. bash_guard が禁止パターンの判定をコマンド全体に当てる。
3. bash_guard が FR1 の条件を判定し、allow を返す。

**代替フロー**:
- 禁止パターンに一致した場合は、承認の有無に関係なく deny になる。
- FR1 の条件を 1 つでも満たさない場合は、文字列全体に今の判定表を当てる。
- 未承認で deny された場合、implementer は再試行せず notes で報告する。

**事後条件**:
- 承認文字列が担当 worktree で実行されている。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | bash_guard: worktree への cd 前置形の許可 | 条件を満たす `cd "<P>" && <残り>` に allow を返す | 高 |
| FR2 | 禁止パターンの判定が先 | FR1 より先に禁止パターンを判定する | 高 |
| FR3 | 条件を満たさない形は今の判定のまま | FR1 を満たさない形には今の判定表を当てる | 高 |
| FR4 | implementer.md の指示を連結形に戻す | Step 3 と Step 6 を連結形の指示にする | 高 |
| FR5 | worktree-task-workflow/SKILL.md の指示を連結形に戻す | merge-task.sh contract 節と Command execution gate 節を連結形にする | 高 |
| FR6 | command-execution-protocol.md に例外を書き足す | FR1 の形を implementer 用の例外として書き足す | 高 |
| FR7 | bash_guard の deny 時 additionalContext を書き分ける | オーケストレーター向けと implementer 向けの案内を分ける | 中 |
| FR8 | README.md と workflow-schema.md の説明 | hook の説明に cd 前置の例外を書き足す | 中 |
| FR9 | bash_guard のテストケース | 許可ケースと許可しないケースを足す | 高 |

### 4.2 機能詳細

#### FR1: bash_guard: worktree への cd 前置形の許可

**説明**: `em-workflow/hooks/bash_guard.py` の hook は、次をすべて満たすコマンドに allow を返す。

- (a) コマンドが `cd "<P>" && <残り>` の形になっている。
- (b) `<P>` は二重引用符で囲んだ絶対パス 1 つで、中に `"`、`$`、バッククォート、バックスラッシュ、改行を含まない。
- (c) `cd` は先頭の 1 つだけで、`cd` にオプション（`-P`、`--` など）は付かない。
- (d) 閉じ引用符と最初の `&&` の間には空白しか無い。
- (e) `realpath(<P>)` が存在するディレクトリで、メイン作業ツリー直下の `.claude/worktrees/em-workflow/` を realpath で解決した場所より深いところにある。その場所そのものは含めない。メイン作業ツリーは、hook の cwd から求めた git common dir の親とする。
- (f) `<残り>` をトリムした文字列が、project_key(cwd) の承認済み文字列のどれかと完全一致する。

分割には `cd` のパス引数の直後にある最初の `&&` を使い、その後ろ全体を `<残り>` とする。

**ビジネスルール**:
- 承認文字列の中に `&&` が含まれていてもよい。
- 承認文字列が自分で環境変数の代入から始まる場合は、`<残り>` としてそのまま一致する。

#### FR2: 禁止パターンの判定が先

**説明**: FR1 の判定より先に、コマンド全体に禁止パターンの判定を当てる。一致したら、承認の有無に関係なく deny する。

#### FR3: 条件を満たさない形は今の判定のまま

**説明**: FR1 の条件を 1 つでも満たさないコマンドは、文字列全体に今の判定表を当てる。

| 状態 | 判定 |
|------|------|
| 承認済みと完全一致 | allow |
| workflow.yaml にあって未承認 | deny |
| それ以外 | 判定なし |

**ビジネスルール**:
- 新しく deny を返す条件は足さない。
- `cd` を前置しないコマンドの判定は変えない。

#### FR4: implementer.md の指示を連結形に戻す

**説明**: `em-workflow/agents/implementer.md` の Step 3 と Step 6 を次のようにする。

- テスト・ビルド・フォーマット・merge_script を `cd "{worktree_path}" && <コマンド>` の 1 回の Bash 呼び出しで実行するよう指示する。
- 「cwd は Bash の呼び出し間で残らない」と書く。
- 単独の `cd` 呼び出しと、`&&` で繋がない指示は削る。
- git の操作は今のまま `git -C "{worktree_path}"` を使う。

#### FR5: worktree-task-workflow/SKILL.md の指示を連結形に戻す

**説明**: `em-workflow/skills/worktree-task-workflow/SKILL.md` の merge-task.sh contract 節と Command execution gate 節を、FR4 と同じ形（`cd "{worktree_path}" && <コマンド>` の 1 呼び出し、cwd は呼び出し間で残らない）にする。

**ビジネスルール**:
- 環境変数の前置禁止と、コマンド文字列そのものを変えない規則は残す。
- gate 節で固定されている文「Never prefix `cd …` or environment assignments」は新しい規則に合わせて書き換え、`tests/test_worktree_skill_instruction_source.py` の期待文字列も同じ変更で合わせる。

#### FR6: command-execution-protocol.md に例外を書き足す

**説明**: `em-workflow/references/command-execution-protocol.md` の Verbatim execution rule と hook の判定表（Runtime enforcement）に、FR1 の形を implementer 用の例外として書き足す。

**ビジネスルール**:
- オーケストレーターの規則（単独 `cd` で移動し、実行後に単独 `cd` でルートへ戻る）は変えない。

#### FR7: bash_guard の deny 時 additionalContext を書き分ける

**説明**: bash_guard.py が未承認コマンドを deny するときの additionalContext を書き分ける。

- オーケストレーターには、単独の `cd` で移動してから承認文字列をそのまま実行するよう案内する。
- implementer には、`cd "{worktree_path}" && <承認文字列>` の形を案内する。
- AskUserQuestion を持たないサブエージェントが、deny された後に再試行せず notes で報告する指示は残す。

#### FR8: README.md と workflow-schema.md の説明

**説明**: `em-workflow/README.md` の 118 行と `em-workflow/references/workflow-schema.md` の 305-306 行にある hook の説明（承認済み文字列と完全一致 → allow）に、FR1 の cd 前置の例外を書き足す。

#### FR9: bash_guard のテストケース

**説明**: bash_guard の hook テストに、許可ケース（FR1 の形）と、許可しないケースを足す。

許可しないケース:
- worktree の外への `cd`
- `cd` が複数
- `;` や `|` の混在
- 残りの不一致
- 引用なしや一重引用のパス
- `..` やシンボリックリンクによる外への移動
- worktrees ディレクトリそのものへの `cd`
- 禁止パターンを含む残り

**ビジネスルール**:
- テストは hook を subprocess で起動して JSON を渡す。
- `EM_WORKFLOW_APPROVALS` で承認ストアを分ける。
- 一時的な git リポジトリを使う。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし。

### 5.2 セキュリティ要件
- NFR1 決定的な判定: 判定は LLM を使わず、コードで決定的に行う。bash_guard.py は Python 標準ライブラリだけを使う。
- NFR2 許可範囲を広げすぎない: 新しく allow するのは FR1 の形だけ。workflow に無関係な Bash コマンドには、今までどおり判定を出さない。

### 5.3 可用性要件
該当なし。

### 5.4 保守性要件
- NFR3 hook 分類テストの前提を守る: bash_guard.py のコメントと docstring を除く実行コードに、部分文字列 `"status"` を足さない（`tests/test_hook_classification_pin.py`）。
- NFR4 hash 固定ファイルを変えない: `em-workflow/hooks/queue_launch_guard.py` と `em-workflow/scripts/merge-task.sh` はバイト単位で変えない。
- NFR5 hook の登録と順序を変えない: `em-workflow/hooks/hooks.json` の登録内容と順序は変えない。
- NFR6 SKILL の gate 節の文言の制約: worktree-task-workflow/SKILL.md の Command execution gate 節では、`(byte-for-byte)` をちょうど 1 回だけにし、ほかに `byte`、`identical to`、`equal to the line` を書かない。`tests/test_worktree_skill_instruction_source.py` の、承認規則とデコード値についての既存の固定は残す。
- NFR8 テストの実行方法: テストは標準ライブラリの unittest だけを使い、`python3 -m unittest discover -s tests` がすべて通る。

### 5.5 互換性要件
- NFR7 version を変えない: プラグインの version は変えない。

## 6. UI/UX要件

該当なし。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約
- NFR1、NFR3、NFR4、NFR5、NFR6、NFR8 のとおり。

### 9.2 ビジネス上の制約
- NFR7 のとおり。

### 9.3 スケジュール制約
- なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/implementer-cd-verbatim-conflict/**`
- `test-docs/implementer-cd-verbatim-conflict/**`

`feature-docs/implementer-cd-verbatim-conflict/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/implementer-cd-verbatim-conflict/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/implementer-cd-verbatim-conflict/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/implementer-cd-verbatim-conflict/` ディレクトリを生成しないが、宣言された `test-docs/implementer-cd-verbatim-conflict/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR1）: X が承認済みで、P がメイン作業ツリーの `.claude/worktrees/em-workflow/` より深いところにある既存ディレクトリのとき、`cd "P" && X` は allow になる。
- [ ] AC-2（FR1）: 承認文字列が `CARGO_TARGET_DIR=src-tauri/target cargo test --manifest-path src-tauri/Cargo.toml --lib` のとき、`cd "<worktree>" && ` にこの文字列を続けたものは allow になる。
- [ ] AC-3（FR1）: 承認文字列に `&&` を含むもの（例: `a && b`）について、`cd "<worktree>" && a && b` は allow になる。
- [ ] AC-4（FR1）: hook の cwd が integration worktree やタスク worktree の中にあっても、AC-1 の判定は同じになる。
- [ ] AC-5（FR1、FR3）: 次の形は allow にならず、変更前と同じ判定になる。worktree の外への `cd`、別リポジトリの worktrees 配下への `cd`、`..` やシンボリックリンクで外へ出る `cd`、worktrees ディレクトリそのものへの `cd`、`cd` が 2 つ、`cd` と `&&` の間に `;` や `|` がある形、引用なしや一重引用のパス、パスに `$` やバッククォートを含む形、残りが承認文字列と一致しない形。
- [ ] AC-6（FR2）: 残りが禁止パターンを含むなら、承認済みでも deny になる。
- [ ] AC-7（FR3）: `cd` を前置しないコマンドの判定は、どれも変更前と同じ（承認済み → allow、宣言済みで未承認 → deny、それ以外 → 判定なし）。
- [ ] AC-8（FR4、FR5）: implementer.md と worktree-task-workflow/SKILL.md は、テスト・ビルド・フォーマット・merge_script を `cd "{worktree_path}" && <コマンド>` の 1 呼び出しで実行するよう指示し、「cwd は呼び出し間で残らない」と書いている。単独の `cd` 呼び出しを求める文と、`&&` で繋ぐことを禁じる文は残っていない。環境変数の前置禁止は残っている。
- [ ] AC-9（FR6）: command-execution-protocol.md の Verbatim execution rule と判定表に implementer の例外がある。オーケストレーターの「単独 `cd` で移動し、実行後に単独 `cd` でルートへ戻る」規則も残っている。
- [ ] AC-10（FR7）: bash_guard の deny 時 additionalContext は、オーケストレーター向けの単独 `cd` の案内と、implementer 向けの `cd "{worktree_path}" &&` の案内を分けて書いている。再試行せず notes で報告する指示も残っている。
- [ ] AC-11（FR8）: README.md と workflow-schema.md の hook の説明に、cd 前置の例外が書いてある。
- [ ] AC-12（FR5、NFR3、NFR4、NFR5、NFR6、NFR8）: `python3 -m unittest discover -s tests` が通る。queue_launch_guard.py と merge-task.sh の hash 固定テスト、hook の分類テスト、hooks.json の登録テストもそのまま通る。

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系 TS-1（AC-1、AC-2、AC-3）: 一時 git リポジトリに `.claude/worktrees/em-workflow/f/t` を作り、承認ストアに X を記録する。`cd "<絶対パス>" && X` を hook に渡す。期待: permissionDecision が allow。
- [ ] 正常系 TS-2（AC-4）: TS-1 と同じ内容で、hook 入力の cwd を worktree（`git worktree add` で作ったもの）にする。期待: allow。
- [ ] 異常系 TS-3（AC-5）: AC-5 に挙げた形を 1 ケースずつ hook に渡す。期待: allow にならない。判定は変更前の判定表と同じ（多くは出力なし）。
- [ ] セキュリティ TS-4（AC-6）: 禁止パターンを含む文字列を承認ストアに直接書いた状態で、`cd "<worktree>" && <その文字列>` を渡す。期待: deny。
- [ ] 回帰 TS-5（AC-7）: `cd` を前置しない承認済みコマンド、宣言済みで未承認のコマンド、無関係なコマンドを渡す。期待: それぞれ allow / deny / 出力なし。
- [ ] 文書契約 TS-6（AC-8、AC-9、AC-10、AC-11）: 対象の文書と bash_guard.py の文言を読み、必要な文があり、消すべき文が無いことを確かめる。期待: すべて合格。
- [ ] 全体 TS-7（AC-12）: `python3 -m unittest discover -s tests` を実行する。期待: 失敗 0。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| メイン作業ツリー | hook の cwd から求めた git common dir の親 |
| 承認文字列 | project_key(cwd) の承認ストアに承認済みとして記録された文字列 |
| `<残り>` | `cd` のパス引数の直後にある最初の `&&` より後ろ全体 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] requirement.nonconforming-cd-form: keep_existing（条件を満たさない cd 前置形は、今の判定のまま扱う。allow しないだけ）
- [x] requirement.worktree-root-basis: main_tree_realpath（worktree 配下かどうかは、メイン作業ツリー（git common dir の親）を基準に、realpath で判定する）
- [x] requirement.cd-path-notation: double_quoted_only（許可の対象にする書き方は `cd "<絶対パス>"` だけ）
- [x] requirement.pinned-skill-sentence: update_pin（SKILL の固定文言と、それを固定しているテストの期待文字列は、同じ変更で直す）
- [x] requirement.doc-scope: include_all（bash_guard の deny メッセージ、README.md、workflow-schema.md も今回直す）
- [x] design-step.recommendation: decide_autonomously（デザインステップは行わない）

前提:

| ID | 内容 | 出典 |
|----|------|------|
| A1 | 条件を満たさない cd 前置形は、今の判定のまま扱う（allow しないだけ）。 | batch |
| A2 | worktree 配下かどうかは、メイン作業ツリー（git common dir の親）を基準に、realpath で判定する。 | batch |
| A3 | 許可の対象にする書き方は `cd "<絶対パス>"` だけ。 | batch |
| A4 | SKILL の固定文言と、それを固定しているテストの期待文字列は、同じ変更で直す。 | batch |
| A5 | bash_guard の deny メッセージ、README.md、workflow-schema.md も今回直す。 | batch |
| A6 | デザインステップは行わない。 | batch |
| A7 | オーケストレーターの単独 `cd` 規則（command-execution-protocol.md、develop/SKILL.md の verify、implement-phase.md の起動前のルート復帰）は変えない。 | task_description |
| A8 | queue_launch_guard.py と merge-task.sh はバイト単位で変えない。 | existing_test（`tests/test_merge_unverified_exit_doc_contract.py`） |
| A9 | 環境変数を前置して承認文字列を変えることは、引き続き禁止する。承認文字列が自分で環境変数の代入から始まる場合は、残りとしてそのまま一致する。 | task_description |
| A10 | 承認文字列の中に `&&` が含まれていてもよい。`cd` のパス引数の直後にある最初の `&&` で分割する。 | existing_doc（command-execution-protocol.md） |

### 14.2 未確認・保留事項
- なし。

## 15. 参考資料

- `em-workflow/references/command-execution-protocol.md`
- `em-workflow/hooks/bash_guard.py`
