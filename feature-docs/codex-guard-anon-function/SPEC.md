# Feature: codex-guard-anon-function

## Overview

codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、zsh の匿名関数 `function () { ... }` の本体を、予約語の直後でも前置なしでも判定し、本体に対話起動があれば deny するようにする。
あわせて、この見逃しの再発をテストで検出できる状態にする。

## Objectives

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、zsh の匿名関数 `function () { ... }` の本体を、予約語の直後でも前置なしでも判定し、本体に対話起動があれば deny する
- fail-open の見逃し（対話待ちの孤児プロセスが残りうる穴）を塞ぎ、再発をテストで検出できる状態にする

## Acceptance Criteria

- [ ] AC1: `zsh -c '! function () { python3 -i; }'` を `{"tool_input": {"command": ...}}` として両コピーの標準入力に渡すと deny の JSON が 1 つ出力される（FR1, FR6）
- [ ] AC2: `zsh -c 'if true; then function () { python3 -i; }; fi'` と `zsh -c 'function () { python3 -i; }'` が両コピーで deny になる（FR1, FR6）
- [ ] AC3: `zsh -c "'function' () { python3 -i; }"` が両コピーで silent のまま（FR2, FR3）
- [ ] AC4: `function function () { python3 -i; }` が両コピーで silent のまま（FR4）
- [ ] AC5: FR7 の 5 ケースが `CASES` にあり、`python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る（両コピーのバイト一致テスト、docstring 文言テストを含む）（FR5, FR6, FR7, NFR1, NFR2, NFR3）

## Technical Requirements

### Functional Requirements
- **FR1:** 引用のない `function` 1 語は関数名にしない。`_Parser._names_function` は、先頭の予約語（RESERVED_WORDS）の連なりと `time` 直後の `-p` を取り除いた後に残った語が 1 語で、その語が引用・エスケープ・展開を含まない（bare な）`function` のとき False を返す。これにより直後の `()` は関数定義の開始にならず、その後の `( ... )` / `{ ...; }` は実行されるグループとして判定される。予約語の前置がない `function () { ... }`（除去で語が減らない場合）も同じ扱いにする。
- **FR2:** 引用の有無を `_Word` に引き継ぐ。`_Parser` が語ごとに持つ既存の `bare` フラグ（引用・エスケープ・展開を一つも含まないとき True）を、`_finish_word` で生成する `_Word` に引き継ぎ、`_names_function` が参照できるようにする。`_Word` に引用の有無を表す属性を追加する。
- **FR3:** 引用・エスケープを含む `function` は従来どおり関数名として扱う。`'function' ()`、`"function" ()`、`\function ()` のように引用・エスケープを含む `function` は zsh で予約語にならず function という名前の関数定義になるため、従来どおり関数名として扱い、本体を判定しない（silent）。
- **FR4:** `function function ()` は従来どおり関数定義として扱う。FR1 の除外条件は、2 語の `function` 前置の処理（`end - first == 2 and words[first].text == "function"`）より前に、予約語除去後に残った 1 語に対してだけ適用する。`function function () { ... }` は従来どおり function という名前の関数定義として扱い、本体を判定しない。
- **FR5:** 関数名判定の説明文を新しい規則に合わせる。モジュール docstring の関数定義の説明（手順 4）、`_Group` の `head` の説明、`_names_function` の docstring に、予約語除去後に残った 1 語が引用もエスケープも含まない `function` のときは関数名でなく、その後のグループを判定することを書き加える。既存テストが固定している文言（``only `name()` and `function name()` start a function definition``、`three words or more left after the removal`、GROUP_HEAD_MARKERS、NAMES_FUNCTION_MARKERS の各文言）は残す。
- **FR6:** 両コピーへ同一の変更を入れる。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` に同じ変更を入れ、バイト単位で同一に保つ。
- **FR7:** 回帰テストを追加する。`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` 形式で次を追加する。
    - deny: `zsh -c '! function () { python3 -i; }'`
    - deny: `zsh -c 'if true; then function () { python3 -i; }; fi'`
    - deny: `zsh -c 'function () { python3 -i; }'`
    - silent: `zsh -c "'function' () { python3 -i; }"`
    - silent: `function function () { python3 -i; }`

### Non-Functional Requirements
- **NFR1:** 既存ケースを消さない。既存の `CASES` の deny / silent ケースは削除・変更しない。既存テストはすべて通る。
- **NFR2:** 既存の実装制約を維持する。標準ライブラリのみ、再帰なし（関数の自己呼び出し・循環なし）、`_names_function` の名前と 1 回の前向き走査（words を変更しない）の性質を保つ。
- **NFR3:** 変更後にリポジトリルートで `python3 -m unittest tests.test_codex_hook_interactive_guard` を実行し、すべて通る。
- **NFR4:** `<plugin>/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は変更しない。

## Implementation Approach

### Components

```
codex-hook-interactive-guard.py（em-workflow / em-review の両コピー、バイト単位で同一）
├── _Parser
│   ├── bare（既存。語ごとの引用・エスケープ・展開の有無）
│   ├── _finish_word … _Word を生成する。bare を _Word に引き継ぐ（FR2）
│   └── _names_function … 予約語除去後に残った 1 語が bare な `function` なら False（FR1, FR4）
├── _Word … 引用の有無を表す属性を追加する（FR2）
└── _Group.head の説明 / モジュール docstring（手順 4）… 説明を書き加える（FR5）
```

### Dependencies

**External Dependencies:**
- Python 標準ライブラリのみ（NFR2）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1-FR6
em-review/scripts/codex-hook-interactive-guard.py     # FR1-FR6（em-workflow 側とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR7
```

## Declared Change Set

ここに挙げる機能固有のパスは手書きの一覧ではなく、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、機能固有のパスに加えて、ワークフローが生成する次の 2 つをデフォルトで宣言に含める。

- `feature-docs/codex-guard-anon-function/**`
- `test-docs/codex-guard-anon-function/**`

`feature-docs/codex-guard-anon-function/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップが生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有し、この節はそれらを引用するだけで規則を再掲しない。

`test-docs/codex-guard-anon-function/**` はタスクごとのテスト記録 `test-docs/codex-guard-anon-function/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有し、この節は引用するだけで規則を再掲しない。

この 2 つのデフォルト項目は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載がないことを理由に外れたとはみなさない。

この宣言は上位集合の宣言であり、検証時に観測される実際の変更集合は宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生成しない機能では `test-docs/codex-guard-anon-function/` は作られないが、その場合も宣言した `test-docs/codex-guard-anon-function/**` は正しく、作られなかったパスは違反にならない。

## Test Scenarios

### Unit Tests
- [ ] TS1: 予約語 `!` の直後の匿名関数 `zsh -c '! function () { python3 -i; }'` - deny（AC1）
- [ ] TS2: `then` の直後の匿名関数 `zsh -c 'if true; then function () { python3 -i; }; fi'` - deny（AC2）
- [ ] TS3: 前置のない匿名関数 `zsh -c 'function () { python3 -i; }'` - deny（AC2）
- [ ] TS4: 単引用符で囲んだ `function` は関数名（回帰） `zsh -c "'function' () { python3 -i; }"` - silent（AC3）
- [ ] TS5: `function function ()` は関数定義（回帰） `function function () { python3 -i; }` - silent（AC4）
- [ ] TS6: 既存スイート全体 `python3 -m unittest tests.test_codex_hook_interactive_guard` - 全テスト成功（AC5）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] `'function' ()`、`"function" ()`、`\function ()` のように引用・エスケープを含む `function` は関数名として扱い、本体を判定しない（silent）（FR3）
- [ ] `function function () { ... }` は function という名前の関数定義として扱い、本体を判定しない（silent）（FR4）
- [ ] 判定はシェルの種類を区別しない。bash -c の中や外側の命令行でも、bare な `function ()` の後のグループは判定され、本体に対話起動があれば deny になる（A5）

## Out of Scope

次の形は対象外とし、残存する見逃しとして記録する。`CASES` には追加しない（A4）。

- `function { python3 -i; }`（括弧なし）
- `function () { python3 -i; } arg`（閉じ波括弧の後に引数）

## Assumptions

- **A1:** 匿名関数として扱うのは、予約語除去後に残った 1 語が引用もエスケープも含まない `function` のときに限る。引用の有無は既存の `_Parser.bare` を `_Word` に引き継いで判定する。`zsh -c "'function' () { python3 -i; }"` は silent のまま回帰ケースとして追加する。
- **A2:** `function function () { ... }` は従来どおり関数定義として扱う。除外条件は 2 語の `function` 前置の処理より前に、予約語除去後に残った 1 語に対してだけ適用する。
- **A3:** version は手で上げない。
- **A4:** `function { python3 -i; }`（括弧なし）と `function () { python3 -i; } arg`（閉じ波括弧の後に引数）は対象外とし、残存する見逃しとして SPEC に記録する。CASES には追加しない。
- **A5:** 判定はシェルの種類を区別しない。bash で `function () { ...; }` は構文エラーになるが、bash -c の中や外側の命令行でも bare な `function ()` の後のグループは判定され、本体に対話起動があれば deny になる。
- **A6:** 既存テストが固定している docstring の文言は残し、新しい規則の説明は書き加えで行う。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed
- [ ] AC1〜AC5 をすべて満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし
