# Feature: cd-prefix-non-directory-dotdot

## Overview

bash_guard.py の cd 前置形の判定で、is_below() の物理パス側の判定を、書かれたとおりのパスで行うように直す。
通常ファイルや存在しない要素の後ろに `..` が続くパスは、cd 前置形として許可しない。
許可から外れた形は cd 前置形でない場合と同じように判定し、新たな deny は出さない。

## Objectives

- bash_guard.py の cd 前置形の判定を、Bash の cd が実際に移動できる場所と一致させる。
- 通常ファイルや存在しない要素の後ろに `..` が続くパスは Bash の cd が「Not a directory」または「No such file or directory」で失敗するので、cd 前置形の許可に含めない。

## Acceptance Criteria

- [ ] **AC-1:** 通常ファイルや存在しない要素の後ろに `..` が続くパスは、論理パスが存在する形でも存在しない形でも、cd 前置形として許可されない（出力なし）。（対象: FR1, FR2, FR3, FR4）
- [ ] **AC-2:** その形を silent のケースとして tests/test_bash_guard_cd_prefix.py の PATH_CASES に加えたテストがあり、通る。（対象: FR5, FR6）
- [ ] **AC-3:** tests/test_bash_guard_cd_prefix.py にある既存の cd 前置形のテスト（ALLOW_CASES、FALLBACK_ALLOW_CASES、/proc/self/root の AC-1、TM1/TM2、NUL、文言、標準ライブラリのみ）がすべて通る。（対象: NFR2, NFR3, NFR4）
- [ ] **AC-4:** 判定が os.path.realpath の strict の挙動に依存していない（テストが realpath の strict の挙動を前提にしていない）。（対象: NFR1）

## Technical Requirements

### Functional Requirements
- **FR1:** 物理パスの存在判定は書かれたとおりのパスで行う。is_below() の物理パス側の判定で、書かれたパスの途中にある `..` の直前の要素が既存のディレクトリでない場合（通常ファイル、存在しない要素、ファイルや存在しない先を指すリンク）、物理パスは既存のディレクトリでないものとして扱う。物理パスの場所は、OS が書かれたとおりのパスを解決できるときだけ比べる。
- **FR2:** 論理パスが存在する形も許可しない。論理パス（各 `..` を直前の要素と字句的に打ち消したパス）が既存ディレクトリになる形（例: `<area>/task0001/does-not-exist/..`、`<area>/afile/../task0001`）でも、FR1 の条件で物理パスがディレクトリでなければ cd 前置形を許可しない。
- **FR3:** 論理パスが存在しない形も許可しない。論理パスが存在しない形（`/proc/self/root/..` を前に置く形など）で、物理パスへのフォールバック分岐に入った場合も、FR1 の条件で物理パスがディレクトリでなければ許可しない。
- **FR4:** 許可しない形は判定なしにする。FR1〜FR3 で許可から外れた cd 前置形は、cd 前置形でない場合と同じように判定する（新たな deny は出さない）。承認済みの文字列が後ろに続く場合は出力なし（silent）になる。
- **FR5:** PATH_CASES に silent のケースを加える。tests/test_bash_guard_cd_prefix.py の PATH_CASES に、通常ファイルの後ろに `..` が続く形と、存在しない要素の後ろに `..` が続く形を、期待値 silent で加える。どちらも、変更前の判定なら allow になる形にする（論理パスと realpath の結果がどちらもエリアより下の既存ディレクトリになる形）。
- **FR6:** `/proc/self/root/..` を前に置く形のテスト。`/proc/self/root/..` の後ろに、通常ファイルの後ろに `..` が続く絶対パスを置く形を silent として確かめるテストがある。`/proc/self/root` がディレクトリでない環境ではスキップする（既存の AC-1 のテストと同じ扱い）。

### Non-Functional Requirements
- **NFR1 - Python の版に依存しない:** 判定は os.path.realpath(path, strict=True) が途中の通常ファイルを拒否するかどうかに依存しない。カーネルによる、書かれたとおりのパスの解決（stat 系の呼び出し）など、版によって変わらない手段で途中の通常ファイルを見分ける。
- **NFR2 - 標準ライブラリだけを使う:** フックもテストも標準ライブラリだけを import する（既存の TestAc7StandardLibraryOnly）。フックの実行コードに `status` という部分文字列を入れない。
- **NFR3 - 解決エラーは False:** パスの解決で OSError または ValueError（NUL を含むパスなど）が起きたら、is_below() は例外を出さずに False を返す（既存の TestNulInPath）。
- **NFR4 - パスを子プロセスに渡さない:** `<path>` は解決するだけで、子プロセスの作業ディレクトリや引数には使わない（既存の test_ac1_no_child_process_uses_the_prefixed_path）。

## Implementation Approach

### Architecture

変更は is_below() の物理パス側の判定と、tests/test_bash_guard_cd_prefix.py へのテストケースの追加に限る。UI はなく、デザインの工程は行わない。

### Assumptions

- **A1:** Bash の cd は、論理パスの各 `..` の直前の要素がディレクトリであることを確かめ（canonpath の PATH_CHECKDOTDOT）、失敗したら書かれたとおりのパスで chdir する。カーネルは `<通常ファイル>/..` と `<存在しない要素>/..` を ENOTDIR / ENOENT で拒否する。なので、書かれたとおりのパスが OS の解決でディレクトリにならない形では、Bash の cd はどちらの経路でも失敗する。
- **A2:** 論理パス側の判定（os.path.normpath を使う、論理パスが既存ディレクトリなら両方がエリアより下であることを求める）は変えない。論理パスの `..` の直前がディレクトリでないだけで、物理パスがエリアより下に解決できる形は、変更前と同じく安全側（許可しないか、両方がエリアより下のときだけ許可）に倒れるので、このタスクでは許可を広げない。
- **A3:** is_below(path, area) の名前と引数は変えない。tests/test_bash_guard_cd_prefix.py の TestNulInPath がモジュールを読み込んで直接呼び、os.path.realpath と os.path.isdir を差し替えた状態でも False になることを確かめている。
- **A4:** フックの docstring と command-execution-protocol.md の「Verbatim execution rule」は、物理パスを「書かれたとおりのパスの realpath、各 `..` はすでに解決したディレクトリに対して効く」と定義していて、コードを直せば記述どおりの判定になる。なので文言の変更は必須にしない。変更する場合は、TestPathConditionWording が見る語（logical path / physical path / strictly below / existing directory / otherwise / both、`logical path (... .. ...)`、`physical path (... as written ...)`）を残し、`realpath of <path> is an existing directory` という書き方は使わない。
- **A5:** テストのフィクスチャで要るのは、既存の FIX.file（`<area>/afile`）、FIX.missing（`<area>/does-not-exist`）、FIX.inside（`<area>/task0001`）だけ。ファイルを指すリンクや壊れたリンクの後ろに `..` が続く形は、加えてもよいが受け入れ条件には入れない。
- **A6:** `/proc/self/cwd` のようなプロセスに依存するパスはスコープ外（別タスク）。
- **A7:** em-workflow/ 配下を変えるが、version は変えない（patch は main への push 時に Actions が上げる）。

### Dependencies

**Internal Dependencies:**
- tests/test_bash_guard_cd_prefix.py: 既存の ALLOW_CASES、PATH_CASES、FALLBACK_ALLOW_CASES、TestNulInPath、TestPathConditionWording、TestAc7StandardLibraryOnly
- command-execution-protocol.md: 「Verbatim execution rule」（A4）

**External Dependencies:**
- なし（標準ライブラリのみ、NFR2）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/cd-prefix-non-directory-dotdot/**`
- `test-docs/cd-prefix-non-directory-dotdot/**`

`feature-docs/cd-prefix-non-directory-dotdot/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/cd-prefix-non-directory-dotdot/**` covers `test-docs/cd-prefix-non-directory-dotdot/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/cd-prefix-non-directory-dotdot/` directory at all; the declared
`test-docs/cd-prefix-non-directory-dotdot/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] **TS-1:** `cd "<area>/afile/../task0001" && make test` は silent。（論理パスは `<area>/task0001` で既存ディレクトリ。変更前は realpath が `afile/..` を字句的に消すので allow）（対象: FR1, FR2, FR4, FR5）
- [ ] **TS-2:** `cd "<area>/task0001/does-not-exist/.." && make test` は silent。（論理パスは `<area>/task0001`。変更前は allow）（対象: FR1, FR2, FR4, FR5）
- [ ] **TS-3:** `cd "/proc/self/root/..<area>/afile/../task0001" && make test` は silent。`/proc/self/root` がディレクトリでなければスキップ。（論理パスは存在せず、フォールバック分岐に入る）（対象: FR1, FR3, FR4, FR6）
- [ ] **TS-4:** フィクスチャの確認: 加えた各形について、書かれたとおりのパスが OS の解決で既存ディレクトリにならない（os.stat が NotADirectoryError / FileNotFoundError を出す、または os.path.isdir が False）一方、os.path.realpath（strict=False）の結果はエリアより下の既存ディレクトリになる。これで、変更前なら allow になっていたことを確かめる。（対象: FR5, NFR1）
- [ ] **TS-5:** 既存の FALLBACK_ALLOW_CASES（リンク、`..`、名前の順の形）と /proc/self/root の AC-1 は allow のまま。`..` の直前がディレクトリへのリンクなので、書かれたとおりのパスを OS が解決できる。（対象: FR1）

### Integration Tests
- [ ] **TS-6:** 回帰確認として `python3 -m unittest tests.test_bash_guard_cd_prefix` と `python3 -m unittest discover -s tests` が通る。（対象: NFR2, NFR3, NFR4）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

## Error Handling

- パスの解決で OSError または ValueError が起きたら、is_below() は False を返す（NFR3）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし
