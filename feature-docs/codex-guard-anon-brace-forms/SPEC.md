# Feature: codex-guard-anon-brace-forms

## Overview

codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、zsh の匿名関数の 3 形（`function { ...; }`、`function () { ...; } arg`、`() { ...; } arg`）で本体を判定し、本体に対話起動があれば deny する。パイプの右側に置いた匿名関数は、パイプの接続を本体に渡して誤って deny しない。要件は `feature-docs/codex-guard-anon-brace-forms/REQUIREMENTS.md` を参照する。

## Objectives

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）が zsh の匿名関数の本体を判定し、本体に対話起動があれば deny する。対象は `function { ...; }`（括弧なし）、`function () { ...; } arg`（閉じ波括弧の後に引数）、`() { ...; } arg`（語の無い空の `()`）の 3 形
- パイプの右側に置いた匿名関数を誤って deny しない
- この見逃し（fail-open）の再発をテストで検出できる状態にする

## User Stories

該当なし（UI を持たないフックスクリプトのパーサー修正とテスト追加のみ）

## Technical Requirements

### Functional Requirements

- **FR1:** 括弧なしの匿名関数を読む。予約語の連なり（RESERVED_WORDS の先頭の連なりと、`time` 直後の非動的な `-p`）を除いたあとに残った語が、引用・エスケープ・展開を含まない（bare な）`function` 1 語のとき、続く単独の `{` 語で波括弧グループを開き、中のコマンドを判定する。引用・エスケープ付きの `function`、2 語以上（`function f {`）、動的な語の場合は、従来どおりグループを開かない。
- **FR2:** 匿名関数の本体を特定し、閉じ波括弧の後の語を引数として読む。次の波括弧グループを匿名関数の本体とする。
  - (a) FR1 で開いたグループ。
  - (b) 予約語除去後に残った語が bare な `function` 1 語である空の `()` の直後のグループ。
  - (c) `(` を開いた時点で語が 1 つも無い空の `()` の直後のグループ。
  - (b) と (c) では、`()` と `{` の間に改行があってもよい。
  - 本体の閉じ `}` の後の語は匿名関数の引数として読み、コマンドとして判定せず、判定不能にもしない。引数は次の区切り（`;` `&&` `||` `|` `|&` `&` 改行）で終わる。
  - 引数の後の標準入力リダイレクト（`<` `<<` `<<<` `<&` `0<`）は、閉じ直後に置いたときと同じく本体を接続する。
- **FR3:** パイプの接続を匿名関数の本体に渡す。`function` の語、または語の無い空の `()` が `|` / `|&` の右側にあるとき、その接続を匿名関数の本体のグループに渡す。本体の中の入れ子のグループにも、既存の規則どおり接続が届く。この継承は匿名関数の本体に限る。本体の後に続く別のコマンドには接続を渡さない。接続下でも `-i` などの明示的な対話起動は deny のまま。
- **FR4:** 既存の読みを保つ。匿名関数でない波括弧グループの後の語（`{ python3 -i; } arg`）と、関数定義の本体の後の語（`f() { python3 -i; } arg`、`function f () { python3 -i; } arg`）は、判定不能（silent）のまま。括弧なしの名前付き定義 `function f { python3 -i; }` と、引用付きの `'function' { python3 -i; }` も silent のまま。前の feature で決まった判定（`function () { ... }` の本体を判定する、`'function' ()` と `function function ()` は関数定義として扱う）は変えない。
- **FR5:** 説明文を新しい規則に合わせる。次の 3 か所に、匿名関数の 3 形、閉じた後の引数、パイプ接続の継承を書き加える。モジュール docstring の手順 4、`_Group` の説明、括弧なし形の判別を担う関数の docstring。手順 4 の「`{` and `}` delimit a group only as a standalone word at command position」は新しい規則に合わせて改める。既存テストが固定している文言（DOCSTRING_MARKERS / GROUP_HEAD_MARKERS / NAMES_FUNCTION_MARKERS）は残す。
- **FR6:** 両コピーへ同一の変更。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` に同じ変更を入れ、バイト単位で同一に保つ。
- **FR7:** 回帰テストを追加する。`tests/test_codex_hook_interactive_guard.py` の `CASES` に、(期待する判定, ラベル, コマンド) 形式で次を追加する（`\n` は改行）。
  - deny:
    - `zsh -c 'function { python3 -i; }'`
    - `zsh -c 'function () { python3 -i; } arg'`
    - `zsh -c 'function { python3 -i; } arg'`
    - `zsh -c '! function { python3 -i; }'`
    - `zsh -c '() { python3 -i; } arg'`
    - `zsh -c 'function ()\n{ python3 -i; } arg'`
    - `zsh -c 'echo x | function { python3 -i; }'`
    - `zsh -c 'echo x | function { cat; }; python3'`
  - silent:
    - `zsh -c 'function f { python3 -i; }'`
    - `zsh -c "'function' { python3 -i; }"`
    - `zsh -c 'function { echo hi; } python3'`
    - `zsh -c 'function () { python3; } arg < f'`
    - `zsh -c 'echo x | function { python3; }'`
    - `zsh -c 'echo x | function () { python3; }'`
    - `zsh -c 'echo x | () { python3; }'`
    - `zsh -c 'echo x | function { { python3; }; }'`
    - `zsh -c '{ python3 -i; } arg'`
    - `zsh -c 'f() { python3 -i; } arg'`

### Non-Functional Requirements

- **NFR1 - 既存テストの維持:** 既存の CASES の deny / silent ケースは削除・変更しない。既存テストはすべて通る。
- **NFR2 - 標準ライブラリのみ・非再帰・1 回の前向き走査:** 標準ライブラリのみを使い、再帰しない（関数の自己呼び出しも循環も作らない）。`_names_function` の名前と、1 回の前向き走査（words を変更しない）という性質を保つ。
- **NFR3 - 括弧なし形の判別の線形時間:** 括弧なし形の判別では、`{` のたびに語の列を走査し直さず、線形時間を保つ。`test_a_long_run_of_reserved_words_before_a_paren_is_answered` の入力に、予約語の長い連なりの後に `function { python3 -i; }` が続く形を加え、既存の入力と同じ時間内に応答することを確かめる。
- **NFR4 - テストスイートの成功:** 変更後、リポジトリルートで `python3 -m unittest tests.test_codex_hook_interactive_guard` を実行し、すべて通る。
- **NFR5 - version を変更しない:** `<plugin>/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は変更しない。

## Implementation Approach

### Architecture

変更対象はフックスクリプト `codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）のパーサーと、その説明文（FR5）。

**Component Diagram:**
```
codex-hook-interactive-guard.py
├── モジュール docstring 手順 4      … FR5 で書き加える
├── _Group                          … 匿名関数の本体のグループ（FR2）、パイプ接続の継承（FR3）
└── _names_function / 括弧なし形の判別 … FR1、NFR2、NFR3
```

### Data Flow

```
{"tool_input": {"command": ...}}（標準入力） → codex-hook-interactive-guard.py → deny の JSON / 出力なし（silent）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- 前の feature で決まった判定（`function () { ... }` の本体を判定する、`'function' ()` と `function function ()` は関数定義として扱う）: 変えない（FR4）

**External Dependencies:**
- Python 標準ライブラリのみ（NFR2）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1-FR6
em-review/scripts/codex-hook-interactive-guard.py     # FR1-FR6（em-workflow 側とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR7、NFR3
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-anon-brace-forms/**`
- `test-docs/codex-guard-anon-brace-forms/**`

`feature-docs/codex-guard-anon-brace-forms/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-anon-brace-forms/**` covers `test-docs/codex-guard-anon-brace-forms/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-anon-brace-forms/` directory at all; the declared
`test-docs/codex-guard-anon-brace-forms/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1: 括弧なしの匿名関数 `zsh -c 'function { python3 -i; }'` - deny（AC1）
- [ ] TS2: 閉じ波括弧の後に引数 `zsh -c 'function () { python3 -i; } arg'` - deny（AC1）
- [ ] TS3: 括弧なしで引数あり / ! の直後 / 語の無い () で引数あり / () と { の間の改行 - deny（AC2）
- [ ] TS4: パイプの右側の匿名関数 3 形と入れ子 - silent。接続下の -i と群の後の別コマンド - deny（AC3）
- [ ] TS5: 名前付き括弧なし定義、引用付き function、引数に置いた python3、引数の後の入力リダイレクト、匿名関数でない波括弧の後の語、定義本体の後の語 - silent（AC4）
- [ ] TS6: 予約語の長い連なりの後の `function { python3 -i; }` が線形時間で応答する（NFR3）
- [ ] TS7: 既存スイート全体 `python3 -m unittest tests.test_codex_hook_interactive_guard` - 全テスト成功（AC5）

### Integration Tests
該当なし

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 未検出

### Acceptance Criteria
- [ ] AC1: `zsh -c 'function { python3 -i; }'` と `zsh -c 'function () { python3 -i; } arg'` を `{"tool_input": {"command": ...}}` として両コピーの標準入力に渡すと、deny の JSON が 1 つ出力される（FR1, FR2, FR6）
- [ ] AC2: `zsh -c '() { python3 -i; } arg'`、`zsh -c 'function { python3 -i; } arg'`、`zsh -c '! function { python3 -i; }'`、`zsh -c 'function ()\n{ python3 -i; } arg'`（`\n` は改行）が両コピーで deny になる（FR1, FR2）
- [ ] AC3: `zsh -c 'echo x | function { python3; }'`、`zsh -c 'echo x | function () { python3; }'`、`zsh -c 'echo x | () { python3; }'`、`zsh -c 'echo x | function { { python3; }; }'` が silent になる。`zsh -c 'echo x | function { python3 -i; }'` と `zsh -c 'echo x | function { cat; }; python3'` は deny になる（FR3）
- [ ] AC4: `zsh -c 'function f { python3 -i; }'`、`zsh -c "'function' { python3 -i; }"`、`zsh -c 'function { echo hi; } python3'`、`zsh -c 'function () { python3; } arg < f'`、`zsh -c '{ python3 -i; } arg'`、`zsh -c 'f() { python3 -i; } arg'` が両コピーで silent のまま（FR2, FR4）
- [ ] AC5: FR7 のケースが CASES にあり、`python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る。バイト一致テスト、docstring 文言テスト、線形性テストを含む（FR5-FR7, NFR1-NFR4）

### Edge Cases
- [ ] `()` と `{` の間の改行: 匿名関数の本体として扱う（FR2、A4）
- [ ] `function` と `{` の間の改行: 扱わない。括弧なし形は同じ行に書かれた場合に限る（A4）
- [ ] 予約語の後の `()`（`then () { ... }` など）: 既存の関数名判定に従う（A5）
- [ ] 引数の後の標準入力リダイレクト: 閉じ直後と同じく本体を接続する（FR2、A2）
- [ ] 既存の `echo x | function () { python3; }`: deny から silent に変わる（既存の CASES には無い）（A9）

### Performance Tests
- [ ] TS6: 予約語の長い連なりの後の `function { python3 -i; }` が、既存の入力と同じ時間内に応答する（NFR3）

## Assumptions

- A1: 括弧なし形を判別する条件は、前の feature と同じ予約語除去をしたあとに残った語が bare な `function` 1 語であること。`'function' { echo x; }` は zsh 5.9 では parse error になり実行されないため、silent のままでよい（オーケストレーターが zsh 5.9 で確認済み）。
- A2: 匿名関数の本体の閉じ `}` の後の語は引数である。zsh 5.9 で `function { echo $1; } A` は A、`function () { echo $1; } B` は B、`() { echo $1; } C` は C を出力した（オーケストレーターが確認済み）。引数の後の標準入力リダイレクトは、閉じ直後と同じく本体を接続する。
- A3: 匿名関数でない波括弧グループの後の語と、関数定義の本体の後の語は、従来どおり判定不能（silent）とする。
- A4: `()` と `{` の間に改行があっても、匿名関数の本体として扱う（既存の関数定義の本体の規則と揃える）。`function` と `{` の間の改行は扱わず、括弧なし形は同じ行に書かれた場合に限る。
- A5: 語の無い空の `()` の形（FR2 (c)）は、`(` を開いた時点で語が 1 つも無い場合に限る。予約語の後の `()`（`then () { ... }` など）は、既存の関数名判定に従う。
- A6: 判定はシェルの種類を区別しない（前の feature の A5 と同じ）。
- A7: version は手で上げない。docstring は、既存テストが固定している文言を残したまま書き加える。
- A8: 回答（scope.nameless-paren-form = include、batch-codex-consultation）により、直前に語の無い空の `()` の直後の波括弧グループも匿名関数の本体として扱い、閉じた後の語を引数として読む。`zsh -c '() { python3 -i; } arg'` を deny として CASES に追加する。
- A9: 回答（requirement.anon-body-stdin-connection = connect、batch-codex-consultation）により、`function` / `()` の前のパイプ接続を匿名関数の本体のグループに渡す。`echo x | function { python3; }`、`echo x | function () { python3; }`、`echo x | () { python3; }` は silent にする。継承は匿名関数の本体に限る。`-i` などの明示的な対話起動は、接続下でも deny のまま。入れ子、群の後の別コマンド、接続下の -i の回帰ケースを CASES に追加する。zsh 5.9 で `echo piped | function { cat; }` が piped を出力することは確認済み。このため、既存の `echo x | function () { python3; }` の判定は deny から silent に変わる（既存の CASES には無い）。

## Security Considerations

該当なし

## Error Handling

該当なし

## Performance Optimization

### Performance Goals
- 括弧なし形の判別は線形時間を保つ。`{` のたびに語の列を走査し直さない（NFR3）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る（NFR4）
- [ ] 両コピーがバイト単位で同一（FR6）
- [ ] version を変更していない（NFR5）

## Open Questions

なし

## References

- 要件定義書: `feature-docs/codex-guard-anon-brace-forms/REQUIREMENTS.md`
