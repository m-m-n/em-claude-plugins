# Verification Document: codex-guard-assignment-paren-head

## Overview
**Feature**: codex-guard-assignment-paren-head / **SPEC.md**: `feature-docs/codex-guard-assignment-paren-head/SPEC.md` / **IMPLEMENTATION.md**: なし（reduced tier で、タスクが 1 つのため作らない）

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）が、配列代入の後に改行を挟んで続くグループの中の対話起動を deny し、関数定義の本体は判定しないことを、統合後のブランチで確かめる。

## Build Verification
- Command: なし（`repo-tests` / `plugin-invariants` とも `build_command` が空）
- Expected: —

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (この hook のテスト): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0、失敗・エラーなし
- Coverage target: 定めない

### Test Scenarios from SPEC.md

コマンドは Python の文字列リテラルで表す（`\n` は改行）。TS-1〜TS-11 は `CASES` のケースとして、両コピーに対して判定する。

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `"a=()\n(python3 -i)"` | deny | Unit |
| TS-2 | `"a+=()\n(python3 -i)"` | deny | Unit |
| TS-3 | `"export a=()\n(python3 -i)"` | deny | Unit |
| TS-4 | `"a=()\n\n(python3)"` | deny | Unit |
| TS-5 | `"a=()\n# c\n(python3 -i)"` | deny | Unit |
| TS-6 | `"a=()\n{ python3 -i; }"` | deny | Unit |
| TS-7 | `"a=() ; (python3 -i)"` | deny | Unit |
| TS-8 | `"foo()\n(python3 -i)"` | silent | Unit |
| TS-9 | `"f() (python3 -i)"` | silent | Unit |
| TS-10 | `"function f() { python3; }"` | silent | Unit |
| TS-11 | `"f() { python3; }"`（既存ケース） | silent | Unit |
| TS-12 | `python3 -m unittest tests.test_codex_hook_interactive_guard` を実行する | 通る。`CASES` に TS-1〜TS-10 のコマンドが期待する判定で入り、`test_cases_are_unique` も通る | Integration |
| TS-13 | `python3 -m unittest discover -s tests` を実行する | 修正前と同じく通る（既存ケースの判定が変わらない） | Integration |
| TS-14 | `TestCopies.test_the_two_copies_are_byte_identical` | 通る（両コピーがバイト単位で同一） | Unit |
| TS-15 | `TestStaticConstraints` と `TestFailOpen` | 通る（標準ライブラリだけを使い、判定できない入力では何も出力しない） | Unit |
| TS-16 | `TestGuardDocumentation` | 通る。既存マーカーが残り、FR1 の条件を述べる docstring の記述を指すマーカーが加わっている | Unit |

## Code Quality Verification
- Format: なし（`format_command` が空）
- Static analysis: なし
- Plugin invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .` が exit code 0 で終わる

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `{"tool_input": {"command": "a=()\n(python3 -i)"}}` を両コピーの標準入力に渡すと deny が出力される | TS-1 |
| AC-2 | FR2 の全コマンドで両コピーが deny を出力する | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 |
| AC-3 | FR3 の全コマンドで両コピーが何も出力しない | TS-8, TS-9, TS-10, TS-11 |
| AC-4 | `a=() ; (python3 -i)` で両コピーが deny を出力する | TS-7 |
| AC-5 | `CASES` に `a=()` / `a+=()` + 改行 + `(python3 -i)` が deny として含まれ、`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る | TS-12 |
| AC-6 | `TestCopies.test_the_two_copies_are_byte_identical` が通る | TS-14 |
| AC-7 | `python3 -m unittest discover -s tests` が修正前と同じく通る | TS-13 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-8, TS-9, TS-10, TS-11 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 |
| FR3 | task0001 | TS-8, TS-9, TS-10, TS-11 |
| FR4 | task0001 | TS-7 |
| FR5 | task0001 | TS-12, TS-14 |
| FR6 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10, TS-12 |
| NFR1 | task0001 | TS-13, TS-15 |
| NFR2 | task0001 | TS-13, TS-16 |

## E2E Testing

なし（E2E の仕組みが無い）

## Manual Testing (E2E Not Possible)

なし（再現手順は TS-1 が両コピーを別プロセスとして起動し、標準入力に JSON を渡して自動で確かめる）

## Performance / Security Verification (if applicable)

- TM-1: `(` の直前が FR1 の 2 つの形のときだけ関数名ありとみなし、配列代入の後に続くグループを判定する（両コピー） — TS-1〜TS-6 で両コピーが deny、TS-8〜TS-11 で何も出力しない、TS-7 で deny のまま、TS-14 で両コピーがバイト単位で同一であることで確かめる

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (TS-1〜TS-11, TS-14〜TS-16) | 14 | 14 | 0 | 0 |
| Integration (TS-12, TS-13) | 2 | 2 | 0 | 0 |
| Code Quality (plugin invariants) | 1 | 1 | 0 | 0 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 18 | 18 | 0 | 0 |
