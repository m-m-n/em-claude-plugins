# Verification Document: loop-command-guard

## Overview
- **Feature**: loop-command-guard
- **SPEC.md**: `feature-docs/loop-command-guard/SPEC.md`
- **IMPLEMENTATION.md**: `feature-docs/loop-command-guard/IMPLEMENTATION.md`
- **THREAT-MODEL.md**: `feature-docs/loop-command-guard/THREAT-MODEL.md`

## Build Verification
- Command: none. workflow.yaml project.components.main.build_command is
  empty, and the Python sources run as they are.
- Expected: not applicable. Do not byte-compile the hook as a stand-in
  build step: that writes a cache directory under em-workflow/, which ships
  to users.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Focused run:
  `python3 -m unittest tests.test_loop_command_guard tests.test_hooks_registration tests.test_guardrail_hooks_migration tests.test_muse_guard_registration`
- Coverage target: the project has no coverage tool configured. Coverage is
  judged by the scenario table below: every command example in SPEC.md AC1
  to AC6 appears as a case row.

### Test Scenarios from SPEC.md
Scenario IDs map to SPEC.md as follows:
- TS-1 to TS-8 correspond one-to-one to SPEC.md's scenarios TS1 to TS8.
- TS-9 to TS-11 were added at plan time. SPEC.md AC10, AC11 and NFR2 had no
  dedicated scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Top-level positions (SPEC TS1; AC1, AC2): a while / until loop is placed first, after `;` `&` `&&` `\|\|` `\|` newline, inside `( )` and `{ ...; }`, after `!`, after then / elif / else, after do in a for loop, and in the background with `&`. The command goes to the hook as a Bash payload | Each case gives one deny object: hookEventName PreToolUse, permissionDecision deny, and a reason that begins with `[loop-command-guard]` and states that while / until loops are prohibited. Exit status is 0 and standard error is empty | Unit (subprocess) |
| TS-2 | Nested forms (SPEC TS2; AC3, AC4): the loop sits in a bash / sh / zsh `-c` string (including `-lc` and `-euo pipefail -c`), an eval argument, a command substitution or backtick (bare, and inside double quotes), or a heredoc body or herestring fed to bash / sh / zsh. Also covered: two-level nesting; shells behind timeout / nohup / env / nice / setsid / stdbuf / command / exec / time; and a loop in the enclosing text next to an undecidable nested text | Each case gives deny, exit status 0 and empty standard error | Unit (subprocess) |
| TS-3 | Non-detection (SPEC TS3; AC5): the seven SPEC AC5 commands; `"while"` and `\while`; for / select loops; reserved words used as arguments; single-quoted data inside a `-c` string; arithmetic expansion; and the A6 exclusions (find -exec sh -c, xargs sh -c, ssh remote command, a quoted script piped into bash, a heredoc piped into bash) | Standard output is empty, exit status is 0 and standard error is empty. No case yields allow or ask | Unit (subprocess) |
| TS-4 | Malformed and undecidable input (SPEC TS4; AC6): non-JSON input; a JSON value that is not an object; a tool_name other than Bash; tool_input missing or not an object; a command that is missing, empty or not a string; a top-level unterminated quote, heredoc, command substitution or backtick; a top-level undecidable command that also holds a loop; and nesting far beyond the maximum depth | Standard output is empty, exit status is 0 and standard error is empty | Unit (subprocess) |
| TS-5 | CLAUDE_BATCH variation (SPEC TS5; AC7): every TS-1 / TS-2 deny case runs once with CLAUDE_BATCH set and once with it removed from the child environment | Both runs give deny | Unit (subprocess) |
| TS-6 | Registration shape (SPEC TS6; AC8): read hooks.json and check the PreToolUse(Bash) group | Nine entries. loop-command-guard.py sits directly after interpreter-mismatch-guard.py and directly before destructive-guard.py, with the pinned command form, timeout 15 and a Japanese statusMessage. The other eight entries are verbatim and in their original relative order. destructive-guard.py is the last decision-capable guard. A forged reordering is caught. tests/test_muse_guard_registration.py passes unmodified | Integration |
| TS-7 | Static source inspection (SPEC TS7; AC9): parse the hook source into a syntax tree | Only standard-library imports, and none of the process-creation or networking modules. No eval / exec / compile / open calls and no process-spawning calls | Unit |
| TS-8 | Full suite (SPEC TS8; AC11): `python3 -m unittest discover -s tests` | All tests pass. This includes tests/test_plugin_version_parity.py (the two manifests agree) | Integration |
| TS-9 | Documentation (plan-added; SPEC AC10) | The em-workflow/README.md guardrail table has a PreToolUse(Bash) row for hooks/loop-command-guard.py. The execution-order sentence matches hooks.json's nine-entry order, with loop-command-guard between interpreter-mismatch-guard and destructive-guard. .claude/rules/hook-tests.md has a loop-command-guard section that names `python3 -m unittest tests.test_loop_command_guard` and the (期待する判定, ラベル, コマンド) / deny / silent case format | Unit (file content) |
| TS-10 | Change set and version (plan-added; SPEC AC11, FR1, FR14): compare the integration HEAD with its merge base on main | Under em-workflow/hooks/, only loop-command-guard.py (added) and hooks.json change. The em-workflow version in em-workflow/.claude-plugin/plugin.json has the same major and minor as the merge base and a strictly greater patch. The em-workflow entry of .claude-plugin/marketplace.json has the identical value. em-review's marketplace version is unchanged | Integration (verify-phase git comparison) |
| TS-11 | Bounded time and determinism (plan-added; NFR2): run a command with a heredoc body of about one megabyte (fed to a non-shell command, and fed to bash with a loop), and a command nested several hundred levels deep. Also run representative deny and silent commands twice | Each run finishes inside the test's named bound, which is at most one third of the 15-second registration timeout. Outcomes are silent / deny / silent respectively, exit status is 0 and standard error is empty. Repeated runs give byte-identical standard output | Unit (subprocess) |

## Code Quality Verification
- Format: not configured (workflow.yaml format_command is empty).
- Static analysis: not configured. TS-7 checks the hook's stdlib-only,
  side-effect-free properties.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Basic while / until / background loops are denied with the `[loop-command-guard]` reason, exit status 0 | TS-1 |
| AC2 | Loops at every FR2 command position are denied | TS-1 |
| AC3 | Loops in `-c` strings, eval, command substitutions / backticks, heredocs / herestrings fed to a shell, and double nesting are denied | TS-2 |
| AC4 | timeout / nohup / env-prefixed shells holding a loop are denied | TS-2 |
| AC5 | The listed non-loop commands are silent with exit status 0 | TS-3 |
| AC6 | Malformed and undecidable input is silent with exit status 0 | TS-4 |
| AC7 | Deny regardless of CLAUDE_BATCH | TS-5 |
| AC8 | Nine-entry registration, loop-command-guard.py directly before destructive-guard.py, registration tests updated | TS-6 |
| AC9 | Stdlib-only imports and empty standard error in every case | TS-7, TS-1 to TS-5 (every case asserts empty standard error) |
| AC10 | README row and execution-order sentence; hook-tests.md section | TS-9 |
| AC11 | Version parity, patch raised, em-review unchanged, full suite passes | TS-10, TS-8 |
| SC-NFR4 | `python3 -m unittest discover -s tests` passes in full | TS-8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-6, TS-10 (new hook exists, is registered, and no other hook script changed) |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-2 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-2 |
| FR6 | task0001 | TS-1, TS-5 |
| FR7 | task0001 | TS-3 |
| FR8 | task0001 | TS-4 |
| FR9 | task0001 | TS-6 |
| FR10 | task0001 | TS-6, TS-8 |
| FR11 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5 (the new test module and its case format) |
| FR12 | task0001 | TS-9 |
| FR13 | task0001 | TS-9 |
| FR14 | task0001 | TS-10, TS-8 |
| NFR1 | task0001 | TS-7 |
| NFR2 | task0001 | TS-7, TS-11 |
| NFR3 | task0001 | TS-6, TS-3 |
| NFR4 | task0001 | TS-8 |

## E2E Testing
None. The project has no E2E framework configured (workflow.yaml
e2e_test_command is empty).

## Manual Testing (E2E Not Possible)
None required to pass. A live-session check would need the plugin cache
refreshed to the new version and Claude Code restarted: a Bash call holding
a while loop is refused and an ordinary command still runs. The verify phase
does not perform that step.

## Performance / Security Verification (if applicable)
- NFR2: finishes within the 15-second registration timeout. Checked by
  TS-11: large and deeply nested inputs finish inside a bound of at most one
  third of the timeout.
- TM-1: nested execution contexts are re-read recursively, and an
  undecidable nested text never cancels a finding in the enclosing text.
  Checked by TS-2's nested-form cases, including the "loop in the enclosing
  text next to an undecidable nested text" case, which must give deny.
- TM-2: detection only at command positions, after quote, heredoc and
  comment handling. Checked by TS-3's silent cases (argument words, quoted
  data, non-shell heredoc bodies, comments, quoted / escaped reserved
  words).
- TM-3: pure text reading, with no process, no evaluation, no file and no
  network. Checked by TS-7's syntax-tree inspection of imports and call
  names.
- TM-4: output is only the deny object or nothing, and the registration sits
  directly before destructive-guard.py. Checked by TS-6's pinned nine-entry
  order and last-decision-capable-guard assertion, and by TS-3 / TS-4
  (every non-deny case has empty standard output, never allow or ask).
- TM-5: bounded depth, silent on every failure, bounded time. Checked by
  TS-4's far-beyond-maximum-depth case (silent, empty standard error, exit
  status 0) and by TS-11's timed large-input and deep-nesting runs.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-11) | 11 | 11 | 0 | 0 |
| Success criteria (AC1 to AC11, SC-NFR4) | 12 | 12 | 0 | 0 |
| Performance (NFR2) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
| Manual | 0 | 0 | 0 | 0 |
