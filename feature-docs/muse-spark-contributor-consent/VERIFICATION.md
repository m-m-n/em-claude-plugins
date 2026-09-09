# Verification Document: muse-spark-contributor-consent

## Overview

**Feature**: muse-spark-contributor-consent
**SPEC.md**: `feature-docs/muse-spark-contributor-consent/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/muse-spark-contributor-consent/IMPLEMENTATION.md`

This document defines the integrated verification of the whole feature. Per-task
completion is defined by each task plan's own Acceptance Criteria.

It is rewritten for the amended SPEC, which added the consent-write provenance
boundary (FR7 / AC-13, scenarios TS-29 and TS-30), narrowed FR13 / AC-12 to a skill
that presents the mutating command rather than running it, and restated the
prompt-injection claim and SC-8 in terms of the boundary those two enforcement
surfaces actually establish.

## Build Verification

- Command: none — `project.components.main.build_command` is empty (Python sources
  and Markdown/YAML documents; nothing is compiled).
- Expected: not applicable. The equivalent smoke check is that both guard copies
  run as scripts, which the test suite exercises through subprocesses.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures, no errors.
- Coverage target: no numeric coverage gate is configured in this repository.
  The substitute gate is scenario coverage: every scenario below is realized by at
  least one collected test, and every requirement below maps to at least one
  scenario.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Store path (overridden to a non-existent path under a temporary directory) absent; a contributor-tier invocation payload is fed to the guard with a temporary repository as the working directory, for both plugin copies | Exit 0; stdout parses as JSON with the PreToolUse event name and decision `deny`; the reason states the missing consent; the additional context steers to a non-contributor entry; the store path still does not exist | Integration |
| TS-2 | Consent recorded through the CLI for that same temporary repository — the recording subprocess is given a pseudo-terminal for standard input, as the provenance boundary requires — then the TS-1 payload replayed | Exit 0, empty stdout; the store holds exactly one project key whose value carries only the timestamp field; consent recorded through one plugin's copy is honored by the other's | Integration |
| TS-3 | Plain `muse-spark` invocations in every spelling, empty store | Exit 0, empty stdout for each | Unit |
| TS-4 | Contributor-tier invocation from a repository whose key is absent, while the store holds an unrelated key | Deny — the plain-tier name must not match the contributor invocation as a substring | Unit |
| TS-5 | Every contributor-tier invocation spelling the harness emits, empty store, both copies: short flag with a separate value, long flag joined by an equals sign, each bare / single-quoted / double-quoted, **and the harness's own shape — an invocation followed by a quoted prompt argument containing a statement separator, and one containing a newline** | Deny for each; a separator or newline inside a quoted argument never splits the statement, so no invocation is lost before classification | Unit |
| TS-6 | Mentions only, both copies: an echoed sentence, a text-search pattern argument, a here-document body, a commit-message argument, **and a non-shell command whose single-quoted argument contains separator-delimited invocation-looking text** | Exit 0, empty stdout for each; a quoted separator never carves a standalone invocation out of a mention | Unit |
| TS-7 | Unrelated commands, a payload whose tool is not the Bash tool, an empty command, unparseable standard input, a command string the tokenizer refuses (unterminated quote) | Exit 0, empty stdout for each; no exception escapes | Unit |
| TS-8 | Store override pointing in turn at a non-JSON file, a JSON array, a mapping whose projects field is not a mapping, and a directory | Contributor invocations deny; all other commands undecided; the store is neither rewritten nor repaired in any case | Unit |
| TS-9 | Non-repository temporary directory reached through a symlink: record with the symlinked path (pseudo-terminal standard input), then invoke from the real path and from the symlinked path | The recorded key equals the fully resolved path; both invocations resolve to that one key (undecided after recording, deny before) | Integration |
| TS-10 | Temporary repository plus a linked second worktree: record from the main worktree, invoke from the linked one, then remove consent and invoke from both — both mutating calls run with a pseudo-terminal standard input | Both worktrees share one entry (undecided after recording, deny after removal); the store never holds two keys for one repository | Integration |
| TS-11 | CLI round trip against a temporary store and repository: `--list`, `--record`, `--list`, `--record`, `--remove`, `--list` — the mutating calls with a pseudo-terminal standard input, the read-only calls through an ordinary pipe | `--record` is idempotent and refreshes the timestamp; `--list` prints the key alone when consented and nothing when not; `--remove` deletes the key entirely; the written file carries no field beyond the version, the projects mapping, the key and its timestamp | Unit |
| TS-12 | Both plugins' committed hooks files: extract the script names under the PreToolUse / Bash group and check each entry against the existing well-formedness rules | The em-workflow extraction equals the updated ordered-guard constant, the new entry precedes the destructive guard and the destructive guard is still last; the em-review file registers the guard under the Bash matcher; both entries use the verbatim command form with timeout 15; both referenced scripts exist and are executable; no script is registered twice under one event in either file | Structural |
| TS-13 | Both plugins' committed review registries: parse each perspective's primary chain and each entry's model | Every chain matches its expected literal list; no model value is the contributor tier; every perspective has a non-empty chain; the em-workflow registry still contains no `cross_validation` literal | Structural |
| TS-14 | Both plugins' review registry and review protocol documents: locate the consent section and inspect it | Each pair states the consent precondition and the two-check read-mapping rule; each protocol document records the exception to the model-substitution prohibition and the before-dispatch timing; exactly one per-dispatch "do not use" bullet and exactly three out-of-scope bullets appear under two distinct headings; the visibility / license condition is a present-state check at dispatch time and contains no comparison against a value recorded at consent time | Structural |
| TS-15 | Both plugins' develop-path and review-path documents: count occurrences of the interactive-question tool name and compare against the pinned per-file baseline | No file's count exceeds its pinned value and no unpinned document contains an occurrence; the two `contributor-consent` skill documents are the only exclusions and are referenced by no develop-phase document | Structural |
| TS-16 | Both plugin manifests and the marketplace file | Each plugin's manifest version equals its marketplace entry, parses as a semantic version, and exceeds the base value (em-workflow above 0.1.69, em-review above 0.5.7) | Structural |
| TS-17 | Repository tree and the discovery run | `tests/test_muse_guard.py` is collected and the suite passes; neither plugin's `hooks/tests/` gained a muse-guard case file or runner; the guard tests import no third-party package | Structural |
| TS-18 | Both plugins' `contributor-consent` skill documents: frontmatter and body | Both exist with valid frontmatter; each describes the availability probe and its not-installed exit, the read-only state check, the three presented facts (remote visibility, license, sole contributor) as one labeled group, exactly one interactive question round with two state-dependent options, and the presentation of the recording and removal commands as lines the user runs in their own terminal; neither contains a step in which the skill itself runs a mutating command; the accompanying line states the interactive-terminal requirement without claiming unbypassability; neither presents unpushed-commit state; neither is referenced by a develop-phase document; no corresponding `commands/` file was added | Structural |
| TS-19 | Byte comparison of the two guard copies | The files differ in exactly one line, the plugin-slug constant, and are otherwise identical | Unit |
| TS-20 | Static inspection of both guard copies plus a behavioral probe | No network-capable module is imported and no LLM is invoked; the only subprocess launched is the key-derivation git call; a non-invocation command returns before that subprocess and before the store read | Unit |
| TS-21 | Static inspection of both guard copies plus the aggregate of every behavioral case | The `ask` decision literal appears in neither copy, and no case in the suite produces a decision other than `deny` or no decision at all | Unit |
| TS-22 | A representative sample of invocation and non-invocation payloads, including the deepest nested and wrapped shapes, timed | Each run completes well inside the registered 15-second timeout, and the non-invocation short circuit is measurably cheaper than the invocation path | Unit |
| TS-23 | Isolation audit of the guard test module | Every case sets the store-path override to a path under a temporary directory; no case resolves the real user store path; a full run leaves real user state untouched | Unit |
| TS-24 | Import audit of every test module this feature adds and of both guard copies | Standard library imports only, including the terminal-allocation facility the provenance cases need | Unit |
| TS-25 | The same payload and store presented to both plugin copies in sequence, in both the consented and unconsented states | Both copies reach the same decision in both states, so a duplicate firing is a no-op | Integration |
| TS-26 | Every remaining model-selection shape against an empty store, for both copies: the long flag with a separate value, the short and the long flag joined by an equals sign, the short flag with the value attached — each with the value bare, single-quoted and double-quoted, **including spellings whose value or surrounding argument carries a quote delimiter** — paired with the matching non-invocation shapes (a commit-message argument, a search pattern argument carrying the colliding short flag, quoted mentions, the plain tier in each of the same shapes) | Deny for every invocation shape and no decision for every paired non-invocation shape, with quoting resolved before the statement split so no invocation is lost and no mention is carved out; the tier names never match each other by prefix, suffix or substring in either direction | Unit |
| TS-27 | Nested and wrapped invocations against an empty store, for both copies: carried as a shell's command-string argument where the flag is **bundled with other short options**; behind the argument-list-expanding wrapper with a separate-value option before the command word; behind the scheduling-priority wrapper with a separate-value option before the command word; inside a parenthesized command substitution; inside a backtick command substitution — each paired with the same construct carrying only a mention, plus one case nested past the resolution bound | Deny for each nested or wrapped invocation; no decision for each paired mention and for the over-bounded nesting; every case completes well inside the registered timeout and launches no subprocess beyond the key-derivation call | Unit |
| TS-28 | Here-document handling against an empty store, for both copies: a payload whose first line carries a here-document header inside a quoted string, whose second line is a real invocation and whose third line is the header word; a genuine here-document whose body only names the tier; a real invocation placed after a genuine here-document's terminator | Deny for the quoted-header payload and for the post-terminator invocation; no decision for the genuine here-document mention; no path classifies both the stripped and the unstripped text | Unit |
| TS-29 | Consent-write refusal on a non-interactive standard input, for both copies: with the store override pointing at a non-existent path under a temporary directory and a temporary repository as the project directory, `--record` and `--remove` are run as subprocesses whose standard input is an ordinary pipe; repeated with an existing store holding an unrelated key | Each exits non-zero; stderr states that an interactive terminal is required; the absent store path still does not exist and no parent directory was created; the existing store is byte-identical; the refused run launches no git subprocess | Unit |
| TS-30 | The read-only command is outside the provenance boundary and the interactive path still writes, for both copies: `--list` through an ordinary pipe, then `--record` through a pseudo-terminal, then `--list` through an ordinary pipe again | The first list exits 0, prints nothing and does not modify the store; the record exits 0 and writes the key; the second list exits 0 and prints the project key | Unit |

## Code Quality Verification

- Format: none configured — `project.components.main.format_command` is empty.
  The substitute check is convention conformance reviewed by the review phase:
  Japanese messages in one register, ASCII identifiers, single-line hook strings,
  no decoration.
- Static analysis: none configured. The equivalent mechanical checks are TS-19
  through TS-24, which are static inspections expressed as tests.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | Every functional requirement FR1–FR13 is implemented and tested | The requirement coverage table below has a non-empty task list and a non-empty test list for every row |
| SC-2 | Every scenario TS-1 through TS-30 passes | `python3 -m unittest discover -s tests` exits 0 with every scenario realized by a collected test |
| SC-3 | Every acceptance criterion AC-1 through AC-13 of SPEC.md is met | Each maps through the SPEC's AC-to-requirement table onto rows of the coverage table below; AC-13 maps to FR7's row |
| SC-4 | Non-functional requirements NFR1–NFR9 hold | TS-15, TS-19 through TS-25 plus the deny/no-decision scenarios |
| SC-5 | The consent store is presence-only | TS-11, TS-2 |
| SC-6 | Chains are byte-identical to the base revision | TS-13 |
| SC-7 | Both plugins' versions agree with their marketplace entries and exceed the base | TS-16 |
| SC-8 | Review is complete **and** the FR7 consent-write provenance boundary is verified by automated tests | The review phase has finished its planned rounds, and TS-29 plus TS-30 pass: a non-interactive `--record` / `--remove` changes nothing and exits non-zero, while `--list` is unaffected. Per the amended SPEC, driving the residual critical/high finding count to zero is **not** a requirement of this criterion |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0006, task0007, task0008 | TS-1, TS-12, TS-19 |
| FR2 | task0001 | TS-2, TS-11 |
| FR3 | task0001 | TS-9, TS-10 |
| FR4 | task0001, task0006, task0007 | TS-1, TS-4, TS-5, TS-26, TS-27, TS-28 |
| FR5 | task0001, task0006, task0007 | TS-3, TS-4, TS-5, TS-6, TS-7, TS-26, TS-27, TS-28 |
| FR6 | task0001 | TS-1, TS-8 |
| FR7 | task0001, task0008 | TS-2, TS-11, TS-29, TS-30 |
| FR8 | task0001 | TS-12 |
| FR9 | task0003 | TS-14 |
| FR10 | task0001, task0006, task0007, task0008 | TS-17 |
| FR11 | task0003 | TS-13 |
| FR12 | task0004 | TS-16 |
| FR13 | task0002, task0009 | TS-18, TS-30 |
| NFR1 | task0001 | TS-20 |
| NFR2 | task0001, task0006, task0007 | TS-7, TS-21 |
| NFR3 | task0002, task0003, task0005, task0009 | TS-15 |
| NFR4 | task0001, task0006, task0007 | TS-22 |
| NFR5 | task0001, task0008 | TS-23 |
| NFR6 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS-17, TS-24 |
| NFR7 | task0001 | TS-11, TS-2 |
| NFR8 | task0001 | TS-12 |
| NFR9 | task0001 | TS-25 |

## E2E Testing

No E2E framework is configured for this repository
(`project.components.main.e2e_test_command` is empty), and none is introduced.
The behavior an E2E run would have covered — a develop run in a project that never
consented — is covered by TS-15 as an automated static equivalent, by the SPEC's
own decision (a9).

## Manual Testing (E2E Not Possible)

- [ ] モックとの目視照合: the design step created **no** mockup files and no token
      sheet (DESIGN.md decision D1 — this feature has no rendered graphical UI), so
      the file list to compare against is empty. In its place, compare the shipped
      user-facing text against the design-fixed content recorded in the task plans:
      the guard's deny reason and additional context (task0001), the CLI's output
      lines and the provenance refusal line (task0001, task0008), and the skill's
      not-installed line, fact labels and value vocabulary, question wordings, option
      labels, presented command lines and no-write line (task0002, task0009). Wording
      must match except for the register adjustment allowed by IMPLEMENTATION.md O1
      and the re-wording allowed by O4.
- [ ] Run the `contributor-consent` skill once in an interactive session in a real
      repository and confirm: the three facts render with their labels, exactly one
      question appears, choosing the consenting option presents the recording command
      instead of running it, and re-running the skill after the user has run that
      command offers the maintain / revoke wording.
- [ ] Copy the presented recording command and run it in a real terminal; confirm it
      records. Then run the same command through the agent's Bash tool and confirm it
      is refused with the interactive-terminal message and changes nothing.
- [ ] Dismiss the question without answering and confirm nothing is written, no command
      is presented, and the no-change line is printed.
- [ ] With consent recorded, confirm a contributor-tier review dispatch is not
      denied; revoke consent and confirm the deny message renders readably in the
      permission UI as a single line.

## Performance / Security Verification

- Latency (NFR4): every hook invocation completes well inside the registered
  15-second timeout; a non-invocation command returns before the git subprocess and
  before the store read; the rebuilt recognition path adds no subprocess and no file
  access — TS-22.
- No network (NFR1): neither guard copy imports a network-capable module, invokes
  an LLM, or fetches repository metadata — TS-20.
- Never `ask` (NFR2): no code path emits the `ask` decision, so an unattended run is
  never stalled by a downgraded prompt; anything the tokenizer refuses ends in no
  decision rather than an exception — TS-7, TS-21.
- Authorization surface: the only authorization signal is the presence of a project
  key in the store; the guard emits `deny` or nothing and never `allow`, so it does
  not override any later guard — TS-1, TS-3, TS-21.
- Recognition completeness: quoting is resolved before the command string is split, so
  no quoted separator either hides a real invocation or manufactures one; no wrapper
  option taking a separate value, no bundled-short-option shell nesting and no command
  substitution lets an unconsented contributor-tier invocation reach the harness
  undecided; and no widening of recognition converts a mention into a deny — TS-5,
  TS-26, TS-27, TS-28 against the floor of TS-3, TS-6, TS-7.
- Consent-write provenance (FR7 / AC-13): the two mutating CLI commands change nothing
  and exit non-zero unless standard input is an interactive terminal, and the refusal
  precedes key derivation and every store access, so a refused run creates, repairs and
  modifies nothing; `--list` stays outside the boundary — TS-29, TS-30.
- Input validation: unparseable payloads, non-Bash tools, empty commands, tokenizer-
  hostile command strings and wrong-shaped stores all end in a no-decision or a deny,
  never in an exception or a store write — TS-7, TS-8.
- Prompt-injection resistance: the gate is decided by code, not by prose, and has two
  enforcement surfaces — the hook's deny and the write CLI's interactive-terminal
  requirement. What they establish is that an agent's ordinary Bash call path can
  neither launch the contributor tier nor record consent; unbypassability is **not**
  claimed (SPEC a12 — the terminal test is a provenance proxy). Additionally, no
  user-facing string produced by the guard echoes any part of the inspected command,
  the working directory, the project key or the store — TS-19 (constants only,
  verified by comparing the two copies against the fixed text), TS-29.
- Data protection (NFR7): nothing but the timestamp is written under a project key;
  visibility, license, contributor lists, diff content and paths never reach the
  store — TS-11.
- Unattended-run safety (NFR3): no develop-path or review-path document gains an
  interactive question, and the skill's own question stays outside that set — TS-15.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit scenarios | 18 | 18 | 0 | 0 |
| Integration scenarios | 5 | 5 | 0 | 0 |
| Structural scenarios | 7 | 7 | 0 | 0 |
| Manual checks | 5 | 0 | 0 | 5 |
| **Total** | **35** | **30** | **0** | **5** |
