# Feature: mixed-rm-self-config-deny

## Overview

`em-workflow/hooks/destructive-guard.py` で、self-modification の ask が出た文の rm 判定をプールから外す単位を、rm の呼び出しから対象に改める。1 つの rm に保護された自己設定パスと deny になる再帰削除の対象が並ぶ形は、保護パスでない側の対象の deny（rm-recursive / rm-root）になる。保護パスだけを消す rm は今と同じく self-modification の ask のまま。要件は `feature-docs/mixed-rm-self-config-deny/REQUIREMENTS.md` を参照する。

## Objectives

- 1 つの rm の対象に保護された自己設定パスと deny になる再帰削除の対象が並んでいるとき、保護パスでない側の対象の deny（rm-recursive / rm-root）を出す。いまは self-modification の ask に飲み込まれている。
- 保護パスだけを消す rm（単体、または他の対象が deny にならない形）は、今と同じく self-modification の ask のままにする。

## User Stories

### US1: 保護パスと deny になる対象が並ぶ rm を deny にする
1 つの再帰 rm に保護パスと deny になる対象が並ぶとき、保護パスでない側の対象の deny（rm-recursive / rm-root）が出る。

**Acceptance Criteria:**
- [ ] AC1: `rm -rf ~/.claude/skills/foo /home/user/valuable` は deny / rm-recursive。理由の本文に「1番目のrmの2番目の対象」が入り、「1番目のrmの1番目の対象」と self-modification の文言は入らない。
- [ ] AC2: 対象の順序を逆にした `rm -rf /home/user/valuable ~/.claude/skills/foo` も deny / rm-recursive（位置表記は「1番目のrmの1番目の対象」）。
- [ ] AC3: CLAUDE_BATCH を立てた AC1 の形は deny / rm-recursive で、理由の本文は CLAUDE_BATCH なしのときと同じ。
- [ ] AC4: `rm -rf ~/.claude/skills/foo ~` は deny / rm-root。
- [ ] AC6: 保護パスの書き方（`~/`、`$HOME/`、`--` の後）が変わっても AC1 と同じく deny / rm-recursive。

### US2: 保護パスだけを消す rm は今のまま
保護パス以外の対象が deny にならない rm は、今と同じく self-modification の ask になる。

**Acceptance Criteria:**
- [ ] AC5: `rm -rf ~/.claude/skills/foo`、`rm -rf ~/.claude/skills/foo tmp/$X`、`rm -rf ~/.claude/skills/foo /tmp/x`、`rm -rf ~/.claude/skills/foo ~/.claude/hooks/bar`、`rm ~/.claude/skills/foo /home/user/valuable` は ask / self-modification のまま。
- [ ] AC7: 旧 feature のケース TS-12・TS-13・TS-14・TS-16・TS-20、42 行目、31 行目の判定と理由 ID は変わらない。

### US3: テストと文書が新しい動作を書いている

**Acceptance Criteria:**
- [ ] AC8: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` が全件通る。
- [ ] AC9: 旧 feature の SPEC.md の FR8・AC9・TS-15 と hook-tests.md の優先順位の箇条が新しい動作を書いている。旧 feature の REQUIREMENTS.md と VERIFICATION.md は変わっていない。

## Technical Requirements

### Functional Requirements
- **FR1:** 除外の単位を rm の呼び出しから対象に改める。その文で self-modification の ask が出ていて（self_modification_asked）、rm の削除対象のうち保護された自己設定パスに一致する対象がある場合、プールから外すのはその対象の rm 判定だけにする。同じ rm の残りの対象の判定はプールに入れる。対象の特定には、check_rm() の record と同じ `_number_rm_operands()` の対象番号を使う。同じ呼び出しの record は同じ anchor を持つ。普通の経路（destructive-guard.py の 10584-10588 行）と、コマンド置換が先頭の経路（10550-10555 行。オペランドの土台は shaped_words[skip_index:]、check_rm() に渡すものと同じ）の両方に当てはめる。どちらでも除外の条件（その文の self_modification_asked）は変えない。対象を数える土台は check_rm() と同じにする（`--` の規則、operator syntax は数えない、`-` で始まる対象は判定しない）。
- **FR2:** 保護パスの判定方法は今と同じ。保護された自己設定パスかどうかは、今の rm_operands_name_self_config() と同じく判定する。生のオペランドか normalize_candidate() で正規化した形のどちらかが SELF_CONFIG に一致すれば保護パスとみなす。正規化後の形だけで判定する方式にはしない。
- **FR3:** 混ざった形の判定。1 つの rm に保護パスと deny になる対象が並ぶ形は、対象の並び順にかかわらず deny とする。理由 ID は rm-recursive（root やホームの形なら rm-root）。理由の本文は、保護パスを外した後の勝ちの対象だけで作る。位置表記は外した対象も数えた番号のまま（例 `rm -rf ~/.claude/skills/foo /home/user/valuable` なら「1番目のrmの2番目の対象」）。self-modification の文言と降格の文言は入れない。CLAUDE_BATCH を立てても同じ deny と理由 ID になる（優先を決めてから降格する）。保護パス以外の対象が ask 止まり（解決できない、グロブ）か、安全な領域の中（例 /tmp/x）か、全部が保護パスか、rm が再帰でないときは、今と同じく self-modification の ask のまま。
- **FR4:** rm_operands_name_self_config() とコメントを直す。rm_operands_name_self_config() を、保護パスに一致する対象の番号の集まりを返す形に変える（名前を変えるか、別の関数に置き換えてもよい）。main() のループにある除外のコメント（10499-10509 行）と、解決の段の前のコメント（10613-10616 行）を、除外の単位が対象になったことに合わせて書き直す。strongest_rm_decision( の直前のコメントブロックには、tests/test_destructive_guard_mixed_rm_precedence.py:809-815 が固定している語（"held ask"、"resolution step"、"self-modification"、"left out"）を残す。
- **FR5:** ケース表。em-workflow/hooks/tests/destructive-guard-cases.json の TS-15（1249 行）を、その場で書き換える。期待する判定を deny に、rule を rm-recursive に、ラベルを新しい動作に合わせる。ラベルの先頭 "destructive-guard-mixed-rm-precedence TS-15" はそのまま残す。この feature のケースは、表の最後に rule 付きで足し、ラベルを "mixed-rm-self-config-deny TS-" で始める。マシン固有のパスは書かない。42 行目（`rm -rf ~/.claude/skills/foo` ask）と 31 行目は変えない。
- **FR6:** 単体テスト。tests/test_destructive_guard_mixed_rm_precedence.py を新しい動作に合わせる。test_a_protected_and_an_unprotected_target_in_one_rm_stay_an_ask（271-275 行）の期待を deny / rm-recursive に変え、テスト名も実態に合わせる。TestCaseTable.test_each_scenario_has_its_case にある TS-15 のタプル（449 行）を ("deny", ..., "rm-recursive", False) に変える。新しい形の理由の本文（位置表記、self-modification の文言が無いこと、batch でも同じこと）を確かめるテストを足す。
- **FR7:** 旧 feature の SPEC.md。feature-docs/destructive-guard-mixed-rm-precedence/SPEC.md のうち、FR8 の「わかっている影響」の文、AC9 の第 3 文（`rm -rf ~/.claude/skills/foo /home/user/valuable` は ask / self-modification）、TS-15 の行（183 行）だけを新しい動作（deny / rm-recursive）に改める。同じ feature の REQUIREMENTS.md と VERIFICATION.md は当時の記録として残し、変えない。
- **FR8:** .claude/rules/hook-tests.md。優先順位の箇条「同じ文の rm の削除対象が保護された自己設定パスのときは、代わりに self-modification の `ask` が残る。」を、除外が対象単位であることに合わせて書き直す。保護パスの対象だけを候補から外す。同じ rm の残りの対象の deny は勝つ。

### Non-Functional Requirements
- **NFR1 - 変化の向き:** 判定が変わるのは、今 ask（self-modification）の形が deny に変わる方向だけにする。今 deny の形を弱めない。ケース表のうち判定が変わるのは TS-15 だけ。
- **NFR2 - deny の無い形の互換:** 保護パス以外の対象が deny にならない形の判定段と理由 ID は今と変えない（self-modification の ask。CLAUDE_BATCH なら deny / self-modification）。
- **NFR3 - 決定性:** 判定は今までどおりコマンド文字列だけで決まる。同じ文字列からは同じ判定段、理由 ID、理由の本文が出る。
- **NFR4 - 性能:** 走査は既存の scan budget と線形の作業上限の中に収まる。どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない。
- **NFR5 - version:** バグ修正なので plugin.json と marketplace.json の version は触らない（patch は Actions が上げる）。

## Implementation Approach

### Architecture

変更は `em-workflow/hooks/destructive-guard.py` の main() のループの中に閉じる。

```
文ごとの走査
  ├─ self_modification_asked（その文で self-modification の ask が出たか）
  ├─ check_rm() の record（_number_rm_operands() の対象番号、同じ呼び出しは同じ anchor）
  └─ 保護パスに一致する対象の番号の集まり（FR4 で rm_operands_name_self_config() を変えたもの）
        │
        ▼
  プールへの追加: self_modification_asked かつ record の対象番号が集まりに入る → 外す
                  それ以外 → 入れる
        │
        ▼
  解決の段（strongest_rm_decision）→ 優先を決めてから CLAUDE_BATCH の降格
```

### Data Flow

```
rm のオペランド（普通の経路 / コマンド置換が先頭の経路 shaped_words[skip_index:]）
  → _number_rm_operands()（check_rm() と同じ土台）
  → 各対象: 生の形か normalize_candidate() の形が SELF_CONFIG に一致するか
  → 一致した対象の番号の集まり
  → 番号が集まりに入る record だけをプールから外す
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- check_rm(): record と対象番号の出どころ
- _number_rm_operands(): 対象の番号づけ
- normalize_candidate() / SELF_CONFIG: 保護パスの判定
- rm_operands_name_self_config(): 保護パスに一致する対象の番号の集まりを返す形に変える
- strongest_rm_decision(): 解決の段

**External Dependencies:**
- なし

### File Structure

```
em-workflow/hooks/destructive-guard.py                         # FR1, FR2, FR3, FR4
em-workflow/hooks/tests/destructive-guard-cases.json           # FR5
tests/test_destructive_guard_mixed_rm_precedence.py            # FR6
feature-docs/destructive-guard-mixed-rm-precedence/SPEC.md     # FR7
.claude/rules/hook-tests.md                                    # FR8
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/mixed-rm-self-config-deny/**`
- `test-docs/mixed-rm-self-config-deny/**`

`feature-docs/mixed-rm-self-config-deny/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/mixed-rm-self-config-deny/**` covers `test-docs/mixed-rm-self-config-deny/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/mixed-rm-self-config-deny/` directory at all; the declared
`test-docs/mixed-rm-self-config-deny/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Integration Tests

`em-workflow/hooks/tests/destructive-guard-cases.json` の表の最後に rule 付きで足す。ラベルは "mixed-rm-self-config-deny TS-" で始める。判定は [期待する判定, 理由 ID] で書く。

- [ ] TS-1: `rm -rf ~/.claude/skills/foo /home/user/valuable` - [deny, rm-recursive]
- [ ] TS-2: `rm -rf /home/user/valuable ~/.claude/skills/foo` - [deny, rm-recursive]
- [ ] TS-3: `rm -rf ~/.claude/skills/foo /home/user/valuable`（batch:true） - [deny, rm-recursive]
- [ ] TS-4: `rm -rf ~/.claude/skills/foo ~` - [deny, rm-root]
- [ ] TS-5: `rm -rf ~/.claude/skills/foo tmp/$X` - [ask, self-modification]
- [ ] TS-6: `rm -rf ~/.claude/skills/foo /tmp/x` - [ask, self-modification]
- [ ] TS-7: `rm -rf ~/.claude/skills/foo ~/.claude/hooks/bar` - [ask, self-modification]
- [ ] TS-8: `rm ~/.claude/skills/foo /home/user/valuable`（再帰でない） - [ask, self-modification]
- [ ] TS-9: `rm -rf $HOME/.claude/skills/foo /home/user/valuable` - [deny, rm-recursive]
- [ ] TS-10: `rm -rf -- ~/.claude/skills/foo /home/user/valuable` - [deny, rm-recursive]
- [ ] TS-11: `rm -rf ~/.claude/skills/foo /home/user/valuable ; git commit --amend` - [deny, rm-recursive]

旧 feature のケース（その場で書き換え、FR5）: 旧 feature の TS-15 `rm -rf ~/.claude/skills/foo /home/user/valuable` を [deny, rm-recursive] にする。

### Unit Tests
- [ ] TS-12: AC1 から AC3 の理由の本文（位置表記、self-modification と降格の文言が無いこと、batch の有無で同じこと）を subprocess の出力で確かめる。 - AC1 から AC3 のとおり
- [ ] TS-13: コマンド置換が先頭の経路 `$(printf rm) -rf ~/.claude/skills/foo /home/user/valuable` の判定と理由の本文を、実際の出力に合わせて固定する。 - 実際の出力どおり

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-14: 同じ保護パスを 2 回書いた形 - どちらも除外される
- [ ] TS-15: リダイレクト先だけが保護パスの形（旧 feature の TS-20） - 今までどおり除外しない

範囲外: `~/.claude/skills/../../valuable` は生の形が SELF_CONFIG に一致するので今も除外される。この feature の範囲外とし、ケースでは固定しない（別タスク）。

### Performance Tests
- どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない（NFR4）。

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** 判定は今までどおりコマンド文字列だけで決まる（NFR3）。今 deny の形を弱めない（NFR1）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

該当なし。

## Performance Optimization

### Performance Goals
- 走査は既存の scan budget と線形の作業上限の中に収まる。
- どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない。

## Assumptions

- A1: 保護パスの判定は、生の形か正規化後の形のどちらかが SELF_CONFIG に一致すること（回答 raw_or_normalized）。正規化後の形だけにすると、HOME が /home 配下に無い環境で単体の自己設定削除が ask から deny に変わってしまう。
- A2: `~/.claude/skills/../../valuable` の形はこの feature の範囲外で、今の動作のまま残す。
- A3: 除外には、今と同じく、その文で self-modification の ask が出ていることが要る。変えるのは除外の単位だけ。
- A4: 旧 feature の文書は SPEC.md の FR8・AC9・TS-15 だけを改める（回答 spec_only）。
- A5: TS-15 の書き換えは ask から deny への変更で、ケースを消すわけではない。検出力は上がるので、hook-tests.md の「既存の deny / ask ケースは消さない」に反しない。
- A6: tests/ 配下でケース表の先頭からのダイジェストを固定しているテストの範囲に TS-15 の位置（index 1226）は入らない（固定は先頭 942 件と 1208 件まで）。
- A7: コマンド置換が先頭の経路で、今 self-modification の ask が出ているかどうかは確かめていない。出ていなければ、その経路では今も除外が効いておらず、この変更でも判定は変わらない（deny のまま）。
- A8: LICENSE ファイル、パッケージマニフェスト、E2E の仕組み、UI はどれも無い。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1 から AC9 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## References

- Requirements: feature-docs/mixed-rm-self-config-deny/REQUIREMENTS.md
- 対象のフック: em-workflow/hooks/destructive-guard.py
- ケース表: em-workflow/hooks/tests/destructive-guard-cases.json
- 単体テスト: tests/test_destructive_guard_mixed_rm_precedence.py
- 旧 feature の SPEC: feature-docs/destructive-guard-mixed-rm-precedence/SPEC.md
- テストのルール: .claude/rules/hook-tests.md
