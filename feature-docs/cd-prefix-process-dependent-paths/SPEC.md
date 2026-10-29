# Feature: cd-prefix-process-dependent-paths

## Overview

`em-workflow/hooks/bash_guard.py` の cd プレフィックス許可で、/proc 配下と /dev/fd 配下のパスをパス判定 `is_below(path, area)` の失敗として扱う。判定は書かれたパスと、論理パス・物理パスの解決の各段階とリンクの行き先で行い、`/proc/self/root/..` 前置の形も許可しなくなる。要件の詳細は `feature-docs/cd-prefix-process-dependent-paths/REQUIREMENTS.md` を参照する。

## Objectives

- cd プレフィックス許可で、解決するプロセスによって行き先が変わるパスを通した承認済みコマンドの実行を、`.claude/worktrees/em-workflow/` の外では一切許さない。攻撃シナリオ `cd "/proc/self/cwd/../tests" && <approved>` を成立させない。
- cd プレフィックス許可における /proc 配下と /dev/fd 配下のパスの扱いを、この SPEC で決め直す。`/proc/self/root/..` 前置の形は許可しなくなる。
- フックプロセスの cwd と入力の cwd が異なる状況の回帰テストを用意する。

## User Stories

ユーザーストーリーは定義しない。受け入れ基準は次のとおり。

**Acceptance Criteria:**
- [ ] AC-1: フックプロセスの cwd を、パスがエリアの下に解決される位置に置き、入力の cwd をメインツリー（および git worktree）にしたとき、`cd "/proc/self/cwd/../<name>" && <approved>` と `cd "/proc/self/cwd/<name>" && <approved>` は出力なしになる。
- [ ] AC-2: FR6 (2) のすべての形で `is_below` は False。最終的な解決先がエリアの真下にある形も含む。
- [ ] AC-3: エリア内の `proc`、`procfoo`、`dev/fd` という名前のディレクトリで `is_below` は True。
- [ ] AC-4: `cd "/proc/self/root/..<worktree のパス>" && <approved>` はメインツリーからも git worktree からも出力なしになり、`is_below("/proc/self/root/.." + <inside>)` は False。
- [ ] AC-5: 承認済み文字列を単独で実行する場合（完全一致）は引き続き allow。除外された形で、残りの部分が宣言済みかつ未承認のものは、cd の無いコマンドとして判定される（新たな deny は生まない）。
- [ ] AC-6: `bash_guard.py` の docstring と Verbatim execution rule が FR1 の規則を記述し、`TestPathConditionWording`、`STATEMENT_PATTERNS`（`tests/test_bash_guard_cd_prefix_operators.py`）、`tests/test_cd_prefix_exception_docs.py` が引き続き通る。
- [ ] AC-7: `python3 -m unittest discover -s tests` が通る。FR6 で変更する 2 件を除き、既存の期待値はすべて変わらず、`tests/test_bash_guard_cd_prefix.py` 870-915 行の検査は維持される。

## Technical Requirements

### Functional Requirements

- **FR1:** /proc または /dev/fd 配下のパスはパス判定に失敗する。`is_below(path, area)` は、次のいずれかが /proc 配下または /dev/fd 配下にあるとき False を返す。
    - (a) 書かれた `<path>`
    - (b) 論理パス（各 `..` を、その直前に書かれた構成要素と先に相殺したパス）を構成要素ごとに解決する途中で到達する各段階。辿った各リンクの行き先を含む。
    - (c) 物理パス（書かれたとおりのパス。各 `..` は、その時点で到達しているディレクトリに適用する）を構成要素ごとに解決する途中で到達する各段階。辿った各リンクの行き先を含む。

    判定は、最終的な realpath や normpath の結果だけに依らない。「/proc 配下」とは、パスを構成要素ごとに比べ、空の構成要素と `.` を無視したとき、最初の構成要素が `proc` であること。「/dev/fd 配下」とは、最初の 2 つの構成要素が `dev`、`fd` であること。/proc 自体、/dev/fd 自体も含む。字句上の変形も同じに扱う: `//proc/...`（POSIX の normpath は先頭の `//` を残す）、`/./proc/...`、`/x/../proc/...`、末尾のスラッシュ。/dev/fd がリンクである環境では /proc/self/fd へ辿られ、どちらの場合も /dev/fd は自身の名前で除外される。次は除外しない: `proc` で始まるだけの最初の構成要素（`/procfoo`）、ルート直下にない `proc`（または `dev/fd`）という名前のディレクトリ（エリア内にある普通の `proc` ディレクトリなど）。
- **FR2:** `/proc/self/root/..` 前置の形を許可しない。`cd "/proc/self/root/..<worktree の絶対パス>" && <approved>` は、他の /proc パスと同様に FR1 で除外される。先頭の /proc/self/root を書き換える例外は設けない。この決定は、フィーチャー is-below-physical-fallback の FR3/AC-1 を上書きする。同フィーチャーの SPEC は編集しない。
- **FR3:** 除外された形は cd プレフィックスが無いものとして判定する。FR1/FR2 で除外された形は、cd プレフィックスが無い場合とまったく同じに判定する: 完全一致で承認されていれば allow、`workflow.yaml` でコマンド全体が宣言されていれば未承認として deny、それ以外は出力なし。FR1/FR2 は新たな deny を生まない。
- **FR4:** 他の判定は変えない。次は変更しない: 構文・承認・演算子・安全側の条件、FR1 で除外されないパスに対する論理パス/物理パスの規則、`..` の前にある通常ファイル・存在しない構成要素・それらへのリンクで判定に失敗する規則（既存の「`..` の前の非ディレクトリ」検査を維持し、`tests/test_bash_guard_cd_prefix.py` 870-915 行にある `/proc/self/root/..` 前置の変形も維持する）、拒否パターンによる deny、完全一致による allow、未承認の deny、無関係なコマンドに対する無出力。
- **FR5:** 2 か所の記述を更新する。`bash_guard.py` のモジュール docstring にある cd プレフィックス段落の `path:` 項目と、`em-workflow/references/command-execution-protocol.md` の Verbatim execution rule にある path 項目に、FR1 の規則（/proc 配下または /dev/fd 配下のパスは、書かれたパス、両方の解決の各段階とリンクの行き先で判定し、パス判定に失敗する）を記述する。更新後の記述は既存のマッチャーを満たし続ける。
    - 文字列 `logical path`、`physical path`、`strictly below`、`existing directory`、`otherwise`、`both` を残す。
    - パターン ``logical path (...`..`...)`` と `physical path (...as written...)` を残す。
    - command-execution-protocol.md には `realpath` と `.claude/worktrees/em-workflow/` を残す。
    - 記述に `realpath of <path> is an existing directory` と `path's realpath is an existing directory` を含めない。
    - docstring の `cd prefix:` 段落は、`tests/test_bash_guard_cd_prefix_operators.py` の `STATEMENT_PATTERNS` に一致し続ける。
- **FR6:** 回帰テスト。`tests/test_bash_guard_cd_prefix.py` に次を追加・変更する。
    1. フックのサブプロセスのプロセス cwd が入力の cwd と異なる、フック単位のケース。`Fixture.run_hook` に任意指定のプロセス cwd 引数を追加し、既存の呼び出し元は変えない。ケースは、承認済み文字列の前に置いた `cd "/proc/self/cwd/../<name>"` と `cd "/proc/self/cwd/<name>"`。プロセス cwd は、フックプロセス内でパスがエリアの下に解決される位置に置く。入力の cwd がメインツリーの場合と git worktree の場合の両方で、出力なしになる。
    2. パス判定が False になるケース: `/proc/self/cwd/<name>`、`/proc/thread-self/cwd/<name>`、エリア内のディレクトリを開いた fd に対する `/proc/self/fd/<N>` と `/dev/fd/<N>`、`/proc/<自プロセスの pid>/cwd/<name>`、`/proc/self/root<inside>`、字句上の変形 `//proc/...`・`/./proc/...`・`/<既存ディレクトリ>/../proc/...`、エリア内にあり行き先が `/proc/self/cwd` のリンク、エリア内にあり行き先が `/dev/fd/<N>` のリンク、エリア内にあり行き先が `/proc/self` のリンクに `/cwd/<name>` を続けたもの。
    3. パス判定が True のままのケース: エリア内の `proc` という名前のディレクトリ、エリア内の `procfoo` という名前のディレクトリ、エリア内の `dev/fd` ディレクトリ。

    `/proc/self/root/..` の形を固定している既存テスト 2 件を変更する: `test_ac1_proc_self_root_dotdot_before_an_absolute_worktree_path_is_allowed`（689-696 行、ALLOW から SILENT に変える。テスト名とクラスの配置も新しい期待値に合わせる）と、`test_ac1_proc_self_root_dotdot_in_front_changes_nothing` の最後のアサーション（855-856 行、True から False に変える）。モジュール docstring の 39-40 行も合わせて変更する。/proc を必要とするテストは、/proc/self がディレクトリでない環境ではスキップする。

### Non-Functional Requirements

- **NFR1 - 依存ライブラリ:** `bash_guard.py` は標準ライブラリだけを import する（AC-7 の import テストで固定）。
- **NFR2 - 実行テキスト:** `bash_guard.py` の実行テキストに `status` という部分文字列を含めない（`test_ac7_hook_executable_text_has_no_status_substring` と `test_hook_classification_pin` で固定）。
- **NFR3 - 子プロセス:** `<path>` は解決するだけで、子プロセスの cwd や引数には使わない。パス判定は子プロセスを起動しない（`test_ac6_the_path_check_starts_no_child_process` で固定）。
- **NFR4 - エラー処理:** 解決または段階の検査中に OSError か ValueError が発生したら判定は False。フックは終了コード 0 で終わり、stderr に何も書かない。`os.path.realpath` または `os.path.isdir` が例外を送出しても `is_below` は False を返す（`test_ac5_a_resolution_error_makes_the_path_check_false`、787-795 行で固定）。`os.path.realpath` を strict を無視する寛容な版に差し替えても結果を保つ（`test_ac4_the_decision_does_not_depend_on_strict_mode_realpath`、905-915 行）。
- **NFR5 - リンク追跡の上限:** 段階的な解決で辿るリンクの数に上限を設ける。ループまたは上限超過で判定は False。
- **NFR6 - テストの分離:** 新しいテストは標準ライブラリだけを使い、実際の `~/.claude` の状態や実際の `workflow.yaml` を読まない（既存の Fixture による分離）。
- **NFR7 - シグネチャ:** `is_below(path, area)` のシグネチャと、その呼び出し元 `is_cd_prefixed_approved`（`bash_guard.py:307`）は変えない。

## Implementation Approach

### Architecture

**System Architecture:**

該当なし

**Component Diagram:**
```
is_cd_prefixed_approved (bash_guard.py:307)
  └── is_below(path, area)
        ├── 書かれたパスの検査 (FR1 (a))
        ├── 論理パスの段階的な解決と各段階・リンクの行き先の検査 (FR1 (b))
        ├── 物理パスの段階的な解決と各段階・リンクの行き先の検査 (FR1 (c))
        └── 既存の論理パス/物理パスの規則 (FR4)
```

### Data Flow

```
cd プレフィックス付きコマンド → is_cd_prefixed_approved → is_below(path, area)
  True  → 既存の cd プレフィックス許可の判定 (FR4)
  False → cd プレフィックスが無いものとして判定 (FR3)
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- is-below-physical-fallback: FR2 でこのフィーチャーの FR3/AC-1 を上書きする。`feature-docs/is-below-physical-fallback/SPEC.md`（A3、FR3、AC-1、TS-1）は過去の記録として残し、編集しない。

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1、NFR6）

### File Structure

```
em-workflow/
├── hooks/
│   └── bash_guard.py                       # is_below と module docstring の path: 項目 (FR1, FR2, FR5)
└── references/
    └── command-execution-protocol.md       # Verbatim execution rule の path 項目 (FR5)
tests/
├── test_bash_guard_cd_prefix.py            # テスト追加と既存 2 件の期待値変更 (FR6)
├── test_bash_guard_cd_prefix_operators.py  # STATEMENT_PATTERNS (FR5, 変更なし)
└── test_cd_prefix_exception_docs.py        # 記述の検査 (FR5, 変更なし)
```

## Declared Change Set

この節は手書きの一覧ではなく create-plan での導出を記す。上記のフィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上記のフィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つをデフォルトで宣言する。

- `feature-docs/cd-prefix-process-dependent-paths/**`
- `test-docs/cd-prefix-process-dependent-paths/**`

`feature-docs/cd-prefix-process-dependent-paths/**` には `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物が含まれる。これらはフェーズドキュメントと `references/phase-state.md` が生成・所有する。この節はそれらを引用するだけで、ルールは再掲しない。

`test-docs/cd-prefix-process-dependent-paths/**` には、タスクごとのテスト記録 `test-docs/cd-prefix-process-dependent-paths/{T}.tests.yaml` が含まれる。これは `implement-phase.md` が生成・所有する。この節はそれを引用するだけで、ルールは再掲しない。

この 2 つのデフォルトのエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことで除外されたとはみなさない。除外は意図的で明示的な絞り込みである。

この宣言はスーパーセット（SUPERSET）の主張である。検証時に観測される実際の変更集合は、宣言された集合に含まれる（CONTAINED IN）必要があり、等しい必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/cd-prefix-process-dependent-paths/` ディレクトリを生成しないが、その場合も宣言された `test-docs/cd-prefix-process-dependent-paths/**` は正しい。宣言されたパスが生成されないことは違反ではない。

## Test Scenarios

### Unit Tests
- [ ] TS-1: `/proc/self/cwd/<name>`、`/proc/self/cwd/../<name>`、`/proc/thread-self/cwd/<name>`、`/proc/self/fd/<N>`、`/dev/fd/<N>`（エリア内のディレクトリを開いた fd）、`/proc/<getpid()>/cwd/<name>`、`/proc/self/root<inside>`、`/proc/self/root/..<inside>` - `is_below` が False（FR1, FR2, FR6）
- [ ] TS-2: 字句上の変形 `//proc/self/cwd/<name>`、`/./proc/self/cwd/<name>`、`/<既存ディレクトリ>/../proc/self/cwd/<name>`、末尾のスラッシュ - `is_below` が False（FR1, FR6）
- [ ] TS-3: エリア内のリンク経由（行き先 `/proc/self/cwd`、行き先 `/dev/fd/<N>`、行き先 `/proc/self` に `/cwd/<name>` を続けたもの） - `is_below` が False（FR1, FR6）
- [ ] TS-4: `<area>/.../proc`、`<area>/.../procfoo`、`<area>/.../dev/fd`、および既存のエリア内の形と `@HOP@/../sub` の形 - `is_below` が True（FR1, FR4, FR6）
- [ ] TS-5: 既存の NUL、解決エラー、寛容な realpath のケース - 引き続き通る（FR4, NFR4）

### Integration Tests
- [ ] TS-6: プロセス cwd が入力の cwd と異なるフックのサブプロセスで、承認済み文字列の前に置いた `/proc/self/cwd` の形 - メインツリーからも git worktree からも出力なし（FR1, FR3, FR6）
- [ ] TS-7: worktree のパスの前に置いた `/proc/self/root/..` 前置 - 出力なし（変更後のテスト）（FR2, FR3, FR6）
- [ ] TS-8: 既存のフック単位の PATH_CASES、演算子、安全側のテスト群 - 変わらない（FR4）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

該当なし

### Edge Cases
- [ ] TS-9: `TestPathConditionWording`、`TestAc6DocstringStatesTheConditions`、`test_cd_prefix_exception_docs` - 拡張後の記述で引き続き通る（FR5）
- [ ] `/procfoo` のように `proc` で始まるだけの最初の構成要素と、ルート直下にない `proc`・`dev/fd` ディレクトリ - 除外しない（TS-4 で確認）
- [ ] /proc 自体、/dev/fd 自体 - 除外する（FR1）
- [ ] リンクのループ、辿るリンク数の上限超過 - 判定は False（NFR5）
- [ ] 解決または段階の検査中の OSError・ValueError - 判定は False。フックは終了コード 0、stderr に何も書かない（NFR4）

### Performance Tests

該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** /proc 配下または /dev/fd 配下のパスを経由する cd プレフィックスは、パス判定に失敗し、cd プレフィックスが無いものとして判定される（FR1, FR2, FR3）。
- **Input Validation:** `<path>` は解決するだけで、子プロセスの cwd や引数には使わない（NFR3）。段階的な解決で辿るリンクの数に上限を設ける（NFR5）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

```
解決・段階の検査中の OSError / ValueError、リンクのループ・上限超過
  → is_below が False → cd プレフィックスが無いものとして判定 (FR3)
  → フックは終了コード 0、stderr に何も書かない (NFR4)
```

## Performance Optimization

### Performance Goals

該当なし

### Optimization Strategies

該当なし

### Caching Strategy

該当なし

## Success Criteria

- [ ] すべての機能要件が実装され、テストされている
- [ ] すべてのテストシナリオが通る
- [ ] 非機能要件を満たしている
- [ ] 記述が更新されている（FR5）
- [ ] コードレビューが完了している
- [ ] `python3 -m unittest discover -s tests` が通る（AC-7）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Assumptions

- A1: 要件は、Claude Code の下でフックプロセスの cwd が Bash の cwd と実際に異なるかに依存しない。除外はどちらの場合も成り立つ。
- A2: 決定はこの SPEC に記録する。`feature-docs/is-below-physical-fallback/SPEC.md`（A3、FR3、AC-1、TS-1）は過去の記録として残し、編集しない。
- A3: 他の cd プレフィックスの判定はすべて変わらず、既存テストで固定される（FR4）。
- A4: /proc 以外のパスにマウント（バインドマウントを含む）された procfs と、/proc 以外のパスにある他のプロセスごとのファイルシステムは対象外。FR1 は /proc と /dev/fd の構成要素だけで判定する。
- A5: フックの判定から Bash の cd までの間にリンクが変更される場合は、このフィーチャー以前と同じく対象外。

## References

- 要件定義書: `feature-docs/cd-prefix-process-dependent-paths/REQUIREMENTS.md`
- 上書きする決定を含む SPEC: `feature-docs/is-below-physical-fallback/SPEC.md`
- Verbatim execution rule: `em-workflow/references/command-execution-protocol.md`
