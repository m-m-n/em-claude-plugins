# Feature: codex-guard-delim-brace-quote-per-shell

## Overview

codex-hook-interactive-guard の、入れ子の -c 文字列のヒアドキュメントの区切り語の位置にある `${ ... }` の読みを、-c 文字列を直接持つシェルの種類で決める。bash は書かれたままの形（FR2）、sh・ksh は bash の読みと今の読みの 2 通り（FR3）、zsh・dash とフックが受け取るコマンドそのものは今の読み（引用除去）のまま。要件の原文は [REQUIREMENTS.md](REQUIREMENTS.md) にある。

## Objectives

- codex-hook-interactive-guard が入れ子の bash / sh / ksh の -c 文字列で、ヒアドキュメントの区切り語の `${ ... }` をそのシェルの規則で読み、終端行の後の `python3 -i` などの対話起動を見逃さないようにする。
- sh の実体が bash か dash か分からない -c 文字列でも、どちらの規則で読んでも終端行の後にある起動を deny する。

## Acceptance Criteria

- [ ] AC1: 再現手順 TS1 が deny になる。（FR1、FR2 / TS1）
- [ ] AC2: bash の -c 文字列では、範囲の外に引用の無い区切り語の `${ ... }` が書かれたまま（単引用符の外のバックスラッシュ＋改行だけ除いて）登録され、その形の終端行の後の起動は deny、引用を除いた形の行では本文が閉じない。範囲の外のバックスラッシュ＋改行は取り除かれ、引用に数えない。`<<-` では先頭のタブを除いて比べる。版数つき・env 経由・`--posix` の bash も同じ。（FR1、FR2 / TS2、TS3、TS4、TS5、TS6、TS7、TS8、TS9、TS15、TS16、TS17、TS32）
- [ ] AC3: bash の -c 文字列で、区切り語の `${ ... }` の範囲の外（前でも後ろでも）に引用があるときは、語全体の引用を除いた形が登録される。（FR2 / TS10、TS11、TS12、TS13）
- [ ] AC4: bash の読みでも、範囲の中の引用されていない `$'` は判定不能のまま。（FR2 / TS14）
- [ ] AC5: sh・ksh（パス付きを含む）の -c 文字列では、bash の読みと今の読みのどちらかで終端行の後にある起動が deny になる。片方の読みが判定不能でも他方の deny が出る。両方の読みで本文の中にある起動は deny にならない。（FR1、FR3 / TS18、TS19、TS20、TS21、TS22、TS23、TS26、TS27）
- [ ] AC6: dash -c、zsh -c、フックが受け取るコマンドそのものの区切り語の読みは変わらない。（FR1 / TS24、TS25、TS28、TS29）
- [ ] AC7: 読みは -c 文字列を直接持つシェルの種類で決まる。（FR1 / TS30、TS31）
- [ ] AC8: 2 つのコピーがバイト単位で同一で、`python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 -m unittest discover -s tests` がどちらも成功する。（FR4、FR5、FR6、NFR1、NFR2、NFR3、NFR4、NFR5）

## Technical Requirements

### Functional Requirements

- **FR1:** -c 文字列の種類ごとの区切り語の読み。区切り語（`<<` / `<<-` の目標の語）の位置の `${ ... }` の読みを、-c 文字列を直接持つシェルの種類で決める。bash（bash5.2 など数字と `.` の接尾辞つき、パス付き、env などの option なしラッパー経由、`bash --posix` を含む）は FR2 の bash の読みだけで読む。zsh と dash（接尾辞つきを含む）は今の読み（引用除去）だけで読む。sh・ksh（接尾辞つきを含む）は FR3 の 2 通りの読みで読む。フックが受け取るコマンドそのもの（入れ子でない文字列）は今の読みのまま変えない。種類は今と同じく直接持つシェルのコマンド語で決まり、bash -c の中の zsh -c の文字列は zsh として読む。coproc / repeat の読みと、両スイッチを切った読み直しの有無は、今の種類（bash / zsh / unknown）のまま変えない。
- **FR2:** bash の読み。区切り語の語に `${ ... }` の範囲の外の引用（`'` `"` `\` の引用単位）が 1 つも無いとき、各 `${ ... }` の範囲を `"`・`'`・`\` を含めて書かれたまま区切り語にする。ただし範囲の中の、単引用符の外にあるバックスラッシュ＋改行は取り除く（二重引用符の中のものも取り除く）。範囲の外のバックスラッシュ＋改行は取り除き、範囲の外の引用に数えない。区切り語に直接書かれた `$( ... )` の中の引用は、範囲の外の引用に数えない。範囲の外に引用が 1 つでもあるときは、範囲の前にあるか後ろにあるかによらず、今と同じく語全体の引用を除いた形を登録する。範囲の閉じの探し方（前の SPEC の FR2）と、範囲の中の引用されていない `$'` / `$"` の判定不能（前の SPEC の FR3）、範囲の外の引用されていない `$'` / `$"` の判定不能（前の SPEC の FR4）は変えない。例: `${v:-"x"}` → `${v:-"x"}`、`${v:-'x'}` → `${v:-'x'}`、`${v:-\x}` → `${v:-\x}`、`${v:-"a<バックスラッシュ><改行>b"}` → `${v:-"ab"}`、`P<バックスラッシュ><改行>${v:-"x"}` → `P${v:-"x"}`、`$(echo "P")${v:-"x"}` → `$(echo "P")${v:-"x"}`、`'P'${v:-"x"}` → `P${v:-x}`、`${v:-"x"}""` → `${v:-x}`。
- **FR3:** sh / ksh の 2 通りの読み。sh・ksh の -c 文字列は、区切り語の位置の `${ ... }` を bash の読み（FR2）で読んだ場合と今の読み（引用除去）で読んだ場合の 2 通りで、文字列全体を独立に読む。どちらか一方でも deny になれば deny を出す。2 通りの読みで区切り語の文字列が一致する文字列では 2 回目を読まない。各読みには今の読み直し（両スイッチを切った再読）とチェックポイントの規則をそれぞれ当て、片方の読みが判定不能でも他方の deny を出す。区切り語ごとの組み合わせは作らず、文字列全体に 1 つの規則を当てる 2 回の読みに限る。
- **FR4:** 区切り語の位置にない読みは変えない。区切り語の位置にない `${ ... }` / `$'` / `$"`、`<<<` と `<` のリダイレクト先、区切り語の中の二重引用符の中の `${ ... }`、区切り語の位置の `$( ... )`、匿名関数の引数の `( ... )` の範囲の引用除去は、どの種類でも今の読みのまま変えない。
- **FR5:** NESTED_READ_LIMIT の数え方。2 通りの読みで読む文字列も、今の読み直しと同じく、その文字列の長さで 1 回だけ NESTED_READ_LIMIT に数える。その文字列の中にある入れ子の -c 文字列は、読むたびに数える。
- **FR6:** 回帰テスト。`tests/test_codex_hook_interactive_guard.py` の CASES に、「Test Scenarios」の各行を `(期待する判定, ラベル, コマンド)` の形で足す。期待する判定は deny か silent。CASES は今のテストで 2 つのコピーの両方に流す。

### Non-Functional Requirements

- **NFR1 - 2 つのコピーの同一性:** `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は同じ変更の中で一緒に直し、バイト単位で同一に保つ。
- **NFR2 - 線形時間:** 1 つの文字列を読む回数は、2 通りの読みとそれぞれの読み直しを合わせて定数回に限り、各読みは線形時間で行う。長さ上限や時間に関する今のテストは通る。
- **NFR3 - 既存の構造テストの保持:** `_scan` の入れ子の parse 呼び出しを囲む try が 1 つであること（TestNestedParseErrorContainment）、再帰しないこと（TestNoRecursion）、フックのコマンドの読み直しが失敗したとき初回の読みに戻ること（TestRereadFallback）、NESTED_READ_LIMIT の今のテスト（TestNestedReadLimit の TS32 を含む）は変えずに通る。
- **NFR4 - docstring の整合:** モジュール docstring の判定手順（step 7 の種類の説明、step 9 の読みの回数、区切り語の位置の読みの説明）を FR1 から FR5 と合わせる。docstring の marker を確かめる今のテスト（DELIMITER_RANGE_MARKERS、CHECKPOINT_MARKERS など）は変えずに通る。
- **NFR5 - 既存ケースの保持:** CASES の今の deny / silent の行は消さず、期待する判定も変えない。
- **NFR6 - 標準ライブラリのみ:** フックとテストは Python 標準ライブラリだけを使う。
- **NFR7 - version:** プラグインの version は変えない。

## Implementation Approach

### Reading by shell kind

| -c 文字列を直接持つシェル | 区切り語の `${ ... }` の読み | 要件 |
|---|---|---|
| bash（数字と `.` の接尾辞つき、パス付き、option なしラッパー経由、`bash --posix` を含む） | bash の読みだけ | FR1、FR2 |
| zsh、dash（接尾辞つきを含む） | 今の読み（引用除去）だけ | FR1 |
| sh・ksh（接尾辞つきを含む） | bash の読みと今の読みの 2 通り | FR1、FR3 |
| フックが受け取るコマンドそのもの | 今の読みのまま | FR1 |

### Dependencies

**External Dependencies:**
- Python 標準ライブラリのみ（NFR6）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1〜FR5、NFR4
em-review/scripts/codex-hook-interactive-guard.py     # em-workflow 側とバイト単位で同一（NFR1）
tests/test_codex_hook_interactive_guard.py            # CASES に TS1〜TS32 を足す（FR6）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-delim-brace-quote-per-shell/**`
- `test-docs/codex-guard-delim-brace-quote-per-shell/**`

`feature-docs/codex-guard-delim-brace-quote-per-shell/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-delim-brace-quote-per-shell/**` covers `test-docs/codex-guard-delim-brace-quote-per-shell/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-delim-brace-quote-per-shell/` directory at all; the declared
`test-docs/codex-guard-delim-brace-quote-per-shell/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

各行は CASES の `(expected, label, command)`。

**command の作り方**: command は lines を改行でつないだ文字列 S から作る。wrap が空なら command = S。wrap が `[h1, ..., hk]`（外側が先）なら、内側から順に `S = hj + " -c " + shlex.quote(S)` を j = k から 1 まで当てたものが command。

```python
S = "\n".join(lines)
for h in reversed(wrap):
    S = h + " -c " + shlex.quote(S)
command = S
```

lines は JSON 文字列で、escape を解いた文字がそのままコマンドの文字（`"\\"` は 1 個のバックスラッシュ、`"\t"` はタブ）。各行の lines は JSON 配列で書き、そのまま Python のリストとして写せる。「before」は今のコードでの判定。

- [ ] TS1: expected `deny`（before `silent`）/ 要件 FR1, FR2
    - label: `bash -c の区切り語の ${...} を書かれたまま登録し、終端行の後の起動は deny (再現手順)`
    - wrap: `[]`
    - lines:
      ```json
      ["bash -c 'false && cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i'"]
      ```
- [ ] TS2: expected `silent`（before `deny`）/ 要件 FR2
    - label: `bash -c では引用を除いた ${...} の行で本文が閉じない`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i", "${v:-\"x\"}"]
      ```
- [ ] TS3: expected `deny`（before `silent`）/ 要件 FR2
    - label: `bash -c の ${...} の単引用符を残す`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-'x'}", "${v:-'x'}", "python3 -i"]
      ```
- [ ] TS4: expected `deny`（before `silent`）/ 要件 FR2
    - label: `bash -c の ${...} のバックスラッシュを残す`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-\\x}", "${v:-\\x}", "python3 -i"]
      ```
- [ ] TS5: expected `deny`（before `silent`）/ 要件 FR2
    - label: `bash -c の ${...} の二重引用符の中の } で閉じず、書かれたまま登録する`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-\"a}b\"}", "${v:-\"a}b\"}", "python3 -i"]
      ```
- [ ] TS6: expected `deny`（before `silent`）/ 要件 FR2
    - label: `bash -c の入れ子の ${...} を書かれたまま登録する`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${a:-${b:-\"x\"}}", "${a:-${b:-\"x\"}}", "python3 -i"]
      ```
- [ ] TS7: expected `deny`（before `deny`）/ 要件 FR2
    - label: `bash -c の ${...} の中の $( ) は書かれたまま`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-$(echo \"x\")}", "${v:-$(echo \"x\")}", "python3 -i"]
      ```
- [ ] TS8: expected `deny`（before `deny`）/ 要件 FR2
    - label: `bash -c の ${...} の引用の外のバックスラッシュ＋改行は取り除く`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-\\", "x}", "${v:-x}", "python3 -i"]
      ```
- [ ] TS9: expected `deny`（before `silent`）/ 要件 FR2
    - label: `bash -c の ${...} の二重引用符の中のバックスラッシュ＋改行は取り除き、引用は残す`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-\"a\\", "b\"}", "${v:-\"ab\"}", "python3 -i"]
      ```
- [ ] TS10: expected `deny`（before `deny`）/ 要件 FR2
    - label: `bash -c で ${...} の前に引用があれば語全体の引用を除く`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<'P'${v:-\"x\"}", "P${v:-x}", "python3 -i"]
      ```
- [ ] TS11: expected `deny`（before `deny`）/ 要件 FR2
    - label: `bash -c で ${...} の後ろに引用があれば語全体の引用を除く`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}\"\"", "${v:-x}", "python3 -i"]
      ```
- [ ] TS12: expected `silent`（before `silent`）/ 要件 FR2
    - label: `bash -c で ${...} の後ろに引用があれば書かれたままの範囲の行では本文が閉じない`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}\"\"", "${v:-\"x\"}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS13: expected `deny`（before `deny`）/ 要件 FR2
    - label: `bash -c で ${...} の前の二重引用符があれば範囲の単引用符も除く`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<\"P\"${v:-'x'}", "P${v:-x}", "python3 -i"]
      ```
- [ ] TS14: expected `silent`（before `silent`）/ 要件 FR2
    - label: `bash -c でも ${...} の中の引用されていない $' は判定不能`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<${v:-$'x'}", "${v:-'x'}", "python3 -i"]
      ```
- [ ] TS15: expected `deny`（before `silent`）/ 要件 FR2
    - label: `bash -c の <<- は先頭タブを除いて書かれたままの ${...} と比べる`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<-${v:-\"x\"}", "\t${v:-\"x\"}", "python3 -i"]
      ```
- [ ] TS16: expected `deny`（before `silent`）/ 要件 FR1
    - label: `env を経由した版数つきの bash も bash の読み`
    - wrap: `["env bash5.2"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]
      ```
- [ ] TS17: expected `deny`（before `silent`）/ 要件 FR1
    - label: `bash --posix も bash の読み`
    - wrap: `["bash --posix"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]
      ```
- [ ] TS18: expected `deny`（before `silent`）/ 要件 FR3
    - label: `sh -c は bash の読みの終端行の後の起動を deny（今の読みは判定不能）`
    - wrap: `["sh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]
      ```
- [ ] TS19: expected `deny`（before `deny`）/ 要件 FR3
    - label: `sh -c は今の読みの終端行の後の起動を deny（bash の読みは判定不能）`
    - wrap: `["sh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i"]
      ```
- [ ] TS20: expected `deny`（before `silent`）/ 要件 FR3
    - label: `sh -c は書かれたままの終端行の後で引用を除いた行の前の起動を deny`
    - wrap: `["sh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS21: expected `deny`（before `deny`）/ 要件 FR3
    - label: `sh -c は引用を除いた終端行の後で書かれたままの行の前の起動を deny`
    - wrap: `["sh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i", "${v:-\"x\"}"]
      ```
- [ ] TS22: expected `silent`（before `silent`）/ 要件 FR3
    - label: `sh -c の両方の読みで本文の中にある起動は deny しない`
    - wrap: `["sh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "python3 -i", "${v:-x}", "${v:-\"x\"}"]
      ```
- [ ] TS23: expected `deny`（before `silent`）/ 要件 FR1, FR3
    - label: `パス付きの sh も 2 通りの読み`
    - wrap: `["/bin/sh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS24: expected `silent`（before `silent`）/ 要件 FR1
    - label: `dash -c は今の読みだけで、書かれたままの行では本文が閉じない`
    - wrap: `["dash"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS25: expected `deny`（before `deny`）/ 要件 FR1
    - label: `dash -c は引用を除いた終端行の後の起動を deny`
    - wrap: `["dash"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i"]
      ```
- [ ] TS26: expected `deny`（before `silent`）/ 要件 FR1, FR3
    - label: `ksh -c も 2 通りの読みで、書かれたままの終端行の後の起動を deny`
    - wrap: `["ksh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS27: expected `deny`（before `deny`）/ 要件 FR1, FR3
    - label: `ksh -c も 2 通りの読みで、引用を除いた終端行の後の起動を deny`
    - wrap: `["ksh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-x}", "python3 -i", "${v:-\"x\"}"]
      ```
- [ ] TS28: expected `silent`（before `silent`）/ 要件 FR1
    - label: `zsh -c の区切り語の読みは変えない`
    - wrap: `["zsh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS29: expected `silent`（before `silent`）/ 要件 FR1
    - label: `フックが受け取るコマンドそのものの区切り語の読みは変えない`
    - wrap: `[]`
    - lines:
      ```json
      ["cat <<${v:-'x'}", "${v:-'x'}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS30: expected `deny`（before `silent`）/ 要件 FR1
    - label: `zsh -c の中の bash -c の文字列は bash の読み`
    - wrap: `["zsh", "bash"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i"]
      ```
- [ ] TS31: expected `silent`（before `silent`）/ 要件 FR1
    - label: `bash -c の中の zsh -c の文字列は zsh の読み`
    - wrap: `["bash", "zsh"]`
    - lines:
      ```json
      ["cat <<${v:-\"x\"}", "${v:-\"x\"}", "python3 -i", "${v:-x}"]
      ```
- [ ] TS32: expected `deny`（before `silent`）/ 要件 FR2
    - label: `bash -c の ${...} の外のバックスラッシュ＋改行は取り除き、引用に数えない`
    - wrap: `["bash"]`
    - lines:
      ```json
      ["cat <<P\\", "${v:-\"x\"}", "P${v:-\"x\"}", "python3 -i"]
      ```

### Integration Tests

- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が成功する（AC8）
- [ ] `python3 -m unittest discover -s tests` が成功する（AC8）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 範囲の後ろにある引用（TS11、TS12）: 語全体の引用を除く
- [ ] 二重引用符の中のバックスラッシュ＋改行（TS9）: 取り除いて引用は残す
- [ ] 範囲の外のバックスラッシュ＋改行（TS32）: 取り除き、引用に数えない
- [ ] 片方の読みだけが判定不能（TS18、TS19）: 他方の deny を出す
- [ ] `<<-` の先頭タブ（TS15）: タブを除いてから比べる

### Performance Tests

- [ ] 長さ上限や時間に関する今のテストが通る（NFR2、NFR3）

## Assumptions

- A-1: ksh / mksh は未導入で未実測。2 通りの読みで見逃しを防げるのは、そのシェルが bash の規則か今の読み（引用除去）のどちらかに従う場合に限る。
- A-2: 2 通りの読みで読む文字列も、その長さで 1 回だけ NESTED_READ_LIMIT に数える（今の読み直しと同じ）。入れ子の -c 文字列が両方の読みに現れるときは、読むたびに数える。TestNestedReadLimit の TS32（sh -c の読み直しを 1 回と数える）は変えずに通る。
- A-3（確認済み）: bash 5.3.9 で実測して確かめた。`cat <<P<バックスラッシュ><改行>${v:-"x"}` は `P${v:-"x"}` の行で閉じる（範囲の外のバックスラッシュ＋改行は取り除かれ、引用に数えない）。`cat <<$(echo "P")${v:-"x"}` は `$(echo "P")${v:-"x"}` の行で閉じ、`$(echo P)${v:-x}` の行では閉じない（区切り語に直接書かれた `$( ... )` の中の引用は範囲の外の引用に数えない）。TS8 と TS9 の終端も同じく実測で確かめた。
- A-4: bash の読みでも範囲の中・外の引用されていない `$'` / `$"` は判定不能のまま（回答どおり）。bash は `${v:-$'x'}` を `${v:-'x'}` で閉じるが、この形の見逃しは受け入れる。
- A-5: 区切り語の位置の匿名関数の引数の `( ... )` の範囲の引用除去は zsh の構文の読みで、どの種類でも変えない。
- A-6: フックのコマンドそのものは今の読み（引用除去）だけで読み、2 通りの読みにしない（回答どおり）。TestRereadFallback の、既定の種類での parser の数が 2 であることは変わらない。
- A-7: bash 5.3.9 / bash --posix / dash / zsh 5.9 での終端行の閉じ方はオーケストレーターの実測に従う。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1〜AC8 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（status: tbd の要件は無い）

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
