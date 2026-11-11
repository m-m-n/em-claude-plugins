# Verification Document: destructive-guard-mixed-rm-precedence

## Overview
**Feature**: destructive-guard-mixed-rm-precedence / **SPEC.md**: `feature-docs/destructive-guard-mixed-rm-precedence/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-mixed-rm-precedence/IMPLEMENTATION.md`

## Build Verification
- Command (workflow.yaml project.components.main.build_command): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0, no errors.

## Test Verification
- Command (workflow.yaml project.components.main.test_command): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0. The runner prints `N/N passed`, and no case is marked FAIL or TIMEOUT.
- Coverage target: no coverage tooling is configured. Instead, every scenario below maps to at least one case-table entry, unittest or manual check.

### Test Scenarios from SPEC.md

TS-1 to TS-17 are SPEC.md's TS-1 to TS-17. TS-18 onward are derived from SPEC.md's requirements and assumptions (the source is named in each row).

Most scenarios are rule-pinned cases in `em-workflow/hooks/tests/destructive-guard-cases.json`, judged by the runner. For these, the expected result reads decision / reason id. Unless a row says batch, CLAUDE_BATCH is cleared.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `rm -rf /home/user/valuable ; git commit --amend` (FR1, SPEC AC1) | deny / rm-recursive | Integration (case) |
| TS-2 | `git commit --amend ; rm -rf /home/user/valuable` (FR2, SPEC AC2) | deny / rm-recursive | Integration (case) |
| TS-3 | `rm -rf /home/user/valuable ; chmod -R 777 /etc` and its reverse | deny / rm-recursive for both orders | Integration (case) |
| TS-4 | `rm -rf /home/user/valuable && terraform destroy` and its reverse | deny / rm-recursive for both orders | Integration (case) |
| TS-5 | `rm -rf /home/user/valuable ; kubectl delete pod x` and its reverse | deny / rm-recursive for both orders | Integration (case) |
| TS-6 | `rm -rf /home/user/valuable ; gcloud projects add-iam-policy-binding p --member=user:a@example.com --role=roles/owner` and its reverse | deny / rm-recursive for both orders | Integration (case) |
| TS-7 | TS-1's command, batch (FR3, SPEC AC3) | deny / rm-recursive. With HOME and PATH fixed, and with or without CLAUDE_BATCH, the reason equals the reason of `rm -rf /home/user/valuable` alone: it contains `1番目のrmの1番目の対象` and the deletion alternative, and neither the git-amend sentence nor the demotion sentence | Integration (case) + Unit |
| TS-8 | `rm -rf ~ ; git commit --amend` (SPEC AC4) | deny / rm-root | Integration (case) |
| TS-9 | `rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json`: self-modification in another statement (SPEC AC5) | deny / rm-recursive | Integration (case) |
| TS-10 | `rm -rf tmp/$X ; git commit --amend`: both parts ask (NFR2) | ask / the reason id the unmodified hook gives (git-amend) | Integration (case) |
| TS-11 | `rm -rf /home/user/valuable`, then a newline and a nest of unclosed command forms that exhausts the scan budget (FR4, SPEC AC10) | deny / rm-recursive. The unmodified hook gives ask / scan-budget-exceeded for the same command | Integration (case) |
| TS-12 | `rm -rf ~/.claude/skills/foo`, added as a new rule-pinned case; the existing case is unchanged (FR8, SPEC AC9) | ask / self-modification | Integration (case) |
| TS-13 | `rm -rf ~/.claude/skills/foo ; rm -rf /home/user/valuable` (FR8, SPEC AC9) | deny / rm-recursive. The reason designates `2番目のrmの1番目の対象` | Integration (case) + Unit |
| TS-14 | `rm -rf /home/user/valuable ; rm -rf ~/.claude/skills/foo` (TS-13 reversed) | deny / rm-recursive | Integration (case) |
| TS-15 | `rm -rf ~/.claude/skills/foo /home/user/valuable`: the known effect (FR8, SPEC AC9) | ask / self-modification | Integration (case) |
| TS-16 | `rm -rf ~/.claude/skills/foo`, batch: demotion after the precedence is decided (FR3, FR8, SPEC AC9) | deny / self-modification | Integration (case) |
| TS-17 | Runner: a case whose `rule` differs from the obtained reason id (TS-1's command pinned to `git-amend`, against the fixed hook); a case without `rule` (FR5, SPEC AC6) | The first fails: exit status 1, and the FAIL line shows the obtained reason id rm-recursive. The second is judged on the decision only | Unit |
| TS-18 | `rm -rf /home/user/valuable` joined to `git commit --amend` by `&&`, by `\|\|`, and by a newline (FR1: separators) | deny / rm-recursive for each separator | Integration (case) |
| TS-19 | `rm -rf /home/user/valuable ; ` followed by each of `chown -R user /srv/x`, `aws s3 rm s3://bucket/key`, `systemctl stop example.service`, `ssh host ls`, `gh pr merge 42`, `tar -xo -f a.tar` (FR1: the remaining non-rm ask sources) | deny / rm-recursive for each | Integration (case) |
| TS-20 | `rm -rf /home/user/valuable > ~/.claude/settings.json`: self-modification only from a redirect in the rm statement (FR8, A7) | deny / rm-recursive | Integration (case) |
| TS-21 | `git commit --amend ; chmod -R 777 /etc` and its reverse: two asks and no deny (NFR2) | ask / git-amend, and ask / chmod-broad for the reverse: the reason ids the unmodified hook gives | Integration (case) |
| TS-22 | `git commit --amend`, then a newline and TS-11's tail: a held ask followed by an early stop, with no deny (FR4, NFR2) | ask / git-amend, the reason id the unmodified hook gives | Integration (case) |
| TS-23 | Runner: a case with `rule` 5, a case with an empty `rule`, and a case with an unknown key; also the existing three-element and cwd / batch-only behaviour (FR5) | Each of the three malformed cases ends the run as a malformed case. Three-element and cwd / batch-only cases are judged as before | Unit |
| TS-24 | FR7 texts (source and document inspection): main()'s comment before the emission, the comment that opens main()'s loop, statements()'s comment before the unclosed-form budget answer, route_substitution_headed_statement()'s docstring, the runner's module docstring and malformed-case message, and the destructive-guard part of `.claude/rules/hook-tests.md` | None of them still says that reaching the rm emission means no other check decided first, that a deny has already been given, or that check_git() exits on an ask. The runner texts and the rule document describe `rule`. The rule document carries the mixed-case guidance | Unit (source inspection) + manual |
| TS-25 | Diff of the feature against the implement base commit, limited to `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (NFR6) | Neither file is modified | Manual (git diff) |
| TS-26 | TS-1's and TS-7's commands, each run twice in the same environment (NFR5) | stdout is byte-identical between the two runs | Unit |
| TS-27 | The full suite: `python3 em-workflow/hooks/tests/run-destructive-guard.py`, then `python3 -m unittest discover -s tests`, plus the diff of the case table against the implement base commit (NFR1, NFR3, NFR4; SPEC AC7, AC8) | Every case passes, each within GUARD_TIMEOUT_SECONDS, and the unattended-demotion check passes. The case-table diff only appends entries after the last pre-existing case. The unittest suite passes | Integration |

## Code Quality Verification
- Format: none configured (format_command is empty).
- Static analysis: none configured. Plugin invariants: the build command above.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The five forms with rm first are deny, and their reasons start with `[destructive-guard/rm-recursive]` | TS-1, TS-3 to TS-6 |
| AC2 | The same five forms in reverse order are deny / rm-recursive | TS-2 to TS-6 |
| AC3 | With CLAUDE_BATCH, rm deny target `; git commit --amend` is deny / rm-recursive; the reason holds the position designation and the rewrite suggestion and no git-amend wording | TS-7 |
| AC4 | `rm -rf ~ ; git commit --amend` is deny / rm-root | TS-8 |
| AC5 | `rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json` is deny / rm-recursive | TS-9 |
| AC6 | The runner fails a rule-pinned case whose reason id differs; a case without `rule` is judged on the decision only | TS-17 |
| AC7 | The full runner passes, including the added cases and the unattended-demotion check | TS-27 |
| AC8 | No existing case is removed or edited | TS-27 |
| AC9 | The four FR8 shapes have the expected decision and reason id | TS-12, TS-13, TS-15, TS-16 |
| AC10 | An rm deny followed by a part that exhausts the scan budget is deny / rm-recursive | TS-11 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3, TS-4, TS-5, TS-6, TS-18, TS-19 |
| FR2 | task0001 | TS-2, TS-3, TS-4, TS-5, TS-6 |
| FR3 | task0001 | TS-7, TS-8, TS-16 |
| FR4 | task0001 | TS-11, TS-22 |
| FR5 | task0001 | TS-17, TS-23 |
| FR6 | task0001 | TS-1 to TS-9, TS-12, TS-13 (all present as rule-pinned cases) |
| FR7 | task0001, task0002 | TS-24 |
| FR8 | task0001 | TS-9, TS-12, TS-13, TS-14, TS-15, TS-16, TS-20 |
| NFR1 | task0001 | TS-12, TS-27 |
| NFR2 | task0001 | TS-10, TS-21, TS-22, TS-27 |
| NFR3 | task0001 | TS-12, TS-15, TS-27 |
| NFR4 | task0001 | TS-11, TS-27 |
| NFR5 | task0001 | TS-26 |
| NFR6 | task0001 | TS-25 |

## Manual Testing (E2E Not Possible)
- [ ] Read the reasons produced for TS-7 (with and without CLAUDE_BATCH) and for TS-13. An unattended agent should be able to tell from the reason alone which rm target to rewrite and how.
- [ ] FR7 (TS-24): read the rewritten comments and docstrings, the runner's docstring and error message, and the destructive-guard part of `.claude/rules/hook-tests.md` against the implemented behaviour. This is the positive half that the source-inspection tests cannot judge.
- [ ] TS-25: confirm that the feature diff leaves the plugin manifest and the marketplace file untouched.

## Performance / Security Verification
- NFR4: every case finishes within GUARD_TIMEOUT_SECONDS (10 seconds). The runner fails a case that runs past it (TS-27). TS-11 and TS-22 exercise the early stop.
- TM-1: a pooled rm deny wins over a non-rm ask in either order, with every separator, and its rm reason is emitted with and without CLAUDE_BATCH. Checked by TS-1 to TS-8, TS-18 and TS-19.
- TM-2: an early stop after an rm deny emits the deny. Checked by TS-11. TS-22 checks the side without a deny.
- TM-3: the FR8 exclusion covers only the rm in the same statement iteration whose own deletion operand is a protected self-config path. Checked by TS-9, TS-13, TS-14 and TS-20 (no exclusion) and by TS-12, TS-15 and TS-16 (exclusion: ask, demoted to deny in batch).
- TM-4: no held ask is lost, and commands without a deny keep their decision and reason id. Checked by TS-10, TS-21, TS-22 and TS-27 (every pre-existing ask and allow case unchanged).
- TM-5: the continued scan stays within the hook timeout. Checked by TS-27 (runner timeout per case) and TS-11 (the scan budget still ends the scan).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-27) | 27 | 26 | 0 | 1 |
| Security verification (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
| Performance verification (NFR4) | 1 | 1 | 0 | 0 |
| Additional manual checks (reason readability, FR7 wording) | 2 | 0 | 0 | 2 |
