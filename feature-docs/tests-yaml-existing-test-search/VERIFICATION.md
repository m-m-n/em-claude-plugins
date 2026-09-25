# Verification Document: tests-yaml-existing-test-search

## Overview

**Feature**: tests-yaml-existing-test-search / **SPEC.md**: `feature-docs/tests-yaml-existing-test-search/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/tests-yaml-existing-test-search/IMPLEMENTATION.md`

## Build Verification

- Command: なし（workflow.yaml の `build_command` は空）
- Expected: 該当なし

## Test Verification

- Command: `python3 -m unittest discover -s tests`（リポジトリルートで実行）
- Coverage target: 設定しない

### Test Scenarios from SPEC.md

SPEC.md の TS1〜TS5 は本書の TS-1〜TS-5 に対応する。TS-6〜TS-8 は SPEC.md の AC-6 と NFR1 / NFR4 から起こしたシナリオ。

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | 新規モジュール `tests/test_existing_test_search_discipline.py` が tdd-testing/SKILL.md の新設セクションを読み、既存テスト検索の必須化（発動条件の `tests: []` と `red_confirmed: false` の 2 形、リポジトリ相対パスとファイル名の両方での検索、ビルド／lint の AC でも検索が先）の記述を assert する（FR1） | 実文書テストが通る | Unit |
| TS-2 | 同じモジュールが同セクションの、見つかった場合の `tests:` 列挙、red_reason の趣旨（専用モジュールはスコープ外／既存テストが検出する／今回 red は発生しなかった）、red_confirmed は観測した事実のまま、合成フィクスチャのヒットの除外、見つからない場合の従来どおりの記録、の記述を assert する（FR2） | 実文書テストが通る | Unit |
| TS-3 | 同じモジュールが implementer.md の Step 4c 範囲に、スキル名 tdd-testing と新設セクションの見出しの文字列による参照（または同じ規律）があり、参照先の見出しが SKILL.md に見出し行として実在することを assert する（FR3） | 実文書テストが通る | Unit |
| TS-4 | 否定テスト: 規律の要素を欠いた偽サンプルで各マッチャーが失敗し、要素をすべて備えた偽サンプルでは通る。Step 4c のマッチャーは、参照を欠いたサンプルと存在しない見出しを参照するサンプルの両方で失敗する（FR4） | 否定テストが通る | Unit |
| TS-5 | version bump: 既存の `tests/test_spec_file_set_completeness_version_bump.py`（`TestPluginManifestVersion` / `TestMarketplaceEntryVersion`）と `tests/test_plugin_version_parity.py`（`TestMarketplaceEntryVersion`）が通る。tests/ 配下に version 専用の新規テストモジュールが追加されていない（FR5、NFR3） | 既存テストが通る。追加モジュールは TS-1〜TS-4 の 1 本だけ | Unit |
| TS-6 | リポジトリルートで全件実行する（AC-6、NFR2） | 失敗 0 | Integration |
| TS-7 | 既存の `tests/test_check_plugin_invariants.py` の `TestRepositoryLevelInvariant` が実リポジトリに対して通る。implementer.md に `# Task assignment` 見出しが無い（NFR4） | 通る | Integration |
| TS-8 | 新規モジュールが discover で検出され、既存の `tests/test_assumptions_reversible_criterion.py` の `TestStandardLibraryOnlyImports` が通る（標準ライブラリのみ）。ファイル名・クラス名・メソッド名が NFR1 の規約に従う（NFR1） | 検出される。違反なし | Unit |

## Code Quality Verification

- Format: なし（workflow.yaml の `format_command` は空）
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .`（リポジトリルートで実行、終了コード 0。TS-7 と同じ検査を直接実行する）

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | AC-1（FR1）: SKILL.md に既存テスト検索の必須化と、パス・ファイル名の両方での検索が書かれている | TS-1 |
| SC-2 | AC-2（FR2）: SKILL.md に見つかった場合の tests 列挙と red_reason の趣旨が書かれている | TS-2 |
| SC-3 | AC-3（FR3）: implementer.md の Step 4c に同じ規律または tdd-testing の該当規律への明示的な参照がある | TS-3 |
| SC-4 | AC-4（FR4）: 新規モジュールが discover で検出され、AC-1〜AC-3 を assert し、否定テストで規律を欠いた文書を弾く | TS-4、TS-8 |
| SC-5 | AC-5（FR5）: plugin.json と marketplace.json の em-workflow エントリの version がともに 0.2.9。他のフィールドと em-review エントリは不変 | TS-5 に加え、2 ファイルを直接読んで値が 0.2.9 であること、ベースコミットとの差分が 2 ファイルの version の行だけであることを確認する |
| SC-6 | AC-6（NFR2）: 全件実行が失敗 0 | TS-6 |
| SC-7 | 完了の定義「再現手順で現象が起きない」 | 下記 Manual Testing の 1 項目目 |
| SC-8 | 完了の定義「再発を検出するテストがある」 | TS-1〜TS-4 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1、TS-4 |
| FR2 | task0001 | TS-2、TS-4 |
| FR3 | task0001 | TS-3、TS-4 |
| FR4 | task0001 | TS-4、TS-8 |
| FR5 | task0001 | TS-5、SC-5 の直接確認 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-5 |
| NFR4 | task0001 | TS-7 |

## E2E Testing

該当なし（E2E フレームワークなし。workflow.yaml の `e2e_test_command` は空）

## Manual Testing (E2E Not Possible)

- [ ] `test-docs/tests-yaml-existing-test-search/task0001.tests.yaml` の version bump の AC エントリで、`tests` に TS-5 の既存テストクラスが列挙され、`red_reason` が「専用の新規モジュール追加はスコープ外だが、既存の X が Y を検出する。今回の変更では red 状態は発生しなかった」趣旨（または red を実際に観測した事実）になっていることを読んで確かめる。
- [ ] 同じファイルに `tests: []` のエントリがあり、その red_reason が既存テストの不在を述べている場合、tests/ 配下にその変更対象ファイルを読むテストが実際に無いことを、リポジトリ相対パスとファイル名で検索して確かめる。
- [ ] SKILL.md の新設セクションと implementer.md の Step 4c を読み、規律が SPEC.md の FR1 / FR2 の趣旨どおりに読めること（識別語がそろっているだけでなく、文として意味が通ること）を確かめる。

## Performance / Security Verification (if applicable)

- 該当なし

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test Scenarios | 8 | 8 | 0 | 0 |
| Code Quality | 1 | 1 | 0 | 0 |
| Success Criteria | 8 | 7 | 0 | 1 |
| Manual Testing | 3 | 0 | 0 | 3 |
