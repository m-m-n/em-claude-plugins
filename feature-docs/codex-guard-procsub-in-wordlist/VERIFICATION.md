# Verification Document: codex-guard-procsub-in-wordlist

## Overview

**Feature**: codex-guard-procsub-in-wordlist / **SPEC.md**: `feature-docs/codex-guard-procsub-in-wordlist/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-procsub-in-wordlist/IMPLEMENTATION.md`

## Build Verification

- Command: なし（`workflow.yaml` の `project.components.main.build_command` が空）
- Expected: 対象外

## Test Verification

- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- 対象モジュールだけを流すとき: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Coverage target: 計測なし（カバレッジを測るコマンドが設定されていない）。代わりに TS-1〜TS-14 の全行が両コピーで期待する判定になることを条件にする。

### Test Scenarios from SPEC.md

TS-1〜TS-14 は SPEC.md の Test Scenarios の行。コマンドは Python 文字列リテラル表記（`\n` は改行、`\\` は 1 つのバックスラッシュ）で、`tests/test_codex_hook_interactive_guard.py` の CASES の行として両コピーに流す。TS-15〜TS-21 は SPEC.md の Regression Tests と NFR から起こした行。

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | 再現手順 2（拒否漏れ）: `zsh -c 'echo "$(for x (<(: # "\n)) { :; })"; python3 -i'` | 両コピーで deny | Unit |
| TS-2 | 再現手順 3（誤拒否）: `zsh -c 'echo "$(for x (<(printf x # )))"; python3 -i; echo "\n)) { :; })"'` | 両コピーで silent | Unit |
| TS-3 | `>(` の同型: `echo "$(for x (>(: # "\n)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-4 | `=(` の同型: `echo "$(for x (=(: # "\n)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-5 | 空白の後の語の先頭: `echo "$(for x (a <(: # "\n)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-6 | エスケープした `<` の後の `(` は入れ子の w: `echo "$(for x (\\<(b #c)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-7 | 語の途中の `=(` は入れ子の w: `echo "$(for x (a=(b #c)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-8 | 数値範囲 glob `<->` の後の `(` は glob 修飾子: `echo "$(for x (<->(#qN)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-9 | 入れ子の項目の中の `<(` は入れ子の w: `echo "$(for x (a(<(b #c))) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-10 | 引用符で囲んだ `<` の後の `(` は入れ子の w: `echo "$(for x ("<"(b #c)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-11 | 入れ子の項目の中の `=(` は入れ子の w で `#` は語の文字: `echo "$(for x (a(=(: #c))) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-12 | エスケープした空白の後の `=(` は語の途中: `echo "$(for x (a\\ =(b #c)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-13 | 語の途中の継続行の後の `=(` は語の途中: `echo "$(for x (a\\\n=(b #c)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-14 | 空白の後の継続行は語の先頭の状態を保つ: `echo "$(for x (a \\\n<(: # "\n)) { :; })"; python3 -i` | 両コピーで deny | Unit |
| TS-15 | 既存の CASES の deny / silent 行（前のフィーチャーの「置換読み TS-1」「TS-2」「TS-7」を含む） | 行を消さず期待する判定を変えずに、両コピーですべて通る | Unit（回帰） |
| TS-16 | TestNoRecursion と TestSubstitutionSkipCallStructure | 通る | Unit（回帰） |
| TS-17 | TestSubstitutionSkipDocumentation（既存の RULE_MARKERS、WORD_LIST_HASH_MARKERS と、FR4 で足した文の目印） | 両コピーで通る | Unit（回帰） |
| TS-18 | TestCopies.test_the_two_copies_are_byte_identical | 通る | Unit（回帰） |
| TS-19 | 全体のテストコマンド `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` | 終了コード 0 | Integration（回帰） |
| TS-20 | `tests/test_codex_hook_interactive_guard.py` の import | Python 標準ライブラリだけ（テストの枠組みは unittest） | Static |
| TS-21 | base_branch から integration ブランチまでの変更ファイル一覧（`git diff --name-only`） | 各プラグインの `.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` を含まない | Static |

## Code Quality Verification

- Format: なし（`format_command` が空）
- Static analysis: なし
- 2 つのコピーのバイト同一: TS-18

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | 拒否漏れの再現入力が両コピーで deny になる | TS-1 |
| AC2 | 誤拒否の再現入力が両コピーで silent になる | TS-2 |
| AC3 | 最も外側の項目の語の先頭（項目を開く `(` の直後、空白の後、空白と継続行の後）の `<(`・`>(`・`=(` が p として読まれ、中の空白の後の `#` がコメントを始める | TS-1、TS-3、TS-4、TS-5、TS-14 |
| AC4 | 入れ子の項目・語の途中・エスケープや引用符の後の `<(`・`>(`・`=(` は入れ子の w のままで、`#` は語の文字 | TS-6〜TS-11、TS-15 |
| AC5 | 2 つのコピーがバイト単位で同一 | TS-18 |
| AC6 | docstring に新しい読みが書かれ、既存の検査対象の文が残っている | TS-17、Manual Testing の docstring 確認 |
| AC7 | 2 つのテストコマンドが通る | TS-19（対象モジュールだけのコマンドも Test Verification のとおり流す） |
| AC8 | エスケープした空白の後と語の途中の継続行の後の `=(` は入れ子の w のまま | TS-12、TS-13 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1、TS-2、TS-3、TS-4、TS-5、TS-12、TS-13、TS-14 |
| FR2 | task0001 | TS-6、TS-7、TS-8、TS-9、TS-10、TS-11、TS-12、TS-13、TS-15。既知の制限の記録は SPEC.md の Known Limitations で満たす |
| FR3 | task0001 | TS-18 |
| FR4 | task0001 | TS-17、Manual Testing の docstring 確認 |
| FR5 | task0001 | TS-1〜TS-14 |
| NFR1 | task0001 | TS-16 |
| NFR2 | task0001 | TS-20 |
| NFR3 | task0001 | TS-21 |
| NFR4 | task0001 | TS-15、TS-19 |

## Manual Testing (E2E Not Possible)

- [ ] docstring の語一覧 w の段落と、`(` 分岐・w 分岐のコメントを読み、FR4 の 3 点（語の先頭の `<(`・`>(`・`=(` が p を開く、その `)` が語の中の閉じ、語の先頭の決め方）が書かれ、コードの読みと食い違わないこと（TS-17 は目印の文があることだけを見る）
- [ ] workflow.yaml の goal の再現手順 2・3 のとおり、PreToolUse(Bash) の JSON をフックの標準入力に渡し、両コピーで拒否漏れの入力が deny、誤拒否の入力が silent になること（コマンド自体は実行しない）

## Performance / Security Verification

- TM-1: 最も外側の項目の語の先頭にある引用・エスケープの無い `<(`・`>(`・`=(` を p として読み、中のコメントをコメントとして読む — TS-1、TS-3、TS-4、TS-5、TS-14 が両コピーで deny
- TM-2: 語の先頭を読みながら持つ字句状態で決め、それ以外の `(` は入れ子の w のまま読む — TS-6〜TS-13 が両コピーで deny
- TM-3: p の中の空白の後の `#` から改行までをコメントとして読み、中の対話的なコマンドを命令として読まない — TS-2 が両コピーで silent
- TM-4: 語の先頭を定数サイズの状態で判定し、読みを線形・再帰なしに保つ — TS-16 が通る

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| CASES の行（TS-1〜TS-14） | 14 | 14 | 0 | 0 |
| 回帰（TS-15〜TS-19） | 5 | 5 | 0 | 0 |
| Static（TS-20、TS-21） | 2 | 1 | 0 | 1 |
| Security（TM-1〜TM-4） | 4 | 4 | 0 | 0 |
| Manual Testing | 2 | 0 | 0 | 2 |
| 合計 | 27 | 24 | 0 | 3 |
