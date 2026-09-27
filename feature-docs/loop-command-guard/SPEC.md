# Feature: loop-command-guard

## Overview

PreToolUse(Bash) の新規 hook `em-workflow/hooks/loop-command-guard.py` を追加し、Bash ツールに渡るコマンドに含まれる while / until ループを拒否する。要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- Bash ツールに渡るコマンドに含まれる while / until ループを PreToolUse hook で拒否し、終わらないループによるハングを防ぐ

## User Stories

### US1: while / until ループを含むコマンドの拒否
Bash ツールの呼び出し元として、while / until ループを含むコマンドが拒否されることで、終わらないループによるハングを防ぎたい。

**Acceptance Criteria:**
- [ ] AC1（FR2・FR6）: `while true; do sleep 1; done`、`until false; do :; done`、`while ...; done &` をそれぞれ渡すと、permissionDecision が deny で理由が `[loop-command-guard]` で始まる出力が返り、終了コードは 0。
- [ ] AC2（FR2）: `cmd && while ...`、`(while ...)`、`{ while ...; }`、`if x; then while ...; fi`、`for i in 1; do until ...; done`、`! while ...` の各位置のループを deny する。
- [ ] AC3（FR3）: `bash -c` / `sh -c` / `zsh -c` / `bash -lc` / `bash -euo pipefail -c` の文字列内のループ、eval の引数内のループ、`$( )` とバッククォート（二重引用符内を含む）内のループ、bash / sh / zsh に渡したヒアドキュメントとヒアストリング内のループ、二重に入れ子になったループを deny する。
- [ ] AC4（FR5）: `timeout 60 bash -c 'while true; do :; done'` と nohup / env を前置きした同形を deny する。
- [ ] AC7（FR6）: CLAUDE_BATCH を設定した場合も設定しない場合も、検出時の判定は deny。

### US2: ループを含まないコマンドと判定できない入力の素通し
Bash ツールの呼び出し元として、ループを含まないコマンドと構造を確定できない入力では hook が何も出さず、後に続く hook の判定がこれまでどおり行われてほしい。

**Acceptance Criteria:**
- [ ] AC5（FR4・FR7）: `echo while`、`grep -r "until" .`、`git commit -m 'while loop'`、`'while true'` を含む単一引用符データ、`cat <<EOF` の本文にあるループ、`# while true` のコメント、`python3 -c 'while True: pass'` では stdout が空で終了コード 0。
- [ ] AC6（FR8）: 壊れた JSON、Bash 以外の tool_name、command 欠落・空・非文字列、閉じていない引用符、閉じていないヒアドキュメントでは stdout が空で終了コード 0。
- [ ] AC9（NFR1）: loop-command-guard.py の import は標準ライブラリだけで、全ケースで stderr が空。

### US3: 登録・文書・version の更新
em-workflow の保守者として、新規 hook が正しい位置に登録され、文書と version が揃っていてほしい。

**Acceptance Criteria:**
- [ ] AC8（FR9・FR10・NFR3）: hooks.json の PreToolUse(Bash) は 9 本で、loop-command-guard.py が destructive-guard.py の直前にあり、他の 8 本の内容と相対順は変わらない。更新した登録テストがこの形を固定し、destructive-guard.py が判定を返せるガードの最後であることを検査する。
- [ ] AC10（FR12・FR13）: README の表に loop-command-guard.py の行があり、実行順の文に含まれる。`.claude/rules/hook-tests.md` にテスト実行コマンドが書かれている。
- [ ] AC11（FR14・NFR4）: plugin.json と marketplace.json の em-workflow の version が同じ値で、HEAD から patch が上がっている。em-review の version は変わらない。`python3 -m unittest discover -s tests` が全件通る。

## Technical Requirements

### Functional Requirements
- **FR1:** 新規ガード hook — PreToolUse(Bash) の新規 hook スクリプト `em-workflow/hooks/loop-command-guard.py` を追加する。既存の hook スクリプトには判定ロジックを足さない。
- **FR2:** コマンド位置の while / until の検出 — コマンド位置にある予約語 while / until を検出する。条件の中身（定数・外部状態など）は問わず、前景・バックグラウンド（`&` 付き）も問わない。コマンド位置には、文字列の先頭、文の区切り（改行 `;` `&` `&&` `||` `|`）の直後、サブシェル `(` やブレースグループ `{` の直後、`!` の直後、予約語 if / then / elif / else / do の直後を含む。
- **FR3:** 入れ子の検出 — シェルに実行させる文字列の中も同じ規則で検出する。対象は bash / sh / zsh の `-c` に渡した文字列（`-lc` や `-euo pipefail -c` のようにオプションが先にある形を含む）、eval の引数、`$( )` とバッククォートの中身（二重引用符の中にあるものを含む）、bash / sh / zsh に渡したヒアドキュメントの本文とヒアストリング。入れ子が重なる場合も再帰的に検出する。
- **FR4:** 検出しないもの — 引用符で囲まれたデータ（単一引用符の中身、二重引用符のうちコマンド置換以外の部分）、シェル以外のコマンドに渡したヒアドキュメントの本文、コメント、引数の単語（`echo while`、`grep "until"` など）では検出しない。
- **FR5:** 例外なし — 制限時間付きのループにも例外を設けない。timeout・nohup・env などの前置きコマンドを付けて呼んだシェルの中のループも拒否する。
- **FR6:** 拒否時の出力 — 検出したら hookSpecificOutput（hookEventName: PreToolUse、permissionDecision: deny、permissionDecisionReason）を stdout に出し、終了コード 0 で終える。理由の文は `[loop-command-guard]` で始め、while / until ループが禁止されていることを述べる。判定は CLAUDE_BATCH の有無にかかわらず常に deny にする。
- **FR7:** 非該当時の出力 — 検出しなければ stdout に何も出さず、終了コード 0 で終える。allow や ask は出さない。後に続く hook（destructive-guard.py を含む）の判定はこれまでどおり行われる。
- **FR8:** fail-open — 壊れた JSON、tool_name が Bash でない、command が無い・空・文字列でない、閉じていない引用符やヒアドキュメントなど構造を確定できない場合は、何も出さずに終了コード 0 で終える。
- **FR9:** hooks.json への登録 — `em-workflow/hooks/hooks.json` の PreToolUse(Bash) グループで、interpreter-mismatch-guard.py の後、destructive-guard.py の直前に登録する。コマンド形式は `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/loop-command-guard.py`、timeout は 15、statusMessage は日本語にする。既存エントリの内容と相対順は変えない。
- **FR10:** 既存の登録テストの更新 — `tests/test_guardrail_hooks_migration.py` の `EXPECTED_BASH_GUARD_ORDER` を 9 本の順序に更新し、`tests/test_hooks_registration.py` の 8 本を前提にした PreToolUse(Bash) 配列の固定検査（本数・heredoc-stdin-guard.py より前のエントリの逐語一致・末尾の位置・並べ替え検出）を 9 本の形に更新する。
- **FR11:** 新規 hook のテスト — `tests/test_loop_command_guard.py` を追加し、hook をサブプロセスとして起動して標準入力に JSON を渡し、stdout と終了コードを検査する。ケースは `(期待する判定, ラベル, コマンド)` で並べ、期待する判定は `deny` か `silent` にする。
- **FR12:** README の更新 — `em-workflow/README.md` のガードレール hook の表に loop-command-guard.py の行を足し、PreToolUse(Bash) の実行順を述べる文を登録順に合わせる。
- **FR13:** テスト手順ルールの追記 — `.claude/rules/hook-tests.md` に loop-command-guard の節を足し、変更時に同じ変更の中で `python3 -m unittest tests.test_loop_command_guard` を走らせることと、ケースの並べ方を書く。
- **FR14:** version の更新 — em-workflow の version の patch を上げる。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリを同じ値にし、em-review の version は変えない。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみ:** hook は Python 標準ライブラリだけを import する。ファイルを書かず、プロセスを起動せず、ネットワークに接続せず、stderr に何も書かない。
- **NFR2 - 静的解析のみ:** 判定はコマンド文字列の静的な読み取りだけで行い、登録 timeout（15 秒）の範囲内で終わる。同じ入力には常に同じ判定を返す。
- **NFR3 - 判定を閉じない:** hook が出すのは deny か無出力のどちらかだけにする。destructive-guard.py を permission decision を返せる Bash ガードの最後に置くという既存の不変条件を保つ。
- **NFR4 - 既存テストの通過:** `python3 -m unittest discover -s tests` が全件通る。

### Assumptions and Constraints
- A1: hook ファイル名は `loop-command-guard.py`、テストは `tests/test_loop_command_guard.py` にする。
- A2: 登録 timeout は標準の 15 秒にし、NONSTANDARD_HOOK_TIMEOUTS には足さない。statusMessage は日本語の文にする。
- A3: ファイルとして実行するスクリプト（`bash script.sh`、`./x.sh`、`source` など）の中身のループは検査しない。対象は Bash ツールに渡るコマンド文字列とそこに埋め込まれた文字列だけ。
- A4: for / select ループは対象外。
- A5: 構造を確定できないコマンドは判定せず無出力にする（fail-open）。
- A6: 入れ子の検出対象は、コマンド位置にある bash / sh / zsh / eval と、その前に置いた前置きコマンド（timeout、nohup、env、nice、setsid、stdbuf、command、exec、time）。`find -exec sh -c` や `xargs sh -c` のように別コマンドの引数として渡したシェル、ssh のリモートコマンド、パイプでシェルに流し込む文字列（`echo '...' | bash`、`cat <<EOF | bash`）は対象外。
- A7: 引用符やバックスラッシュを付けた `"while"` / `\while` は予約語として扱わず、検出しない。
- A8: version は patch を上げる。
- A9: em-review プラグインには登録しない。
- A10: 判定は ask ではなく deny にする。
- A11: 制約: ユーザーのグローバル hook `~/.claude/hooks/plugin-version-guard.py` が、em-workflow/ 配下を変更しながら em-workflow の plugin.json の version を HEAD から変えていない git commit を拒否する。
- A12: 不変条件: destructive-guard.py は包括的な allow を返すので、permission decision を返せる Bash ガードの中で最後に置く。`tests/test_guardrail_hooks_migration.py` と `tests/test_muse_guard_registration.py` がこれを固定している。
- A13: `em-workflow/references/implement-phase.md` は更新しない。

## Implementation Approach

### Architecture

**System Architecture:**
```
Claude Code (Bash ツール呼び出し)
        │ PreToolUse(Bash) グループを登録順に実行
        ▼
  ... → interpreter-mismatch-guard.py → loop-command-guard.py → destructive-guard.py
                                              │
                                              ├─ 検出: deny の hookSpecificOutput（終了コード 0）
                                              └─ 非該当 / fail-open: 無出力（終了コード 0）
```

**Component Diagram:**
```
loop-command-guard.py
  ├─ 入力の読み取り: 標準入力の JSON、tool_name と command の確認（FR8）
  ├─ 構造の読み取り: 引用符・ヒアドキュメント・コメント・コマンド位置の判別（FR2・FR4・FR8）
  ├─ 入れ子の展開: -c の文字列、eval の引数、$( ) とバッククォート、
  │                シェルへのヒアドキュメントとヒアストリング、前置きコマンド（FR3・FR5・A6）
  └─ 出力: deny の hookSpecificOutput または無出力（FR6・FR7）
```

### Data Flow

```
標準入力 JSON → 入力の確認 → コマンド文字列の静的な読み取り（入れ子は再帰）
  → 検出あり: stdout に hookSpecificOutput（deny）、終了コード 0
  → 検出なし / 構造を確定できない: stdout は空、終了コード 0
```

### API Design

#### Endpoint 1: PreToolUse(Bash) hook の入出力

**Request:**
```
標準入力: PreToolUse の入力 JSON（tool_name、command を含む）
```

**Response:**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "[loop-command-guard] ..."
  }
}
```

permissionDecisionReason は `[loop-command-guard]` で始め、while / until ループが禁止されていることを述べる（FR6）。終了コードは 0。

**Error Response:**
```
stdout は空、終了コード 0（FR7・FR8）
```

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/hooks.json`: PreToolUse(Bash) グループへの登録（FR9）
- `em-workflow/hooks/destructive-guard.py`: 直前に登録する。permission decision を返せる Bash ガードの最後に置く不変条件を保つ（NFR3・A12）
- `em-workflow/hooks/interpreter-mismatch-guard.py`: この後に登録する（FR9）
- `tests/test_guardrail_hooks_migration.py`、`tests/test_hooks_registration.py`: 9 本の形に更新する（FR10）

**External Dependencies:**
- Python 標準ライブラリ: hook が import するのはこれだけ（NFR1）

### File Structure

```
em-workflow/
├── .claude-plugin/
│   └── plugin.json                    # version の patch を上げる（FR14）
├── hooks/
│   ├── hooks.json                     # 登録を追加（FR9）
│   └── loop-command-guard.py          # 新規（FR1）
└── README.md                          # 表と実行順の文を更新（FR12）
tests/
├── test_loop_command_guard.py         # 新規（FR11）
├── test_guardrail_hooks_migration.py  # 更新（FR10）
└── test_hooks_registration.py         # 更新（FR10）
.claude/rules/hook-tests.md            # 節を追加（FR13）
.claude-plugin/marketplace.json        # em-workflow の version を揃える（FR14）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/loop-command-guard/**`
- `test-docs/loop-command-guard/**`

`feature-docs/loop-command-guard/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/loop-command-guard/**` covers `test-docs/loop-command-guard/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/loop-command-guard/` directory at all; the declared
`test-docs/loop-command-guard/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1（AC1・AC2）: トップレベルの各位置に while / until を置いたコマンドを JSON で渡し、deny を確認する。
- [ ] TS2（AC3・AC4）: 入れ子の各形式（`-c`、eval、`$( )`、バッククォート、シェルへのヒアドキュメントとヒアストリング、多重入れ子、前置きコマンド付き）で deny を確認する。
- [ ] TS3（AC5）: 引数・引用データ・非シェルのヒアドキュメント本文・コメント・シェル以外のインタプリタで無出力を確認する。
- [ ] TS4（AC6）: 不正な入力と構造を確定できないコマンドで無出力・終了コード 0 を確認する。
- [ ] TS5（AC7）: 環境変数 CLAUDE_BATCH の有無を変えて同じ検出ケースを走らせ、どちらも deny を確認する。
- [ ] TS7（AC9）: hook のソースを ast で読み、import が標準ライブラリだけであることを検査する。

### Integration Tests
- [ ] TS6（AC8）: hooks.json を読み、PreToolUse(Bash) の順序・本数・逐語内容を検査する。
- [ ] TS8（AC11）: `python3 -m unittest discover -s tests` を全件実行する。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression
- [ ] 該当なし

### Edge Cases
- [ ] 閉じていない引用符・閉じていないヒアドキュメント: 無出力、終了コード 0（FR8）
- [ ] command が無い・空・文字列でない: 無出力、終了コード 0（FR8）
- [ ] 引用符やバックスラッシュを付けた `"while"` / `\while`: 検出しない（A7）
- [ ] `find -exec sh -c`、`xargs sh -c`、ssh のリモートコマンド、`echo '...' | bash`、`cat <<EOF | bash`: 入れ子の検出対象外（A6）
- [ ] for / select ループ: 対象外（A4）

### Performance Tests
- [ ] 該当なし（判定は登録 timeout 15 秒の範囲内で終わる: NFR2）

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 壊れた JSON、tool_name が Bash でない、command が無い・空・文字列でない、構造を確定できない入力は判定せず、何も出さずに終了コード 0 で終える（FR8）
- **Data Protection:** ファイルを書かず、プロセスを起動せず、ネットワークに接続しない（NFR1）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| - | 該当なし（エラー時は stdout を空にして終了コード 0 で終える: FR8） | - | - |

### Error Flow

```
入力を読めない / 構造を確定できない → 何も出さない → 終了コード 0
```

## Performance Optimization

### Performance Goals
- 判定は登録 timeout（15 秒）の範囲内で終わる（NFR2）

### Optimization Strategies
- 該当なし

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` が全件通る（NFR4）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
