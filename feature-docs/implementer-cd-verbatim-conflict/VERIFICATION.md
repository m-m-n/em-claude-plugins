# Verification Document: implementer-cd-verbatim-conflict

## Overview
**Feature**: implementer-cd-verbatim-conflict / **SPEC.md**: `feature-docs/implementer-cd-verbatim-conflict/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/implementer-cd-verbatim-conflict/IMPLEMENTATION.md`

統合ブランチ（`em-workflow/implementer-cd-verbatim-conflict/integration`）の作業ツリーのルートで実行する。

## Build Verification
- Command: 該当なし（`project.components.main.build_command` が空）
- Expected: -

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: 終了コード 0、失敗 0・エラー 0
- Coverage target: 計測しない（標準ライブラリの unittest だけを使う、NFR8）

個別に確かめるときのモジュール（いずれも上のコマンドに含まれる）:

- `tests/test_bash_guard_cd_prefix.py`（task0001）
- `tests/test_implementer_cd_chain_docs.py`、`tests/test_worktree_skill_instruction_source.py`（task0002）
- `tests/test_cd_prefix_exception_docs.py`（task0003）
- 既存の固定: `tests/test_hook_classification_pin.py`、`tests/test_merge_unverified_exit_doc_contract.py`、`tests/test_hooks_registration.py`、`tests/test_guardrail_hooks_migration.py`、`tests/test_muse_consent_no_new_questions.py`、`tests/test_implementer_tests_yaml_record_contract.py`

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | （AC-1、AC-2、AC-3）一時 git リポジトリに `.claude/worktrees/em-workflow/f/t` を作り、承認ストアに X を記録する。`cd "<絶対パス>" && X` を hook に渡す。X が環境変数の代入で始まる場合、X が `&&` を含む場合も渡す | permissionDecision が allow | Unit |
| TS-2 | （AC-4）TS-1 と同じ内容で、hook 入力の cwd を git の worktree 追加で作った worktree の中にする | allow | Unit |
| TS-3 | （AC-5）AC-5 に挙げた形を 1 ケースずつ hook に渡す。worktree の外、別リポジトリの worktrees 配下、`..` やシンボリックリンクで外へ出る形、worktrees ディレクトリそのもの、名前が前方一致する兄弟ディレクトリ、`cd` が 2 つ、`cd` と `&&` の間にセミコロンやパイプがある形、引用なしや一重引用のパス、パスに `$` やバッククォートを含む形、残りが承認文字列と一致しない形 | allow にならない。判定は変更前の判定表と同じ（出力なし） | Unit |
| TS-4 | （AC-6）禁止パターンを含む文字列を承認ストアに直接書いた状態で、`cd "<worktree>" && <その文字列>` を渡す | deny（禁止パターンの理由） | Unit |
| TS-5 | （AC-7）`cd` を前置しない承認済みコマンド、宣言済みで未承認のコマンド、無関係なコマンドを渡す。`cd "<worktree>" && <宣言済みで未承認の文字列>` も渡す | それぞれ allow / deny / 出力なし。cd 前置形は出力なし | Unit |
| TS-6 | （AC-8、AC-9、AC-10、AC-11）implementer.md、worktree-task-workflow/SKILL.md、command-execution-protocol.md、README.md、workflow-schema.md の文言を読み、必要な文があり、消すべき文が無いことを確かめる。bash_guard の未承認 deny 時の additionalContext は hook を起動して確かめる | すべて合格 | Unit |
| TS-7 | （AC-12）`python3 -m unittest discover -s tests` を実行する。queue_launch_guard.py と merge-task.sh の hash 固定テスト、hook の分類テスト、hooks.json の登録テスト、SKILL の固定文言のテスト、AskUserQuestion の出現数のテストを含む | 失敗 0 | Integration |
| TS-8 | （NFR1）bash_guard.py が import するモジュールを AST で集め、標準ライブラリに含まれることを確かめる | 標準ライブラリ以外の import が 0 | Unit |
| TS-9 | （NFR4、NFR5、NFR7）実装フェーズの base_commit から統合ブランチの HEAD までの差分に、変更しないファイルが含まれないことを git diff で確かめる。対象: `em-workflow/hooks/queue_launch_guard.py`、`em-workflow/scripts/merge-task.sh`、`em-workflow/hooks/hooks.json`、各プラグインの `.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json` | 対象ファイルの差分なし | Integration |

## Code Quality Verification
- Format: 該当なし（`project.components.main.format_command` が空）
- Static analysis: 該当なし

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | 下の Functional Requirements Coverage の各行のテストが合格する |
| SC-2 | All test scenarios pass | TS-1〜TS-9 がすべて合格する |
| SC-3 | Security requirements are satisfied | Performance / Security Verification の NFR2 と TM-1〜TM-3 の確認が合格する |
| SC-4 | Documentation is complete | TS-6 が合格する（AC-8〜AC-11） |
| SC-5 | Code review is completed | workflow.yaml の review が completed で、residual_critical_high が 0 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1、TS-2、TS-3 |
| FR2 | task0001 | TS-4 |
| FR3 | task0001 | TS-3、TS-5 |
| FR4 | task0002 | TS-6 |
| FR5 | task0002 | TS-6、TS-7 |
| FR6 | task0003 | TS-6 |
| FR7 | task0001 | TS-6 |
| FR8 | task0003 | TS-6 |
| FR9 | task0001 | TS-1、TS-2、TS-3、TS-4、TS-5 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-3、TS-5 |
| NFR3 | task0001 | TS-7（`tests/test_hook_classification_pin.py`） |
| NFR4 | task0001, task0002 | TS-7（`tests/test_merge_unverified_exit_doc_contract.py`）、TS-9 |
| NFR5 | task0001 | TS-7（`tests/test_hooks_registration.py`、`tests/test_guardrail_hooks_migration.py`）、TS-9 |
| NFR6 | task0002 | TS-7（`tests/test_worktree_skill_instruction_source.py`） |
| NFR7 | task0001, task0002, task0003 | TS-9 |
| NFR8 | task0001, task0002, task0003 | TS-7 |

## Manual Testing (E2E Not Possible)
- なし

## Performance / Security Verification (if applicable)
- NFR2: 新しく allow するのは C1 の形だけ — TS-3 と TS-5 で、C1 の対象外の形と cd を前置しないコマンドの判定が変更前と同じことを確かめる
- TM-1: 前置部の構文条件と残りの完全一致を満たさない形を C1 の対象外にする — TS-3 の構文のケース（引用なし・一重引用・相対パス・`$`・バッククォート・バックスラッシュ・改行・オプション・パス引数 2 つ・セミコロンやパイプの混在・残りの後ろへの追加・残りの一部だけ・空の残り）がすべて allow にならず出力なしになる
- TM-2: worktree 領域の判定を realpath とパスの要素ごとの比較で行う — TS-3 のパスのケース（領域の外・別リポジトリ・`..`・シンボリックリンク・worktrees ディレクトリそのもの・前方一致する兄弟ディレクトリ・存在しないパス）がすべて allow にならず出力なしになる。TS-2 で、hook の cwd が worktree の中でも同じ判定になる
- TM-3: C1 の候補にも禁止パターンの判定を先に当てる — TS-4 で、禁止パターンを含む承認済み文字列の cd 前置形が deny になる

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 9 | 9 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 5 | 5 | 0 | 0 |
| Security (NFR2, TM-1〜TM-3) | 4 | 4 | 0 | 0 |
