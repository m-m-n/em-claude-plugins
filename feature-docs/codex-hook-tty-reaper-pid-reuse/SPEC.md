# Feature: codex-hook-tty-reaper-pid-reuse

## Overview

`codex-hook-tty-reaper.py` が、PID の再利用が起きた場合を含むどの段階でも、起動した Codex（起点）の子孫でないプロセスに SIGTERM も SIGKILL も送らないようにする。子孫と祖先チェーンのリンクに開始時刻の順序規則を加え、信号は確認の前に取得した pidfd を通じて送る。要件は `feature-docs/codex-hook-tty-reaper-pid-reuse/REQUIREMENTS.md` を参照する。

## Objectives

- `codex-hook-tty-reaper.py` は、PID の再利用が起きた場合を含むどの段階でも、起点の子孫でないプロセスに SIGTERM も SIGKILL も送らない。

## User Stories

該当なし（UI のない、プロセスへ信号を送るスクリプトの内部の不具合修正）。受け入れ基準は「Success Criteria」に AC-1〜AC-8 として置く。

## Technical Requirements

### Functional Requirements
- **FR1:** 子孫リンクへの開始時刻の順序規則。起点の子孫をスナップショットから求めるとき、子 C から親 P へのリンクは、P の記録上の開始時刻が C の開始時刻より後でない場合に限って採用する。開始時刻が等しいリンクは採用する。採用しなかったリンクの子 C と、C を経由してしか到達できないすべてのプロセスは子孫として扱わない。起点の開始時刻はスナップショットから取る。起点がスナップショットにないときは何も止めない（A3）。
- **FR2:** 確認の前に取得した pidfd を通じた送信。各対象について、まず `os.pidfd_open(pid)` で pidfd を取得する。その pidfd を保持したまま、`/proc/PID/stat` が記録した開始時刻のままであり、状態が死亡状態（`Z`、`X`、`x`）でないことを確かめる。確認が通ったときだけ、その pidfd に対して `signal.pidfd_send_signal` で SIGTERM を送る。確認が通らなかった対象には、その時点でも以後も信号を送らず、その pidfd を閉じる。
- **FR3:** SIGTERM から SIGKILL までの pidfd の保持。SIGTERM を送った各対象の pidfd を、猶予の待ちと SIGKILL の段階を通して保持する。SIGKILL は同じ pidfd を通じて、同じ開始時刻と死亡状態の確認を経て送る。1 つの対象に 2 つ目の pidfd を開かない。フックが開いたすべての pidfd を、どの経路でも実行が終わる前に閉じる。
- **FR4:** pidfd が使えない場合。`os.pidfd_open` か `signal.pidfd_send_signal` が存在しないとき、またはカーネルが pidfd に対応していないとき（例: ENOSYS）は、信号を送らず何も止めない。`os.kill` には戻らない。
- **FR5:** エラーの扱い。`pidfd_open` または `pidfd_send_signal` の ProcessLookupError はエラーとして扱わない。その対象にはそれ以上信号を送らず、ほかの対象の処理は続ける。それ以外のエラーは実行を終わらせ、以後の信号は送らない。pidfd を開くときの EMFILE と ENOSYS もこれに含む（A4）。
- **FR6:** フックの祖先チェーンへの開始時刻の順序規則。フック自身の祖先チェーンを PID 1 までたどるとき、プロセス X からその親 Y へのリンクを FR1 の規則で確かめる。Y の開始時刻が X の開始時刻より後なら、何も止めない。開始時刻が等しい場合は許容する。チェーンは引き続き、起点の妥当性の確認と除外対象の両方に使う。
- **FR7:** 2 つのコピー。`em-workflow/scripts/codex-hook-tty-reaper.py` と `em-review/scripts/codex-hook-tty-reaper.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR8:** 回帰テスト。`tests/test_codex_hook_tty_reaper.py` に、タスクの 2 つの再現手順、開始時刻が等しい場合、祖先チェーンの規則、pidfd が使えない場合、pidfd の処理中のエラーについてのプロセス内テストを追加する。テストの差し替え口を pidfd による送信に合わせて変える。偽の `pidfd_open` と `pidfd_send_signal` は、pidfd を開いた時点でその PID を持っていたプロセスのインスタンスに pidfd を結びつける。`main()` の既定値を固定するテストは、`os.kill` ではなく実際の pidfd の関数を既定値として確かめる。
- **FR9:** docstring。モジュールの docstring の Flow の手順 4、6、8、10 とエラーの段落に、開始時刻によるリンクの規則（子孫と祖先チェーン）、SIGKILL まで保持する pidfd による送信、pidfd が使えないときの動作を書く。

### Non-Functional Requirements
- **NFR1 - Dependencies:** 標準ライブラリだけを使う。`os.pidfd_open` と `signal.pidfd_send_signal` は Python 3.9 からあり、リポジトリは Python 3.14 を使う。
- **NFR2 - Silent operation:** どの経路でも終了コード 0 で、stdout にも stderr にも出力しない。環境変数を読まない。コピーを import しても何も実行しない。プラグインのディレクトリに `__pycache__` を残さない。既存のテストがこれらを固定している。
- **NFR3 - Behaviour preservation:** 対象の選び方（新しいリンク規則を除く）、順序（深いものから。同じ深さは PID の昇順）、SIGTERM → 0.5 秒の猶予 → SIGKILL のタイミング、その他の既存の動作は変えない。
- **NFR4 - Versioning:** プラグインの version を変えない（A1）。

## Implementation Approach

### Architecture

**System Architecture:**
```
┌──────────────────────────────────────────────┐
│ スナップショット（PID・PPID・開始時刻・状態）│
├──────────────────────────────────────────────┤
│ 祖先チェーンの確認（FR6）                    │
│  - 起点の妥当性の確認と除外対象              │
├──────────────────────────────────────────────┤
│ 子孫の計算（FR1）                            │
│  - 親の開始時刻 <= 子の開始時刻のリンクだけ  │
├──────────────────────────────────────────────┤
│ 対象の並べ替え（NFR3: 深い順、同深は PID 昇順）│
├──────────────────────────────────────────────┤
│ pidfd による停止（FR2〜FR5）                 │
│  pidfd_open → 確認 → SIGTERM → 0.5 秒        │
│  → 確認 → SIGKILL（同じ pidfd）→ close       │
└──────────────────────────────────────────────┘
```

**Component Diagram:**
```
em-workflow/scripts/codex-hook-tty-reaper.py  ─┐ バイト単位で同一（FR7）
em-review/scripts/codex-hook-tty-reaper.py    ─┘
        ▲ 引数 ANCHOR（変更なし、A2）
        │
em-workflow/scripts/run_codex_exec.sh / em-review/scripts/run_codex_exec.sh（変更なし）

tests/test_codex_hook_tty_reaper.py
  - 偽の pidfd_open / pidfd_send_signal（pidfd を開いた時点のプロセスのインスタンスに結びつく）
  - FakeTable（スナップショットの偽物）
```

### Data Flow

```
スナップショット
  → 祖先チェーン（FR6: 親が子より後に開始したリンクがあれば何も止めない）
  → 起点の確認（起点がスナップショットになければ何も止めない、A3）
  → 子孫の計算（FR1: 親が子より後に開始したリンクは採用しない）
  → 対象ごとに pidfd_open（FR2。使えなければ何も止めない、FR4）
  → pidfd を保持したまま開始時刻・状態を確認 → pidfd_send_signal(SIGTERM)
  → 0.5 秒の猶予（NFR3）
  → 同じ pidfd で開始時刻・状態を確認 → pidfd_send_signal(SIGKILL)（FR3）
  → すべての pidfd を閉じる（FR3）
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/run_codex_exec.sh`、`em-review/scripts/run_codex_exec.sh`: スクリプトを引数 `ANCHOR` で起動する。スクリプトのファイル名と引数は変えないため、変更しない（A2）。

**External Dependencies:**
- Python 標準ライブラリ: `os.pidfd_open`、`signal.pidfd_send_signal`（Python 3.9 から。リポジトリは Python 3.14）（NFR1）。

### File Structure

```
em-workflow/scripts/codex-hook-tty-reaper.py   # 修正（FR1〜FR6、FR9）
em-review/scripts/codex-hook-tty-reaper.py     # 修正（上とバイト単位で同一、FR7）
tests/test_codex_hook_tty_reaper.py            # テストの追加と差し替え口の変更（FR8）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-hook-tty-reaper-pid-reuse/**`
- `test-docs/codex-hook-tty-reaper-pid-reuse/**`

`feature-docs/codex-hook-tty-reaper-pid-reuse/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-hook-tty-reaper-pid-reuse/**` covers
`test-docs/codex-hook-tty-reaper-pid-reuse/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-hook-tty-reaper-pid-reuse/` directory at all; the declared
`test-docs/codex-hook-tty-reaper-pid-reuse/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1（AC-1）: FakeTable に、起点 A、ppid が P である無関係な古いプロセス C（開始 100）、A の下に作り直された P（開始 200）を置く。`main()` を実行し、C が SIGTERM も SIGKILL も受けないことを確かめる。
- [ ] TS-2（AC-2）: 開始 100 の対象を置く。偽の stat 読み取りは 100 を返し、その直後にその PID のプロセスが開始 200 になる。開始 200 のインスタンスに対する信号が記録されないことを確かめる（pidfd はインスタンス 100 を指す）。
- [ ] TS-3（AC-3）: 起点の下に、開始時刻が等しい親と子を置く。子が SIGTERM を受けることを確かめる。
- [ ] TS-4（AC-4）: フックの祖先チェーンに、親の開始時刻が子より後のリンクがある。信号が送られないことを確かめる。対になるケースとして、チェーン上の開始時刻が等しい場合は対象が止められることを確かめる。
- [ ] TS-5（AC-5）: `pidfd_open` の差し替え口を欠いた（または None の）状態で 1 回、OSError(ENOSYS) を投げる状態で 1 回実行する。信号が送られず、`os.kill` が使われないことを確かめる。
- [ ] TS-6（AC-6）: `pidfd_open` または `pidfd_send_signal` がある対象で ProcessLookupError を投げ、ほかの対象には信号が届くことを確かめる。OSError(EMFILE) または PermissionError を投げ、以後の信号が送られないことを確かめる。
- [ ] TS-7（AC-7）: 同じ対象の SIGTERM と SIGKILL に使った pidfd を記録し、同じであることを確かめる。エラー経路を含め、`main()` が戻った後にすべての偽の pidfd が閉じていることを確かめる。

### Integration Tests
- [ ] TS-8（AC-8）: 2 つのコピーのバイト同一性の既存テスト、pidfd の関数向けに更新した既定値のテスト、Linux での既存の実プロセスのテストが通る。
  - `python3 -m unittest tests.test_codex_hook_tty_reaper`
  - `python3 -m unittest discover -s tests`

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 親と子の開始時刻が等しい子孫リンク: 採用し、子は対象になる（FR1、TS-3）。
- [ ] 祖先チェーン上の開始時刻が等しいリンク: 停止を妨げない（FR6、TS-4）。
- [ ] 起点がスナップショットにない: 何も止めない（FR1、A3）。
- [ ] pidfd が使えない: 信号を送らず、`os.kill` に戻らない（FR4、TS-5）。

### Performance Tests
該当なし。SIGTERM → 0.5 秒の猶予 → SIGKILL のタイミングは変えない（NFR3）。

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 信号を送る前に、保持した pidfd のもとで `/proc/PID/stat` の開始時刻が記録どおりであり、状態が死亡状態（`Z`、`X`、`x`）でないことを確かめる（FR2、FR3）。子孫と祖先チェーンのリンクに開始時刻の順序規則を適用する（FR1、FR6）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | Behaviour |
|------|-------------|-----------|
| ProcessLookupError | `pidfd_open` または `pidfd_send_signal` で発生 | エラーとして扱わない。その対象にはそれ以上信号を送らず、ほかの対象の処理は続ける（FR5） |
| EMFILE | pidfd を開くときに発生 | 実行を終える。以後の信号は送らない（FR5） |
| ENOSYS | カーネルが pidfd に対応していない | 信号を送らず、何も止めない（FR4、FR5） |
| pidfd の関数が存在しない | `os.pidfd_open` か `signal.pidfd_send_signal` がない | 信号を送らず、何も止めない。`os.kill` に戻らない（FR4） |
| その他のエラー | 上記以外 | 実行を終える。以後の信号は送らない（FR5、A4） |

どの経路でも、開いたすべての pidfd を閉じ（FR3）、終了コード 0 で stdout / stderr に出力しない（NFR2）。

### Error Flow

```
エラー発生 → ProcessLookupError ならその対象だけ飛ばして続行
           → それ以外なら以後の信号を送らない → pidfd をすべて閉じる → 終了コード 0
```

## Performance Optimization

### Performance Goals
- SIGTERM → 0.5 秒の猶予 → SIGKILL のタイミングを変えない（NFR3）。

### Optimization Strategies
該当なし。

### Caching Strategy
該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC-1: 再現手順 1 で C に信号を送らない。C の古い PPID と、再利用された P の新しい PPID が 1 つのスナップショットに現れ、再利用された P の開始時刻は C の開始時刻より後である。
- [ ] AC-2: 再現手順 2 で、開始時刻 200 のインスタンスに SIGTERM も SIGKILL も送らない。stat の読み取りが開始時刻 100 を返し、その後その PID のプロセスが開始時刻 200 のものに入れ替わる。
- [ ] AC-3: 親と子の開始時刻が等しい子孫リンクはたどられ、子は引き続き対象になる。
- [ ] AC-4: フックの祖先チェーンに、親が子より後に開始したリンクがあると、信号を一切送らない。チェーン上の開始時刻が等しいリンクは、停止を妨げない。
- [ ] AC-5: `os.pidfd_open` か `signal.pidfd_send_signal` が存在しないとき、または `pidfd_open` が ENOSYS で失敗したとき、信号を送らず、`os.kill` を一度も呼ばない。
- [ ] AC-6: `pidfd_open` または `pidfd_send_signal` の ProcessLookupError では、その対象を飛ばし、ほかの対象には信号が届く。EMFILE を含むそれ以外の OSError では、以後の信号を止める。
- [ ] AC-7: ある対象への SIGKILL は、その対象の SIGTERM の前に開いた pidfd を通じて送る。`main()` が戻った後、成功時もエラー時も、開いたままの pidfd はない。
- [ ] AC-8: 2 つのコピーがバイト単位で同一である。`python3 -m unittest tests.test_codex_hook_tty_reaper` と `python3 -m unittest discover -s tests` が、Linux での実プロセスのテストを含めて通る。

## Assumptions

- A1: この作業ではプラグインの version を変えない（`.claude/rules/core-plugin-version-bump.md`）。
- A2: スクリプトのファイル名と、ただ 1 つの引数 `ANCHOR` は変えない。2 つの `run_codex_exec.sh` は変更しない。
- A3: 起点がスナップショットにないときは、何も止めない。既存の方針「疑わしければ何も止めない」に従う。
- A4: 既存のエラー規則を保つ。プロセスが存在しないことはエラーではなく、それ以外のエラーは以後の信号を送らずに実行を終える。pidfd のエラーも同じ規則に従う。
- A5: 親と子の両方の pidfd を取った後の追加の再確認は加えない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件はない）。

## References

- 要件定義書: `feature-docs/codex-hook-tty-reaper-pid-reuse/REQUIREMENTS.md`
- プラグインの version の扱い: `.claude/rules/core-plugin-version-bump.md`
