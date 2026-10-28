# Feature: is-below-physical-fallback

## Overview

`bash_guard.py` の `is_below(path, area)` は、論理パス `realpath(normpath(path))` が存在しないだけで、有効な cd 前置形を allow から外している。有効な cd 前置形とは、Bash の `cd` が物理パスへのフォールバックで領域内へ移動できる形を指す。本機能では、論理パスが存在するディレクトリでないときは物理パス `realpath(path)` だけで判定するように変える。シンボリックリンクの後ろの `..` で領域外へ出る形を allow しない保護は維持する。

## Objectives

- `bash_guard.py` の `is_below()` が、論理パスが存在しないだけで有効な cd 前置形（Bash の `cd` が物理パスへのフォールバックで領域内へ移動できる形）を allow から外す問題をなくす
- シンボリックリンクの後ろの `..` で領域外へ出る形を allow しない保護は維持する

## User Stories

### US1: 物理パスへのフォールバックで領域内へ移動できる cd 前置形を allow する

論理パスが存在しないだけで有効な cd 前置形を allow から外す問題をなくす。

**Acceptance Criteria:**
- [ ] AC-1: `cd "/proc/self/root/..<area 内の worktree パス>" && <承認済み文字列>` が allow になる。`/proc/self/root` が使えない環境ではこのケースをスキップする。（FR1, FR3）
- [ ] AC-2: /proc に依存しない再現。area の外に置いた、area 内の深いディレクトリを指すシンボリックリンク L について、`cd "L/../<L の指す先の親から見た既存ディレクトリ名>" && <承認済み文字列>` が allow になる。この形では論理パスは存在せず、物理パスは area 内の既存ディレクトリになる。（FR1）
- [ ] AC-6: `bash_guard.py` の docstring と `command-execution-protocol.md` の path 条件が、論理パスが存在するディレクトリなら両方、そうでなければ物理パスで判定する規則を述べている。（FR7）

### US2: 領域外へ出る形を allow しない保護を維持する

シンボリックリンクの後ろの `..` で領域外へ出る形を allow しない保護を維持する。

**Acceptance Criteria:**
- [ ] AC-3: area 内のシンボリックリンクの後ろに `..` を置き、論理パスが area の外の既存ディレクトリ、物理パスが area 内の既存ディレクトリになる形は出力なし（allow しない）。（FR2, FR4）
- [ ] AC-4: 論理パスが存在せず、物理パスが area の外の既存ディレクトリ・area そのもの・接頭辞だけ一致する兄弟ディレクトリになる形は、それぞれ出力なし。（FR5）
- [ ] AC-5: `tests/test_bash_guard_cd_prefix.py` と `tests/test_hook_classification_pin.py` の既存テストが期待値を変えずに通る。（FR6, NFR1, NFR2, NFR3）

## Technical Requirements

### Functional Requirements
- **FR1: 論理パスが使えないときの物理パス判定:** `is_below(path, area)` は、論理パス `realpath(normpath(path))` が存在するディレクトリでないとき（存在しない、またはディレクトリでない）、物理パス `realpath(path)` だけで判定する。物理パスが存在するディレクトリで、かつ area より厳密に下（パス要素単位の比較）のときに True、それ以外は False を返す。
- **FR2: 論理パスが使えるときの判定は現状維持:** 論理パスが存在するディレクトリのときは、現行どおり論理パスと物理パスの両方が存在するディレクトリで、かつ両方が area より厳密に下のときだけ True を返す。
- **FR3: 再現手順の形を allow する:** P を `/proc/self/root/..` に area 内の worktree の絶対パスを連結したものとしたとき、`cd "P" && <承認済み文字列>` は allow になる（構文条件と承認条件を満たす場合）。
- **FR4: シンボリックリンクの後ろの .. で領域外へ出る形は引き続き allow しない:** 論理パスが存在するディレクトリで area の外にある形は、物理パスが area 内であっても allow しない（出力なし）。area 内のシンボリックリンクの後ろに `..` を置き、字句上の移動先が area の外になる形もこれに含む。
- **FR5: フォールバック時も領域外・領域そのものは allow しない:** 論理パスが使えず物理パスで判定する場合でも、物理パスが次のいずれかのときは allow しない（出力なし）。area の外、area そのもの、名前の接頭辞だけが一致する兄弟ディレクトリ（`em-workflow-x` 等）、存在しないパス、ファイル。
- **FR6: 他の判定は変えない:** 次の判定は変更しない。cd 前置形の構文条件・承認条件、禁止パターンによる deny、完全一致の allow、宣言済み未承認の deny、無関係なコマンドの無出力。`is_below` の判定条件を満たさない形は、従来どおり cd 前置なしと同じ扱いで、新たな deny を生まない。
- **FR7: 判定条件の記述を実装に合わせる:** 次の 2 箇所の path 条件を、論理パス／物理パスの判定規則（FR1・FR2）に合わせて記述する。
  - `bash_guard.py` のモジュール docstring（現状 'the realpath of <path> is an existing directory strictly below ...'）
  - `command-execution-protocol.md` の Verbatim execution rule（現状 'the path's realpath is an existing directory deeper than ...'）
- **FR8: 再発検出テスト:** `tests/test_bash_guard_cd_prefix.py` に、FR3（再現手順）、FR1 の /proc に依存しない再現、FR4、FR5 のケースを追加する。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみの import:** `bash_guard.py` は標準ライブラリだけを import する（`tests/test_bash_guard_cd_prefix.py` の AC-7 テストが固定）。
- **NFR2 - 実行テキストに status を含めない:** `bash_guard.py` の実行テキスト（docstring を除く識別子・文字列リテラル）に部分文字列 `status` を含めない（`test_bash_guard_cd_prefix.py` の `test_ac7_hook_executable_text_has_no_status_substring` と `test_hook_classification_pin.py` の `test_bash_guard_reads_workflow_yaml_but_not_task_status` が固定）。
- **NFR3 - path を子プロセスに使わない:** `<path>` は解決するだけで、子プロセスの作業ディレクトリや引数には使わない（`test_ac1_no_child_process_uses_the_prefixed_path` が固定）。
- **NFR4 - 例外時は判定なし側に倒す:** パス解決や判定で `OSError` / `ValueError` が起きたら False を返す（判定なし側に倒す）。フックは終了コード 0 で、標準エラー出力に書かない。
- **NFR5 - テストの隔離:** 新しく追加するテストは標準ライブラリだけを使い、実際の `~/.claude` の状態や実リポジトリの `workflow.yaml` を読まない（既存 Fixture の隔離方式に従う）。

## Implementation Approach

### Architecture

**System Architecture:**

変更対象は `bash_guard.py` の `is_below(path, area)` 1 関数。cd 前置形の判定の中で、`<path>` が area より厳密に下かを返す。

**Component Diagram:**
```
cd 前置形の判定（構文条件・承認条件: 変更なし）
  └── is_below(path, area)   ← 本機能の変更対象
        ├── 論理パス  realpath(normpath(path))
        └── 物理パス  realpath(path)
```

### Data Flow

```
is_below(path, area)
  │
  ├─ 論理パス L = realpath(normpath(path))
  ├─ 物理パス P = realpath(path)
  │
  ├─ L が存在するディレクトリ（FR2: 現状維持）
  │     L と P がともに存在するディレクトリ、かつ両方が area より厳密に下 → True
  │     それ以外 → False
  │
  ├─ L が存在するディレクトリでない（不在・ファイル）（FR1）
  │     P が存在するディレクトリ、かつ area より厳密に下（パス要素単位） → True
  │     それ以外 → False
  │
  └─ OSError / ValueError → False（NFR4）
```

### API Design

該当なし（外部 API の追加・変更はない）。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `command-execution-protocol.md`: Verbatim execution rule の path 条件の記述を FR1・FR2 に合わせる（FR7）。
- `tests/test_bash_guard_cd_prefix.py`: 既存の Fixture とケース表に再発検出テストを追加する（FR8）。
- `tests/test_hook_classification_pin.py`: 既存テストが期待値を変えずに通る（AC-5）。

**External Dependencies:**
- なし（標準ライブラリのみ。NFR1, NFR5）。

### File Structure

```
bash_guard.py                          # is_below の判定変更、モジュール docstring の path 条件更新
command-execution-protocol.md          # Verbatim execution rule の path 条件更新
tests/
├── test_bash_guard_cd_prefix.py       # 再発検出テストの追加
└── test_hook_classification_pin.py    # 変更なし（既存テストが通ること）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/is-below-physical-fallback/**`
- `test-docs/is-below-physical-fallback/**`

`feature-docs/is-below-physical-fallback/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/is-below-physical-fallback/**` covers `test-docs/is-below-physical-fallback/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/is-below-physical-fallback/` directory at all; the declared
`test-docs/is-below-physical-fallback/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1（AC-1 / FR1, FR3）: Fixture の cwd（repo1 と git worktree の両方）で、`'/proc/self/root/..' + str(FIX.inside)` を P とした cd 前置形を流し、allow を確認する。`os.path.isdir('/proc/self/root')` が偽ならスキップする。
- [ ] TS-2（AC-2 / FR1）: Fixture ルート直下に `hop -> <area>/task0001/sub` のシンボリックリンクを作り、`P = <root>/hop/../sub` で allow を確認する。論理パス `<root>/sub` は不在、物理パス `<area>/task0001/sub` は存在する。
- [ ] TS-3（AC-3 / FR2, FR4）: area 内に `lnk -> <area>/a/b` を作り、P を組んで出力なしを確認する。P の論理移動先は area の外の既存ディレクトリ（例: `em-workflow-x/task0001`）、物理移動先は area 内の既存ディレクトリになる。
- [ ] TS-4（AC-4 / FR5）: area の外に置いたシンボリックリンクと `..` を組み合わせて論理パスを不在にし、物理パスが outside / area そのもの / `em-workflow-x` 配下になる 3 形で出力なしを確認する（`PATH_CASES` に追加）。

### Integration Tests
- [ ] TS-5（AC-5 / FR6, NFR1, NFR2, NFR3）: `python3 -m unittest discover -s tests` を実行し、全件成功を確認する。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 論理パスがファイルの場合: 物理パスで判定する（FR1）。
- [ ] 物理パスが存在しないパス・ファイルの場合: allow しない（FR5）。
- [ ] 物理パスが名前の接頭辞だけ一致する兄弟ディレクトリ（`em-workflow-x` 等）の場合: allow しない（FR5）。
- [ ] パス解決や判定で `OSError` / `ValueError` が起きた場合: False を返す（NFR4）。

### Documentation Review
- [ ] TS-6（AC-6 / FR7）: `bash_guard.py` の docstring と `command-execution-protocol.md` の該当箇所を読み、規則の記述を確認する（レビューで確認）。

### Performance Tests

該当なし。

## Security Considerations

- **Authentication:** 該当なし。
- **Authorization:** 論理パスが存在するディレクトリで area の外にある形は、物理パスが area 内でも allow しない（FR4）。物理パスで判定する場合も、area の外・area そのもの・接頭辞だけ一致する兄弟ディレクトリ・存在しないパス・ファイルは allow しない（FR5）。
- **Input Validation:** `<path>` は解決するだけで、子プロセスの作業ディレクトリや引数には使わない（NFR3）。
- **Data Protection:** 該当なし。
- **XSS Prevention:** 該当なし。
- **SQL Injection Prevention:** 該当なし。
- **CSRF Protection:** 該当なし。

## Error Handling

### Error Codes

該当なし（エラーコードの追加はない）。

### Error Flow

```
パス解決・判定で OSError / ValueError → is_below は False（判定なし側）
フック全体: 終了コード 0、標準エラー出力に書かない（NFR4）
```

## Performance Optimization

該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied（FR4, FR5）
- [ ] Documentation is complete（FR7）
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件はない）。

## Assumptions

- **A1:** 論理パスが存在するディレクトリのときは、現行どおり物理パスも area 内であることを要求する（FR2）。
- **A2:** フォールバックの条件は「論理パスが存在するディレクトリでない」とし、不在とファイルの両方を含む。
- **A3:** `/proc/self/cwd` のように解決先がプロセスごとに変わるパスは特別扱いしない。
- **A4:** `command-execution-protocol.md` の path 条件の記述更新（FR7）を範囲に含める。
- **A5:** 再発検出テストは既存の `tests/test_bash_guard_cd_prefix.py` の Fixture とケース表に追加する。

## Implementation Phases (if applicable)

該当なし。

## References

- `bash_guard.py`
- `command-execution-protocol.md`（Verbatim execution rule）
- `tests/test_bash_guard_cd_prefix.py`
- `tests/test_hook_classification_pin.py`
