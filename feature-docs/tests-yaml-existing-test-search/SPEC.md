# Feature: tests-yaml-existing-test-search

## Overview

implementer が `*.tests.yaml` のエントリで既存テストが無いと述べる前に、変更対象ファイルを参照する既存テストをリポジトリ相対パスとファイル名で検索することを必須にする。規律は `em-workflow/skills/tdd-testing/SKILL.md` に置き、`em-workflow/agents/implementer.md` の Step 4c に反映し、新規テストモジュールで記述の存在を静的に検査する。要件の詳細は `feature-docs/tests-yaml-existing-test-search/REQUIREMENTS.md` を参照する。

## Objectives

- implementer が書く `*.tests.yaml` の `red_reason` / `tests` が、既存テストの有無を検索した事実に基づくようにする。
- verify / retrospect が参照する永続記録で、既存の耐久不変条件（レジストリ一致・patch 前進など）が存在しないと読み手に誤認させない。

## User Stories

### US1: 既存テストの不在を記録する前に検索する
implementer エージェントとして、既存テストが無いと記録する前に変更対象ファイルを参照する既存テストを検索したい。記録が検索の事実に基づくようにするため。

**Acceptance Criteria:**
- [ ] AC-1（FR1）: tdd-testing/SKILL.md に、既存テストが無いと記録する前に変更対象ファイルを参照する既存テストを検索することが必須だと書かれている。検索対象がパスとファイル名の両方であることが書かれている。
- [ ] AC-3（FR3）: implementer.md の Step 4c に同じ規律が書かれている、または tdd-testing の該当規律を明示的に参照している。

### US2: 見つかった既存テストを記録する
implementer エージェントとして、検索で見つかった既存テストを `tests:` に列挙し、`red_reason` をその事実に沿って書きたい。verify / retrospect の読み手が既存の耐久不変条件を見落とさないようにするため。

**Acceptance Criteria:**
- [ ] AC-2（FR2）: tdd-testing/SKILL.md に、既存テストが見つかった場合は `tests:` にそのモジュール／クラスを列挙し、red_reason を「専用の新規モジュールはスコープ外だが既存の X が Y を検出する、今回の変更では red は発生しなかった」趣旨にすることが書かれている。

### US3: 規律の欠落を検出する
リポジトリの保守者として、規律の記述が文書から消えたときにテストで検出したい。

**Acceptance Criteria:**
- [ ] AC-4（FR4）: 新規テストモジュールが unittest discover で検出され、AC-1〜AC-3 の記述を assert する。規律の記述を取り除いた文書では失敗する（否定テストで証明）。
- [ ] AC-5（FR5）: plugin.json と marketplace.json の em-workflow エントリの version がともに 0.2.9。他のフィールドと em-review エントリは変更されていない。
- [ ] AC-6（NFR2）: `python3 -m unittest discover -s tests` がリポジトリルートで失敗 0 で終わる。

## Technical Requirements

### Functional Requirements
- **FR1:** 既存テスト検索の必須化（tdd-testing）。`em-workflow/skills/tdd-testing/SKILL.md` に次の規律を追加する: `*.tests.yaml` のエントリで既存テストが無いと述べる前（`tests: []` と書く場合、または `red_confirmed: false` の理由として既存テストの不在を挙げる場合）に、変更対象ファイルを参照する既存テストをプロジェクトのテストディレクトリから検索して確認する。検索はリポジトリ相対パスだけでなくファイル名（basename）でも行う。
- **FR2:** 既存テストが見つかった場合の記録方法。検索で変更対象ファイルを実際に読む既存テストが見つかった場合、そのエントリの `tests:` にそのモジュール／クラスを列挙する。`red_reason` は「専用の新規モジュール追加はスコープ外だが、既存の X が Y を検出する。今回の変更では red 状態は発生しなかった」という趣旨にする。`red_confirmed` は観測した事実のまま（red を見ていなければ false）とする。
- **FR3:** implementer エージェント定義への反映。`em-workflow/agents/implementer.md` の Step 4c（test record の記述、`red_confirmed: false` の段落と `tests: []` の段落）に FR1 / FR2 の規律を反映する（tdd-testing スキルを参照する形でもよい）。
- **FR4:** 再発検出テスト。`tests/` 配下に新規テストモジュールを追加し、tdd-testing/SKILL.md と implementer.md が FR1 / FR2 の規律（既存テストの検索必須・見つかった場合の tests 列挙と red_reason の趣旨）を含むことを assert する。各マッチャーには、規律を欠いた偽サンプルを弾くことを示す否定テストを付ける。
- **FR5:** プラグイン version bump。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの version を 0.2.8 から 0.2.9（patch）に上げ、両者を同じ値にする。em-review エントリは変更しない。

### Non-Functional Requirements
- **NFR1 - テスト規約:** テストコードは Python 標準ライブラリの unittest のみを使う（test/README.md）。ファイル名は `test_<target>.py`、クラスは `Test<Behavior>`、メソッドは `test_<condition>_<expected_result>`。
- **NFR2 - テスト全通過:** `python3 -m unittest discover -s tests` がリポジトリルートからすべて通る。
- **NFR3 - version bump 専用テストを追加しない:** version bump 用の専用テストモジュールは新規に追加しない。既存の `tests/test_spec_file_set_completeness_version_bump.py` と `tests/test_plugin_version_parity.py` が、レジストリ間の一致・patch 前進・キー集合を既に検証している。
- **NFR4 - 禁止見出し:** `em-workflow/agents/implementer.md` に `# Task assignment` 見出しを追加しない（check-plugin-invariants の forbidden heading 検査。`tests/test_check_plugin_invariants.py` の実リポジトリ検査で落ちる）。

## Implementation Approach

### Architecture

**System Architecture:**
該当なし（UI・アプリケーション層・データベースを持たない。変更対象はエージェント定義・スキル文書・テスト・マニフェストのみ）

**Component Diagram:**
```
em-workflow/skills/tdd-testing/SKILL.md   <-- 規律の置き場所（FR1 / FR2）
        ^
        | 同じ規律を記述、または参照
em-workflow/agents/implementer.md (Step 4c)   （FR3）
        ^
        | 記述を静的に検査
tests/<新規テストモジュール>   （FR4）

em-workflow/.claude-plugin/plugin.json  --  version 0.2.9  --  .claude-plugin/marketplace.json (em-workflow エントリ)   （FR5）
        ^
        | 既存テストが検査（NFR3）
tests/test_spec_file_set_completeness_version_bump.py / tests/test_plugin_version_parity.py
```

### Data Flow

```
implementer → テストディレクトリをパスとファイル名で検索 → *.tests.yaml に tests / red_reason / red_confirmed を書く
verify / retrospect ← *.tests.yaml を参照
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/agents/implementer.md` Step 4c: tdd-testing スキルの規律を記述または参照する（FR3）。
- `tests/test_spec_file_set_completeness_version_bump.py`（`TestPluginManifestVersion` / `TestMarketplaceEntryVersion`）: version bump を検証する既存テスト（NFR3）。
- `tests/test_plugin_version_parity.py`（`TestMarketplaceEntryVersion`）: version bump を検証する既存テスト（NFR3）。
- `tests/test_check_plugin_invariants.py`: implementer.md の forbidden heading を実リポジトリで検査する既存テスト（NFR4）。

**External Dependencies:**
- Python 標準ライブラリ unittest（NFR1）

### File Structure

```
em-workflow/
├── .claude-plugin/
│   └── plugin.json              # version 0.2.8 → 0.2.9（FR5）
├── agents/
│   └── implementer.md           # Step 4c に規律を反映（FR3）
└── skills/
    └── tdd-testing/
        └── SKILL.md             # 既存テスト検索の規律を追加（FR1 / FR2）
.claude-plugin/
└── marketplace.json             # em-workflow エントリの version 0.2.9（FR5）
tests/
└── test_<target>.py             # 新規の再発検出テストモジュール（FR4、命名は NFR1）
```

変更しないファイル:
- `em-workflow/references/implement-phase.md`
- `test-docs/declared-change-set-implementation/task0002.tests.yaml`
- `.claude-plugin/marketplace.json` の em-review エントリ

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/tests-yaml-existing-test-search/**`
- `test-docs/tests-yaml-existing-test-search/**`

`feature-docs/tests-yaml-existing-test-search/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/tests-yaml-existing-test-search/**` covers `test-docs/tests-yaml-existing-test-search/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1（FR1）: 新規モジュールで tdd-testing/SKILL.md を読み、既存テスト検索の必須化の記述があることを assert する。
- [ ] TS2（FR2）: 新規モジュールで tdd-testing/SKILL.md を読み、見つかった場合の tests 列挙と red_reason の趣旨の記述があることを assert する。
- [ ] TS3（FR3）: 新規モジュールで implementer.md の Step 4c 範囲に、同じ規律または tdd-testing の該当規律への参照があることを assert する。
- [ ] TS4（FR4）: 否定テスト。規律の記述を欠いた偽の文書サンプルに対して各マッチャーが失敗することを assert する。
- [ ] TS5（FR5 / NFR3）: version bump（AC-5）。新規テストは作らず、既存の `tests/test_spec_file_set_completeness_version_bump.py`（`TestPluginManifestVersion` / `TestMarketplaceEntryVersion`）と `tests/test_plugin_version_parity.py`（`TestMarketplaceEntryVersion`）を tests.yaml の tests に列挙する。このフィーチャー自体が FR2 の適用例になる。

### Integration Tests
該当なし

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出されず
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 変更対象ファイルが専用テストを持たないように見えるが、横断的なテスト（`*_invariants.py` / `*_version_bump.py` など）がカバーしている（今回の不具合の発生条件）。
- [ ] テストがパスを分割して組み立てている（例: `PLUGIN_ROOT / ".claude-plugin" / "plugin.json"`）。そのためリポジトリ相対パスの完全一致検索では見つからず、ファイル名での検索が要る。
- [ ] 検索にヒットしたテストが実ファイルではなく合成フィクスチャを読んでいる（例: `tests/test_check_plugin_invariants.py` は一時ディレクトリに合成した implementer.md を検査する）。このヒットは変更対象ファイルのカバレッジにならない。
- [ ] 検索しても該当テストが無い: 従来どおり `tests: []` と、既存テストが無い旨の red_reason を書いてよい。
- [ ] AC の検証結果がビルドや lint の結果である場合: `tests: []` は引き続き許される。ただし既存テストが無いと述べる場合は、その前に検索する。

### Performance Tests
該当なし

## Security Considerations

該当なし

## Error Handling

該当なし

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1〜AC-6 を満たす
- [ ] `python3 -m unittest discover -s tests` がリポジトリルートで失敗 0 で終わる（NFR2）

## Assumptions

requirements-analyst が採用した前提（いずれも覆すことができる）:

- PR #18 の `test-docs/declared-change-set-implementation/task0002.tests.yaml`（過去フィーチャーの記録）は書き換えない。対象は今後 implementer が書く記録の規律だけとする。
- LLM の実行時の振る舞いはユニットテストで直接観測できないため、再発検出テストは規律を定める文書（SKILL.md / implementer.md）の記述を静的に検査する形とする。これはこのリポジトリの既存の慣習（例: `tests/test_refitted_worker_agents.py`）に従う。
- `em-workflow/references/implement-phase.md` は変更しない。tests_yaml_path を渡すことだけを定めており、red_reason / red_confirmed の規律を持たないため。
- version は patch 単位で上げる（0.2.8 → 0.2.9）。`.claude/rules/core-plugin-version-bump.md` の「挙動の修正は patch」に従う。
- 既存テストの version 検査は耐久不変条件（major/minor 基準より後・patch 前進・レジストリ一致）で書かれており、0.2.9 はそれを満たす。plugin.json description の固定アンカー `/em-workflow:develop drives` は残す。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/tests-yaml-existing-test-search/REQUIREMENTS.md`
- `em-workflow/skills/tdd-testing/SKILL.md`
- `em-workflow/agents/implementer.md`
- `.claude/rules/core-plugin-version-bump.md`
