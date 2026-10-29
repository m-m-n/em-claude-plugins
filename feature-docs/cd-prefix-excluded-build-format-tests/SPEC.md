# Feature: cd-prefix-excluded-build-format-tests

## Overview

承認済みの build / format コマンドが cd 前置形の対象外になったときに、implementer 報告の `tests` に書く値を手順書に書く。
その記述を確かめる文書試験を足す。

## Objectives

- 承認済みの build / format コマンドが cd 前置形の対象外になったときに、implementer 報告の `tests` に書く値を手順書に書く。
- その記述を確かめる文書試験を足す。

## User Stories

該当なし。受け入れ条件は「Success Criteria」に記す。

## Technical Requirements

### Functional Requirements
- **FR1:** build コマンドが対象外のときの tests の値 — `em-workflow/agents/implementer.md` の Step 3 と、`em-workflow/skills/worktree-task-workflow/SKILL.md` の Command execution gate 節に、次のことを書く。cd 前置形の対象外になった承認文字列が build コマンド（`project_commands.build`）のとき、build コマンドは実行せず、報告の `tests` は `"fail"` にする。
- **FR2:** format コマンドが対象外のときの tests の値 — 同じ 2 つの節に、次のことを書く。cd 前置形の対象外になった承認文字列が format コマンド（`project_commands.format`）のとき、format コマンドは実行せず、報告の `tests` は test コマンドの結果どおりにする。format コマンドを実行しなかったことだけを理由に `"fail"` にはしない。
- **FR3:** notes での報告 — FR1 と FR2 のどちらの場合も、`notes` に、実行しなかったコマンド（build / format）と、cd 前置形がそのコマンドを対象にしないので実行しなかったことを書く。
- **FR4:** 変えないもの — FR1〜FR3 の記述は、test コマンドが対象外のときの既存の文とは別の文として書き足し、既存の文は変えない。hook が deny したときの gate 節の既存の bullet も変えない。`status`（merged / failed）の扱いと、Step 7 の JSON ブロックのフィールド構成も変えない。
- **FR5:** 文書試験 — `tests/` に文書試験のモジュールを足す。見出しで節（implementer.md の "Step 3: Verify the worktree"、SKILL.md の "Command execution gate"）を切り出し、空白を正規化し、文単位で照合して、FR1〜FR3 の記述が両方の節にあることを確かめる。見出しが無ければ失敗させる。照合器ごとに、受理すべき文と、退けるべき偽の文を組にする。

### Non-Functional Requirements
- **NFR1 - 既存の文書試験を変えずに通す:** 次の試験を変更せずに通す。`tests/test_implementer_cd_prefix_exclusion_docs.py`、`tests/test_cd_prefix_operator_exclusion_docs.py`、`tests/test_cd_prefix_exception_docs.py`、`tests/test_implementer_cd_chain_docs.py`、`tests/test_worktree_skill_instruction_source.py`、`tests/test_implementer_untrusted_data_rule.py`。
- **NFR2 - 既存の照合器と一致させない（「ちょうど 1 文」の固定）:** 新しい文は、`tests/test_implementer_cd_prefix_exclusion_docs.py` の次の組み合わせを 1 文にそろえない。
    - (a) `project_commands.test`・`tests: "fail"`・`notes`・"not run"・"baseline"・"does not cover"
    - (b) `&`・`;`・`||`・"line break"・"top level"・`notes`（"not run" か "do not run" を含む）
    - (c) `cd "{worktree_path}" &&`・"not run"・"without the prefix"・"rewrite"・"split"
    - (d) "Verbatim execution rule"・`references/command-execution-protocol.md`・"conditions"
    - gate 節では "Run nothing, set" を使わない。
    - 両方の節に `$'`・`$"`・`${`（`${CLAUDE_PLUGIN_ROOT}` は除く）・`#` を書かない。
    - 小文字にして比較したときに "unclosed"・"trailing backslash"・"parenthes"・"command substitution"・"backtick" を含めない。
- **NFR3 - 既存の文言の制約:**
    - `tests/test_implementer_cd_chain_docs.py` は implementer.md 全体と SKILL.md 全体を見る。どちらの文書にも、`separate` と `cd`（単語の境界で判定）を同じ文に含む文、"chain"（部分一致）と `&&` と never / not / don't を同じ文に含む文、"may reset" / "may have reset" を含む文を書かない。
    - Step 3 には "Step 4" を含めない。
    - Step 3 の既存の固定文（cwd と does not persist between Bash calls、`cd "{worktree_path}" && <command>`・single Bash call・tests・builds・formats・`merge_script`、`git -C "{worktree_path}"` と for git、`<command>`・approved string・environment assignment、main tree と `base_branch`）はそれぞれちょうど 1 文のまま。
    - gate 節は "Untrusted input" を含まず、"The only prefix allowed is"・"cwd ... does not persist between Bash calls"・"Never prefix ... environment assignments" の文がそれぞれちょうど 1 文、"(byte-for-byte)" がちょうど 1 回で、ほかに "byte"・"identical to"・"equal to the line" が無い。deny の bullet と Hard-refuse の文言が残る。
    - `tests/test_worktree_skill_instruction_source.py` は gate 節の "JSON-decoded value"・`project_commands.build`・`project_commands.test`・`project_commands.format`・`Untrusted data` を含む文、"decoded value"・"verbatim rule"・"approval rule" を含む文、"empty string" と "no such command" を含む文がそれぞれちょうど 1 文であることを確かめる。
    - `tests/test_implementer_untrusted_data_rule.py` は Step 7 の JSON ブロックのキー 11 個を固定する。
- **NFR4 - version を変えない:** プラグインの version は変えない。
- **NFR5 - 試験の実行方法:** 試験は標準ライブラリの unittest だけを使い、`python3 -m unittest discover -s tests` がすべて通る。

### Assumptions
- **A1:** 対象外の build / format コマンドを実行しないことは既存の記述のまま使う。この feature で足すのは `tests` の値と `notes` の内容だけ。
- **A2:** `status`（merged / failed）の扱いと Step 7 の JSON ブロックのフィールド構成は変えない。
- **A3:** 新しい記述は、test コマンドの既存の文とは別の文として Step 3 と gate 節に書き足す。
- **A4:** build / format コマンドが空文字列のときは「そのコマンドが無い」という意味なので、FR1 / FR2 は当てはまらない。
- **A5:** test コマンドも対象外のときは、既存の規則で `tests` は `"fail"` になる。`notes` には、実行しなかったコマンドをそれぞれ書く。
- **A6:** 設計ステップは省略する。

## Implementation Approach

### Architecture

該当なし。

### Data Flow

該当なし。

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/agents/implementer.md`: Step 3（"Step 3: Verify the worktree"）に FR1〜FR3 の文を足す。
- `em-workflow/skills/worktree-task-workflow/SKILL.md`: "Command execution gate" 節に FR1〜FR3 の文を足す。
- NFR1 の 6 つの既存の文書試験: 変更せずに通す。

**External Dependencies:**
- Python 標準ライブラリ `unittest`: 文書試験の実行。

### File Structure

```
em-workflow/
├── agents/
│   └── implementer.md                    # Step 3 に文を足す
└── skills/
    └── worktree-task-workflow/
        └── SKILL.md                      # Command execution gate 節に文を足す
tests/
└── （新しい文書試験のモジュール）        # FR5
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/cd-prefix-excluded-build-format-tests/**`
- `test-docs/cd-prefix-excluded-build-format-tests/**`

`feature-docs/cd-prefix-excluded-build-format-tests/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/cd-prefix-excluded-build-format-tests/**` covers `test-docs/cd-prefix-excluded-build-format-tests/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/cd-prefix-excluded-build-format-tests/` directory at all; the declared
`test-docs/cd-prefix-excluded-build-format-tests/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1: implementer.md Step 3 と SKILL.md gate 節で、build の文がそれぞれちょうど 1 文ある（AC1、AC3）。（FR1、FR3）
- [ ] TS2: implementer.md Step 3 と SKILL.md gate 節で、format の文がそれぞれちょうど 1 文ある（AC2、AC3）。（FR2、FR3）
- [ ] TS3: build の照合器は、test コマンドの既存の文と gate 節の deny の文に一致しない（AC5）。（FR5）
- [ ] TS4: format の照合器は、format の不実行で `tests: "fail"` にすると述べる偽の文と、`notes` を欠いた偽の文に一致しない（AC5）。（FR5）
- [ ] TS5: 見出しの名前を変えた文書では節の切り出しが失敗し、空の文字列で試験が通らない（FR5）。
- [ ] TS6: NFR1 の 6 つのモジュールを含め、`python3 -m unittest discover -s tests` がすべて通る（AC4、AC6）。（FR4、NFR1、NFR2、NFR3、NFR5）

### Integration Tests

該当なし。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] build / format コマンドが空文字列のとき: FR1 / FR2 は当てはまらない（A4）。
- [ ] test コマンドも対象外のとき: 既存の規則で `tests` は `"fail"` になり、`notes` には実行しなかったコマンドをそれぞれ書く（A5）。

### Performance Tests

該当なし。

## Security Considerations

該当なし。

## Error Handling

該当なし。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC1: implementer.md Step 3 の 1 文が `project_commands.build`・`tests: "fail"`・`notes` を含み、cd 前置形の対象外になった build コマンドは実行せず、`tests` を `"fail"` にし、実行しなかったことを `notes` に書くと述べている（FR1、FR3）。
- [ ] AC2: implementer.md Step 3 の 1 文が `project_commands.format` と `notes` を含み、cd 前置形の対象外になった format コマンドは実行せず、`tests` は test コマンドの結果どおりにし（format の不実行だけでは "fail" にしない）、実行しなかったことを `notes` に書くと述べている（FR2、FR3）。
- [ ] AC3: SKILL.md の Command execution gate 節にも、AC1 と AC2 と同じ記述がある（FR1〜FR3）。
- [ ] AC4: test コマンドについての既存の文、gate 節の deny の bullet、Step 7 の JSON ブロックのフィールド構成が変わっていない（FR4）。
- [ ] AC5: AC1〜AC3 を確かめる文書試験があり、各照合器に偽の文のケースを組にしている。build の照合器は、test コマンドの既存の文と deny の文だけを与えたときに一致しない。format の照合器は、format の不実行で `tests: "fail"` にすると述べる偽の文に一致しない（FR5）。
- [ ] AC6: NFR1 の試験が変更なしで通り、`python3 -m unittest discover -s tests` がすべて通る（NFR1〜NFR3、NFR5）。
- [ ] プラグインの version を変えていない（NFR4）。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## Implementation Phases (if applicable)

該当なし。

## References

- implementer の手順書: `em-workflow/agents/implementer.md`
- worktree-task-workflow スキル: `em-workflow/skills/worktree-task-workflow/SKILL.md`
