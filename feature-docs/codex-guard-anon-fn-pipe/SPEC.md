# Feature: codex-guard-anon-fn-pipe

## Overview

`codex-hook-interactive-guard.py`（em-workflow と em-review の 2 つのコピー）は、頭にパイプまたは標準入力のリダイレクトを受けた zsh の無名関数 `function () { ...; }` の本体にある、プログラム指定なしの `python3` を deny しない。この挙動を `tests/test_codex_hook_interactive_guard.py` の `CASES` に回帰ケースとして追加して固定する。要件の詳細は `feature-docs/codex-guard-anon-fn-pipe/REQUIREMENTS.md` を参照する。

## Objectives

- `codex-hook-interactive-guard.py`（em-workflow と em-review の 2 つのコピー）は、頭にパイプまたは標準入力のリダイレクトを受けた zsh の無名関数 `function () { ...; }` の本体にある、プログラム指定なしの `python3` を deny しない。
- 誤検知の deny が再発しないよう、挙動を回帰ケースで固定する。

## User Stories

該当なし。

## Technical Requirements

### Functional Requirements
- **FR1:** `function ()` へのパイプが本体につながる。コマンド `zsh -c 'printf "print(1)\n" | function () { python3; }'` に対し、フックの 2 つのコピーはいずれも終了コード 0 で終わり、標準出力・標準エラー出力に何も書かない。
- **FR2:** パイプを受けた `function ()` 本体の `-i` は引き続き deny する。コマンド `zsh -c 'printf "print(1)\n" | function () { python3 -i; }'` に対し、フックの 2 つのコピーはいずれも deny の判定（`permissionDecision: deny`）を 1 件出力する。
- **FR3:** `function` と `()` の間の標準入力リダイレクトが本体につながる。コマンド `zsh -c 'function < /dev/null () { python3; }'`（再現手順 3）に対し、フックの 2 つのコピーはいずれも終了コード 0 で終わり、標準出力・標準エラー出力に何も書かない。
- **FR4:** `tests/test_codex_hook_interactive_guard.py` の `CASES` に、`(期待する判定, ラベル, コマンド)` の形で次の 3 件を追加する。
    - silent: `zsh -c 'printf "print(1)\n" | function () { python3; }'`
    - deny: `zsh -c 'printf "print(1)\n" | function () { python3 -i; }'`
    - silent: `zsh -c 'function < /dev/null () { python3; }'`
    - ラベルは既存のエントリと同じく日本語で書く。
    - 配置の目安: パイプの 2 件は zsh の無名関数の形のセクション（既存の `echo x | function () { python3; }` のエントリの近く）、リダイレクトの 1 件は頭の標準入力リダイレクトのセクション（`function < /dev/null { python3; }` の近く）。
    - 3 件のコマンドはいずれも `CASES` にまだ無い（grep で確認済み）。`test_cases_are_unique` は引き続き通る。
- **FR5:** フックスクリプトは、追加したケースが現行コードで失敗した場合に限り変更する。変更する場合は 2 つのコピーを同じ変更の中で直し、バイト単位で同一に保つ。

### Non-Functional Requirements
- **NFR1:** `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` はバイト単位で同一に保つ（`TestCopies.test_the_two_copies_are_byte_identical` で固定）。
- **NFR2:** 既存の `CASES` のエントリは削除も変更もしない（`.claude/rules/hook-tests.md`: 既存の deny ケースは消さない）。
- **NFR3:** テストコードは Python の標準ライブラリだけを使う（`test/README.md`）。
- **NFR4:** プラグインの version は変更しない（`.claude/rules/core-plugin-version-bump.md`）。patch 相当の変更で、Actions が上げる。

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
- `em-workflow/scripts/codex-hook-interactive-guard.py`、`em-review/scripts/codex-hook-interactive-guard.py`: `CASES` の表を両方のコピーに流す（`test_cases_run_against_both_copies`）。

**External Dependencies:**
- なし（NFR3）。

### File Structure

```
tests/
└── test_codex_hook_interactive_guard.py   # CASES に 3 件追加（FR4）
em-workflow/scripts/
└── codex-hook-interactive-guard.py        # 新ケースが失敗した場合に限り変更（FR5）
em-review/scripts/
└── codex-hook-interactive-guard.py        # 同上。em-workflow のコピーとバイト同一（NFR1）
```

`CASES` に追加するエントリのコマンドは、Python のリテラルとしては次のように書く。

```python
"zsh -c 'printf \"print(1)\\n\" | function () { python3; }'"
"zsh -c 'printf \"print(1)\\n\" | function () { python3 -i; }'"
"zsh -c 'function < /dev/null () { python3; }'"
```

### Assumptions

- A1: 基準リビジョンで挙動は既に正しい。オーケストレーターが `dfe45b1a` で行った事前調査でフックを実行し、3 件のコマンドについて silent / silent / deny を確認している。コードを読んだ結果もこれを裏付ける。`_open_group`（em-workflow のコピーの 646〜669 行、em-review のコピーも同じ行）は `_flush()` の前に `anon_pipe = self.pipe_pending` と `anon_stdin = anon and self.stdin` を読み、空の `()` を閉じた時点で `anon_head` を通じて続く `{` の本体に引き渡す。このためフックのコード変更は想定しない。要件分析ではコマンド実行の手段が無く、フックを再実行していない。（取り消し可能）
- A2: タスクの完了条件が挙げる `CASES` のエントリは 2 件である。再現手順 3 のリダイレクトの形（`function < /dev/null () { python3; }`）を 3 件目の silent エントリとして加える。再現手順のどの再発もテストで検出する、という完了条件を満たすためである。テスト 1 行の追加で、外すのも容易である。（取り消し可能）
- A3: 追加する `CASES` エントリの配置とラベルの文言は SPEC と実装に任せる。固定するのは期待する判定とコマンド文字列だけである。エントリの挿入で `SAMPLE_CASES = CASES[::12]` がずれるが、正しさには影響しない。（取り消し可能）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-anon-fn-pipe/**`
- `test-docs/codex-guard-anon-fn-pipe/**`

`feature-docs/codex-guard-anon-fn-pipe/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-anon-fn-pipe/**` covers `test-docs/codex-guard-anon-fn-pipe/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-anon-fn-pipe/` directory at all; the declared
`test-docs/codex-guard-anon-fn-pipe/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

実行コマンド: `python3 -m unittest tests.test_codex_hook_interactive_guard`

### Unit Tests
- [ ] TS1（FR1、FR2、FR3、FR4）: `tests.test_codex_hook_interactive_guard.TestCasesTable.test_cases_run_against_both_copies` - `CASES` の表が、追加したエントリを 2 つのコピーの両方に流す。
- [ ] TS2（FR4）: `tests.test_codex_hook_interactive_guard.TestCasesTable.test_cases_are_unique` - 追加したコマンドが既存のものと重複しない。
- [ ] TS3（FR5、NFR1）: `tests.test_codex_hook_interactive_guard.TestCopies.test_the_two_copies_are_byte_identical` - 2 つのコピーがバイト単位で同一である。

### Diff Review
- [ ] TS4（NFR2）: `tests/test_codex_hook_interactive_guard.py` の `ceefe2b5` との差分確認 - 差分は `CASES` の行の追加だけである。

### Integration Tests

該当なし。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

該当なし。

### Performance Tests

該当なし。

## Security Considerations

該当なし。

## Error Handling

該当なし。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC1: 2 つのコピーはいずれも `zsh -c 'printf "print(1)\n" | function () { python3; }'` に対し、終了コード 0、標準出力・標準エラー出力ともに空になる。（FR1）
- [ ] AC2: 2 つのコピーはいずれも `zsh -c 'printf "print(1)\n" | function () { python3 -i; }'` に対し、deny の判定を出力する。（FR2）
- [ ] AC3: 2 つのコピーはいずれも `zsh -c 'function < /dev/null () { python3; }'` に対し、終了コード 0、標準出力・標準エラー出力ともに空になる。（FR3）
- [ ] AC4: `CASES` に FR4 の 3 件があり、`python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る（`test_cases_are_unique` と `test_cases_run_against_both_copies` を含む）。（FR4）
- [ ] AC5: `TestCopies.test_the_two_copies_are_byte_identical` が通る。（FR5、NFR1）
- [ ] AC6: 基準リビジョン `ceefe2b5` 時点にあった `CASES` のエントリが、すべて変更されずに残っている。（NFR2）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## Implementation Phases (if applicable)

該当なし。

## References

- 要件定義書: `feature-docs/codex-guard-anon-fn-pipe/REQUIREMENTS.md`
- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
- `test/README.md`
