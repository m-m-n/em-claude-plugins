# Feature: env-route-lex-flag-isolation

## Overview

destructive-guard の env 経路（`/usr/bin/env` などを経由した `bash -c` の本文の読み取り）が立てる字句解析の大域フラグ（`_lex_unreadable_met` と `_lex_extglob_met`）を、env 経路の中に閉じ込める。env 経路の本文の読み取りは notion ペアの検査だけに効かせ、notion 以外の判定を変えない。

デザイン工程: skipped（UI の無いフックの判定ロジックの修正）。

## Objectives

- destructive-guard の env 経路の本文の読み取りを notion ペアの検査だけに効かせ、notion 以外の判定を変えない
- 無人実行で、`/usr/bin/env` 経由の `bash -c` 本文に読めないヒアドキュメント区切り語があるだけで止まることを無くす

## Acceptance Criteria

- [ ] AC-1: `/usr/bin/env bash -c` の本文が区切り語 `${tag}` の cat のヒアドキュメントだけを持つコマンドを、`CLAUDE_BATCH` ありで destructive-guard に渡すと allow になる（lone `-` の env の形でも同じ）。（TS-1, TS-2）
- [ ] AC-2: 通常の `bash -c` の形と、env 経路の外で立ったフラグによる判定は変わらない。（TS-3, TS-4）
- [ ] AC-3: env 経路の notion ペアの検出範囲は狭まらない。extglob の有効時にだけ見える notion ペアの呼び出しも検出し deny になる。拡張パターンの括弧を含むだけで notion の無い本文の判定は変わらない。（TS-5, TS-6）
- [ ] AC-4: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` がすべて通る。TS-1〜TS-6 が `destructive-guard-cases.json` に入っている。（TS-7）

## Technical Requirements

### Functional Requirements

- **FR1: 大域フラグの退避と復元** — `_args_json_env_payload_values()` の本文の読み取り（`_args_json_payload_chunk()`、`_args_json_chunk_statements()`、`head()`、`_args_json_lifted_notion_words()`、`_args_json_read_values()` を通る `lex_shell()` の呼び出しのすべて）の前に `_lex_unreadable_met` と `_lex_extglob_met` の値を退避し、読み取りの後に退避した値へ戻す。本文に持ち上げられた notion 文があってもなくても戻す。戻す値は読み取り前の値であり、`False` ではない（env 経路より前に立っていたフラグはそのまま残る）。
- **FR2: 例外を含むすべての出口で復元** — FR1 の復元は、env 経路を抜けるすべての出口（途中の return、`LexBudgetExceeded` などの例外の送出を含む）で行う。例外そのものの扱い（`_judge_under()` の scan-budget の ask など）は変えない。
- **FR3: extglob の両方の読み方での notion 検査** — env 経路の本文の読み取り（その時点の読み方 `_lex_extglob` で行う）が拡張パターンの括弧に出会ったとき（読み取り中に返った `LexMap` の `ext_met` が真のとき）は、env 経路の中で extglob の有効時と無効時の両方で本文を読み、どちらかの読み方で見つかった notion ペアを検査する。2 回目の読み取りのために切り替えた `_lex_extglob` は、読み取りの後に元の値へ戻す。FR1 のフラグの復元は両方の読み取りの後に行う。
- **FR4: 両方の読み方で同じ notion 文が見つかったときの扱い** — FR3 で両方の読み方が同じ値（デコードした command 文字列、候補の本文）を返したときは、その値を 1 回だけ返し、charge も 1 回分だけ計上する。overrun と unrestorable はどちらかの読み方で立てば立てる。
- **FR5: 再発を検出するケース** — `em-workflow/hooks/tests/destructive-guard-cases.json` に、TS-1〜TS-6 のケースを追加する。batch の判定を固定するケースは 4 要素目に `{"batch": true}` を、ask / deny のケースには `rule` も付ける。

### Non-Functional Requirements

- **NFR1 - env 経路以外の判定の不変:** env 経路以外の `lex_shell()` の呼び出しが立てるフラグ、`run()` の 2 つ目の読み方（`_judge_under(payload, True)`）の起動条件、extglob-switch の判定、unreadable-heredoc-delimiter の判定は、env 経路の本文の読み取りを除いて変えない。
- **NFR2 - extglob の単位数の記録の不変:** extglob の単位数（`_lex_ext_seen`、`_count_extglob_units()`）は env 経路から記録されない現状を保つ（`_note_extglob_units()` の呼び出し元は `statements()` だけ）。
- **NFR3 - 既存ケースの維持:** 既存の deny / ask のケースは消さない。既存のケースはすべて通る。
- **NFR4 - version の据え置き:** `plugin.json` と `marketplace.json` の version は変えない。

## Implementation Approach

### 対象

- `em-workflow/hooks/destructive-guard.py` — env 経路（`_args_json_env_payload_values()`）の本文の読み取り（FR1〜FR4）
- `em-workflow/hooks/tests/destructive-guard-cases.json` — TS-1〜TS-6 のケース（FR5）

### 前提

- version は main への push で Actions が patch を上げるため、この変更では触らない。
- env 経路から `LexBudgetExceeded` が抜けたときの判定（scan-budget の ask）は変えず、フラグの復元だけを加える。
- env 経路は `statements()` を呼ばないため、extglob の単位数の記録に影響しない（現在のコードで確認した事実）。
- 本文に持ち上げられた notion 文があるとき、そこから取り出した command 文字列と候補の本文は `statements()` に queue され、その字句解析が立てるフラグは通常どおり `run()` に届く。env 経路の本文そのものの読み取りが立てたフラグだけを戻す。

### Commands

- テスト: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- ユニットテスト: `python3 -m unittest discover -s tests`

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を示す。機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

機能固有のパスに加えて、既定で次の 2 つのワークフロー生成物を宣言する。

- `feature-docs/env-route-lex-flag-isolation/**`
- `test-docs/env-route-lex-flag-isolation/**`

`feature-docs/env-route-lex-flag-isolation/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml` と、デザイン工程が作る成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有し、この節はそれらの規則を言い直さない。

`test-docs/env-route-lex-flag-isolation/**` はタスクごとのテスト記録 `test-docs/env-route-lex-flag-isolation/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有し、この節はその規則を言い直さない。

この 2 つの既定の宣言は、明示的に外さない限り宣言に含まれる。

この宣言は上位集合の宣言であり、検証時に観測した実際の変更集合は宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生まない機能では `test-docs/env-route-lex-flag-isolation/` は作られないが、宣言した `test-docs/env-route-lex-flag-isolation/**` はその場合も正しく、実体化しない宣言パスは違反ではない。

## Test Scenarios

### Hook Decision Cases（`em-workflow/hooks/tests/destructive-guard-cases.json`）

- [ ] TS-1: `["allow", ..., "/usr/bin/env bash -c '<本文>'", {"batch": true}]`。本文は `cat <<${tag}` で始まり、無害な行と `${tag}` の区切り語の行だけを持つヒアドキュメント。修正前は deny（unreadable-heredoc-delimiter）になる。
- [ ] TS-2: TS-1 と同じ本文を `env - bash -c '<本文>'` の形で渡し、batch で allow。
- [ ] TS-3: 対照: TS-1 と同じ本文を `bash -c '<本文>'`（env 無し）で渡し、batch で deny、rule unreadable-heredoc-delimiter。現状の判定を固定する。
- [ ] TS-4: env 経路の外で立ったフラグが残ること: `/usr/bin/env bash -c 'echo hi'` の文と、トップレベルの読めない区切り語のヒアドキュメント（例: `cat <<$(x)`、`echo hello`、`$(x)` の行）を 1 つのコマンドに並べ、batch で deny、rule unreadable-heredoc-delimiter。復元先が `False` ではなく読み取り前の値であることを固定する。
- [ ] TS-5: `/usr/bin/env bash -c` の本文が配列の中の拡張パターンの括弧（例: `a=(@(x))`）を含み notion 呼び出しを含まないとき、判定は env 経路の読み取りが無いときと同じ（allow）。
- [ ] TS-6: cases.json 1590 行目の既存の mcp-bridge-function-shadow のケースと同じ形の notion ペアの呼び出し（`git branch -D` を command に持つ）を、extglob 無効時は構文エラーとして捨てられる行（配列の中の拡張パターンの括弧を含む行）の同じ行の後ろに `;` で続けた本文を `/usr/bin/env ... bash -c` で渡し、deny。extglob の有効時の読み方でだけ notion ペアが見えることを実装時に字句解析器で確かめる。FR1 だけを入れて FR3 を入れない実装では allow に落ちて失敗すること（red）を確かめる。

### Regression

- [ ] TS-7: 既存の mcp-bridge-function-shadow のケース 2 件を含む既存ケースがすべて通り、`python3 -m unittest discover -s tests` も通る。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] AC-1〜AC-4 を満たす
- [ ] TS-1〜TS-7 が通る

## Open Questions

なし
