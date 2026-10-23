# Feature: codex-guard-escaped-hash-brace-case-heredoc

## Overview

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）の置換の読み（`_skip_substitution`）で、エスケープした文字や継続行の後の `#` を語の文字として読み、zsh の波括弧形式の `case x { ... }` を読めるようにする。ヒアドキュメントは rule 8 のまま判定不能で silent とする。docstring とコメントを実際の読みに合わせる。

要件の詳細は `feature-docs/codex-guard-escaped-hash-brace-case-heredoc/REQUIREMENTS.md` を参照する。

## Objectives

- codex-hook-interactive-guard（em-workflow / em-review の両コピー）の置換の読み（`_skip_substitution`）で、エスケープした文字や継続行の後の `#` をコメントの始まりと読み違えて判定不能になり、後ろの対話コマンド（`python3 -i` など）を拒否しない漏れ（fail-open）を塞ぐ
- zsh の波括弧形式の `case x { ... }` を置換の中で読み、閉じ位置を確定して後ろの対話コマンドを検査できるようにする
- ヒアドキュメントの扱いは今の rule 8（case 文の中は判定不能で silent）のまま保つ
- docstring とコメントを実際の `#` の判定と波括弧形式の case の読みに合わせる

## User Stories

N/A

## Technical Requirements

### Functional Requirements

- **FR1:** エスケープした文字と継続行の後の # の判定 — `_skip_substitution` の中で、`#` がコメントを始めるのは、直前の文字が空白・タブ・改行・`;`・`&`・`|`・`(` のどれかで、かつその文字がエスケープされていない（バックスラッシュの対の 2 文字目でない）ときだけとする。継続行（バックスラッシュの直後の改行）は判定の上で透明とし、継続行の前の文字で決める（`: a\<改行>#x` の `#` は語の文字、`: \<改行>#x` の `#` はコメントの始まり）。エスケープした空白・タブ・`;`・`&`・`|`・`(` の後の `#` は語の文字とする。対象は `#` の判定をしている全箇所: コマンド列 p と項目本体 8 の語の始まりの判定（現 2701 行）と一般のコメント判定（現 3004 行）、パターン 6 と群 g（現 2903 行）、語一覧 w の最も外側の項目（現 2998 行）。case 文の待ちの段（1・3・4・5・7、現 2771 行）も同じ条件に揃える。`)` の直後（rule 3 を含む）・`<`・`>` の直後の `#` の読みは今のまま変えない
- **FR2:** 波括弧形式の case の開始 — case 文の対象の後の in を待つ段（phase 3）で、継続行を除いた文字で単独の語の `{`（続く文字が空白・タブ・改行、または入力の終わり）を in の代わりとして受け付け、その case 文を波括弧形式としてパターン位置（phase 4）へ進める。引用・エスケープした `{` や、単独の語でない `{` は今のまま case without in で判定不能とする。in 形式の読みは変えない
- **FR3:** 波括弧形式の case の閉じ — 波括弧形式の case 文は次で閉じる。(a) パターン位置で単独の語の `}`（引用・エスケープしていないもの）。(b) パターン位置で単独の語の `esac`（zsh 5.9 の実測で受理）。(c) 項目本体のコマンド位置の単独の `}` で、その項目本体の中で開いている `{ }` 群の深さが 0 のとき。閉じた後は、esac で閉じたときと同じく case 文を持つリストがコマンド位置になる。引用・エスケープした `}` や `esac` はパターンを始める（パターン位置）か普通の語（本体）として読む
- **FR4:** 波括弧形式の case の項目本体の { } 群の深さ — 波括弧形式の case 文ごとに、項目本体のリストそのもので読んだコマンド位置の単独の `{` で深さを 1 上げ、コマンド位置の単独の `}` で深さが 1 以上なら 1 下げる。引用・エスケープした括弧、`${ }`・置換・算術・語の括弧の中の括弧、本体の中で開いた入れ子のリスト（サブシェル、置換、入れ子の case 文）の中の括弧は数えない。入れ子の case 文（in 形式・波括弧形式とも）は自分の状態を持ち、外側の case 文の深さと混ざらない。深さが 1 以上のまま項目の終端（`;;` `;&` `;|` `;;&`）を読んだら判定不能とする。波括弧形式の項目本体のコマンド位置の `esac` は判定不能とする（zsh 5.9 の実測で parse error）
- **FR5:** 算術コマンドの読み直しでの状態の復元 — 波括弧形式かどうかと `{ }` 群の深さ（FR2〜FR4 で足す状態）は、算術コマンド `((` の読み直し（rule 9）で `((` の時点の値に戻す
- **FR6:** ヒアドキュメントは今のまま — ヒアドキュメントの読みは rule 8 のまま変えない。case 文の中（波括弧形式を含む）の `<<` は判定不能で silent、case 文の外の `<<` は改行が来るまで保留する。既存 CASES の 1050・1293・1298〜1300・1305 行は silent のまま
- **FR7:** docstring とコメントの更新 — `_skip_substitution` の docstring（rule 2 の case 文の開閉、判定不能になる形の一覧、語一覧 w の `#` と語の始まりの説明）と、w の状態を進める箇所・w 分岐・`#` の判定箇所のコメントを、実際の `#` の判定（FR1）と波括弧形式の case の読み（FR2〜FR5）に合わせる。判定不能の一覧から「no `in` after the subject (zsh's brace form included)」の波括弧形式の部分を外し、波括弧形式で判定不能になる形（FR4 の 2 つ）を加える。「The start of a word is a state kept while reading and never looked up backward」は、`#` の判定を含めて実際と食い違わない文にする
- **FR8:** テストの追加と更新 — `tests/test_codex_hook_interactive_guard.py` の `CASES` に再現手順 2・3・4 の入力（deny）と、FR1〜FR6 の境界の入力を追加し、両コピーに流す。既存行 1051（zsh の `case x { x) :;; }` の形）を deny に変え、ラベルを読める形に合わせる。docstring の文言を固定しているテスト（`UNDECIDABLE_MARKERS`、`WORD_LIST_PROCESS_SUBSTITUTION_MARKERS` など）を FR7 の文に合わせる
- **FR9:** 両コピーの同一性 — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更で直し、バイト単位で同一に保つ

### Non-Functional Requirements

- **NFR1 - 線形の読み:** 置換の読みは 1 回の前向きの走査のまま、全体の仕事量を文字列の長さの定数倍に保つ。`#` の判定に後ろ向きの探索を足すときも、1 文字あたり定数の仕事に収める
- **NFR2 - 既存の判定の維持:** CASES の既存行は 1051 行を除いて期待する判定を変えない。既存の deny / ask・silent の行を消さない
- **NFR3 - 置換の中身は判定しない契約:** 置換の中身のコマンドは判定せず、閉じ位置だけを読む契約を保つ。閉じ位置が確定しないときは判定不能で、確定済みのコマンドだけを検査する（silent の契約）
- **NFR4 - version を触らない:** プラグインの version は変更しない（`.claude/rules/core-plugin-version-bump.md`）

## Implementation Approach

### Architecture

N/A

### Data Flow

N/A

### API Design

N/A

### Database Schema

N/A

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py`: バイト単位で同一に保つ（FR9）

**External Dependencies:**
- N/A

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py
em-review/scripts/codex-hook-interactive-guard.py
tests/test_codex_hook_interactive_guard.py
```

現在のファイルでの該当行（A8）:

- `#` の判定: 2701・2771・2903・2998・3004 行
- case without in: 2778・2875・2898 行
- heredoc in a substitution: 2695・2885・3014 行

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-escaped-hash-brace-case-heredoc/**`
- `test-docs/codex-guard-escaped-hash-brace-case-heredoc/**`

`feature-docs/codex-guard-escaped-hash-brace-case-heredoc/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-escaped-hash-brace-case-heredoc/**` covers `test-docs/codex-guard-escaped-hash-brace-case-heredoc/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-escaped-hash-brace-case-heredoc/` directory at all; the declared
`test-docs/codex-guard-escaped-hash-brace-case-heredoc/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

テストは `tests/test_codex_hook_interactive_guard.py` の `CASES` に置き、両コピーに流す。

### Unit Tests

- [ ] TS-1（FR1）: `zsh -c 'echo "$(for x (<(: \ #x)) { :; })"; python3 -i'` - deny
- [ ] TS-2（FR1）: `zsh -c 'echo "$(: \ #x)"; python3 -i'` - deny
- [ ] TS-3（FR2, FR3）: `zsh -c 'echo "$(for x (<(case x { x) :;; })) { :; })"; python3 -i'` - deny
- [ ] TS-4（FR2, FR3, FR4, FR6, FR8, NFR2）: `echo "$(case x { x) :;; })"; python3 -i`（既存 1051 行の変更） - deny
- [ ] TS-5（FR1）: `echo "$(: a\<改行>#x)"; python3 -i`（語の文字の後の継続行の後の `#` は語の文字） - deny
- [ ] TS-6（FR1）: `zsh -c` で `printf x \<改行># )"; python3 -i; echo "<改行>)` を置換に入れた形（空白の後の継続行の後の `#` はコメントのままで、コメントの中の `)` で閉じない） - silent
- [ ] TS-7（FR1）: `echo "$(: a\;#x)"; python3 -i`（エスケープした `;` の後の `#` は語の文字） - deny
- [ ] TS-8（FR1）: `echo "$(case x in x) : \ #y;; esac)"; python3 -i`（項目本体） - deny
- [ ] TS-9（FR1）: `echo "$(case x in a\ #b) :;; esac)"; python3 -i`（パターン） - deny
- [ ] TS-10（FR1）: `echo "$(for x (a\ #b) { :; })"; python3 -i`（語一覧の最も外側の項目） - deny
- [ ] TS-11（FR6, FR8, NFR2）: `echo "$(: >#x)"; python3 -i`（`>` の後の `#` の読みは今のまま） - deny
- [ ] TS-12（FR2, FR3, FR4）: `zsh -c 'echo "$(case x { x) :;; esac)"; python3 -i'`（パターン位置の `esac` で閉じる） - deny
- [ ] TS-13（FR2, FR3, FR4）: `echo "$(case x { x) :; })"; python3 -i`（項目本体の深さ 0 の `}` で閉じる） - deny
- [ ] TS-14（FR2, FR3, FR4）: `echo "$(case x { x) { :; };; })"; python3 -i`（本体の `{ }` 群は閉じでない） - deny
- [ ] TS-15（FR2, FR3, FR4）: `echo "$(case x { x) echo "}" '{' \{;; })"; python3 -i`（引用・エスケープした括弧は数えない） - deny
- [ ] TS-16（FR2, FR3, FR4）: `echo "$(case x { x) echo };; })"; python3 -i`（引数の位置の `}` は閉じない） - deny
- [ ] TS-17（FR2, FR3, FR4）: `echo "$(case x { x) case y in y) :;; esac;; })"; python3 -i`（波括弧形式の中の in 形式） - deny
- [ ] TS-18（FR2, FR3, FR4）: `echo "$(case x in x) case y { y) :;; };; esac)"; python3 -i`（in 形式の中の波括弧形式） - deny
- [ ] TS-19（FR4, FR6）: `echo "$(case x { x) cat <<E<改行>body<改行>E<改行>;; })"; python3 -i`（波括弧形式の中のヒアドキュメント） - silent
- [ ] TS-20（FR4, FR6）: `echo "$(case x { x) :;;"; python3 -i`（閉じない波括弧形式） - silent
- [ ] TS-21（FR4, FR6）: `echo "$(case x { x) :; esac)"; python3 -i`（波括弧形式の本体の `esac`） - silent
- [ ] TS-22（FR4, FR6）: `echo "$(case x { x) { :;; })"; python3 -i`（深さ 1 以上での項目の終端） - silent
- [ ] TS-23（FR2, FR3, FR4）: `echo "$(case x "{" x) :;; })"; python3 -i`（引用した `{` は in の代わりにならない） - silent
- [ ] TS-24（FR6, FR8, NFR2）: `echo "$(case x { x) python3 -i;; })"`（置換の中身は判定しない） - silent
- [ ] TS-25（FR5）: `echo "$(case x { x) { ((echo a) ); };; })"; python3 -i`（算術コマンドの読み直しを挟む） - deny
- [ ] TS-26（FR7, FR8）: docstring の文言テスト（判定不能の一覧・語の始まり・語一覧の `#` の説明） - pass

### Integration Tests

- [ ] TS-27（FR8, FR9）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と両コピーのバイト比較 - pass

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 継続行の前の文字で `#` の読みが決まる: TS-5（deny）、TS-6（silent）
- [ ] 波括弧形式で判定不能になる形: TS-19・TS-20・TS-21・TS-22（silent）
- [ ] 引用した `{` は in の代わりにならない: TS-23（silent）

### Performance Tests

- [ ] NFR1: 置換の読みは 1 回の前向きの走査のまま、全体の仕事量を文字列の長さの定数倍に保つ

## Security Considerations

- **Input Validation:** 閉じ位置が確定しないときは判定不能で、確定済みのコマンドだけを検査する（NFR3）
- 上記以外: N/A

## Error Handling

判定不能（`_Undecidable`、silent）になる形:

- 引用・エスケープした `{` や、単独の語でない `{` を case 文の対象の後に置いた形（case without in、FR2）
- 波括弧形式で、深さが 1 以上のまま項目の終端（`;;` `;&` `;|` `;;&`）を読んだ形（FR4）
- 波括弧形式の項目本体のコマンド位置の `esac`（FR4）
- case 文の中（波括弧形式を含む）の `<<`（FR6）

## Performance Optimization

- NFR1: `#` の判定に後ろ向きの探索を足すときも、1 文字あたり定数の仕事に収める

## Success Criteria

- [ ] AC-1（FR1）: 再現手順 2 の `zsh -c 'echo "$(for x (<(: \ #x)) { :; })"; python3 -i'` を deny する
- [ ] AC-2（FR1）: 再現手順 3 の `zsh -c 'echo "$(: \ #x)"; python3 -i'` を deny する
- [ ] AC-3（FR2, FR3）: 再現手順 4 の `zsh -c 'echo "$(for x (<(case x { x) :;; })) { :; })"; python3 -i'` を deny する
- [ ] AC-4（FR1）: 継続行の前が語の文字なら `#` は語の文字、空白なら `#` はコメントの始まりとして読む。エスケープした `;`・`&`・`|`・`(` の後の `#` も語の文字として読む。パターン・項目本体・語一覧の最も外側の項目でも同じ
- [ ] AC-5（FR2, FR3, FR4）: 波括弧形式の case 文をパターン位置の `}`・`esac`、項目本体の深さ 0 の `}` で閉じ、本体の `{ }` 群・引用した括弧・引数の位置の `}`・入れ子の case 文を閉じと取り違えない
- [ ] AC-6（FR4, FR6）: 波括弧形式の本体の `esac`、深さ 1 以上での項目の終端、閉じない波括弧形式、波括弧形式の中のヒアドキュメントは判定不能（silent）
- [ ] AC-7（FR5）: 算術コマンドの読み直しを挟んでも波括弧形式の case 文を正しく閉じる
- [ ] AC-8（FR6, FR8, NFR2）: 既存 CASES 1051 行は deny、1050・1293・1298〜1300・1305 行は silent。それ以外の既存行の判定は変わらない
- [ ] AC-9（FR7, FR8）: docstring とコメントが実際の `#` の判定と波括弧形式の case の読みを述べ、文言を固定するテストが通る
- [ ] AC-10（FR8, FR9）: `python3 -m unittest tests.test_codex_hook_interactive_guard` が両コピーで通り、両コピーがバイト単位で同一

## Assumptions

- A1: 質問 requirement.brace-case-heredoc-handling の回答（read_brace_case_keep_heredoc、batch の Codex 相談、記録上は前提）に従う: 波括弧形式の case を読み、ヒアドキュメントは rule 8 のまま判定不能で silent
- A2: 前回の前提 A3（波括弧形式では esac は閉じ語でない）は回答の zsh 5.9 実測で置き換える: パターン位置の esac は閉じ、項目本体のコマンド位置の esac は parse error なので判定不能とする
- A3: 項目本体のコマンド位置の `}`（深さ 0）で波括弧形式の case 文が閉じる読みは、zsh の文法（本体が esac で閉じない以上、閉じは `}`）からの推定で、実測していない。TS-13 は `zsh -c` で包まない形にし、zsh が受け付けない場合も誤拒否は実行されない文字列に限られる
- A4: 深さ 1 以上で項目の終端を読んだときは判定不能とする（シェルの文法で `{ }` 群の中の `;;` は構文エラー）
- A5: 波括弧形式の読みはシェルの種類に関わらず適用する（既存 1051 行は `zsh -c` で包まない形で deny に変える回答に合わせる）
- A6: `#` の判定の修正は p だけでなく、同じ直前 1 文字の判定を持つパターン・群・語一覧の最も外側の項目にも当てる（docstring が語一覧の `#` を「same start condition as in a command list」と書いているため）
- A7: 対象外: in 形式のパターン位置の `}` による閉じ（zsh 5.9 は受理するが今の読みのまま）、メインの読みの `)` 救済 case 印（既存 870 行の既知の見逃し A9 は silent のまま）、`)`・`<`・`>` の直後の `#` の読み
- A8: task_description の該当行番号（2633・2663〜2669・2394・2469・2677）は現在のファイルではずれている。現在は `#` の判定が 2701・2771・2903・2998・3004 行、case without in が 2778・2875・2898 行、heredoc in a substitution が 2695・2885・3014 行

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Implementation Phases (if applicable)

N/A

## References

- `feature-docs/codex-guard-escaped-hash-brace-case-heredoc/REQUIREMENTS.md`
- `feature-docs/codex-guard-procsub-in-wordlist/reviews/round1.yaml`（ブランチ `em-workflow/codex-guard-procsub-in-wordlist/integration`）の `evaluation.round_summary`
- `.claude/rules/core-plugin-version-bump.md`
- `.claude/rules/hook-tests.md`
