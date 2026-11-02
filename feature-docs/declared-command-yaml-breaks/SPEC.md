# Feature: declared-command-yaml-breaks

## Overview

workflow.yaml の `*_command` で、引用符の内側の端に U+0085 を置いて宣言したとき（YAML 1.1 では空白 1 つになる）の扱いを直す。その YAML 解析結果をコマンドとして渡されても、`bash_guard` のフックは未承認として拒否し、判定なしにはしない。U+00A0 についての approval-unicode-whitespace FR8 の決定はそのまま残し、対策と残る食い違いを文書に書き残す。

## Objectives

- workflow.yaml の `*_command` で、引用符の内側の端に U+0085 を置いて宣言したとき（YAML 1.1 では空白 1 つになる）の扱いを直す。その YAML 解析結果をコマンドとして渡されても、`bash_guard` のフックは未承認として拒否する。判定なしにはしない。
- U+00A0 についての approval-unicode-whitespace FR8 の決定はそのまま残す。誤って拒否する範囲は、YAML の改行文字 3 つ（U+0085、U+2028、U+2029）にとどめる。
- 上流に修正がないので、この対策と残る食い違いを文書に書き残す。

## Technical Requirements

### Functional Requirements

- **FR1: 宣言済みコマンドに 2 つ目の形を足す** — `em-workflow/hooks/bash_guard.py` の `declared_commands` は、抽出した値（`strip_yaml_quotes` の後で、空でも `"null"` でも `"~"` でもない値）ごとに、宣言集合へ次の 2 つを入れる。
    - (a) 今と同じ `trim_blanks(value)`。空でないときだけ入れる。
    - (b) 値の両端から、スペース（U+0020）、タブ（U+0009）、U+0085、U+2028、U+2029 を除いた値。これも空でないときだけ入れる。
    - 値全体への引数なしの `str.strip()` は使わない。
- **FR2: U+00A0 などは除かないまま残す** — FR1 (b) で除くのは、FR1 に挙げた 5 文字だけにする。U+00A0、U+000B、U+000C、U+2000〜U+200A、U+3000、LF、CR など、ほかの `str.isspace()` 文字は除かない。これらについては approval-unicode-whitespace FR8 の扱いが変わらない。たとえば `test_command:<U+00A0>make lint` から宣言集合に入るのは `<U+00A0>make lint` だけで、`make lint` は入らない。
- **FR3: 許可の範囲を広げない** — `trim_blanks`（スペースとタブだけを除く）、`is_matchable`、`approved_for`、`hook_main` の完全一致による許可、cd 前置形による許可、`read_stdin_commands`、`--record` / `--remove` / `--list` の挙動は変えない。宣言集合は、ワークフローに関係するかどうかの判定と、未承認としての拒否にしか使わない。FR1 で集合に足した値から許可が出ることはない。
- **FR4: 対策を文書に残す** — `feature-docs/approval-unicode-whitespace/SPEC.md` の FR8 と `feature-docs/approval-unicode-whitespace/THREAT-MODEL.md` の TM-5 に追記する。追記だけにして、既存の文は書き換えない。追記するのは次の 2 点。
    - (1) `declared_commands` が FR1 (b) の形も宣言集合に入れること。
    - (2) YAML のエスケープ表記、ブロックスカラー、値の内側の文字による食い違いは対象外で、そうした呼び出しは通常の権限確認に回ること。
    - `feature-docs/approval-unicode-whitespace/reviews/round1.yaml` と `em-workflow/references/command-execution-protocol.md` は変更しない。
- **FR5: 回帰テスト** — フックをサブプロセスとして動かすテストを足す。workflow.yaml には、U+0085 / U+2028 / U+2029 を前後それぞれの端に生の文字で置いた引用符付きの宣言を書く。その生の形、YAML 解析結果の形、端の文字を除いた形をコマンドとして渡し、どれも未承認として拒否されることを確かめる。あわせて、U+00A0 の形が判定なしのままであること、許可が広がっていないことも確かめる。YAML 解析結果の形はテストのソースにリテラルで書き、PyYAML は import しない。

### Non-Functional Requirements

- **NFR1 - 依存:** `bash_guard.py` は標準ライブラリのモジュールだけを import する（`tests/test_bash_guard_unicode_whitespace.py` の `test_ac7_the_hook_imports_only_standard_library_modules`、`tests/test_bash_guard_store_unicode_whitespace.py` の `test_ac6_guard_imports_only_standard_library_modules`）。
- **NFR2 - classification pin:** `bash_guard.py` の実行されるテキストには、新しい定数名・コメント・docstring を含めて、部分文字列 `'status'` を入れない（`test_ac7_the_hook_source_has_no_status_substring`、`test_ac6_guard_executable_text_has_no_status_substring`、`tests/test_hook_classification_pin.py`）。
- **NFR3 - トップレベル関数の並びと trim_blanks の意味:** トップレベル関数は増やさない。`strip_yaml_quotes`、`trim_blanks`、`is_matchable`、`declared_commands` の並びを保つ（`test_the_helpers_are_defined_once`、`test_ac6_trim_helpers_are_defined_once_between_strip_yaml_quotes_and_declared_commands`）。除く文字の集合は、モジュールレベルの定数にしてよい。`trim_blanks` はスペースとタブだけを除くままにする。すべての空白文字について確かめるテストがある（`test_ac6_trim_blanks_removes_spaces_and_tabs_only`）。ソースには、U+0085 / U+2028 / U+2029 を生の文字ではなくエスケープで書く。
- **NFR4 - テスト:** テストは Python 3.14 標準ライブラリの `unittest` だけを使い、PyYAML は import しない。ストアは `EM_WORKFLOW_APPROVALS` で切り離し、フックの環境からは `CLAUDE_PROJECT_DIR` を外す。リポジトリは一時ディレクトリの git リポジトリを使う。テストのソースでは、非 ASCII 文字をエスケープで書く。
- **NFR5 - 既存の docstring で固定された文言:** `bash_guard.py` のモジュール docstring にある、テストで固定された文言は残す（`'after removing surrounding spaces and tabs only'`、`'any other whitespace at either end is never allowed'`、cd 前置形の approval 項目の文言）。
- **NFR6 - Version:** version は変えない。

## Acceptance Criteria

- [ ] **AC1** (FR1, FR5): workflow.yaml の `test_command` が `"<U+0085>./unapproved"`（二重引用符の内側の先頭が生の U+0085）で、承認ストアには `/usr/bin/true` しかないとき、フックは `<U+0085>./unapproved`、` ./unapproved`（YAML 解析結果）、`./unapproved` のどれも、理由に「未承認」を含めて deny する。
- [ ] **AC2** (FR1, FR5): 末尾の場合。`"./unapproved<U+0085>"` と宣言したとき、`./unapproved<U+0085>`、`./unapproved `（YAML 解析結果）、`./unapproved` のどれも、未承認として deny される。
- [ ] **AC3** (FR1, FR5): U+2028 と U+2029 を引用符の内側の先頭または末尾に置いて宣言したとき、生の形と端の文字を除いた形のどちらも、未承認として deny される。PyYAML は引用符内のこの 2 文字を残すので、YAML 解析結果は生の形と同じになる。
- [ ] **AC4** (FR2): `tests/test_bash_guard_unicode_whitespace.py:418` の `assert_silent("make lint", FIX.declared)` と `:422` の `assert_silent("make e2e", FIX.declared)` は、変更しないままで通る。宣言集合に `<U+00A0>make lint` を入れたときに、`make lint` が入らないことも確かめる。
- [ ] **AC5** (FR3): 許可が広がっていない。AC1〜AC3 の宣言があっても、`./unapproved` とその前後を埋めた形はどれも allow されない。承認済みの `/usr/bin/true` の前か後ろに U+0085 / U+2028 / U+2029 を置いた形は、宣言があれば deny、なければ判定なしになる。`/usr/bin/true` そのものは、これまでどおり完全一致で allow される。
- [ ] **AC6** (FR4): approval-unicode-whitespace の `SPEC.md` FR8 と `THREAT-MODEL.md` TM-5 に、FR4 の 2 点が追記されている。既存の文と `round1.yaml` は変わっていない。
- [ ] **AC7** (NFR1, NFR2, NFR3, NFR4, NFR5): `python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/bash_guard.py`: `declared_commands` を変更する（FR1, FR2）。`trim_blanks`、`is_matchable`、`approved_for`、`hook_main`、`read_stdin_commands` は変えない（FR3）。

**External Dependencies:**
- なし。`bash_guard.py` は標準ライブラリだけを import する（NFR1）。テストは Python 3.14 標準ライブラリの `unittest` だけを使う（NFR4）。

### File Structure

```
em-workflow/hooks/bash_guard.py                              # FR1, FR2（変更）
tests/test_bash_guard_declared_yaml_breaks.py                # FR5, TS1〜TS3（新規）
feature-docs/approval-unicode-whitespace/SPEC.md             # FR4（FR8 への追記のみ）
feature-docs/approval-unicode-whitespace/THREAT-MODEL.md     # FR4（TM-5 への追記のみ）
```

変更しないもの: `feature-docs/approval-unicode-whitespace/reviews/round1.yaml`、`em-workflow/references/command-execution-protocol.md`（FR4）、既存テストファイルの `declared_lines`（TS1）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/declared-command-yaml-breaks/**`
- `test-docs/declared-command-yaml-breaks/**`

`feature-docs/declared-command-yaml-breaks/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/declared-command-yaml-breaks/**` covers `test-docs/declared-command-yaml-breaks/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/declared-command-yaml-breaks/` directory at all; the declared
`test-docs/declared-command-yaml-breaks/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] **TS2** (AC4 / FR2): U+00A0 の形。既存の `:418` / `:422` はそのまま。新しいファイルからは `declared_commands` を直接呼び、`<U+00A0>make lint` を宣言したとき集合に `make lint` が入らないことを確かめる。モジュールはバイトコードを書かずに読み込む（既存の `_load_guard_module` と同じ方法）。

### Integration Tests
- [ ] **TS1** (AC1, AC2, AC3, AC5 / FR1, FR3, FR5): 新規ファイル `tests/test_bash_guard_declared_yaml_breaks.py` を作り、独自の fixture を持たせる（既存ファイルの `declared_lines` は変えない）。fixture は宣言ありと宣言なしの 2 つのリポジトリで、ストアには `/usr/bin/true` だけを登録する。テストでは、文字（U+0085 / U+2028 / U+2029）× 位置（前 / 後）× コマンドの形（生 / YAML 解析結果 / 端の文字を除いた形）について、フックのサブプロセスで deny を確かめる。allow が出ないことも確かめる。
- [ ] **TS4** (AC7 / NFR1〜NFR5): テスト一式を `python3 -m unittest discover -s tests` で回す。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] **TS3** (FR1): 端の場合。シングルクォートの宣言と引用符なしの宣言でも、端の文字を除いた形が宣言集合に入る。`"<U+0085>"` のように、除くと空になる値からは (b) の形が入らない（生の値はこれまでどおり入る）。

## Security Considerations

- **Authorization:** 許可の範囲は FR3 のとおり変えない。`hook_main` で許可が出るのは exact（approved への完全一致）と `cd_prefix_allowed` の 2 つだけで、どちらも declared を参照しない（A2）。

## Assumptions

- **A1:** 対策は orchestrator の回答（`yaml_breaks_only`）に従う。`trim_blanks(value)` に加えて、スペース・タブ・U+0085・U+2028・U+2029 を両端から除いた値を宣言集合に入れる。`str.strip()` は使わない。
- **A2:** 宣言集合から許可が出ることはない。`hook_main` で許可が出るのは、exact（approved への完全一致）と `cd_prefix_allowed` の 2 つだけで、どちらも declared を参照しない。FR1 で集合が大きくなっても、変わるのは拒否と判定なしの境目だけになる。
- **A3:** `declared_commands` はテキストモードの行単位の反復で workflow.yaml を読む。行の区切りは LF / CR / CRLF だけで、U+0085 / U+2028 / U+2029 では区切らない（`str.splitlines` とは違う）。そのため、これらの文字は値の中にそのまま残る。
- **A4:** (b) の形に `"null"` / `"~"` の除外は追加しない。元の値に対する既存の除外と、空なら入れないという扱いだけを適用する。
- **A5:** 対象外: YAML のエスケープ表記（`\x85`、`\N`、`\u2028` など）、ブロックスカラー、複数行の値、値の内側の文字による食い違い、`merge-preflight.py`、承認ゲートの手順。どれも通常の権限確認に回り、FR4 で文書に残す。
- **A6:** 既存の fixture で宣言リポジトリに U+0085 を端に置いた宣言（`all_padded` の `OTHER_CHARS`）があると、新たに宣言集合に `/usr/bin/true` が入る。`/usr/bin/true` は承認済みなので、完全一致による allow が先に効き、既存の期待（`TestFixtureControls` の exact allow、`test_ac6_other_whitespace_characters_before_or_after_are_not_allowed` の deny）は変わらない。

## Success Criteria

- [ ] FR1〜FR5 が実装され、テストされている
- [ ] TS1〜TS4 がすべて通る
- [ ] FR3 のとおり許可の範囲が広がっていない
- [ ] FR4 の文書への追記が済んでいる
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## References

- approval-unicode-whitespace SPEC: `feature-docs/approval-unicode-whitespace/SPEC.md`
- approval-unicode-whitespace THREAT-MODEL: `feature-docs/approval-unicode-whitespace/THREAT-MODEL.md`
