# Feature: approval-unicode-whitespace

## Overview

承認照合のトリムを、スペース（U+0020）とタブ（U+0009）だけを両端から除く形に揃える。トリム後も前後に `str.isspace()` が真になる文字が残る値は照合対象外とし、merge-preflight.py と bash_guard.py のどの経路でも承認しない。要件は `feature-docs/approval-unicode-whitespace/REQUIREMENTS.md` を参照する。

## Objectives

- Bash が単語の区切りとして扱わない Unicode 空白（U+00A0、U+000B、U+000C など）をコマンドの前後に置いても、そのコマンドが承認済みの別のコマンドとして数えられない
- merge-preflight.py と bash_guard.py を同じ変更で直し、両者の承認判定を一致させたままにする

## User Stories

該当なし

## Technical Requirements

### Functional Requirements

- **FR1:** 「照合対象」とトリムの定義。承認照合のためにトリムするすべての箇所で、両端から除くのはスペース（U+0020）とタブ（U+0009）だけにする。トリム後の値の先頭または末尾が `str.isspace()` が真になる文字（LF、CR、U+000B、U+000C、U+00A0、U+0085、U+2000〜U+200A、U+3000 など）のとき、その値は照合対象外とし、どの経路でも承認しない。内側の空白は正規化せず、完全一致で比較する。
- **FR2:** preflight の承認照合。merge-preflight.py の `check_approval` は、照合対象の値だけをスペースとタブを除いた形で `--list` の集合と照合する。照合対象外の値は `commands_unapproved` で止める。LF / CR を含む値を除外する既存の扱いは維持する。`commands` に出力するコマンドは、トリムしていない元の値のままにする。
- **FR3:** preflight の空値判定。`collect_commands` は、スペースとタブを除いて空になる値だけを空として扱う。それ以外の空白だけでできた値（例: U+00A0 のみ）は読み飛ばさず、未承認のコマンドとして扱う。
- **FR4:** フックの入口。bash_guard.py の `hook_main` は、受け取ったコマンドの両端からスペースとタブだけを除き、LF も除かない。トリム後に照合対象外のコマンドは許可しない。workflow.yaml で宣言されていれば未承認として拒否し、宣言されていなければ判定を返さない。トリム後に空になるコマンドは、現在と同じく判定を返さない。
- **FR5:** cd 前置形の残り部分。`is_cd_prefixed_approved` と `cd_remainder_excluded` での残り部分のトリムは、スペースとタブだけを除く。照合対象外の残り部分は、cd 前置形では許可しない。
- **FR6:** 保存済みエントリ。`approved_for` は保存済みエントリからスペースとタブだけを除き、照合対象外のエントリを承認済みとして数えない。`--list` は照合対象外のエントリを出力しない。
- **FR7:** `--record` / `--remove` の入力。`read_stdin_commands` は、stdin の各行から行末の LF をちょうど 1 つ除き、その後スペースとタブを除いて検証する。CR、U+000B、U+000C、U+00A0 は除かない。トリム後に空になる行は、現在と同じく読み飛ばす。1 回の入力に照合対象外の行が 1 つでもあれば、`--record` と `--remove` はどちらも拒否パターンと同じく stderr に報告して終了コード 1 で終わり、その入力からは何も保存せず、何も削除しない。
- **FR8:** 宣言済みコマンドの抽出。`declared_commands` は `COMMAND_KEY_RE` の `\s` を `[ \t]` に変え、値からスペースとタブだけを除く。照合対象外の値も宣言済みの集合に含め、フックはそれを未承認として拒否する。
- **FR9:** ドキュメント。次のトリムの記述を「スペースとタブだけを除く。それ以外の空白が前後にある値は承認しない」という内容に改める。`tests/test_cd_prefix_operator_exclusion_docs.py` が固定している文言は維持する。
    - `em-workflow/references/command-execution-protocol.md` の 'Trim surrounding whitespace; skip empty' / 'after trimming' / '(surrounding whitespace aside)'
    - bash_guard.py の docstring の 'surrounding blanks removed'
    - merge-preflight.py のモジュール docstring（Approval rule の `str.strip()` の記述）
    - `check_approval` のコメント

### Non-Functional Requirements

- **NFR1 - Dependencies:** bash_guard.py は標準ライブラリのモジュールだけを import する（`TestAc7StandardLibraryOnly`）。
- **NFR2 - Classification pin:** bash_guard.py の実行されるテキストに部分文字列 'status' を含めない（`tests/test_hook_classification_pin.py`）。
- **NFR3 - Tests:** テストは Python 3.14 標準ライブラリの unittest だけを使い、`EM_WORKFLOW_APPROVALS` でストアを分離する。
- **NFR4 - Version:** version は変更しない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
merge-preflight.py
  check_approval      ... FR1, FR2
  collect_commands    ... FR3

bash_guard.py
  hook_main                                    ... FR1, FR4
  is_cd_prefixed_approved / cd_remainder_excluded ... FR5
  approved_for / --list                        ... FR6
  read_stdin_commands (--record / --remove)    ... FR7
  declared_commands / COMMAND_KEY_RE           ... FR8

em-workflow/references/command-execution-protocol.md
bash_guard.py docstring
merge-preflight.py module docstring / check_approval comment ... FR9
```

### Data Flow

```
値 → スペースとタブだけを両端から除く
   → 空 → 空として扱う（preflight は読み飛ばし / フックは判定なし / stdin の行は読み飛ばし）
   → 先頭または末尾が str.isspace() の文字 → 照合対象外（承認しない）
   → それ以外 → 照合対象（完全一致で照合）
```

### Dependencies

**Internal Dependencies:**
- merge-preflight.py と bash_guard.py: 承認判定を一致させる（FR2、FR4、AC5）。
- `tests/test_cd_prefix_operator_exclusion_docs.py`: 固定している文言を維持する（FR9）。

**External Dependencies:**
- Python 3.14 標準ライブラリ（NFR1、NFR3）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/approval-unicode-whitespace/**`
- `test-docs/approval-unicode-whitespace/**`

`feature-docs/approval-unicode-whitespace/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/approval-unicode-whitespace/**` covers `test-docs/approval-unicode-whitespace/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/approval-unicode-whitespace/` directory at all; the declared
`test-docs/approval-unicode-whitespace/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1 `tests/test_merge_preflight.py` [FR1, FR2, FR3, FR4]: AC1、AC4、AC9（U+00A0 / U+000B / U+000C × 前 / 後 / 両方。`'  make test'` のようなスペースとの混在を含む）。1198〜1199 行の 2 ケースの期待を「承認されない」に変える（AC5）
- [ ] TS2 bash_guard（既存の `test_bash_guard_cd_prefix*` のファイル、または新規の `tests/test_bash_guard_*.py`）[FR1, FR2, FR4, FR5, FR6, FR7, FR8]: AC2、AC3、AC4、AC6、AC7、AC8。フックのサブプロセス、`--record` / `--remove` / `--list`、`EM_WORKFLOW_APPROVALS` を通す
- [ ] TS3 [FR4, FR5]: `tests/test_bash_guard_cd_prefix.py:424` と `tests/test_bash_guard_cd_prefix_operators.py:396` の期待を ALLOW から ALLOW 以外に変える
- [ ] TS4 [FR1]: その他の `str.isspace()` の代表的な文字（U+0085、U+2000、U+3000、U+001F）も承認されない
- [ ] TS5 [FR1]: 内側に U+00A0 がある `make<U+00A0>test` は `make test` と一致しない

### Integration Tests

該当なし

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 末尾 LF、またはバックスラッシュ + LF が続く承認済みの文字列は、単独のコマンドとしても cd 前置形でも許可しない（AC6）
- [ ] CRLF の行を含む stdin を与えた `--record` / `--remove` は終了コード 1 で、ストアは変わらない（AC7）
- [ ] U+00A0 だけでできた値は preflight で未承認として止まる（AC9）

### Performance Tests

該当なし

## Security Considerations

- **Input Validation:** FR1〜FR8 のとおり。照合対象外の値は、preflight・フック・cd 前置形・保存済みエントリ・`--record` / `--remove` の入力のどの経路でも承認しない。

## Error Handling

### Error Codes

| Code | Description | 発生箇所 |
|------|-------------|----------|
| `commands_unapproved` | 照合対象外の値、または U+00A0 だけでできた値 | merge-preflight.py（FR2、FR3） |
| 拒否（未承認） | workflow.yaml で宣言された照合対象外のコマンド | bash_guard.py `hook_main`（FR4、FR8） |
| 判定なし | 宣言されていない照合対象外のコマンド、トリム後に空のコマンド | bash_guard.py `hook_main`（FR4） |
| 終了コード 1（stderr に報告） | stdin に照合対象外の行が 1 行以上ある。ストアは変更しない | bash_guard.py `--record` / `--remove`（FR7） |

## Success Criteria

- [ ] AC1 [FR1, FR2]: `/usr/bin/true` が承認済みのとき、test_command の前・後・両方に U+00A0、U+000B、U+000C のいずれかがあれば、preflight は `commands_unapproved` で止まる
- [ ] AC2 [FR1, FR4, FR8]: `/usr/bin/true` が承認済みのとき、前・後・両方に U+00A0、U+000B、U+000C のいずれかがあるコマンドを bash_guard は許可しない。同じ値が workflow.yaml で宣言されていれば拒否する
- [ ] AC3 [FR5]: cd 前置形で、残り部分の前または後に U+00A0、U+000B、U+000C のいずれかがあれば許可しない
- [ ] AC4 [FR2, FR4]: 攻撃シナリオ（test_command = U+00A0 + `/usr/bin/true`、作業ツリーに `<U+00A0>/usr/bin/true` の実行ファイル）を再現しても、preflight と bash_guard のどちらも承認しない
- [ ] AC5 [FR2, FR4]: `test_fr4_ac3_preflight_agrees_with_bash_guards_own_approval_decision` で、U+000C/U+000B のケースと U+00A0 のケースが「承認されない」になり、両者の一致は保たれる
- [ ] AC6 [FR4, FR5]: 承認済みの文字列に末尾 LF を付けたもの、承認済みの文字列にバックスラッシュ + LF を続けたものは、単独のコマンドとしても cd 前置形でも許可しない。末尾 LF で ALLOW を期待していた既存の 2 テスト（`tests/test_bash_guard_cd_prefix.py:424`、`tests/test_bash_guard_cd_prefix_operators.py:396`）は ALLOW を期待しなくなる
- [ ] AC7 [FR7]: 照合対象外の行（CRLF の行を含む）を含む stdin を与えると、`--record` と `--remove` は終了コード 1 で終わり、同じ入力の他の行が照合対象でもストアは変わらない
- [ ] AC8 [FR6]: ストアに既にある照合対象外のエントリを、`approved_for` と `--list` は承認済みとして扱わない
- [ ] AC9 [FR3]: U+00A0 だけでできた値を preflight は読み飛ばさず、未承認として止まる
- [ ] AC10 [FR1]: 前後にスペースとタブだけがあるコマンドの照合は、これまでどおり承認される（既存のスペース / タブのケースが通る）
- [ ] AC11 [FR9]: ドキュメントに、スペースとタブだけを除くことが書かれている。`python3 -m unittest discover -s tests` が通る

## Assumptions

- A1（影響度: 中、可逆）: `--remove` は照合対象外の行を `--record` と同じく扱う。終了コード 1 で、ストアは変更しない。ストアに既にある照合対象外のエントリは `approved_for` が返さないため、次に成功した `--record` / `--remove` がそれを除いてストアを書き直す。`--remove` で拒否しても片付けは妨げられない。
- A2（影響度: 低、可逆）: POSIX では `sys.stdin` は改行を変換しない。`--record` / `--remove` の stdin の CRLF の行は、LF を 1 つ除いた後も CR が残り、照合対象外として拒否される。
- A3（影響度: 低、可逆）: `declared_commands` は workflow.yaml を `open()` のユニバーサル改行で読むため、CRLF の行末は LF に正規化される。`[ \t]` への変更で宣言値に CR が入ることはない。
- A4（影響度: 低、可逆）: 既存の挙動を維持する。preflight での LF / CR を含む値の除外、内側の空白を含めた完全一致、`CD_PREFIX_RE` の区切り（`[ \t]`）、拒否パターン。
- A5（影響度: 低、可逆）: version は変更しない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/approval-unicode-whitespace/REQUIREMENTS.md`
- コマンド実行プロトコル: `em-workflow/references/command-execution-protocol.md`
