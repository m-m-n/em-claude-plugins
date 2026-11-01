# Feature: launch-guard-common-dir-fallback

## Overview

launch guard の git-common-dir フォールバック（worktree_path に区切り `/.claude/worktrees/em-workflow/` が無い経路）で、プロジェクトのルートの判定と cwd の確認の規則を足す。共通管理ディレクトリが主作業場所直下の `.git` でない構成や、プロジェクトのルート自体が linked worktree の構成で、正しい場所からの起動を拒否しない。要件は `REQUIREMENTS.md` に従う。

## Objectives

- launch guard の git-common-dir フォールバックが、共通管理ディレクトリが主作業場所直下の `.git` でない構成（サブモジュール、`--separate-git-dir`）や、プロジェクトのルート自体が linked worktree の構成で、正しい場所からの起動を拒否しないようにする
- 判断できない状態は fail-open を保つ（NFR2）

## User Stories

### US1: 共通管理ディレクトリの末尾が `.git` でない構成での起動
em-workflow の利用者として、サブモジュールや `--separate-git-dir` の構成で、正しい場所からの起動を拒否されずに行いたい。

**Acceptance Criteria:**
- [ ] AC1: 正規化した共通管理ディレクトリの末尾要素が `.git` でないときは確認を省く（fail-open）
- [ ] AC3: `/super/.git/modules/sub` と `/store/proj.git` を返す構成で拒否されないことをテストで確かめる
- [ ] AC4: 区切りが無い経路で、求めたルートが worktree_path を内包しないときは確認を省く（fail-open）

### US2: linked worktree をルートにした構成での起動
em-workflow の利用者として、プロジェクトのルートが linked worktree の構成で、正しい場所からの起動を拒否されずに行いたい。

**Acceptance Criteria:**
- [ ] AC2: プロジェクトのルートが linked worktree の場合に、正しい場所からの起動が拒否されない。主作業場所の外に置く配置と内側に置く配置の両方で確かめる
- [ ] AC5: 標準 linked layout で、integration worktree や task worktree 自身からの起動は拒否されたまま（既存テストが通る）

### US3: 既存の挙動と固定値の維持
em-workflow の保守者として、git の呼び出し回数・docstring の固定文・sha256 の固定値が変更後の実態と一致した状態を保ちたい。

**Acceptance Criteria:**
- [ ] AC6: git-common-dir の呼び出しは 1 回のまま（TestFallbackCallShape が通る）
- [ ] AC7: docstring の既存の固定文が残り、新しい規則が書かれている
- [ ] AC8: EXPECTED_LAUNCH_GUARD_SHA256 が変更後のフックと一致し、`python3 -m unittest discover -s tests` が通る

## Technical Requirements

### Functional Requirements
- **FR1:** 共通管理ディレクトリ末尾の確認 — 区切り（`/.claude/worktrees/em-workflow/`）が無い経路で、`git rev-parse --path-format=absolute --git-common-dir` の出力を正規化し、末尾要素が `.git` でないとき、プロジェクトのルートは未確定とし、cwd の確認を省く（fail-open）。
- **FR2:** ルートが worktree_path を内包しないときの fail-open — 区切りが無い経路で、共通管理ディレクトリの親として求めたルートが worktree_path を内包しないとき、cwd の確認を省く（fail-open）。内包は realpath を取った両者を `os.path.commonpath` で比べて判定する。
- **FR3:** linked worktree のルートからの起動を拒否しない — 区切りが無い経路で、次の 2 つがどちらも成り立つときは拒否しない。求めたルートが cwd の git toplevel を内包する。その toplevel が worktree_path を真に内包する（toplevel と worktree_path が同一の場合は除く）。内包は realpath と `os.path.commonpath` で判定する。
- **FR4:** git 呼び出しの回数 — FR1〜FR3 の判定は、既存の git-common-dir 呼び出し 1 回と、既存の show-toplevel 呼び出しの結果だけを使う。git の呼び出しは増やさない。
- **FR5:** 区切りがある経路は変えない — worktree_path に区切りがあるとき、ルートは最後の出現より前の部分とする（先頭にあれば未確定）。この挙動とプロセスを起動しないことは変えない。FR1〜FR3 は区切りが無い経路だけに適用する。
- **FR6:** モジュール docstring — フック冒頭の docstring の Project root 段落に、FR1〜FR3 の規則を加える。TestHookDocstring が固定している 3 文（区切りの文、フォールバックの文、fail-open の文）はそのまま残す。
- **FR7:** テスト — `tests/test_queue_launch_guard_linked_layout.py` に次を足す。(1) 共通管理ディレクトリが `/super/.git/modules/sub` と `/store/proj.git` を返す構成で、ルートが未確定になる。他の toplevel を cwd にしても拒否されない。hook_main が出力なしで exit 0 になり、launched を 1 件記録する。(2) ルートが worktree_path を内包しない構成で fail-open になる。(3) linked worktree をルートにした構成で、そのルートを cwd とした起動が拒否されない。主作業場所の外に置く配置と、主作業場所の内側に置く配置の両方で確かめる。(4) FR3 の境界: toplevel == worktree_path は拒否する。ルートが toplevel を内包しないときは拒否する。既存の `TestFallbackCallShape.CANONICAL_PATH` と `TestFallbackFailures.WORKTREE_PATH`（`/proj-store/em-workflow/f/task0001` で `/proj/.git` と組）は、区切りの無い `/proj` 配下のパスに直す。既存の拒否の検証（`test_a_resolved_common_dir_with_another_toplevel_is_a_denial` など）は残す。
- **FR8:** sha256 の固定値の更新 — `tests/test_merge_unverified_exit_doc_contract.py` の `EXPECTED_LAUNCH_GUARD_SHA256` を、変更後の launch guard の sha256 に同じ変更の中で更新する。直前のコメントと `TestNeverModifiedFilesAreByteIdentical` の docstring の、変更されていないという記述も実態に合わせて直す。

### Non-Functional Requirements
- **NFR1:** フックとテストは標準ライブラリだけを import する（TestStdlibAndDeterminism）。
- **NFR2:** 判断できない状態は fail-open。どの経路でもフックは exit 0 で、クラッシュしない。
- **NFR3:** git-common-dir の呼び出しは区切りが無い経路で 1 回のまま。コマンド形・cwd（worktree_path）・タイムアウト（GIT_TIMEOUT_SECONDS）は変えない。
- **NFR4:** 標準 linked layout（主作業場所がルートで、保管先がプロジェクト内）で、integration worktree や task worktree 自身を cwd にした起動は、主作業場所を名指しして拒否されたまま。拒否時は journal に launched を残さない。
- **NFR5:** テストは時間待ちや CPU 負荷に頼らない（sleep や時間計測のモジュールを使わない）。

## Implementation Approach

### Architecture

区切りが無い経路（FR5 の対象外）での判定の順序:

```
git-common-dir の出力（既存の呼び出し 1 回）
  → normpath した basename が `.git` と完全一致しない → ルート未確定、cwd の確認を省く（FR1）
  → 親をルートとする
  → ルートが worktree_path を内包しない → cwd の確認を省く（FR2）
  → cwd の git toplevel（既存の show-toplevel の結果）について
       ルートが toplevel を内包し、toplevel が worktree_path を真に内包する → 拒否しない（FR3）
  → それ以外 → 既存の判定のまま
```

- 内包の判定は realpath を取った両者を `os.path.commonpath` で比べる（FR2、FR3）。
- 末尾の確認は、git-common-dir の出力を normpath した結果の basename が `.git` と完全一致するかで行う（A1）。

### Data Flow

```
worktree_path → 区切りあり → 最後の出現より前をルート（既存のまま、FR5）
              → 区切りなし → git-common-dir → FR1 → FR2 → FR3 → 判定
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `tests/test_queue_launch_guard_linked_layout.py`: FR7 のテストを足し、既存 fixture のパスを直す
- `tests/test_merge_unverified_exit_doc_contract.py`: `EXPECTED_LAUNCH_GUARD_SHA256` と関連する記述を更新する（FR8、A5）

**External Dependencies:**
- git: 既存の `git rev-parse --path-format=absolute --git-common-dir` と show-toplevel の呼び出しのみ（FR4、NFR3）
- Python 標準ライブラリのみ（NFR1）

### File Structure

```
tests/
├── test_queue_launch_guard_linked_layout.py      # FR7
└── test_merge_unverified_exit_doc_contract.py    # FR8
```

launch guard 本体（FR1〜FR6）も変更対象。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/launch-guard-common-dir-fallback/**`
- `test-docs/launch-guard-common-dir-fallback/**`

`feature-docs/launch-guard-common-dir-fallback/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/launch-guard-common-dir-fallback/**` covers `test-docs/launch-guard-common-dir-fallback/{T}.tests.yaml`, the
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
- [ ] TS1 (AC1/AC3): RecordingRunner で common dir に `/super/.git/modules/sub` を返す。project root は未確定になり、cwd_outside_project_root は他の toplevel でも None。git-common-dir の呼び出しは 1 回
- [ ] TS2 (AC1/AC3): `/store/proj.git` で TS1 と同じことを確かめる
- [ ] TS4 (AC1): `/proj/.git/` や `/proj/./x/../.git` のように末尾スラッシュや `.`・`..` を含む出力でも、正規化してから末尾が `.git` と判定される
- [ ] TS5 (AC4): common dir `/proj/.git`、worktree_path `/elsewhere/em-workflow/f/task0001`、cwd の toplevel が別の場所 → None（拒否しない）
- [ ] TS8 (FR3 の境界): toplevel == worktree_path → 拒否。ルートが toplevel を内包しない（toplevel がルートの外側の祖先）→ 拒否

### Integration Tests
- [ ] TS3 (AC1/AC3, hook_main): TS1・TS2 の出力で hook_main が exit 0、stdout が空、launched が 1 件
- [ ] TS6 (AC2, 実際の git): 主作業場所 M の外に linked worktree L を作り、L を project root にして linked layout（保管先は L の中）の task worktree を作る。cwd を L にして起動 → 許可され、launched が記録される
- [ ] TS7 (AC2, 実際の git): linked worktree L を主作業場所 M の内側に置いて TS6 と同じことを確かめる → cwd が L なら許可される
- [ ] TS9 (AC5): 既存の TestLinkedLayoutOtherWorktreeLaunch がそのまま通る
- [ ] TS10 (AC6/AC7): 既存の TestFallbackCallShape・TestFallbackFailures（fixture のパスは `/proj` 配下に直す）・TestHookDocstring が通る
- [ ] TS11 (AC8): `tests.test_merge_unverified_exit_doc_contract.TestNeverModifiedFilesAreByteIdentical.test_launch_guard_untouched` が通る

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 末尾スラッシュや `.`・`..` を含む git-common-dir の出力（TS4）
- [ ] toplevel と worktree_path が同一（TS8、拒否）
- [ ] ルートが toplevel を内包しない（TS8、拒否）

### Performance Tests
該当なし。

## Security Considerations

- **Authorization:** 標準 linked layout で、integration worktree や task worktree 自身を cwd にした起動は、主作業場所を名指しして拒否されたまま。拒否時は journal に launched を残さない（NFR4、A3）。
- **Input Validation:** git-common-dir の出力は normpath してから末尾を確認する（FR1、A1）。内包は realpath と `os.path.commonpath` で判定する（FR2、FR3）。

## Error Handling

### Error Flow

```
判断できない状態 → cwd の確認を省く（fail-open） → exit 0
```

- どの経路でもフックは exit 0 で、クラッシュしない（NFR2）。

## Performance Optimization

- git の呼び出しは増やさない（FR4、NFR3）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1〜AC8 が満たされる
- [ ] `python3 -m unittest discover -s tests` が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- A1: 末尾の確認は、既存の git-common-dir 呼び出しの出力を normpath した結果の basename が `.git` と完全一致するかで行う。
- A2: TestHookDocstring が固定している 3 文は、空白を正規化した部分文字列として docstring に残す。
- A3: 標準 linked layout の既存の拒否ケースは、FR2・FR3 の後も拒否されたまま。
- A4: 受け入れ条件 3 は、RecordingRunner で git-common-dir の出力を差し替える単体テストと、hook_main のテストで確かめる。実際のサブモジュールや `--separate-git-dir` の fixture は作らない。
- A5: EXPECTED_LAUNCH_GUARD_SHA256 は、同じ変更の中で新しいフックの内容の sha256 に更新する。
- A6: plugin の version は変えない（main への push 時に Actions が patch を上げる）。

## References

- 要件定義書: `feature-docs/launch-guard-common-dir-fallback/REQUIREMENTS.md`
