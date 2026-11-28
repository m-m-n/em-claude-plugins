# Feature: destructive-guard-resolver-only-evidence

## Overview

destructive-guard の置換頭部コマンド名 evidence の読み取り（`read_command_name_evidence()`）で、resolver でない置換本文が rm / git の evidence になり deny に倒れる誤爆をなくす。evidence として読む本文を `which [-a] [--] NAME` / `command -v [--] NAME` / `printf NAME` の形に限定し、それ以外の本文は unreadable とする。`$(which rm)` / `$(command -v rm)` / `$(printf rm)` の検知は維持する。

## Objectives

- destructive-guard の置換頭部コマンド名 evidence の読み取りで、resolver でない置換本文が rm / git の evidence になり deny に倒れる誤爆をなくす。
- `$(which rm)` / `$(command -v rm)` / `$(printf rm)` の検知は維持する。

## Technical Requirements

### Functional Requirements

- **FR1: evidence を読む本文の形を限定する** — `read_command_name_evidence()` は、継続行（バックスラッシュ + 改行）を取り除き前後の空白を落とした本文を、スペースとタブで分割する。語の並びが次のどれかに一致するときだけ、NAME の basename をコマンド名として返す。NAME はちょうど 1 語。
    - `which NAME` / `which -a NAME` / `which -- NAME` / `which -a -- NAME`（`-a` と `--` を両方置くときはこの順）。先頭語は `which` との完全一致か、basename が `which` のパス形（`/usr/bin/which`）
    - `command -v NAME` / `command -v -- NAME`。`command` と `-v` は完全一致で比べる
    - `printf NAME`。`printf` は完全一致で比べる
    - `-a` と `--` も完全一致で比べる
- **FR2: それ以外の本文は unreadable** — FR1 の形に一致しない本文は `None`（unreadable）を返す。対象は次のとおり。
    - 先頭語が FR1 の語以外の本文（`dirname` / `basename` / `readlink` / `ls -d` / `echo` / `type` など）
    - 1 語だけの本文（`rm`）
    - オペランドが 2 語以上の本文（`which ls rm`）
    - FR1 にない option 語、または FR1 にない順序の option 語を含む本文（`which -s rm`、`which -- -a rm`、`command -V rm`）
    - 先頭語が basename `which` 以外のパス形の本文（`/usr/bin/command -v rm`、`/usr/bin/printf rm`）
    - 継続行の除去後に改行が残る本文
- **FR3: 既存の読み取り規則を残す** — RAW_BODY が `None`、空、空白だけのときは unreadable。NAME が `-` で始まるときは unreadable。NAME の basename が空のときは unreadable。継続行の除去は今と同じ（`which r\<改行>m` は `rm`）。文字列処理だけで、置換の評価・プロセス起動・ファイルシステム参照をしない。
- **FR4: unreadable の扱いは変えない** — `route_substitution_headed_statement()` は今と同じく、evidence が rm なら rm 経路、git なら git 経路に入り、それ以外と `None` では経路に入らない（allow。ask へは倒さない）。evidence が rm でない文の plain route は今どおり実行される。
- **FR5: ケース表に追加する** — `em-workflow/hooks/tests/destructive-guard-cases.json` に次のケースを足す。既存のケースは消さない。
    - allow:
        - `$(dirname /opt/rm) -rf /home/user/valuable`
        - `$(ls -d /usr/bin/rm) -rf /home/user/valuable`
        - `$(readlink -f ./rm) -rf /home/user/valuable`
        - `$(basename /a/b git) clean -fd`
        - `$(which ls rm) -rf /home/user/valuable`
        - `$(rm) -rf /home/user/valuable`
    - deny:
        - `$(command -v rm) -rf /home/user/valuable`
        - `$(command -v git) reset --hard HEAD`
        - `$(which -a rm) -rf /home/user/valuable`
        - `$(/usr/bin/which rm) -rf /home/user/valuable`
        - `$(command -v -- rm) -rf /home/user/valuable`
- **FR6: docstring を直す** — `read_command_name_evidence()` の docstring の読み取り手順（「LAST word」を取る 2〜4 番）を FR1〜FR3 に合わせて書き直す。`route_substitution_headed_statement()` の docstring を直す場合は、tests が固定している語句（`held`、`one ordinal`）を残し、`tests/test_destructive_guard_rm_reason_positions.py` の STALE パターンに一致する語句を入れない。
- **FR7: 既存の単体テストの期待値を 1 つ直す** — `tests/test_destructive_guard_lexer_agreement.py` の `H.read_command_name_evidence("which a\\\\\nm")` の期待値を `"m"` から `None` に変える。同じテストの `which r\<改行>m` → `"rm"` と、そのコマンドの deny はそのまま。

### Non-Functional Requirements

- **NFR1:** evidence を読めない形は allow に倒す。fail-closed の ask を足さない。
- **NFR2:** 見逃し側（区切り演算子やパイプを含む本文、クォートでコマンド名を包んだ本文）は対象外のまま。
- **NFR3:** plugin の version は触らない。
- **NFR4:** `failed-run-cleanup-guard.py` のミラーは変えない。

## Implementation Approach

### 対象

- `em-workflow/hooks/destructive-guard.py`
    - `read_command_name_evidence()`: FR1〜FR3 の読み取り規則と FR6 の docstring
    - `route_substitution_headed_statement()`: 振る舞いは変えない（FR4）。docstring を直す場合は FR6 の制約に従う
- `em-workflow/hooks/tests/destructive-guard-cases.json`: FR5 のケース追加
- `tests/test_destructive_guard_lexer_agreement.py`: FR7 の期待値変更

### 読み取りの流れ

```
RAW_BODY
  → None / 空 / 空白だけ → unreadable（FR3）
  → 継続行（\ + 改行）を除去し、前後の空白を落とす（FR3）
  → 改行が残る → unreadable（FR2）
  → スペースとタブで分割
  → 語の並びが which [-a] [--] NAME / command -v [--] NAME / printf NAME のどれか
     （which は完全一致か basename が which のパス形。それ以外の語は完全一致）
       一致しない → unreadable（FR2）
  → NAME が - で始まる → unreadable（FR3）
  → NAME の basename が空 → unreadable（FR3）
  → NAME の basename を返す（FR1）
```

```
route_substitution_headed_statement()（変更なし、FR4）
  evidence = rm   → rm 経路
  evidence = git  → git 経路
  それ以外 / None → 経路に入らない（allow）
  evidence が rm でない文 → plain route は今どおり実行
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### ケース表（`em-workflow/hooks/tests/destructive-guard-cases.json`）

- [ ] TS-1 (allow): `$(dirname /opt/rm) -rf /home/user/valuable`
- [ ] TS-2 (allow): `$(ls -d /usr/bin/rm) -rf /home/user/valuable`
- [ ] TS-3 (allow): `$(readlink -f ./rm) -rf /home/user/valuable`
- [ ] TS-4 (allow): `$(basename /a/b git) clean -fd`
- [ ] TS-5 (deny, rm-recursive): `$(command -v rm) -rf /home/user/valuable`
- [ ] TS-6 (deny, git-reset-hard): `$(command -v git) reset --hard HEAD`
- [ ] TS-7 (allow): `$(which ls rm) -rf /home/user/valuable`
- [ ] TS-8 (allow): `$(rm) -rf /home/user/valuable`
- [ ] TS-9 (既存・維持): cases.json の `$(which ...)` ケースと `$(printf rm)` ケース
- [ ] TS-10 (既存・維持): `$(true) rm -rf /home/user/valuable` は plain route で deny
- [ ] TS-12 (deny, rm-recursive): `$(which -a rm) -rf /home/user/valuable`
- [ ] TS-13 (deny, rm-recursive): `$(/usr/bin/which rm) -rf /home/user/valuable`
- [ ] TS-14 (deny, rm-recursive): `$(command -v -- rm) -rf /home/user/valuable`

### スイート全体

- [ ] TS-11: `run-destructive-guard.py` 全件 pass、`unittest discover` の失敗 ID 集合が base と一致

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] AC-1: `$(dirname /opt/rm) -rf /home/user/valuable`、`$(ls -d /usr/bin/rm) -rf /home/user/valuable`、`$(readlink -f ./rm) -rf /home/user/valuable`、`$(basename /a/b git) clean -fd` が allow。
- [ ] AC-2: `$(which rm) -rf /home/user/valuable`、`` `which rm` -rf /home/user/valuable ``、`$(command -v rm) -rf /home/user/valuable`、`$(which git) reset --hard HEAD`、`$(printf rm) -rf ...`、`$(which -a rm) -rf /home/user/valuable`、`$(/usr/bin/which rm) -rf /home/user/valuable`、`$(command -v -- rm) -rf /home/user/valuable` が deny で、既存ケースは今と同じ判定と理由 ID。
- [ ] AC-3: `destructive-guard-cases.json` に FR5 のケースが入っている。
- [ ] AC-4: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る。
- [ ] AC-5: `python3 -m unittest discover -s tests` の失敗テスト ID 集合が base revision と一致する。

## Assumptions

- 「which / command -v 等」の範囲は which / command -v とし、既存テストが固定している printf を互換のために残す。type / echo は含めない（Codex 相談で決定）。
- resolver のオペランドはちょうど 1 語。2 語以上は unreadable。
- `which` は basename が `which` のパス形も受け付け、option 語 `-a` と終端語 `--` を受け付ける。`command -v` は `--` を受け付ける。`-a` と `--` を両方置く形は `-a -- NAME` の順に限る（create-plan 中の Codex 相談で決定）。
- lexer_agreement の期待値 `"m"` を `None` に変える（Codex 相談で決定）。
- `$(printf rm)` を rm evidence とする既存の deny / ask ケースは変わらない。
- evidence が `None` の文は plain route が今どおり走る。

## Open Questions

なし（`status: tbd` の要件はない）。
