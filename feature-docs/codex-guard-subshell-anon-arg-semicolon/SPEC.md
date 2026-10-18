# Feature: codex-guard-subshell-anon-arg-semicolon

## Overview

codex-hook-interactive-guard（em-workflow / em-review の両コピー）が、サブシェル `( ... )` の中で匿名関数の引数から仮に開いた `(` の最初の直接の区切りが `;` か単独の `&` で、後の `)` がその群を閉じる形を deny にする。`)` を読んだ時点で仮の群の連鎖を救済し、chain_base の `(` 群を閉じる。要件は [REQUIREMENTS.md](REQUIREMENTS.md) にある。

再現形:

```
zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'
```

行番号は `tests/test_codex_hook_interactive_guard.py` のもの。`_close_paren` 1071-1072 だけはスクリプトの行番号。

## Objectives

- サブシェルの中で、仮の群の最初の直接の区切りが `;` か単独の `&` で、後の `)` がその群を閉じる形を deny にする。
- chain_base が None（最上位）か `{` 群の場合の `)` の読みは変えない。
- 2 つのコピーをバイト単位で同一に保つ。

## User Stories

### US1: サブシェルの中の再現形と変形を deny にする
em-workflow / em-review の利用者として、サブシェルの中で仮の群を `)` で閉じる形を deny にしてほしい。

**Acceptance Criteria:**
- [ ] AC1: 再現形が両コピーとも deny になる。
- [ ] AC2: 単独の `&` の形、入れ子の連鎖の形、語が残る `)` の形、`)` の後に続きがある形が deny になる。

### US2: 対象外の形は読みを変えない
em-workflow / em-review の利用者として、救済の条件を満たさない形と既存の行の結果は変わらないでほしい。

**Acceptance Criteria:**
- [ ] AC3: 最初の直接の区切りが `&&`・改行の形、閉じた群が接続される形、関数定義の本体の中の形、`)` がコメントの中にある形は silent になる。
- [ ] AC4: 行 672 を `... } #)` の形に直して silent とし、元の入力を既知の誤拒否と書いた deny の行として足す。`( function { :; } foo(a; python3) ) < /dev/null` も既知の誤拒否と書いた deny の行として足す。
- [ ] AC5: 最上位の行（560、591-633）と `}` 救済の行（641-676、672 を除く）の結果が変わらない。

### US3: 性能と制約を保つ
em-workflow / em-review の利用者として、解析の性能と既存の制約が保たれてほしい。

**Acceptance Criteria:**
- [ ] AC6: chain_base が `(` 群で深い連鎖を `)` で閉じる規模テストが、制限時間内に答えを返す（deny）。
- [ ] AC7: `python3 -m unittest tests.test_codex_hook_interactive_guard` が全て通り、2 つのコピーがバイト単位で同一のまま。docstring テストも通る。

## Technical Requirements

### Functional Requirements
- **FR1:** 再現形を deny — `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'` を両コピーとも deny にする。単独の `&` を区切りにした形 `( function { :; } foo(a & python3 -i; )` も deny にする。
- **FR2:** `)` の時点での救済 — `)` を読んだときに次がすべて成り立てば、仮の群の連鎖を内側から救済し、連鎖のすぐ外側の `(` 群（chain_base）を閉じる。
    - 最内の開いた群が仮の群であること。
    - その連鎖が既存の区切り条件を満たすこと（`_rescue_separator`・`outer_blocked`）。直接の first_sep だけで判断し、範囲を見つけた先読みは使わない。
    - chain_base が仮でない `(` 群であること。
    - 判定は群を開いたときに `_mark_provisional` が固定した値だけを読み、定数時間で済ませる。連鎖の各群は開いた群から 1 回だけ取り除く。救済した群の `(` は引数の語の文字として読み、群はその区切りで終わる。条件を満たさない `)` は従来どおり最内の `(` 群を閉じる。
- **FR3:** 区切り条件は共通の定義のまま — 救済の条件は `_rescue_separator` の定義 1 つを、入力の終わりでの救済・`}` での救済・`)` での救済で共有する。最初の直接の区切りが改行・`&&`・`||`・`|`・`|&` の場合、引用符やバックスラッシュで打ち消した `;` / `&` の場合、`&>` / `>&` の場合は救済しない。外側の仮の群に区切りが無ければ内側の区切りを受け継ぐ。
- **FR4:** 対象は chain_base が `(` 群の場合だけ — chain_base が None（最上位）の場合と `{` 群の場合、`)` の読みは変えない。行 560 の `function { :; } foo(a; python3 -i)` は群として読んで deny、`{` 群の場合は既存の `}` 救済の規則のまま。
- **FR5:** `)` の前に残る語 — 読み替える `)` の前に語が残っていれば、それを閉じる `(` 群のコマンドとして確定してから群を閉じる。`)` は残る語の有無によらず、語を終えてサブシェルを閉じる。
- **FR6:** 救済後のコマンドの所属と閉じた後の読み — 救済した群のコマンドは移動しない。救済で閉じた `(` 群のコマンドとして判定するので、群の後の入力リダイレクトやパイプの接続はそれらにも届き、関数定義の本体の中なら skipped になる。群を閉じた後のテキストは群の外として読む。その後に対の無い `)` があれば、既存のコードのとおり区切りとして読む（`_close_paren` 1071-1072）。
- **FR7:** 既存行 672 の扱い — 行 672 の入力は `)` をコメントの中に移した `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } #)'` に直し、silent のまま「仮の群のすぐ外側が ( 群なら } は閉じない」ことを確かめる行として残す。元の入力 `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } )'` は deny の行として新しく足し、zsh 5.9 では parse error になる既知の誤拒否だとラベルに書く。
- **FR8:** 行 661 の `}` 救済の再現形 — 行 661 の `}` 救済の再現形の行は期待値を deny に変え、ラベルを新しい読みに合わせる。640 行目のコメント（この行を判定不能に数えている）も直す。
- **FR9:** ドキュメントの更新 — モジュール docstring の手順 4、`_Parser`、`_Group`（provisional・chain_base・outer_blocked）、`_rescue_separator`、`_rescue_argument_groups`、`_read_argument_parens`、`_close_paren` と、変更・追加するメソッドの docstring を `)` での救済に合わせて直す。docstring テストが確かめている既存の文言（RESCUE_PROVISIONAL_MARKER、RESCUE_MARKERS、BRACE_CLOSE_MARKER、COMMENT_EXCEPTION_MARKERS など）は残し、STALE_DOCSTRING_SENTENCES と STALE_GROUP_SENTENCES の文は書き戻さない。
- **FR10:** 2 つのコピー — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で一緒に直し、バイト単位で同一に保つ。

### Non-Functional Requirements
- **NFR1 - 性能:** 解析は文字列の長さに対して線形時間のまま保つ。`)` での判定は定数時間で、各仮の群を取り除くのは 1 回だけにする。
- **NFR2 - 構造:** 再帰を使わない（`test_no_function_calls_itself_and_no_functions_form_a_cycle`）。
- **NFR3 - 安全性:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（既存の制約テスト）。
- **NFR4 - 判定:** この feature で足す読みのほかは、判定できない入力を silent のままにする。

## Implementation Approach

### Architecture

変更するのは `_Parser` の `)` の読みだけ。対象のコンポーネント:

```
codex-hook-interactive-guard.py（em-workflow / em-review の 2 コピー、バイト単位で同一）
└── _Parser
    ├── _Group（provisional・chain_base・outer_blocked）
    ├── _mark_provisional       群を開いたときに判定に使う値を固定する
    ├── _rescue_separator       区切り条件。入力の終わり・} ・) の救済で共有する
    ├── _rescue_argument_groups
    ├── _read_argument_parens
    └── _close_paren            ) での救済を足す
```

### Data Flow

`)` を読んだときの判定:

```
) を読む
  → 最内の開いた群が仮の群か
  → 連鎖が _rescue_separator・outer_blocked の条件を満たすか（直接の first_sep だけ）
  → chain_base が仮でない ( 群か
     すべて成り立つ:
       → ) の前に残る語を chain_base のコマンドとして確定する（FR5）
       → 連鎖の各群を開いた群から 1 回だけ取り除く
       → chain_base を閉じる
       → 閉じた後のテキストは群の外として読む（FR6）
     いずれかが成り立たない:
       → 従来どおり最内の ( 群を閉じる
```

chain_base が None か `{` 群の場合は、`)` の読みを変えない（FR4）。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `_rescue_separator`: 入力の終わりでの救済・`}` での救済と同じ定義を使う（FR3）。既存の区切り条件（行 603-615、656-657 で確かめている）は変えずに使う（A4）。
- `_mark_provisional`: 群を開いたときに固定した値を、`)` での判定が読む（FR2）。

**External Dependencies:**
- 標準ライブラリだけ（NFR3）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py
em-review/scripts/codex-hook-interactive-guard.py
tests/test_codex_hook_interactive_guard.py
```

## Declared Change Set

このセクションは手で列挙した一覧の代わりに create-plan での導出を述べる。このフィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

フィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する:

- `feature-docs/codex-guard-subshell-anon-arg-semicolon/**`
- `test-docs/codex-guard-subshell-anon-arg-semicolon/**`

`feature-docs/codex-guard-subshell-anon-arg-semicolon/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-subshell-anon-arg-semicolon/**` に含まれるもの: タスクごとのテスト記録 `test-docs/codex-guard-subshell-anon-arg-semicolon/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

既定の 2 つは、SPEC作成者が明示的に除外しない限り宣言に含まれる。記載が無いことで除外とはみなさない。除外は意図的な絞り込みとして明示する。

この宣言はスーパーセット（superset）の主張であり、verify 時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致は求めない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-subshell-anon-arg-semicolon/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-subshell-anon-arg-semicolon/**` は依然として正しい。実際には生成されないパスが宣言されていても違反にはならない。

## Test Scenarios

`tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` で並べ、同じ表を 2 つのコピーの両方に流す。

### Unit Tests
- [ ] TS1: 再現形（行 661 の行を反転）- deny（FR1・FR2・FR8）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'
    ```
- [ ] TS2: 単独の `&` - deny（FR1・FR3）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a & python3 -i; )'
    ```
- [ ] TS3: (c) 語が残る `)`。zsh 5.9 は R3 を出力する - deny（FR5）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i )'
    ```
- [ ] TS4: (d) `)` の後のコマンド。zsh 5.9 は R4R5 を出力する - deny（FR6）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; :; ); python3 -i'
    ```
- [ ] TS5: 入れ子の仮の群の連鎖 - deny（FR2）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(function { :; } bar(a; python3 -i; )'
    ```
- [ ] TS6: 最初の区切りが `&&` - silent（FR3）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a && python3 -i; )'
    ```
- [ ] TS7: 最初の区切りが改行。Python の文字列リテラルで書く（`\n` は改行）- silent（FR3）
    ```
    "zsh -c 'setopt nobadpattern; ( function { :; } foo(a\npython3 -i; )'"
    ```
- [ ] TS8: 閉じたサブシェルの入力リダイレクトが救済後のコマンドに届く - silent（FR6）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3; ) < /dev/null'
    ```
- [ ] TS9: 閉じたサブシェルのパイプ接続が届く - silent（FR6）
    ```
    zsh -c 'setopt nobadpattern; echo x | ( function { :; } foo(a; python3; )'
    ```
- [ ] TS10: 関数定義の本体の中は skipped - silent（FR6）
    ```
    zsh -c 'setopt nobadpattern; f() ( function { :; } foo(a; python3 -i; )'
    ```
- [ ] TS11: 行 672 を直した形。`}` は閉じない - silent（FR7）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } #)'
    ```
- [ ] TS12: 既知の誤拒否。zsh 5.9 では parse error（(b)）。元の行 672 の入力 - deny（FR7）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } )'
    ```
- [ ] TS13: 既知の誤拒否。zsh 5.9 では parse error（(a)）。救済で閉じた後の対の無い `)` は区切り - deny（FR6）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3) ) < /dev/null'
    ```
- [ ] TS14: 引用符の中の `)` は契機にならず、群が開いたまま残る - silent（FR2・NFR4）
    ```
    zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; ")"'
    ```

既存の行:
- [ ] 最上位の行（560、591-633）と `}` 救済の行（641-676、672 を除く）の結果が変わらない（AC5・FR4）。
- [ ] docstring テストが通る（FR9）。

### Integration Tests
- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が全て通る（AC7）。
- [ ] 2 つのコピーがバイト単位で同一のまま（FR10）。

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし
- [ ] 該当なし

### Edge Cases
- [ ] 区切りが `&&`・改行: 救済しない（TS6・TS7）。
- [ ] 引用符の中の `)`: 契機にならない（TS14）。
- [ ] コメントの中の `)`: `}` は閉じない（TS11）。
- [ ] 既知の誤拒否: TS12・TS13 は deny とし、ラベルに既知の誤拒否と書く（A2）。

### Performance Tests
- [ ] TS15: 規模。chain_base が `(` 群で深い連鎖を `)` で閉じる入力に、制限時間内に答える - deny（NFR1・NFR2）。Python の式で組み立てる
    ```
    '( ' + 'function { :; } x(' * depth + '; python3 -i; )'
    ```

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** この feature で足す読みのほかは、判定できない入力を silent のままにする（NFR4）。
- **Data Protection:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（NFR3）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

該当なし

### Error Flow

条件を満たさない `)` は従来どおり最内の `(` 群を閉じる（FR2）。救済で閉じた後の対の無い `)` は区切りとして読む（FR6）。

## Performance Optimization

### Performance Goals
- 解析は文字列の長さに対して線形時間（NFR1）。
- `)` での判定は定数時間（NFR1）。

### Optimization Strategies
- 判定に使う値: 群を開いたときに `_mark_provisional` が固定した値だけを読む（FR2）。
- 群の取り除き: 連鎖の各群は開いた群から 1 回だけ取り除く（FR2・NFR1）。

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] 2 つのコピーがバイト単位で同一（FR10）

## Assumptions

- A1: `setopt nobadpattern` のもとで zsh は引数の語 `foo(a` を最初の引用符の外の `;` か単独の `&` で終え、後の `)` を外側のサブシェルの閉じとして読む。
- A2: 既知の誤拒否 2 件（TS12、TS13）は、zsh 5.9 では parse error になり何も実行されない入力に限られ、受け入れる。
- A3: プラグインの version は変えない（push 時に Actions が patch を上げる）。
- A4: 既存の区切り条件（行 603-615、656-657 で確かめている）は変えずに使う。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
- 既存のテスト: `tests/test_codex_hook_interactive_guard.py`
- version の扱い: `.claude/rules/core-plugin-version-bump.md`
