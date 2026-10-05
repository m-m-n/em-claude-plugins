# Feature: codex-interactive-guard-hook

## Overview

em-workflow と em-review の `run_codex_exec.sh` が、`codex exec` の起動に PreToolUse hook（`scripts/codex-hook-interactive-guard.py`）を渡す。hook は Bash ツールのコマンド文字列を解析し、対話モードの処理系の起動を拒否する。判定できないものは通す。

要件定義は `feature-docs/codex-interactive-guard-hook/REQUIREMENTS.md` を参照。

## Objectives

- Codex レビュアーと、同じラッパーを使う Codex 相談が、疑似端末付きで対話モードの処理系（`python3 -i` など）を起動できないようにする。
- 端末が閉じた後も空回りし続ける孤児プロセスを生まないようにする。

## User Stories

### US1: Codex に対話モードの処理系を起動させない
As a em-workflow / em-review の利用者, I want to Codex レビュアーと Codex 相談が疑似端末付きで対話モードの処理系を起動できないようにする, so that 端末が閉じた後も空回りし続ける孤児プロセスが生まれない.

**Acceptance Criteria:**
- [ ] AC1: em-workflow 既定経路・`--litellm` 経路・em-review の各起動 argv に、`hooks.PreToolUse` を設定する `-c` 値が含まれる。matcher は `"Bash"` で、command はそのプラグインの `scripts/codex-hook-interactive-guard.py` を絶対パスで指す。
- [ ] AC2: 同じ 3 つの起動 argv に `--dangerously-bypass-hook-trust` が含まれる。readonly と readwrite の両モードで成り立つ。
- [ ] AC3: `em-workflow/scripts/` と `em-review/scripts/` に `codex-hook-interactive-guard.py` があり、2 つはバイト単位で同一である。
- [ ] AC4: `python3 -i`、`python3 -B -i -c ...`、`bash -i`、`python3 -Bi`、`node -i`、`lua -i`、`python3.14 -i`、`cd x && python3 -i`、`bash -lc 'python3 -i'` は拒否の JSON を出す。
- [ ] AC5: `python3`、`node`、`python3 -B`、`ruby`、`perl`、`deno`、`irb`、`ipython` を単独で起動すると拒否の JSON を出す。
- [ ] AC6: `python3 -c '...'`、`python3 script.py`、`python3 - <<EOF`、`python3 <<EOF`、`cmd | python3`、`python3 < f`、`python3 --version`、`python3 script.py -i`、`perl -i -pe ...`、`ruby -i`、`sed -i`、`echo 'python3 -i'`、`python3-config` は何も出力しない。
- [ ] AC7: 不正な JSON、command 欠落、閉じていないクォートでは、何も出力せず exit 0 になる。
- [ ] AC8: 両プラグインの `codex-reviewer.md` の Step 4 に、対話モードを使わず `python3 -c` などで確かめる旨が書かれ、Step 5 の起動行と見出しは変わっていない。
- [ ] AC9: `--ignore-user-config` の付け外しと usage 文言が変わらず、`python3 -m unittest discover -s tests` がすべて通る。

## Technical Requirements

### Functional Requirements
- **FR1:** em-workflow 既定経路で hook を渡す — `em-workflow/scripts/run_codex_exec.sh` の既定経路の `codex exec` 起動に、`-c "hooks.PreToolUse=[...]"`（matcher は `"Bash"`、command は同じプラグインの `scripts/codex-hook-interactive-guard.py` を絶対パスで実行する）と `--dangerously-bypass-hook-trust` を足す。既存の `-c` 上書き（推論 effort、otel）と `--ignore-user-config` は消さない。
- **FR2:** em-workflow --litellm 経路で hook を渡す — `--litellm` 経路の起動にも FR1 と同じ 2 つを足す。`-p litellm -m MODEL` が argv の中で連続する並びは崩さない。この経路は従来どおり `--ignore-user-config` を付けない。
- **FR3:** em-review で hook を渡す — `em-review/scripts/run_codex_exec.sh` の起動にも、em-review の `scripts/codex-hook-interactive-guard.py` を指す同じ 2 つを足す。
- **FR4:** 全起動に適用 — hook は readonly と readwrite の両モード、em-workflow の既定経路と `--litellm` 経路、em-review のすべての起動に渡す。
- **FR5:** hook スクリプトの配置と同一性 — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を置く。Python 3、標準ライブラリだけを使う。2 つのファイルはバイト単位で同一にする。
- **FR6:** -i 付き起動の拒否 — 次の処理系が `-i` を伴って起動されたら拒否する: python 系、node、bash / sh / zsh / dash / ksh、lua。`-i` は束ねた短いオプション（`-Bi`、`-ic`）の中にあっても検知する。node は `--interactive` も同じ扱い。オプションの読み取りは、最初のオペランド、または `-c` / `-m` / `-e` の値で止める。それより後ろの `-i` は対象の引数なので拒否しない。`perl -i`、`ruby -i`、`php -i`、`sed -i` は拒否しない。
- **FR7:** 引数なし起動の拒否 — FR6 の処理系と ruby、perl、deno、irb、ipython について、次の条件をすべて満たす起動を拒否する: スクリプトのオペランドが無い、コードを渡すオプション（`-c` / `-m` / `-e` と、その処理系での同等のもの）が無い、`-` が無い、標準入力が `<` / `<<` / `<<<` でリダイレクトされていない、パイプの右側でもない。`python3 -B` のようにオプションだけの起動も拒否する。長いオプション `--version` / `--help` は拒否しない。情報表示の短いオプションは処理系ごとに定める。bash / sh / zsh / dash / ksh には無く、シェルの `-h` / `-V` は拒否しないオプションに含まれない。
- **FR8:** 処理系名の判定 — コマンド語の basename が既知の名前そのもの、または既知の名前に数字と点だけの接尾が付いたもの（`python3.14`、`python3.N`、`ipython3`、`node22` など）のとき、同じ処理系とみなす。それ以外の接尾（`python3-config`、`bashcov` など）は対象外。
- **FR9:** コマンドの解析範囲 — `tool_input.command` の文字列を解析して判定する（入力に tty の情報は無い）。手順: heredoc 本文を除く。`;` `&&` `||` `|` 改行で単純コマンドに分ける。リダイレクトを除く。先頭の環境変数の代入、オプションの無いラッパー（`env` / `nohup` / `nice` / `exec` / `command` / `time` / `sudo`）、`timeout DURATION` を読み飛ばす。`bash -c` / `bash -lc` / `sh -c` にリテラル文字列が渡されていたら、その文字列を 1 段だけ同じ手順で判定する。クォートの中、コメント、heredoc 本文は判定しない。
- **FR10:** 対話モードでない起動は通す — `python3 -c '...'`、`python3 script.py`、`python3 - <<EOF` は拒否しない（何も出力せず exit 0）。
- **FR11:** fail-open — 入力 JSON が壊れている、`tool_input.command` が無いか文字列でない、閉じていないクォートや heredoc がある、例外が起きた、オプション付きのラッパー（`env -i` など）でくるまれている——このように判定できない場合は、何も出力せず exit 0 で抜ける。hook 自体が起動できない・失敗した場合は Codex の既定の挙動（コマンドを実行する）に任せる。
- **FR12:** 拒否の出力形式 — 拒否するときは stdout に `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}` を出して exit 0。理由文は日本語で書き、`python3 -c`、スクリプトファイル、`python3 - <<EOF` への切り替えを示す。
- **FR13:** レビュアーへの指示 — `em-workflow/agents/codex-reviewer.md` と `em-review/agents/codex-reviewer.md` の Step 4 の `<grounding_rules>` に入れる内容として、対話モードの処理系を起動せず、`python3 -c` などで確かめることを書き足す。Step 5 の起動行、各見出し、`'timeout of 600000 milliseconds'` の記述は変えない。
- **FR14:** テストとルール — `tests/test_codex_hook_interactive_guard.py` を足す。`(期待する判定 deny|silent, ラベル, コマンド)` の CASES 表を両方のコピーに対して流し、両コピーのバイト一致も確かめる。stub の codex を使うラッパーテストで、3 つの起動経路の argv に hook の `-c` 値（matcher `Bash`、そのプラグインのスクリプトの絶対パス）と `--dangerously-bypass-hook-trust` があることを確かめる。`.claude/rules/hook-tests.md` に、この hook のテストコマンドとケース表の形式を書いた節を足す。

### Non-Functional Requirements
- **NFR1:** hook は標準ライブラリだけを使う。ネットワーク、ファイル書き込み、サブプロセスには触れない。
- **NFR2:** 誤爆（対話モードでないコマンドの拒否）を避けることを優先する。判定できないものは通す。
- **NFR3:** 既存テストの固定を壊さない: em-workflow ラッパーの起動は 1 回、テキストに `2>&1` を含めない、usage 文言、既定経路は `--ignore-user-config` ありで `-p` / `-m` なし、`--litellm` 経路は `-p litellm -m MODEL` が連続し `--ignore-user-config` なし、em-review ラッパーの非コメント行で `'codex exec'` が 1 回、`codex-reviewer.md` の起動行と見出し。
- **NFR4:** テストは stub の codex を PATH の先頭に置き、HOME を隔離して実行する。本物の Codex には触れない。`python3 -m unittest discover -s tests` がすべて通る。
- **NFR5:** `--ignore-user-config` と `--ignore-rules` を外さない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
em-workflow/scripts/run_codex_exec.sh（既定経路 / --litellm 経路、readonly / readwrite）
em-review/scripts/run_codex_exec.sh（readonly / readwrite）
  └─ codex exec ... -c "hooks.PreToolUse=[...]" --dangerously-bypass-hook-trust ...
        └─ Bash ツールの呼び出しごとに PreToolUse hook を実行
              └─ <そのプラグイン>/scripts/codex-hook-interactive-guard.py
                    stdin : PreToolUse JSON
                    stdout: 拒否の JSON、または空
                    exit  : 0
```

### ラッパーの変更（FR1〜FR4）

- `-c` の値は TOML 配列で、次の形とする（A6）。

  ```
  [{matcher="Bash", hooks=[{type="command", command="python3 '<SCRIPT_DIR>/codex-hook-interactive-guard.py'"}]}]
  ```

  - 正確なキー名と、command がシェル経由で実行されるかどうかは、実装時に Codex 0.160.0 で確かめる。
  - パスに含まれる引用符や空白は TOML とシェルの両方でエスケープする。
- `<SCRIPT_DIR>` はそのラッパーと同じプラグインの `scripts/` の絶対パス。
- ラッパーは hook スクリプトの有無を確かめずに渡す。ファイルが無い場合は Codex の fail-open に任せる（A5）。
- 既存の `-c` 上書き（推論 effort、otel）、`--ignore-user-config`、`--ignore-rules` は消さない（FR1、NFR5）。
- 引数の並びは NFR3 の固定を崩さない。`--litellm` 経路の `-p litellm -m MODEL` は連続させる（FR2）。
- usage 文言と受け付けるフラグは変えない（A4）。`--ignore-user-config` の付け外しも変えない（A3）。

### Data Flow（hook の判定手順）

```
stdin の JSON を読む
  → tool_input.command を取り出す（無い・文字列でない → 出力なしで exit 0）
  → heredoc 本文を除く
  → ; && || | 改行で単純コマンドに分ける
  → 各単純コマンドについて:
       リダイレクトを除く（標準入力のリダイレクトの有無は FR7 の判定に使う）
       先頭の環境変数の代入、オプションの無いラッパー、timeout DURATION を読み飛ばす
       オプション付きのラッパー（env -i など）→ 判定しない（fail-open）
       bash -c / bash -lc / sh -c のリテラル文字列 → 1 段だけ同じ手順で判定
       コマンド語の basename で処理系を判定（FR8）
       -i 付き起動（FR6）または引数なし起動（FR7）→ 拒否
  → 拒否が 1 つでもあれば拒否の JSON を出して exit 0
  → それ以外は出力なしで exit 0
```

- 判定ロジックは `em-workflow/hooks/interpreter-mismatch-guard.py` の解析手順（heredoc 除去、単純コマンドへの分割、リダイレクト除去、ラッパー読み飛ばし）を写して使う。`em-workflow/hooks/` のファイルは import しない（A8）。
- クォートの中、コメント、heredoc 本文は判定しない（FR9）。
- 閉じていないクォートや heredoc、例外は fail-open（FR11）。

### 処理系ごとの判定（FR6、FR7、A9）

| 処理系 | `-i` で拒否（FR6） | 引数なし起動で拒否（FR7） | コードを渡すオプション（A9） |
|--------|--------------------|----------------------------|------------------------------|
| python 系 | する | する | `-c` / `-m` |
| node | する（`--interactive` も） | する | `-e` / `-p` / `--eval` / `--print` |
| bash / sh / zsh / dash / ksh | する | する | `-c`（`-s` は、標準入力がつながれていなければオプションだけの起動として扱う） |
| lua | する | する | A9 に個別の定めなし |
| ruby | しない | する | `-e` |
| perl | しない | する | `-e` / `-E` |
| deno | 対象外 | する | A9 に個別の定めなし |
| irb | 対象外 | する | A9 に個別の定めなし |
| ipython | 対象外 | する | A9 に個別の定めなし |

- `-i` は束ねた短いオプション（`-Bi`、`-ic`）の中にあっても検知する。
- オプションの読み取りは、最初のオペランド、または `-c` / `-m` / `-e` の値で止める。それより後ろの `-i` は拒否しない。
- `php -i`、`sed -i` は拒否しない。
- 引数なし起動でも、`-`、標準入力のリダイレクト（`<` / `<<` / `<<<`）、パイプの右側、長いオプション `--version` / `--help` は拒否しない。情報表示の短いオプションは処理系ごとに定める。bash / sh / zsh / dash / ksh には無く、シェルの `-h` / `-V` は拒否しないオプションに含まれない。

### API Design

#### hook の入力（stdin）

PreToolUse JSON。`tool_name` は `"Bash"`。判定に使うのは `tool_input.command`（文字列）だけ。

#### hook の出力（拒否時）

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
```

- exit 0。
- `permissionDecisionReason` は日本語で書き、`python3 -c`、スクリプトファイル、`python3 - <<EOF` への切り替えを示す。

#### hook の出力（拒否しないとき・fail-open）

stdout は空。exit 0。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/interpreter-mismatch-guard.py`: 解析手順の写し元。import はしない（A8）。

**External Dependencies:**
- Python 3 標準ライブラリ: hook の実装（NFR1）。
- Codex 0.160.0: `-c` 値のキー名と command の実行形式を実装時に確かめる対象（A6）。

### File Structure

```
em-workflow/
├── agents/codex-reviewer.md                    # Step 4 の <grounding_rules> に指示を足す
└── scripts/
    ├── run_codex_exec.sh                       # hook の -c 値と --dangerously-bypass-hook-trust を足す
    └── codex-hook-interactive-guard.py         # 新規
em-review/
├── agents/codex-reviewer.md                    # Step 4 の <grounding_rules> に指示を足す
└── scripts/
    ├── run_codex_exec.sh                       # hook の -c 値と --dangerously-bypass-hook-trust を足す
    └── codex-hook-interactive-guard.py         # 新規（em-workflow のものとバイト単位で同一）
tests/
└── test_codex_hook_interactive_guard.py        # 新規
.claude/rules/
└── hook-tests.md                               # この hook の節を足す
```

`em-workflow/hooks/hooks.json` には登録しない（A2）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-interactive-guard-hook/**`
- `test-docs/codex-interactive-guard-hook/**`

`feature-docs/codex-interactive-guard-hook/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-interactive-guard-hook/**` covers `test-docs/codex-interactive-guard-hook/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-interactive-guard-hook/` directory at all; the declared
`test-docs/codex-interactive-guard-hook/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

テストは stub の codex を PATH の先頭に置き、HOME を隔離して実行する。本物の Codex には触れない（NFR4）。

### Unit Tests
- [ ] TS1（hook、deny）: AC4 と AC5 の各コマンドを PreToolUse JSON（tool_name `"Bash"`）で渡すと、`hookSpecificOutput.permissionDecision` が `deny` になる。両方のコピーで確かめる。
- [ ] TS2（hook、silent）: AC6 の各コマンドと、クォート・コメント・heredoc 本文の中の `python3 -i` では、stdout が空で exit 0 になる。両方のコピーで確かめる。
- [ ] TS3（hook、fail-open）: 壊れた JSON、`tool_input` 欠落、command が文字列でない、閉じていないクォート、`env -i python3` では、stdout が空で exit 0 になる。
- [ ] TS4（hook、non-vacuity）: CASES 表に deny と silent の両方が含まれる。
- [ ] TS5（copies）: 2 つの hook ファイルのバイト列が一致する。

CASES 表は `(期待する判定 deny|silent, ラベル, コマンド)` の形で、両方のコピーに対して流す（FR14）。

### Integration Tests
- [ ] TS6（wrapper argv）: stub の codex で、em-workflow readonly 既定経路、readwrite、readonly `--litellm MODEL`、em-review readonly の各起動を記録する。argv に hook の `-c` 値（Bash matcher、スクリプトの絶対パス）と `--dangerously-bypass-hook-trust` が含まれること、既存の固定（`--ignore-user-config`、`-p litellm -m MODEL` の連続、起動 1 回）が保たれることを確かめる。
- [ ] TS7（docs）: 両方の `codex-reviewer.md` の Step 4 の節に、対話モードの禁止と `python3 -c` への言及がある。
- [ ] TS8（regression）: `python3 -m unittest discover -s tests` の既存テストがすべて通る。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] `python3 -B -i -c ...`: `-c` より前の `-i` なので拒否する（AC4）。
- [ ] `python3 script.py -i`: オペランドより後ろの `-i` なので拒否しない（AC6）。
- [ ] `python3 -Bi`: 束ねた短いオプションの中の `-i` を検知して拒否する（AC4）。
- [ ] `python3.14 -i`: 数字と点だけの接尾なので同じ処理系として拒否する（AC4）。
- [ ] `python3-config`: それ以外の接尾なので対象外（AC6）。
- [ ] `cd x && python3 -i`: 2 つ目の単純コマンドを拒否する（AC4）。
- [ ] `bash -lc 'python3 -i'`: リテラル文字列を 1 段だけ判定して拒否する（AC4）。
- [ ] `echo 'python3 -i'`: クォートの中なので判定しない（AC6）。
- [ ] `python3 -B`: オプションだけの起動なので拒否する（AC5）。
- [ ] `python3 <<EOF`、`python3 < f`、`cmd | python3`: 標準入力がつながっているので拒否しない（AC6）。
- [ ] `env -i python3`: オプション付きのラッパーなので fail-open（TS3）。

### Performance Tests
該当なし。

## Security Considerations

- **Authentication:** 該当なし。
- **Authorization:** 該当なし。
- **Input Validation:** 判定できない入力は何も出力せず exit 0 で抜ける（FR11）。
- **Data Protection:** hook は標準ライブラリだけを使い、ネットワーク、ファイル書き込み、サブプロセスには触れない（NFR1）。`--ignore-user-config` と `--ignore-rules` を外さない（NFR5）。
- **XSS Prevention:** 該当なし。
- **SQL Injection Prevention:** 該当なし。
- **CSRF Protection:** 該当なし。

## Error Handling

### fail-open の条件

| 条件 | 動作 |
|------|------|
| 入力 JSON が壊れている | 何も出力せず exit 0 |
| `tool_input.command` が無いか文字列でない | 何も出力せず exit 0 |
| 閉じていないクォートや heredoc がある | 何も出力せず exit 0 |
| 例外が起きた | 何も出力せず exit 0 |
| オプション付きのラッパー（`env -i` など）でくるまれている | 何も出力せず exit 0 |
| hook 自体が起動できない・失敗した | Codex の既定の挙動（コマンドを実行する）に任せる |
| hook スクリプトのファイルが無い | Codex の fail-open に任せる（A5） |

### Error Flow

```
判定できない → 何も出力しない → exit 0
```

## Performance Optimization

該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1〜AC9 を満たす
- [ ] `python3 -m unittest discover -s tests` がすべて通る
- [ ] Documentation is complete
- [ ] Code review is completed

## Assumptions

- A1: version は手で変更しない。main への push 時に Actions が patch を上げる。
- A2: この hook は Codex 専用で、`em-workflow/hooks/hooks.json` には登録しない。
- A3: `--ignore-user-config` の付け外しは変えない。
- A4: ラッパーの usage 文言と受け付けるフラグは変えない。
- A5: ラッパーは hook スクリプトの有無を確かめずに渡す。ファイルが無い場合は Codex の fail-open に任せる。
- A6: `-c` の値は TOML 配列 `[{matcher="Bash", hooks=[{type="command", command="python3 '<SCRIPT_DIR>/codex-hook-interactive-guard.py'"}]}]` の形とする。正確なキー名と、command がシェル経由で実行されるかどうかは、実装時に Codex 0.160.0 で確かめる。パスに含まれる引用符や空白は TOML とシェルの両方でエスケープする。
- A7: `write_stdin` 経由の対話、`code.interact()` のようにコードの中から開く対話モード、`deno repl` のようにサブコマンドで開く REPL は検知しない。
- A8: hook の判定ロジックは `interpreter-mismatch-guard.py` の解析手順（heredoc 除去、単純コマンドへの分割、リダイレクト除去、ラッパー読み飛ばし）を写して使う。`em-workflow/hooks/` のファイルは import しない（em-review からは参照できないため）。
- A9: 引数なし判定でのコードを渡すオプションは、python 系は `-c` / `-m`、node は `-e` / `-p` / `--eval` / `--print`、perl は `-e` / `-E`、ruby は `-e`、シェルは `-c` とする。シェルの `-s` は、標準入力がつながれていなければオプションだけの起動として扱う。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件は無い）。

## References

- 要件定義書: `feature-docs/codex-interactive-guard-hook/REQUIREMENTS.md`
- フックのテストのルール: `.claude/rules/hook-tests.md`
- 解析手順の写し元: `em-workflow/hooks/interpreter-mismatch-guard.py`
