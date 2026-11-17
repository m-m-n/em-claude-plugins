# Feature: declared-command-edge-fold

## Overview

`em-workflow/hooks/bash_guard.py` の `hook_main` で、宣言集合と照合する 3 か所のすべてに、受け取ったコマンドの両端から 6 文字（U+0020・U+0009・LF・U+0085・U+2028・U+2029）を除いた形の照合を足す。これにより、workflow.yaml の `*_command` の引用符付きの値の端に U+0085 / U+2028 / U+2029 が混在または連続していても、その YAML 解析結果（PyYAML）は未承認として deny される。許可の範囲は変えない。要件は `feature-docs/declared-command-edge-fold/REQUIREMENTS.md` を参照する。

## Objectives

- workflow.yaml の `*_command` の引用符付きの値の端に、U+0085 / U+2028 / U+2029 が混在または連続していても、その YAML 解析結果（PyYAML）をコマンドとして渡されたら、bash_guard のフックは未承認として deny する。判定なしにはしない。
- 許可の範囲は広げない（TM-2 は維持）。
- 上流に修正版がないので、暫定の緩和策、広がった拒否の範囲、残る対象外の範囲を文書に書き残す。

## User Stories

該当なし

## Technical Requirements

### Functional Requirements

- **FR1:** hook_main で、両端から 6 文字を除いた形も宣言集合と照合する。
    - `hook_main` では、宣言集合と照合する 3 か所（受け取ったコマンドが宣言されておらず、承認ストアのファイルもないときの早期 return、ワークフローに関係するかどうかの判定、未承認の deny）のすべてで、今の照合（`trim_blanks` した command が `declared` にあるか）に加えて、もう 1 つの形も照合する。
    - その形は、受け取ったコマンドの両端から U+0020・U+0009・LF（U+000A）・U+0085・U+2028・U+2029 を除いたもので、これが `declared` にあれば「宣言済み」とする。
    - 両端を除いた形が空なら、宣言済みとはしない。
    - この 6 文字以外（U+00A0、CR、U+000B、U+000C、U+2000〜U+200A、U+3000 など）は除かない。
    - 受け取ったコマンド自体は書き換えない。`refusal_reason`、exact、cd 前置形の判定は、これまでどおり `trim_blanks` した command に当てる。
    - 判定順序（禁止パターン -> exact -> cd 前置形 -> 宣言済みかつ未承認の deny -> 判定なし）は変えない。
- **FR2:** declared_commands と許可の範囲を変えない。
    - `declared_commands` が入れる 2 つの形（`trim_blanks(value)` と `value.strip(DECLARED_END_STRIP)`）と、`DECLARED_END_STRIP` は変えない。
    - `trim_blanks`、`is_matchable`、`approved_for`、exact と cd 前置形による許可、`cd_prefix_allowed` / `is_cd_prefixed_approved`、`read_stdin_commands`、`--record` / `--remove` / `--list`、`refusal_reason` の挙動も変えない。
    - FR1 の照合から許可が出ることはない。
- **FR3:** 広がった拒否の範囲。
    - FR1 によって、宣言済みの値の端に FR1 の 6 文字（スペース・タブ以外の LF / U+0085 / U+2028 / U+2029 を含む）を付けたコマンドは、その値が承認済みであっても、判定なしではなく未承認として deny される（例: `/usr/bin/true` が宣言済みかつ承認済みのとき、`'/usr/bin/true'` + LF は deny）。
    - 宣言のないリポジトリでは、同じ形はこれまでどおり判定なしになる。
    - deny の理由の文言と additionalContext は変えない。
- **FR4:** 回帰テスト。
    - フックをサブプロセスとして動かすテストを新しいファイルに足す。宣言は、二重引用符とシングルクォートの両方で、生の文字で書く。YAML 解析結果の形はテストのソースにリテラルで書き、PyYAML は import しない。
    - 確かめるのは次のとおり。
        1. 先頭 U+0085 + 末尾 U+2028 / U+2029 と、その逆（先頭 U+2028 / U+2029 + 末尾 U+0085）。
        2. 同じ端での U+0085 U+0085（-> LF）、U+0085 U+2028（-> U+2028）、U+2028 U+0085（-> U+2028 LF）を、先頭と末尾のそれぞれに置いた宣言。
        - (1)(2) の YAML 解析結果の形が、理由に「未承認」を含めて deny されること。宣言のないリポジトリでは判定なしのままであること。allow が出ないこと。承認済みの `/usr/bin/true` が完全一致で allow されること。
    - 既存の `tests/test_bash_guard_declared_yaml_breaks.py` の `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` は、FR1 の 6 文字のどれかで両端を埋めた形だけを deny の期待に変える。U+00A0 で埋めた形は判定なしの期待を保つ。
    - 既存の deny のケースは消さない。
- **FR5:** 文書への追記。
    - 次の 4 か所に追記する。追記だけにして、既存の文は書き換えない: approval-unicode-whitespace の SPEC.md FR8 と THREAT-MODEL.md TM-5、declared-command-yaml-breaks の SPEC.md FR1 と THREAT-MODEL.md TM-1。
    - 追記する内容は 3 点。
        1. `hook_main` が、両端から 6 文字を除いた形も宣言集合と照合すること。
        2. FR3 の、広がった拒否の範囲（承認済みの値でも、端を改行文字で埋めると未承認として deny されること）。
        3. 対象外の範囲。改行文字だけの宣言（両端を除くと空になる値）の解析結果、YAML のエスケープ表記、ブロックスカラー、値の内側の文字による食い違いは対象外で、通常の権限確認に回ること。
    - `bash_guard.py` のモジュール docstring（Matching の段落と判定表の declared 行）と `hook_main` まわりのコメントも、FR1 に合わせて更新する。
    - `feature-docs/*/reviews/round1.yaml` と `em-workflow/references/command-execution-protocol.md` は変えない。

### Non-Functional Requirements

- **NFR1 - 依存:** `bash_guard.py` は標準ライブラリのモジュールだけを import する（`test_ac7_the_hook_imports_only_standard_library_modules`、`test_ac6_guard_imports_only_standard_library_modules`）。
- **NFR2 - classification pin:** `bash_guard.py` の実行されるテキストには、新しい定数名・コメント・docstring を含めて、部分文字列 `'status'` を入れない（`tests/test_hook_classification_pin.py` ほか）。
- **NFR3 - 関数の並び:** `strip_yaml_quotes`、`trim_blanks`、`is_matchable`、`declared_commands` の 4 つは、この順で連続して並び、それぞれ 1 回だけ定義されるままにする。FR1 は `hook_main` の中に書くか、モジュールレベルの定数を足して実現し、この並びの間に関数を足さない。
- **NFR4 - ソースの文字:** `bash_guard.py` のソースには、U+0085 / U+2028 / U+2029 をエスケープで書き、生の文字を入れない（`test_ac7_the_hook_source_has_no_raw_next_line_or_separator_character`）。
- **NFR5 - docstring:** モジュール docstring の固定された文言（`'after removing surrounding spaces and tabs only'`、`'any other whitespace at either end is never allowed'`、cd 前置形の approval 項目）を残す。
- **NFR6 - テスト:** Python 3.14 標準ライブラリの unittest だけを使い、PyYAML は import しない。ストアは `EM_WORKFLOW_APPROVALS` で切り離し、フックの環境から `CLAUDE_PROJECT_DIR` を外し、一時ディレクトリの git リポジトリを使う。テストのソースは ASCII だけにして、非 ASCII 文字はエスケープで書く。
- **NFR7 - Version:** version は変えない。

## Acceptance Criteria

- [ ] AC1 (FR1, FR4): `build_command` が `"<U+0085>./unapproved<U+2028>"` で、承認ストアには `/usr/bin/true` だけがあるとき、`' ./unapproved<U+2028>'`（YAML 解析結果）が、理由に「未承認」を含めて deny される。末尾が U+2029 の宣言なら `' ./unapproved<U+2029>'` も同じ。生の形と、両端を除いた形 `'./unapproved'` も deny される。
- [ ] AC2 (FR1, FR4): その逆。`"<U+2028>./unapproved<U+0085>"` と `"<U+2029>./unapproved<U+0085>"` の YAML 解析結果（`'<U+2028>./unapproved '`、`'<U+2029>./unapproved '`）が、未承認として deny される。
- [ ] AC3 (FR1, FR4): 同じ端の連続。`"<U+0085><U+0085>./unapproved"` -> LF + `'./unapproved'`、`"./unapproved<U+0085><U+0085>"` -> `'./unapproved'` + LF、`"<U+0085><U+2028>./unapproved"` -> `'<U+2028>./unapproved'`、`"./unapproved<U+0085><U+2028>"` -> `'./unapproved<U+2028>'`、`"<U+2028><U+0085>./unapproved"` -> `'<U+2028>'` + LF + `'./unapproved'`。どれも未承認として deny される。
- [ ] AC4 (FR1, FR4): AC1〜AC3 の宣言をシングルクォートで書いた場合も、同じ YAML 解析結果の形が deny される。
- [ ] AC5 (FR1, FR2, FR4): AC1〜AC4 の形は、宣言のないリポジトリでは判定なしになる。宣言があってもなくても allow は出ない。`/usr/bin/true` そのものは、これまでどおり完全一致で allow される。U+00A0 で端を埋めた `'./unapproved'` は、宣言のあるリポジトリでも判定なしのまま。
- [ ] AC6 (FR3): `/usr/bin/true` が宣言済みかつ承認済みのリポジトリでは、`'/usr/bin/true'` + LF、`'<U+0085>/usr/bin/true'`、`'/usr/bin/true<U+2028>'` が未承認として deny される。宣言のないリポジトリでは、どれも判定なしになる。
- [ ] AC7 (FR2): `declared_commands` が返す集合は変わらない。`tests/test_bash_guard_declared_yaml_breaks.py` の AC-4 / AC-5 の集合比較のテストは、変更しないままで通る。
- [ ] AC8 (FR4): `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` は、U+0020 / U+0009 / U+0085 / U+2028 / U+2029 で埋めた形を deny と期待し、U+00A0 で埋めた形を silent と期待する。allow が出ないことの確認は残る。
- [ ] AC9 (FR5): FR5 の 4 文書に 3 点が追記されている。既存の文、`round1.yaml`、`command-execution-protocol.md` は変わっていない。
- [ ] AC10 (NFR1〜NFR7): `python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### Architecture

`hook_main` の判定順序は変えない（FR1）。

```
禁止パターン -> exact -> cd 前置形 -> 宣言済みかつ未承認の deny -> 判定なし
```

「宣言済み」の判定（早期 return、ワークフローに関係するかどうかの判定、未承認の deny の 3 か所）は、次のどちらかが `declared` にあれば真とする。

```
(a) trim_blanks(command)                      ... 今の照合
(b) command の両端から 6 文字を除いた形        ... FR1 で足す照合（空なら宣言済みとしない）
    6 文字 = U+0020 U+0009 U+000A U+0085 U+2028 U+2029
```

許可が出るのは exact と `cd_prefix_allowed` の 2 つだけで、どちらも `declared` を参照しない。FR1 で変わるのは、deny と判定なしの境目だけになる（A4、TM-2 は維持）。

### Data Flow

```
受け取ったコマンド
  -> refusal_reason / exact / cd 前置形 : trim_blanks(command) に当てる（変更なし）
  -> 宣言済みの判定                   : (a) または (b) が declared にあるか
  -> 宣言済みかつ未承認 -> deny（理由の文言と additionalContext は変えない）
  -> それ以外           -> 判定なし
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `declared_commands`: 宣言集合を返す。FR2 により変えない。
- `trim_blanks` / `is_matchable` / `approved_for` / `cd_prefix_allowed` / `is_cd_prefixed_approved` / `read_stdin_commands` / `refusal_reason`: FR2 により挙動を変えない。

**External Dependencies:**
- なし（NFR1、NFR6）

### File Structure

```
em-workflow/hooks/bash_guard.py                           # FR1, FR5（docstring / コメント）
tests/test_bash_guard_declared_edge_fold.py               # FR4（新しいファイル、名前は例）
tests/test_bash_guard_declared_yaml_breaks.py             # FR4（test_ac6_... の期待値の変更）
feature-docs/approval-unicode-whitespace/SPEC.md          # FR5（FR8 への追記）
feature-docs/approval-unicode-whitespace/THREAT-MODEL.md  # FR5（TM-5 への追記）
feature-docs/declared-command-yaml-breaks/SPEC.md         # FR5（FR1 への追記）
feature-docs/declared-command-yaml-breaks/THREAT-MODEL.md # FR5（TM-1 への追記）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/declared-command-edge-fold/**`
- `test-docs/declared-command-edge-fold/**`

`feature-docs/declared-command-edge-fold/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/declared-command-edge-fold/**` covers `test-docs/declared-command-edge-fold/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/declared-command-edge-fold/` directory at all; the declared
`test-docs/declared-command-edge-fold/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: `declared_commands` を直接呼び、宣言集合が変わらないことを確かめる（既存の AC-4 / AC-5 の集合比較のテストをそのまま通す）。モジュールは、既存の `_load_guard_module` と同じ方法で、バイトコードを書かずに読み込む。 - AC7 / FR2

### Integration Tests
- [ ] TS-2: 新しいファイル（例: `tests/test_bash_guard_declared_edge_fold.py`）を作り、独自の fixture を持たせる。fixture は、ケースごとに宣言を 1 つだけ持つ一時 git リポジトリと、宣言のないリポジトリで、ストアには `/usr/bin/true` だけを入れる。宣言（二重引用符 / シングルクォート）× YAML 解析結果の形について、フックのサブプロセスで deny を確かめ、宣言なしでは silent になることも確かめる。allow が出ないことも確かめる。 - AC1〜AC5 / FR1, FR4
- [ ] TS-3: `/usr/bin/true` を宣言したリポジトリと、宣言のないリポジトリで、LF / U+0085 / U+2028 / U+2029 で端を埋めた `/usr/bin/true` が、それぞれ deny / silent になる。 - AC6 / FR3
- [ ] TS-4: 既存の `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` の期待値を、FR1 の 6 文字による埋め方なら deny、U+00A0 なら silent に変える。 - AC8 / FR4
- [ ] TS-5: `python3 -m unittest discover -s tests` でテスト一式を回す。 - AC10 / NFR1〜NFR7

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-6: 改行文字だけの宣言（例: `"<U+0085><U+2028><U+2029>"`）の解析結果は、両端を除くと空になる。宣言済みとはしないこと（判定なし）を確かめ、対象外として記録する。 - FR1
- [ ] TS-7: cd 前置形 `cd "<path>" && <値><U+2028>` は、両端を除いた後の文字列全体が宣言値と一致しないので、今の判定のまま変わらない。 - FR1, FR2
- [ ] TS-8: 承認ストアのファイルがなく、宣言だけがあるとき（早期 return の経路）でも、AC1 の YAML 解析結果の形が deny される。 - FR1

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 許可が出るのは exact と `cd_prefix_allowed` の 2 つだけで、どちらも `declared` を参照しない。FR1 の照合から許可が出ることはない（FR2、A4、TM-2 は維持）。
- **Input Validation:** 受け取ったコマンド自体は書き換えない。両端から除くのは FR1 の 6 文字だけで、両端を除いた形が空なら宣言済みとはしない（FR1）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

### 対象外の範囲

改行文字だけの宣言の解析結果、YAML のエスケープ表記（`\N`、` `、二重引用符の中のエスケープした改行）、ブロックスカラー、複数行の値、値の内側の文字による食い違い、CR、`merge-preflight.py`、承認ゲートの手順は対象外。どれも通常の権限確認に回り、FR5 で文書に残す（A3）。

## Error Handling

### Error Codes

該当なし。deny の理由の文言と additionalContext は変えない（FR3）。

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed

## Assumptions

- **A1:** 緩和策は案 1（`hook_main` 側で、両端から 6 文字を除いた形も照合する）を採る。`declared_commands` の 2 つの形は変えない。
- **A2:** 拒否の範囲が広がり、宣言済みの値の端を改行文字で埋めたコマンドは、承認済みの値でも未承認として deny される。これは受け入れ、文書に明記する。
- **A3:** 対象外: 改行文字だけの宣言の解析結果、YAML のエスケープ表記（`\N`、` `、二重引用符の中のエスケープした改行）、ブロックスカラー、複数行の値、値の内側の文字による食い違い、CR、`merge-preflight.py`、承認ゲートの手順。どれも通常の権限確認に回り、FR5 で文書に残す。
- **A4:** 許可が出るのは exact と `cd_prefix_allowed` の 2 つだけで、どちらも `declared` を参照しない。そのため FR1 で変わるのは、deny と判定なしの境目だけになる（TM-2 は維持）。
- **A5:** 他の feature の文書（approval-unicode-whitespace と declared-command-yaml-breaks の SPEC / THREAT-MODEL）には追記だけをする。`round1.yaml` と `command-execution-protocol.md` は変えない。
- **A6:** version は変えない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/declared-command-edge-fold/REQUIREMENTS.md`
- approval-unicode-whitespace の SPEC.md（FR8）と THREAT-MODEL.md（TM-5）
- declared-command-yaml-breaks の SPEC.md（FR1、A5）と THREAT-MODEL.md（TM-1、TM-2）
