# Feature: destructive-guard-mixed-rm-precedence

## Overview

複合コマンドのどこかに deny になる再帰削除があるとき、destructive-guard はセグメントの順序や他の check の有無に関係なく deny と再帰削除側の理由 ID（rm-recursive / rm-root）を出す。D6 で入った退行（後ろのセグメントの rm 以外の ask が、先に集めた rm の deny を飲み込む）を直す。ケース表に理由 ID を固定するキー `rule` を足し、同じ退行を検出できるようにする。

要件の詳細は `feature-docs/destructive-guard-mixed-rm-precedence/REQUIREMENTS.md` を参照する。

## Objectives

- 複合コマンドのどこかに deny になる再帰削除があるとき、セグメントの順序や他の check の有無に関係なく deny と再帰削除側の理由 ID（rm-recursive / rm-root）を出す。
- 無人実行（CLAUDE_BATCH）では、エージェントが自分で直すために読む判定文に、再帰削除の対象の位置と書き換え案が残るようにする（今は git-amend などの理由に置き換わって消えている）。
- rm と rm 以外が混ざった形で同じ退行が再び起きたら、ケース表で検出できるようにする。判定段と理由 ID の両方を固定する。

## User Stories

### US1: 混ざった複合コマンドでも再帰削除の deny が出る
As an em-workflow の利用者, I want to 再帰削除と rm 以外の ask 源が混ざった複合コマンドで deny / 再帰削除側の理由 ID を受け取る, so that セグメントの順序に関係なく再帰削除が止まる.

**Acceptance Criteria:**
- [ ] AC1: CLAUDE_BATCH を立てずに、task の 5 つの形（rm を先に置いた順）を destructive-guard.py に渡すと、permissionDecision が deny、理由の先頭が [destructive-guard/rm-recursive] になる。
- [ ] AC2: 同じ 5 つの形で順序を逆にしても deny / rm-recursive になる。
- [ ] AC4: rm -rf ~ ; git commit --amend は deny / rm-root になる。
- [ ] AC5: rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json は deny / rm-recursive になる。
- [ ] AC9: `rm -rf ~/.claude/skills/foo` は ask / self-modification のまま。`rm -rf ~/.claude/skills/foo ; rm -rf /home/user/valuable` は deny / rm-recursive。`rm -rf ~/.claude/skills/foo /home/user/valuable` は ask / self-modification。CLAUDE_BATCH を立てた `rm -rf ~/.claude/skills/foo` は deny / self-modification（降格は優先を決めた後）。
- [ ] AC10: rm -rf /home/user/valuable の後に、scan budget を超えるか lex を確定できない部分が続く形を作れるなら、それは deny / rm-recursive になる。

### US2: 無人実行の判定文に再帰削除の対象と書き換え案が残る
As a 無人実行（CLAUDE_BATCH）のエージェント, I want to 判定文で再帰削除の対象の位置と書き換え案を読む, so that 自分でコマンドを直せる.

**Acceptance Criteria:**
- [ ] AC3: CLAUDE_BATCH を立てて rm の deny 対象 ; git commit --amend を渡すと deny / rm-recursive になる。理由の本文に「1番目のrmの1番目の対象」の位置表記と書き換え案が入り、git-amend の文言は入らない。

### US3: ケース表で判定段と理由 ID を固定する
As a フックの開発者, I want to ケースに期待する理由 ID を書く, so that rm と rm 以外が混ざった形の退行をケース表で検出できる.

**Acceptance Criteria:**
- [ ] AC6: run-destructive-guard.py は `rule` 付きのケースで理由 ID が違えば FAIL にする（例: rule を git-amend にしたケースは修正後のフックで FAIL）。`rule` が無いケースは判定段だけで判定する。
- [ ] AC7: 追加したケースを含めて `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る（無人実行の降格チェックも含む）。
- [ ] AC8: 既存のケースを 1 件も消さず、書き換えもしない。

## Technical Requirements

### Functional Requirements
- **FR1:** 後ろの rm 以外の ask より、先に集めた rm の deny を優先する。deny になる再帰削除のセグメントの後に rm 以外の ask 源（check_git の git-amend、check_permissions の chmod-broad / chown-recursive、check_external の terraform / kubectl-destructive / cloud-iam / cloud-delete / systemctl-system / remote-exec / gh-pr-merge、check_file_destruction の archive-overwrite、別の文の check_self_modification の self-modification）が続く複合コマンドの判定は deny とする。理由 ID は再帰削除側（rm-recursive。root やホームの形なら rm-root）にする。区切りは `;` `&&` `||` 改行のどれでも同じ。同じ文の中の self-modification は FR8 に従う。
- **FR2:** 順序を逆にしても同じ判定にする。rm 以外の ask 源が先で、deny になる再帰削除が後ろのセグメントにある複合コマンドも deny とし、理由 ID は再帰削除側にする。rm 以外の ask は走査が終わるまで後回しにし、コマンド全体を見てから確定させる。今は最初の ask で exit するため後ろのセグメントを見ていない。
- **FR3:** 優先を決めてから降格する。rm の deny と rm 以外の ask を比べるときは降格前の段（ask）を使う。CLAUDE_BATCH による ask から deny への降格は、どれを優先するか決めた後に行う。発火する理由 ID は再帰削除側で、理由の本文に再帰削除の対象の位置（rm_target_designation）と書き換え案がそのまま入る。
- **FR4:** 走査の途中で出る ask も、集めた rm の deny には勝たない。statements() の走査中に scan budget を超えたとき（scan-budget-exceeded）と、LexBudgetExceeded / LexUnmatchedSubscript になったとき（ask_lex_unsettled）は、その場で走査をやめる。その時点で集めた rm 判定に deny があれば（FR8 で候補から外した分は除く）、deny と再帰削除側の理由を出す。deny が無ければ今と同じ ask を出す。statements() の「先に出た deny はすでに出ている」という前提のコメントは、D6 以後は成り立っていない。
- **FR5:** ケースの 4 要素目に理由 ID を固定するキーを足す。run-destructive-guard.py はケースの 4 要素目に任意の `rule`（空でない文字列）を受け付ける。`rule` があるケースでは、permissionDecisionReason の先頭 `[destructive-guard/<rule>]` から取り出した理由 ID も期待値と比べる。判定段か理由 ID のどちらかが違えば FAIL にする。FAIL の行には得られた理由 ID も出す。`rule` が無いケースは今までどおり判定段だけを比べる。3 要素のケースと、cwd / batch だけの 4 要素のケースは今と同じ結果になる。`rule` が文字列でない、または知らないキーがあるときは、今までどおり malformed case として実行を止める。
- **FR6:** 退行を検出するケースを足す。destructive-guard-cases.json に、少なくとも次のケースを `rule` 付きで足す。(a) task に挙がっている 5 つの形（rm の deny 対象 ; git commit --amend / ; chmod -R 777 /etc / && terraform destroy / ; kubectl delete pod x / ; gcloud projects add-iam-policy-binding ...）を、rm を先に置いた順と後ろに置いた順の両方で、それぞれ deny / rm-recursive に固定する。(b) 少なくとも 1 つの形の batch:true 版を deny / rm-recursive に固定する。(c) rm-root の形（rm -rf ~ ; git commit --amend）を deny / rm-root に固定する。(d) 別の文の self-modification との組み合わせと、FR8 の 3 つの例（TS-9・TS-12・TS-13）を固定する。対象パスは既存ケースと同じ汎用の例（/home/user/valuable など）にし、マシン固有のパスは書かない。
- **FR7:** コメントとドキュメントを今の制御の流れに合わせる。main() で strongest_rm_decision() を呼ぶ直前のコメント、statements() の「a deny among them has been given」、route_substitution_headed_statement() の docstring の check_git() が exit するという記述、run-destructive-guard.py のモジュール docstring と case_options() のエラーメッセージ、`.claude/rules/hook-tests.md` のケース形式の説明を、修正後の動作（FR8 の例外も含む）と `rule` キーに合わせて書き換える。
- **FR8:** 同じ文の self-modification は、その文の rm 判定より優先する。rm の呼び出しの削除対象そのものが保護された自己設定パス（SELF_CONFIG）なために self-modification の ask が出たとき、その ask は同じ文の rm 判定より優先する。ここでの「文」は、main() のループで statements() が 1 回 yield した単位を指す。ループの 1 回ごとに区別し、文字列や行が同じかどうかでは決めない。別に yield されるコマンド置換の本文や bash -c の payload には広げない。その文の rm 判定（rm-recursive / rm-root / rm-unresolvable）は、プールで勝ちを決める候補から外す。self-modification の ask は他の ask と同じく走査の最後まで後回しにする。他の文の rm の deny は、順序に関係なくこの ask に勝つ。CLAUDE_BATCH による降格は、優先を決めた後に行う。例: `rm -rf ~/.claude/skills/foo` は ask / self-modification のまま（既存ケース 42 行目）。`rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json` は deny / rm-recursive。`rm -rf ~/.claude/skills/foo ; rm -rf /home/user/valuable` は deny / rm-recursive。わかっている影響: 1 つの rm に保護パスと /home/user/valuable を並べた形（`rm -rf ~/.claude/skills/foo /home/user/valuable`）は ask / self-modification のままになる。

### Non-Functional Requirements
- **NFR1 - 検出力:** 検出力を下げない。今 deny のコマンドは、修正後もすべて deny のまま。既存の deny / ask ケースは消さず、書き換えもしない（hook-tests.md のルール）。42 行目の `rm -rf ~/.claude/skills/foo`（ask）も含む。
- **NFR2 - deny の無いコマンドの互換:** どこにも deny が無いコマンドの判定段と理由 ID は今と変えない。ask が複数あるときは、今の実装が出している理由 ID がそのまま発火する（今と同じく、ループの中で最初に出た rm 以外の ask が、ループ後の unsettled / gh-pr-merge fallback / rm の ask より先に立つ）。
- **NFR3 - 変化の向き:** ask を後回しにして後ろのセグメントを見るようにしたことで、そこで rm 以外の deny が見つかった場合は deny に変わってよい（強くなる方向の変化）。弱くなる方向の変化は許さない。FR8 の例外は、今 ask の形を ask のまま残すためのもので、今 deny の形を弱めない。
- **NFR4 - Performance:** 後ろのセグメントまで見るようにしても、走査は既存の scan budget と線形の作業上限の中に収まる。どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない。
- **NFR5 - 決定性:** 判定は今までどおりコマンド文字列だけで決まる。同じコマンド文字列からは、同じ判定段・理由 ID・理由の本文が出る。
- **NFR6 - version:** plugin.json / marketplace.json の version は触らない（バグ修正なので patch。上げるのは Actions）。

## Implementation Approach

### Architecture

**Component Diagram:**
```
em-workflow/hooks/destructive-guard.py
  main()
    statements() の yield ごとに 1 文を判定する
      rm 判定 ──────────────> rm 判定のプール（FR8 で外した文の分は候補にしない）
      rm 以外の deny ───────> その場で exit（A2・A8、今と同じ）
      rm 以外の ask ────────> 走査の最後まで後回し（FR2）
    走査の終わり、または scan-budget-exceeded / ask_lex_unsettled（FR4）
      降格前の段で比べる（FR3）
        rm の deny がある ──> deny / rm-recursive・rm-root
        rm の deny が無い ──> 今と同じ ask（NFR2）
      優先を決めた後に CLAUDE_BATCH の降格（FR3・FR8）

em-workflow/hooks/tests/run-destructive-guard.py
  case_options(): 4 要素目の cwd / batch / rule を受け付ける（FR5）
  判定段と理由 ID を比べる（rule があるケースだけ理由 ID も）

em-workflow/hooks/tests/destructive-guard-cases.json
  rule 付きのケースを足す（FR6）
```

### Data Flow

```
コマンド文字列 → statements() の走査 → rm 判定のプール / 後回しの ask
              → 優先を決める（降格前の段） → CLAUDE_BATCH の降格 → permissionDecision / permissionDecisionReason
```

### Case Format

`destructive-guard-cases.json` のケースは `[期待する判定, ラベル, コマンド]`、または 4 要素目にオプションを足した形。

| キー | 型 | 必須 | 説明 |
|------|-----|------|------|
| `cwd` | 文字列 | × | ペイロードの作業ディレクトリ（既存） |
| `batch` | 真偽値 | × | そのケースだけ CLAUDE_BATCH を立てる（既存） |
| `rule` | 空でない文字列 | × | 期待する理由 ID。permissionDecisionReason の先頭 `[destructive-guard/<rule>]` と比べる（FR5） |

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: 判定の優先順位を変える対象
- `em-workflow/hooks/tests/run-destructive-guard.py`: フックを subprocess で動かしてケースを判定する（A6）
- `em-workflow/hooks/tests/destructive-guard-cases.json`: ケース表
- `.claude/rules/hook-tests.md`: ケース形式の説明（FR7）

**External Dependencies:**
- なし

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py              # FR1〜FR4、FR7、FR8
└── tests/
    ├── run-destructive-guard.py      # FR5、FR7
    └── destructive-guard-cases.json  # FR6
.claude/rules/
└── hook-tests.md                     # FR7
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-mixed-rm-precedence/**`
- `test-docs/destructive-guard-mixed-rm-precedence/**`

`feature-docs/destructive-guard-mixed-rm-precedence/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/destructive-guard-mixed-rm-precedence/**` covers `test-docs/destructive-guard-mixed-rm-precedence/{T}.tests.yaml`, the
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

### Integration Tests

TS-1〜TS-16 は `destructive-guard-cases.json` に `rule` 付きのケースとして足し、`python3 em-workflow/hooks/tests/run-destructive-guard.py` でフックを subprocess で動かして判定する。表記は [期待する判定段, 理由 ID]。

- [ ] TS-1: `rm -rf /home/user/valuable ; git commit --amend` - [deny, rm-recursive]
- [ ] TS-2: `git commit --amend ; rm -rf /home/user/valuable` - [deny, rm-recursive]
- [ ] TS-3: `rm -rf /home/user/valuable ; chmod -R 777 /etc` とその逆順 - [deny, rm-recursive]
- [ ] TS-4: `rm -rf /home/user/valuable && terraform destroy` とその逆順 - [deny, rm-recursive]
- [ ] TS-5: `rm -rf /home/user/valuable ; kubectl delete pod x` とその逆順 - [deny, rm-recursive]
- [ ] TS-6: `rm -rf /home/user/valuable ; gcloud projects add-iam-policy-binding p --member=user:a@example.com --role=roles/owner` とその逆順 - [deny, rm-recursive]
- [ ] TS-7: `rm -rf /home/user/valuable ; git commit --amend`（batch:true） - [deny, rm-recursive]
- [ ] TS-8: `rm -rf ~ ; git commit --amend` - [deny, rm-root]
- [ ] TS-9: `rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json`（別の文の self-modification） - [deny, rm-recursive]
- [ ] TS-10: `rm -rf tmp/$X ; git commit --amend`（どちらも ask） - [ask、理由 ID は今の実装と同じ。今の出力は git-amend]
- [ ] TS-11: （作れる場合）`rm -rf /home/user/valuable` の後に、scan budget を超える入れ子が続く形 - [deny, rm-recursive]
- [ ] TS-12: `rm -rf ~/.claude/skills/foo`（既存の 42 行目と同じ形を `rule` 付きでもう 1 件足す。既存ケースは書き換えない） - [ask, self-modification]
- [ ] TS-13: `rm -rf ~/.claude/skills/foo ; rm -rf /home/user/valuable` - [deny, rm-recursive]
- [ ] TS-14: `rm -rf /home/user/valuable ; rm -rf ~/.claude/skills/foo`（TS-13 の逆順） - [deny, rm-recursive]
- [ ] TS-15: `rm -rf ~/.claude/skills/foo /home/user/valuable`（わかっている影響を固定する） - [ask, self-modification]
- [ ] TS-16: `rm -rf ~/.claude/skills/foo`（batch:true。優先を決めた後に降格する） - [deny, self-modification]
- [ ] TS-17: `rule` 付きのケースで理由 ID が違うとき（例: rule を git-amend にしたケースを修正後のフックで動かす） - run-destructive-guard.py が FAIL にする。`rule` が無いケースは判定段だけで判定する（AC6）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 上の TS-10・TS-11・TS-15 を参照

### Performance Tests
- [ ] どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない（NFR4）

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** ランナーは `rule` が文字列でない、または 4 要素目に知らないキーがあるケースを malformed case として実行を止める（FR5）
- **Data Protection:** ケースにマシン固有のパスを書かない（FR6）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| malformed case | `rule` が文字列でない、または 4 要素目に知らないキーがある | - | case_options() のエラーメッセージ（FR7 で `rule` キーに合わせる） |
| FAIL | 判定段か理由 ID のどちらかが期待値と違う | - | FAIL の行に得られた理由 ID も出す |

### Error Flow

```
ケースを読む → 4 要素目を検査（malformed なら実行を止める）→ フックを subprocess で動かす
→ 判定段を比べる →（rule があれば）理由 ID を比べる → 違えば FAIL（得られた理由 ID を出す）
```

## Performance Optimization

### Performance Goals
- どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない。
- 走査は既存の scan budget と線形の作業上限の中に収まる。

## Assumptions

- A1: rm 以外を先に置いた逆順の形も deny / rm-recursive に固定する（batch の回答 create-spec.reverse-order: A で確定）。
- A2: rm 以外の deny と rm の deny が同じコマンドにあるときは、今の動作（rm 以外の deny はループの中ですぐ exit する）を残す（batch の回答 create-spec.deny-vs-deny: A で確定）。
- A3: task の「同じ露出を持つ他の非 rm ask 源」は一部がコードと合わない。git-worktree-force-remove はコード上 deny（check_git）なので ask 源ではない。archive-overwrite は tar / unzip の -o / --overwrite から出るもので、sed -i からは出ない。要件はコード上の実際の ask 源を対象にする。
- A4: 理由 ID を固定するには、ケースの 4 要素目に任意キー `rule` を足す（batch の回答 create-spec.rule-key: A で確定）。既存ケースには付け足さない。
- A5: LICENSE ファイル、パッケージマニフェスト、E2E の仕組み、UI はどれも無い。
- A6: ケースの判定は、今までどおりフックを subprocess で動かした出力で行う。テストからフックの関数を直接 import することはしない。
- A7: FR8 の例外は、self-modification の ask が rm の削除対象から出たときだけ効く。rm の文で ask が redirect 先（例: `rm -rf /home/user/valuable > ~/.claude/settings.json`）だけから出た場合は、その文の rm 判定を候補から外さないので、rm の deny が勝つ。FR8 は rm の呼び出しを、普通の経路でもコマンド置換を先頭に置いた経路でも、同じ yield の中なら同じに扱う。
- A8: 同じ文で transcript-write（deny）が出た場合は、rm 以外の deny なので今までどおりループの中ですぐ exit する（A2）。FR8 は self-modification の ask だけを対象にする。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1〜AC10 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## References

- 要件定義書: `feature-docs/destructive-guard-mixed-rm-precedence/REQUIREMENTS.md`
- フックのテストのルール: `.claude/rules/hook-tests.md`
