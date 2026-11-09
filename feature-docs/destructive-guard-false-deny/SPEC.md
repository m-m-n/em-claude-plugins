# Feature: destructive-guard-false-deny

## Overview

em-workflow の destructive-guard（`em-workflow/hooks/destructive-guard.py`）について、プロトコルが規定するコマンドを止めない状態（現象 1）と、シェルが実行しないデータ引数（単一引用符の中）に書かれた git コマンド文字列で deny しない状態（現象 2）にする。単一引用符の中の文字列が後でシェルに実行される経路の検知は維持し、`destructive-guard-cases.json` のケースで固定する。

要件の詳細は `feature-docs/destructive-guard-false-deny/REQUIREMENTS.md` を参照する。

## Objectives

- em-workflow のプロトコルが規定するコマンドを、em-workflow 自身の destructive-guard が止めない状態にする。
- シェルが実行しないデータ引数（単一引用符の中）に書かれた git コマンド文字列で destructive-guard が deny しない状態にする。
- 単一引用符の中の文字列が後でシェルに実行される経路（bash -c / sh -c / eval / here-string / シェルへのパイプなど）の検知は維持する。
- 上記を `destructive-guard-cases.json` のケースで固定し、既存の deny / ask の検知力を落とさない。

## Acceptance Criteria

- [ ] AC-1: `git -C /home/user/.claude/worktrees/em-workflow/some-feature/integration branch -d "em-workflow/some-feature/task0001"` が allow になる（FR1）。
- [ ] AC-2: `git branch -D em-workflow/some-feature/task0001` が git-branch-force-delete で deny のまま（FR1）。
- [ ] AC-3: `implement-phase.md` Step I.2.b step 4 が非強制削除を規定し、強制削除への切り替えを禁じる記述を保っている（FR1）。
- [ ] AC-4: 単一引用符の JSON 引数の中にバッククォート / `$( )` で `git branch -D example` を書いた mcp-bridge コマンド、および ANSI-C 引用の中に書いたデータ引数が allow になる（FR2）。
- [ ] AC-5: 引用符無し・二重引用符内の置換、bash -c / sh -c / eval / here-string / シェルへのパイプ / 同じコマンド中のシェル実行 / プロセス置換・コマンド置換の本文に置いた単一引用符内の置換の `git branch -D example` が deny のまま（FR4）。
- [ ] AC-6: 既存の deny / ask ケースが 1 件も削除・変更されず、`run-destructive-guard.py` が全件通る（FR3、FR5、NFR1）。
- [ ] AC-7: 修正前のフックで deny 側の追加ケースが通り、TS-3・TS-4・TS-6 が deny になることを確かめた記録がある（FR6）。

## Technical Requirements

### Functional Requirements

- **FR1:** 現象 1 の方針: フックの強制削除 deny は維持し、プロトコルは非強制削除を使う。`destructive-guard.py` の `check_git` にある git-branch-force-delete の判定（`git branch -D`、および `-d` / `--delete` と `--force` の併用を deny）は変えない。マージ済みタスクブランチの後片付けは、`em-workflow/references/implement-phase.md` Step I.2.b step 4 の形 `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"`（integration worktree からの非強制削除。失敗時に `-D` / `--force` へ切り替えない）とする。この記述は現行の `implement-phase.md` にすでにあるため本文は変えず、フックがこの形を allow することをケースで固定する。
- **FR2:** データ引数の中の単一引用符内置換候補だけを再走査しない。`statements()` が `scan_structure(..., honor_single_quotes=False)` で拾う単一引用符内（ANSI-C 引用 `$'...'` を含む）のコマンド置換候補のうち、次の条件をすべて満たすものに限り、その本文を pending に積まない（コマンドとして再走査しない）。
    - (a) 候補が置かれたチャンクが元のコマンド文字列そのもの（最上位のチャンク）である。置換本文・プロセス置換本文・閉じないコマンド形式の本文・ヒアドキュメント本文・-c / eval / here-string のペイロードとして積まれたチャンクでは従来どおり再走査する。
    - (b) そのチャンクの全文が字句解析に成功している（parse-failure fallback を通っていない）。
    - (c) そのチャンクのどの文も、代入とラッパーを読み飛ばした後のコマンド語が実行系の語ではない。実行系の語は少なくとも `SINK_WORD_RE` の語彙（sh / bash / zsh / dash / ksh / python / perl / ruby / node）、eval、source、`.`、exec、xargs、find、su、ssh、および env の -S / --split-string を含む。語彙を足すのは deny 側に倒すだけなので実装で追加してよい。
    - (d) そのチャンクのどの文もコマンド語を静的に決められる（置換や変数展開がコマンド語の位置に無い）。またコマンド名を上書きする構文（`_overrides_command_name()` が検出するもの）がチャンクに無い。
    - どれか 1 つでも満たさない、または判断できないときは、従来どおり再走査する。
- **FR3:** 単一引用符内候補の印付けは維持する。FR2 で変えるのは pending への積み込みだけとする。`top_spans` の算出、`_mark_substitutions()` / `_mark_quoted_substitutions()` による印付け、`all_subs` への追加と目印の添字の対応、トークンの `.unresolved` / `.substitution_only` の付与は変えない。例:
    - `rm -rf '$(pwd)/../tmp/scratch'` は deny のまま。
    - `echo 'a $(' ; rm -rf /home/user/x ; f "(" ; echo ')'` は deny のまま。
    - `X='foo$(bar'; rm -rf $X` は ask のまま。
- **FR4:** 実際に実行される位置の置換は従来どおり検知する。次の置換は従来どおり再走査し、git-branch-force-delete などで deny する。
    - 引用符無しのバッククォート / `$( )`
    - 二重引用符内のバッククォート / `$( )`
    - 引用符無しの区切り語のヒアドキュメント本文内の置換
    - 単一引用符の中の置換で、後からシェルに実行されるもの: `bash -c` / `sh -c` のペイロード、`eval` の引数、シェルへの here-string（`bash <<< '...'`）、シェルへパイプされる文字列（`printf '%s\n' '...' | bash`）、同じコマンド文字列の中で実行系の語を持つ文があるもの（ファイルに書いてから `bash` で実行する形など）、プロセス置換やコマンド置換の本文の中にあるもの（`bash <(printf ...)`、`eval "$(printf ...)"`）
- **FR5:** テストケースの追加。`em-workflow/hooks/tests/destructive-guard-cases.json` に Test Scenarios の TS-1〜TS-17 をケースとして追加する。allow は TS-1、TS-3、TS-4、TS-5、TS-6。deny は TS-2、TS-7〜TS-17。既存の deny / ask ケースは消さず、期待値も変えない。ケースにホームディレクトリやマシン固有のパスを書かない。integration worktree のパスは既存ケースと同じ `/home/user/.claude/worktrees/em-workflow/some-feature/integration` を使う。
- **FR6:** ケースの追加を修正より先に行う。`.claude/rules/hook-tests.md` に従い、ケースは `destructive-guard.py` を直す前に追加する。修正前のフックで、deny 側の追加ケース（TS-2、TS-7〜TS-17）がすべて通ること、TS-3・TS-4・TS-6 が deny になる（現象 2 を再現する）ことを確かめてから修正する。
- **FR7:** コード内の説明の更新。`scan_structure()` の docstring の HONOR_SINGLE_QUOTES の段落、`statements()` の `legacy_spans` 周辺のコメント（単一引用符内候補が pending の再走査対象になると書いている箇所）、`_mark_quoted_substitutions()` と `extract_shell_payload_anchored()` の docstring の単一引用符に触れた記述を、FR2 / FR3 の挙動に合わせて書き換える。

### Non-Functional Requirements

- **NFR1 - 既存スイートの全通過:** `python3 em-workflow/hooks/tests/run-destructive-guard.py` が追加ケースを含めて全件通る。既存ケースの期待値は変えない。
- **NFR2 - 性能:** 1 回の判定は `hooks.json` の timeout（10 秒）とランナーの `GUARD_TIMEOUT_SECONDS`（10 秒）以内に収まる。`statements()` の走査量の上限（`scan_budget`、`MAX_SHELL_PAYLOAD_EXPANSIONS`）は変えない。
- **NFR3 - version を触らない:** em-workflow の `plugin.json` / `marketplace.json` の version は変更しない。
- **NFR4 - リポジトリ全体のテスト:** `python3 -m unittest discover -s tests` が変更前と同じ結果になる。

## Implementation Approach

### Changed Files

```
em-workflow/hooks/
├── destructive-guard.py                 # statements() の pending 積み込み条件（FR2）、コード内の説明（FR7）
└── tests/
    └── destructive-guard-cases.json     # TS-1〜TS-17 のケース追加（FR5）
```

変更しないもの:

- `destructive-guard.py` の `check_git` にある git-branch-force-delete の判定（FR1）
- `em-workflow/references/implement-phase.md` の本文（FR1）
- `top_spans` の算出、`_mark_substitutions()` / `_mark_quoted_substitutions()` による印付け、`all_subs` への追加と目印の添字の対応、トークンの `.unresolved` / `.substitution_only` の付与（FR3）
- `scan_budget`、`MAX_SHELL_PAYLOAD_EXPANSIONS`（NFR2）
- em-workflow の `plugin.json` / `marketplace.json` の version（NFR3）

### Assumptions

- A1: 現象 1 はフックの強制削除 deny を維持し、プロトコルは integration worktree からの非強制削除を使う（回答 phenomenon1-policy、案 B）。完了の定義の「再現手順で現象が起きない」は、現象 1 については「プロトコルが規定するコマンドがフックに止められない」ことと解釈する。再現手順 2 の強制削除そのものは deny のまま。
- A2: 完了の定義の「両プラグインに同じ判断を反映する」について、本分析の読み取り範囲に em-review / plugin-dev は無く、写しの有無は未確認。写しが無い前提で em-workflow だけを変更対象とする。
- A3: ANSI-C 引用 `$'...'` の中でもシェルはコマンド置換を行わないため、単一引用符と同じ扱いにする。
- A4: 既存の deny / ask ケースは消さない（`.claude/rules/hook-tests.md`）。
- A5: `implement-phase.md` の Resume guard（Clean re-attempt）と route-back の後片付けが規定する `git worktree remove --force` / `git branch -D` は本機能の対象外とし、別タスクとして起票する（回答 protocol-force-forms-scope、案 X）。
- A6: 回答 phenomenon2-fix-scope（案 Q）の「実行されないデータ引数」は、静的に判断できる範囲に限る保守的な定義（FR2 の条件 (a)〜(d)）とする。判断できないときは再走査（deny 側）に倒す。
- A7: TS-7〜TS-17 が修正前のフックで deny になることはコード読解で確かめた（要件分析のディスパッチではフックを実行できなかった）。FR6 で修正前に実行して確かめる。

### Design Step

スキップ。UI を持たないフックスクリプトとテストケースの変更のみのため。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-false-deny/**`
- `test-docs/destructive-guard-false-deny/**`

`feature-docs/destructive-guard-false-deny/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/destructive-guard-false-deny/**` covers `test-docs/destructive-guard-false-deny/{T}.tests.yaml`, the
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

TS-1〜TS-17 は `em-workflow/hooks/tests/destructive-guard-cases.json` のケース（FR5）。期待する判定とコマンドを示す。

### Unit Tests

#### allow

- [ ] TS-1: allow（AC-1 / FR1）

    ```
    git -C /home/user/.claude/worktrees/em-workflow/some-feature/integration branch -d "em-workflow/some-feature/task0001"
    ```

- [ ] TS-3: allow（AC-4 / FR2）

    ```
    mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"`git branch -D example` と記載する"}'
    ```

- [ ] TS-4: allow（AC-4 / FR2）

    ```
    mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"$(git branch -D example) と記載する"}'
    ```

- [ ] TS-5: allow（AC-4 / FR2）。タスク記載の再現手順の形。コード読解では現状すでに allow。

    ```
    mcp-bridge run --mcp notion --tool notion-create-comment --args-json "$(cat comment.json)"
    ```

- [ ] TS-6: allow（AC-4 / FR2）

    ```
    printf '%s\n' $'`git branch -D example` と記載する'
    ```

#### deny

- [ ] TS-2: deny（AC-2 / FR1）

    ```
    git branch -D em-workflow/some-feature/task0001
    ```

- [ ] TS-7: deny（AC-5 / FR4）

    ```
    echo `git branch -D example`
    ```

- [ ] TS-8: deny（AC-5 / FR4）

    ```
    echo "`git branch -D example`"
    ```

- [ ] TS-9: deny（AC-5 / FR4）

    ```
    bash -c 'echo `git branch -D example`'
    ```

- [ ] TS-10: deny（AC-5 / FR4）

    ```
    bash -c 'echo $(git branch -D example)'
    ```

- [ ] TS-11: deny（AC-5 / FR4）

    ```
    sh -c 'echo $(git branch -D example)'
    ```

- [ ] TS-12: deny（AC-5 / FR4）

    ```
    eval 'echo $(git branch -D example)'
    ```

- [ ] TS-13: deny（AC-5 / FR4）

    ```
    bash <<< 'echo $(git branch -D example)'
    ```

- [ ] TS-14: deny（AC-5 / FR4）

    ```
    printf '%s\n' 'echo $(git branch -D example)' | bash
    ```

- [ ] TS-15: deny（AC-5 / FR4）

    ```
    printf '%s\n' 'echo $(git branch -D example)' > run.sh && bash run.sh
    ```

- [ ] TS-16: deny（AC-5 / FR4）

    ```
    bash <(printf '%s\n' 'echo $(git branch -D example)')
    ```

- [ ] TS-17: deny（AC-5 / FR4）

    ```
    eval "$(printf '%s\n' 'echo $(git branch -D example)')"
    ```

### Integration Tests

- [ ] TS-18: 既存スイート全件通過（AC-6 / FR3、FR5、NFR1）

    ```
    python3 em-workflow/hooks/tests/run-destructive-guard.py
    ```

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Pre-fix Verification

FR6 により、`destructive-guard.py` を直す前に追加ケースで次を確かめる。

- deny 側の追加ケース（TS-2、TS-7〜TS-17）がすべて通る。
- TS-3・TS-4・TS-6 が deny になる（現象 2 を再現する）。

## Performance Optimization

### Performance Goals

- 1 回の判定は `hooks.json` の timeout（10 秒）とランナーの `GUARD_TIMEOUT_SECONDS`（10 秒）以内に収まる（NFR2）。
- `statements()` の走査量の上限（`scan_budget`、`MAX_SHELL_PAYLOAD_EXPANSIONS`）は変えない（NFR2）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` が変更前と同じ結果になる（NFR4）
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件は無い）。

## Implementation Phases

### Phase 1: ケースの追加と修正前の確認

**Goals:** FR5 のケースを追加し、FR6 の修正前の確認を行う。
**Deliverables:**
- `destructive-guard-cases.json` への TS-1〜TS-17 の追加
- 修正前のフックで TS-2、TS-7〜TS-17 が通り、TS-3・TS-4・TS-6 が deny になることを確かめた記録

### Phase 2: フックの修正

**Goals:** FR2〜FR4、FR7 を満たす。
**Deliverables:**
- `destructive-guard.py` の `statements()` の pending 積み込み条件の変更
- コード内の説明の更新
- TS-18（`run-destructive-guard.py` 全件通過）と NFR4 の確認

## References

- 要件定義書: `feature-docs/destructive-guard-false-deny/REQUIREMENTS.md`
- フック本体: `em-workflow/hooks/destructive-guard.py`
- ケース: `em-workflow/hooks/tests/destructive-guard-cases.json`
- ランナー: `em-workflow/hooks/tests/run-destructive-guard.py`
- プロトコル: `em-workflow/references/implement-phase.md`（Step I.2.b step 4）
- フックのテストのルール: `.claude/rules/hook-tests.md`
