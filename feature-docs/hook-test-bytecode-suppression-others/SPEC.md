# Feature: hook-test-bytecode-suppression-others

## Overview

7 つのテストモジュールで、`em-workflow/hooks/` または `em-review/hooks/` のフックモジュールをテストプロセス内で読み込む箇所すべてを、バイトコードの書き込みを止めた状態で読み込むように変える。各モジュールを単体で実行しても、フックのディレクトリに `__pycache__` が残らないようにする。要件は `feature-docs/hook-test-bytecode-suppression-others/REQUIREMENTS.md` を参照する。

## Objectives

- 次の 7 つのテストモジュールのどれを単体で実行しても、`em-workflow/hooks/` と `em-review/hooks/` の下に `__pycache__` が残らない
    - `tests/test_queue_stop_guard.py`
    - `tests/test_queue_stop_guard_routeback_record.py`
    - `tests/test_failed_run_cleanup_guard.py`
    - `tests/test_hooks_registration.py`
    - `tests/test_queue_failure_net_cross_hook.py`
    - `tests/test_muse_guard.py`
    - `tests/test_consultation_harness_chain.py`

## User Stories

### US1: テストモジュールを単体で実行する
テストの実行者として、7 モジュールのどれかを `python3 -m unittest tests.<module>` で単体実行したい。実行後、`em-workflow/hooks/` と `em-review/hooks/` の下に `__pycache__` が無い状態であってほしい。

**Acceptance Criteria:**
- [ ] AC-1: `em-workflow/hooks/` と `em-review/hooks/` の下に `__pycache__` が無い状態から始める。リポジトリのルートで、7 モジュールのそれぞれを `python3 -m unittest tests.<module>` で単体実行する。各実行の後、どちらのディレクトリにも `__pycache__` が無い。（FR1、FR2）

### US2: テストスイート全体を実行する
テストの実行者として、`python3 -m unittest discover -s tests` でスイート全体を実行したい。

**Acceptance Criteria:**
- [ ] AC-2: `python3 -m unittest discover -s tests` が、変更前と同じく通る。（NFR1、NFR2）

## Technical Requirements

### Functional Requirements
- **FR1:** テストプロセス内のフック読み込みでバイトコードを書かない。7 つのテストモジュールの中で、`em-workflow/hooks/` または `em-review/hooks/` のフックモジュールをテストプロセス内で読み込む箇所（`importlib.util.spec_from_file_location` の後に `spec.loader.exec_module`）はすべて、バイトコードの書き込みを止めた状態で読み込む。この読み込みによって、どちらのフックのディレクトリにも `__pycache__` を書かない。対象の読み込み箇所:

    | テストモジュール | 読み込み箇所 | 読み込むフック |
    |------------------|--------------|----------------|
    | `tests/test_queue_stop_guard.py` | `TestQueueStopGuardOwnershipAmbiguity._load_hook_module` | `queue_stop_guard.py` |
    | `tests/test_queue_stop_guard_routeback_record.py` | `load_hook_module` | `queue_stop_guard.py` |
    | `tests/test_failed_run_cleanup_guard.py` | `load_hook_module`（`run_hook_in_process` からも使う） | `failed-run-cleanup-guard.py` |
    | `tests/test_hooks_registration.py` | `load_hook_module` | `queue_launch_guard.py`、`queue_agent_index.py`、`queue_failure_net.py` |
    | `tests/test_queue_failure_net_cross_hook.py` | `_load_module_from_path` | `queue_failure_net.py`、`queue_launch_guard.py` |
    | `tests/test_muse_guard.py` | `_load_guard_module` | `em-workflow` と `em-review` の `muse_guard.py` |
    | `tests/test_consultation_harness_chain.py` | `_load_guard` | `em-workflow` と `em-review` の `muse_guard.py` |

- **FR2:** 各モジュールを単体で実行しても成り立つ。7 モジュールのそれぞれをリポジトリのルートで単体実行（`python3 -m unittest tests.<module>`）したときにも FR1 が成り立つ。同じプロセスで `tests/test_merge_ci_wait.py` が先に `sys.dont_write_bytecode` を設定していることに依存しない。

### Non-Functional Requirements
- **NFR1:** テストは引き続き標準ライブラリだけを使う（`test/README.md`）。
- **NFR2:** 各テストモジュールは、`python3 -m unittest discover -s tests` と `python3 -m unittest tests.<module>` のどちらでも引き続き動く。

## Implementation Approach

### Architecture

FR1 の各読み込み箇所で、`spec.loader.exec_module` の呼び出しを次の形で囲む（前提 A1）。これは `tests/test_destructive_guard_extglob_units.py` の `load_hook` と `tests/test_queue_launch_guard_linked_layout.py` の `load_hook_module` で使われている形と同じ。

```
呼び出し元の sys.dont_write_bytecode を保存
sys.dont_write_bytecode = True
try:
    spec.loader.exec_module(module)
finally:
    sys.dont_write_bytecode = 保存した値
```

- `sys.dont_write_bytecode = True` にするのは `exec_module` の実行中だけ。プロセス全体のフラグを変えたままにしない。
- `exec_module` が例外を投げても、`finally` で呼び出し元の値に戻す（EC1）。
- 読み込んだフックのモジュール本体が同じフックのディレクトリの別モジュールを import する場合、その import は `exec_module` の実行中に起きるので、書き込みの抑止が効く（EC3）。

### Data Flow

```
テスト → 読み込み関数 → [フラグを保存・True に設定] → exec_module(フック) → [finally: フラグを戻す] → モジュールを返す
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/`、`em-review/hooks/` のフックモジュール: FR1 の表に挙げたもの。変更しない

**External Dependencies:**
- Python 標準ライブラリ（`importlib.util`、`sys`、`unittest`）

### File Structure

```
tests/
├── test_queue_stop_guard.py                    # TestQueueStopGuardOwnershipAmbiguity._load_hook_module
├── test_queue_stop_guard_routeback_record.py   # load_hook_module
├── test_failed_run_cleanup_guard.py            # load_hook_module
├── test_hooks_registration.py                  # load_hook_module
├── test_queue_failure_net_cross_hook.py        # _load_module_from_path
├── test_muse_guard.py                          # _load_guard_module
└── test_consultation_harness_chain.py          # _load_guard
```

### Out of Scope

- `tests/test_merge_ci_wait.py`（モジュールの先頭で `sys.dont_write_bytecode = True` を設定し、戻さない）は変更しない（A2）。
- `tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` はタスクの指定により対象外（A2）。
- フックをサブプロセス（`sys.executable <hook>.py`）として実行する箇所は、TS-1 でフックのディレクトリに `__pycache__` が現れない限り変更しない。`__main__` として実行されたフック自身はキャッシュされず、キャッシュされるのはそれが import する同じディレクトリのフックモジュールだけ（A3）。
- `tests/test_consultation_harness_chain.py` の `_pinned_consent_check_command` が `tests/test_contributor_tier_criteria.py` を読み込むときのバイトコードは、配布されない `tests/` の下に書かれるので、このフィーチャーの受け入れ基準の対象外（A4）。
- プラグインのファイルを変更しないので、プラグインの version も変えない（A5、`.claude/rules/core-plugin-version-bump.md`）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/hook-test-bytecode-suppression-others/**`
- `test-docs/hook-test-bytecode-suppression-others/**`

`feature-docs/hook-test-bytecode-suppression-others/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/hook-test-bytecode-suppression-others/**` covers `test-docs/hook-test-bytecode-suppression-others/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/hook-test-bytecode-suppression-others/` directory at all; the declared
`test-docs/hook-test-bytecode-suppression-others/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 7 モジュールのそれぞれについて、どちらのフックのディレクトリにも `__pycache__` が無いことを確かめ、そのモジュールを単体で実行し、再びどちらにも `__pycache__` が無いことを確かめる - 各実行の後、`em-workflow/hooks/` と `em-review/hooks/` の下に `__pycache__` が無い（AC-1、FR1、FR2）

### Integration Tests
- [ ] TS-2: `python3 -m unittest discover -s tests` でスイート全体を実行する - すべてのテストが通る（AC-2、NFR1、NFR2）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] TS-3: 読み込みのフラグを自動で確かめる場合の先例の形 - `sys.dont_write_bytecode` の開始値（`False` と `True`）をテストの中で設定する。スイート全体の実行では `tests/test_merge_ci_wait.py` がこの値を `True` のままにするため（先例: `tests/test_destructive_guard_extglob_units.py` の `TestHookLoadWritesNoBytecode`）（FR2）
- [ ] EC1: `exec_module` が例外を投げても、呼び出し元の `sys.dont_write_bytecode` を元に戻す。
- [ ] EC2: `tests/test_failed_run_cleanup_guard.py` の `run_hook_in_process` は、読み込みが終わった後にテストプロセス内で読み込んだフックの `main()` を呼ぶ。`main()` が `em-workflow/hooks/` のモジュールを遅延 import すると、その import はフラグを戻した後に走り、`__pycache__` を書く可能性がある。AC-1 で検出する。
- [ ] EC3: 読み込んだフックのモジュール本体が同じフックのディレクトリの別モジュールを import する場合、その import は `exec_module` の実行中に起きるので、書き込みの抑止が効く。
- [ ] EC4: `tests/test_muse_guard.py` の `test_neither_plugins_hooks_tests_directory_gained_a_file` が調べるのは `em-workflow/hooks/tests` と `em-review/hooks/tests` だけで、フックのディレクトリ直下の `__pycache__` は調べない。

### Performance Tests
該当なし

## Security Considerations

該当なし（テストコードのみの変更）

## Error Handling

- `exec_module` が例外を投げた場合も、`finally` で `sys.dont_write_bytecode` を呼び出し元の値に戻す（EC1）。

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1、AC-2 を満たす
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（すべての要件は resolved）

### Assumptions

- A1: 抑止は、`tests/test_destructive_guard_extglob_units.py` の `load_hook` と `tests/test_queue_launch_guard_linked_layout.py` の `load_hook_module` で使われている形に従う。`exec_module` の実行中だけ `sys.dont_write_bytecode = True` にし、`finally` で呼び出し元の値に戻す。プロセス全体のフラグを変えたままにしない。
- A2: `tests/test_merge_ci_wait.py`（モジュールの先頭で `sys.dont_write_bytecode = True` を設定し、戻さない）は変更しない。`tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` はタスクの指定により対象外。
- A3: 対象は FR1 に列挙したテストプロセス内の読み込み。フックをサブプロセス（`sys.executable <hook>.py`）として実行する箇所は、TS-1 でフックのディレクトリに `__pycache__` が現れない限り変更しない。`__main__` として実行されたフック自身はキャッシュされず、キャッシュされるのはそれが import する同じディレクトリのフックモジュールだけ。
- A4: `tests/test_consultation_harness_chain.py` の `_pinned_consent_check_command` は `tests/test_contributor_tier_criteria.py` を読み込む。その読み込みのバイトコードは配布されない `tests/` の下に書かれるので、このフィーチャーの受け入れ基準の対象外。
- A5: プラグインのファイルを変更しないので、プラグインの version も変えない（`.claude/rules/core-plugin-version-bump.md`）。

## References

- 要件定義書: `feature-docs/hook-test-bytecode-suppression-others/REQUIREMENTS.md`
- テストの実行方法: `test/README.md`
- 既存の抑止の形: `tests/test_destructive_guard_extglob_units.py`（`load_hook`、`TestHookLoadWritesNoBytecode`）、`tests/test_queue_launch_guard_linked_layout.py`（`load_hook_module`）
