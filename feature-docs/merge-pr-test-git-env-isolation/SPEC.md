# Feature: merge-pr-test-git-env-isolation

## Overview

`tests/test_merge_pr.py` の実行が、テストごとの一時ディレクトリの外にある git リポジトリへ書き込まないようにする。環境に `GIT_*` 変数が入っている場合（例: git フックの中で実行された場合）も同様とする。この隔離が崩れたことを検出するテストを追加する。

## Objectives

- `tests/test_merge_pr.py` の実行は、環境に `GIT_*` 変数が入っている場合（例: git フックの中）も、テストごとの一時ディレクトリの外にある git リポジトリへ書き込まない。
- この隔離が崩れたことをテストで検出できる。

## User Stories

該当なし。

## Acceptance Criteria

- [ ] AC1: `GIT_DIR` が別のリポジトリを指した状態で `python3 -m unittest tests.test_merge_pr` を実行しても、そのリポジトリにコミットも `user.name` / `user.email` の設定も追加されない。（FR1, FR2）
- [ ] AC2: `MergePrTestCase.setUp` の後、setUp が組み立てた環境には、setUp 自身が設定するもの（`GIT_CONFIG_NOSYSTEM`、`GIT_CONFIG_GLOBAL`）以外の `GIT_` キーが無く、`GIT_CONFIG_GLOBAL` は `os.devnull` と等しい。（FR1, FR2）
- [ ] AC3: `tests/test_merge_pr.py` の回帰テストが、`GIT_*` を引き継いだ状況を扱う。修正前の setUp では失敗し、修正後は成功する。（FR3, NFR3）
- [ ] AC4: `python3 -m unittest tests.test_merge_pr` がすべて成功し、`em-workflow/` 配下のファイルは変更されない。（FR4, NFR1, NFR2, NFR4）

## Technical Requirements

### Functional Requirements
- **FR1:** 引き継いだ `GIT_*` 変数を setUp で取り除く。`tests/test_merge_pr.py` の `MergePrTestCase.setUp` は、`os.environ` のコピーから `GIT_` で始まるキーをすべて削除してから、テスト用の値を追加する。書き方は `tests/test_merge_preflight.py` と同じく、`list(env)` を走査して `key.startswith("GIT_")` のキーを削除する。これにより `self.env` と、`self.env` から作る `self.real_env` は引き継いだ `GIT_*` キーを持たず、フィクスチャを作る git 呼び出しと `merge-pr.py` の子プロセスはどちらもそれらの変数なしで動く。
- **FR2:** `GIT_CONFIG_GLOBAL` を `os.devnull` に固定する。`MergePrTestCase.setUp` は、既存の `GIT_CONFIG_NOSYSTEM=1` と並べて `GIT_CONFIG_GLOBAL=os.devnull` を `self.env` に追加する。これにより `self.real_env` にも入る。
- **FR3:** 引き継いだ `GIT_*` からの隔離の回帰テスト。`tests/test_merge_pr.py` に次のテストを置く。プロセスの環境に `GIT_DIR`、`GIT_WORK_TREE`、`GIT_INDEX_FILE` を設定して囮の git リポジトリを指させ、`MergePrTestCase.setUp` とそのクリーンアップを実行する。囮リポジトリの refs、HEAD、ローカル設定が変わっていないこと（新しいコミットが無く、`user.name`、`user.email`、`commit.gpgsign` の項目が無いこと）を確かめる。あわせて、テストの一時ディレクトリ配下のフィクスチャリポジトリに初回コミットが入ったこと、setUp が組み立てた環境に setUp 自身が設定するもの以外の `GIT_` キーが無いこと、`GIT_CONFIG_GLOBAL` が `os.devnull` と等しいことを確かめる。このテストは現在の setUp では失敗し、FR1 / FR2 の後は成功する。
- **FR4:** 既存の環境の扱いを保つ。`GH_REPO`、`GH_TOKEN`、`GITHUB_TOKEN`、`EM_WORKFLOW_MERGE_PR_GH_TIMEOUT` の既存の削除と、`PATH`、`HOME`、`GIT_CONFIG_NOSYSTEM`、`GH_STUB_DIR`、`PYTHONDONTWRITEBYTECODE` の既存の値は、そのまま残す。

### Non-Functional Requirements
- **NFR1 - テストのみの変更:** 変更するのは `tests/` 配下のファイルだけ。`em-workflow/` 配下は何も変更しない。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` のプラグインの version も変更しない。
- **NFR2 - 標準ライブラリのみ:** テストコードは Python の標準ライブラリ（`unittest`、`unittest.mock`、`tempfile`、`subprocess`、`os`）だけを使う。
- **NFR3 - 回帰テスト自体の隔離:** 回帰テストは、囮リポジトリを自身の一時ディレクトリの中に、`GIT_*` を取り除いた環境で作る。`os.environ` の変更は `unittest.mock.patch.dict` のような範囲を限った仕組みでだけ行い、失敗時も含めて後で元に戻す。外側のプロセスがすでに `GIT_*` 変数を持っている場合も、自身の一時ディレクトリの外には何も書き込まない。
- **NFR4 - ネットワークと実ユーザー状態に触れない:** どのテストもネットワークと実際の `~/.claude` に触れない。

## Implementation Approach

### Architecture

**System Architecture:**
```
tests/test_merge_pr.py
├── MergePrTestCase.setUp
│     os.environ のコピー → GIT_* を削除（FR1）
│                        → 既存の GH_* 等の削除・既存の値の設定（FR4）
│                        → GIT_CONFIG_NOSYSTEM=1, GIT_CONFIG_GLOBAL=os.devnull（FR2）
│     → self.env → self.real_env
└── 回帰テスト用の TestCase（FR3）
      囮リポジトリ作成 → os.environ を範囲を限って書き換え
      → MergePrTestCase.setUp とクリーンアップを実行 → 検証
```

**Component Diagram:**
```
MergePrTestCase.setUp ──self.env──> フィクスチャを作る git 呼び出し
                      ──self.real_env──> merge-pr.py の子プロセス
回帰テスト ──駆動──> MergePrTestCase.setUp / doCleanups
```

### Data Flow

```
os.environ（GIT_* を含みうる）
  → setUp 内のコピー（GIT_* 削除、テスト値追加）
  → self.env / self.real_env
  → git 呼び出し・merge-pr.py 子プロセス（テストの一時ディレクトリ内でのみ動作）
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `tests/test_merge_preflight.py`: FR1 の `GIT_*` 削除の書き方をこのファイルに揃える。

**External Dependencies:**
- Python 標準ライブラリ（`unittest`、`unittest.mock`、`tempfile`、`subprocess`、`os`）

### File Structure

```
tests/
└── test_merge_pr.py      # MergePrTestCase.setUp の変更と回帰テストの追加
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/merge-pr-test-git-env-isolation/**`
- `test-docs/merge-pr-test-git-env-isolation/**`

`feature-docs/merge-pr-test-git-env-isolation/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/merge-pr-test-git-env-isolation/**` covers `test-docs/merge-pr-test-git-env-isolation/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/merge-pr-test-git-env-isolation/` directory at all; the declared
`test-docs/merge-pr-test-git-env-isolation/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 1 つのコミットを持つ囮リポジトリを作り、refs、HEAD、`config --local --list` を記録する。`os.environ` を `GIT_DIR=<decoy>/.git`、`GIT_WORK_TREE=<decoy>`、`GIT_INDEX_FILE=<decoy>/.git/index` で書き換える。インスタンスに対して `MergePrTestCase.setUp` と `doCleanups` を実行する - 囮リポジトリの記録が変わっておらず、フィクスチャリポジトリに `initial` コミットがある。（AC1, AC3 / FR1, FR2, FR3, NFR3）
- [ ] TS-2: 書き換えた環境に `GIT_DIR`、`GIT_CONFIG_GLOBAL`、`GIT_CONFIG_PARAMETERS` を設定して setUp を実行する - `self.env` と `self.real_env` の `GIT_*` キーの集合がちょうど `{GIT_CONFIG_NOSYSTEM, GIT_CONFIG_GLOBAL}` で、`GIT_CONFIG_GLOBAL == os.devnull` である。（AC2 / FR1, FR2）

### Integration Tests
- [ ] TS-3: 環境に `GIT_*` が無い状態で、既存の `tests.test_merge_pr` スイート全体を実行する - 既存のテストがすべて成功する。（AC4 / FR4, NFR1, NFR2, NFR4）

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし
- [ ] Existing E2E tests pass without regression（該当なし）

### Edge Cases

該当なし。

### Performance Tests

該当なし。

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 該当なし
- **Data Protection:** テストはテストごとの一時ディレクトリの外にある git リポジトリへ書き込まない（FR1, FR2, NFR3）。ネットワークと実際の `~/.claude` に触れない（NFR4）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

該当なし。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1〜AC4 を満たす
- [ ] Code review is completed

## Assumptions

- A1: 回帰テストは `tests/test_merge_pr.py` に新しい TestCase クラスとして置き、スイート全体をサブプロセスで起動するのではなく、`MergePrTestCase.setUp` を同じプロセス内で駆動する。
- A2: 回帰テストが設定する囮の変数は `GIT_DIR`、`GIT_WORK_TREE`、`GIT_INDEX_FILE` とする。
- A3: 削除の条件はちょうど `key.startswith("GIT_")` とし、`tests/test_merge_preflight.py` と同じにする。ほかの接頭辞やキー（例: `XDG_CONFIG_HOME`、`EM_WORKFLOW_APPROVALS`）は加えない。
- A4: setUp はフィクスチャリポジトリへのローカルな `git config` で `user.name`、`user.email`、`commit.gpgsign` を設定し続ける。`GIT_AUTHOR_*` と `GIT_COMMITTER_*` は環境に加えない。
- A5: setUp の既存の `GH_*` 削除と既存の環境の値は保つ（不変条件）。
- A6: プラグインの version は変更しない（制約）。
- A7: `tests/test_merge_pr.py` の既存テストは、引き継いだ `GIT_*` 変数に依存しない。`env_extra` を含め、setUp の `GIT_CONFIG_NOSYSTEM` 以外に `GIT_*` の使用は無い。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## Implementation Phases (if applicable)

該当なし。

## References

- `tests/test_merge_pr.py`: 変更対象
- `tests/test_merge_preflight.py`: FR1 / A3 の `GIT_*` 削除の書き方
