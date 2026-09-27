# Implementation Plan: loop-command-guard

## Overview
This feature adds one self-contained PreToolUse(Bash) hook,
em-workflow/hooks/loop-command-guard.py. The hook denies any Bash command
that has a while / until loop at a command position, including inside nested
shell texts, and says nothing about any other command. The feature also
registers the hook directly before destructive-guard.py and updates the
registration tests, README, test-procedure rule and em-workflow version to
match. The whole feature is one implementation task (D1).

## Technology Stack
- **Language**: Python 3, standard library only (NFR1). The hook and its
  tests use nothing else.
- **Test framework**: standard-library unittest, run as
  `python3 -m unittest discover -s tests`. This is the test command in
  workflow.yaml project.components.main.
- **New dependencies**: none. There is no new dependency to check against a
  license. project.license is `none`.

## Layer Structure
| Layer | Location | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Hook | em-workflow/hooks/loop-command-guard.py | Read the PreToolUse payload, read the command statically, emit deny or nothing | Python standard library only |
| Registration | em-workflow/hooks/hooks.json | Place the hook in the PreToolUse(Bash) execution order | The hook file exists |
| Tests | tests/ | Drive the hook as a subprocess; pin the registration shape | Hook file and hooks.json (read-only) |
| Documentation and metadata | em-workflow/README.md, .claude/rules/hook-tests.md, em-workflow/.claude-plugin/plugin.json, .claude-plugin/marketplace.json | Describe the guard; carry the version | Nothing at runtime |

Nothing in the plugin imports the new hook, and the hook imports no other
hook (D3).

## Shared Components
Any task that later touches this feature must keep these two contracts. That
includes rework tasks appended by the review or verify phase.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| loop-command-guard.py I/O contract | The hook's behaviour as seen by Claude Code and by the other Bash guards | Pre: one PreToolUse payload on standard input. Post (loop found at a command position, directly or in a nested text that FR3 / FR5 name): standard output holds exactly one deny object. Its hookEventName is PreToolUse, its permissionDecision is deny, and its reason begins with `[loop-command-guard]`. Post (anything else, including every input that cannot be settled): standard output is empty. In every case the exit status is 0 and standard error is empty. The hook never emits allow or ask. CLAUDE_BATCH does not change the outcome | task0001 |
| PreToolUse(Bash) registration position | The hook's place in hooks.json | The Bash group holds nine entries. loop-command-guard.py sits directly after interpreter-mismatch-guard.py and directly before destructive-guard.py. The other eight entries keep their content and relative order. destructive-guard.py stays the last entry able to return a permission decision | task0001 |

## Conventions
- **Version bump ownership**: any task, including a later rework task, that
  changes a file under em-workflow/ raises the em-workflow patch version in
  the same commit. The raise goes in both
  em-workflow/.claude-plugin/plugin.json and the em-workflow entry of
  .claude-plugin/marketplace.json, with identical values, counted from that
  commit's own HEAD (A11, .claude/rules/core-plugin-version-bump.md). A task
  that changes only files outside em-workflow/ leaves both manifests alone.
  em-review's version never moves in this feature (A9).
- **Commit discipline**: plugin-version-guard checks each commit separately.
  So within one task, all changes under em-workflow/ go into a single commit,
  and the version is bumped once. Commits that touch only tests/, .claude/ or
  test-docs/ need no bump.
- **Hook conventions**: the hook follows the existing em-workflow Python
  guards. It reads standard input once, writes a single JSON object only on
  deny, always exits 0, stays silent (fail-open) on anything it cannot
  settle, and writes nothing to standard error.

## Cross-task Design Decisions

### D1: One implementation task for the whole feature
- **Decision**: task0001 owns every file in the feature's change set.
- **Rationale**: the user's plugin-version-guard hook (A11) refuses any
  commit that changes em-workflow/ without a version bump. Parallel tasks
  touching em-workflow/ would each bump the version and conflict at merge.
  The registration tests in tests/ must change in the same worktree as
  hooks.json; otherwise the suite fails in that worktree (NFR4). The new
  hook's test module is that hook's TDD contract. The one file that could be
  split off, .claude/rules/hook-tests.md, is a short section that restates
  the test module's name and case format. Moving it to its own task would
  add a cross-task contract and gain nothing.
- **Affected tasks**: task0001.

### D2: Version bump position and value
- **Decision**: raise the em-workflow patch position (A8, FR14). The concrete
  value comes from HEAD at commit time, per
  .claude/rules/core-plugin-version-bump.md. Verification accepts any patch
  strictly above the value at the merge base with main, with major and minor
  unchanged. It does not require exactly one step, because later commits
  that touch em-workflow/ (review fixes, for example) each bump again under
  the same rule.
- **Affected tasks**: task0001, plus any rework task that touches em-workflow/.

### D3: The static reader is written fresh inside the new hook
- **Decision**: loop-command-guard.py carries its own shell-text reader. It
  imports nothing from destructive-guard.py or
  interpreter-mismatch-guard.py, and those files are not changed.
- **Rationale**: FR1 forbids adding decision logic to existing hook scripts.
  NFR1 allows only standard-library imports, and a sibling hook module is not
  part of the standard library.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Legitimate commands are denied (false positives), including the finite idiom of piping into a while-read loop, which FR2 denies on purpose | Medium | Medium | Detect only at command positions, after quote, heredoc and comment handling (THREAT-MODEL.md TM-2). A silent case table covers every FR4 / A7 example. The README row states what the guard denies |
| Loops that SPEC.md leaves out pass through: script files, piped or ssh shells, non-bash shells, undecidable top-level commands, and command substitutions inside a heredoc body fed to a non-shell command | Medium | Low | Accepted by SPEC.md (A3, A6, FR8, FR4). Listed under Open Questions and in THREAT-MODEL.md's Rationale |
| The version is bumped more than once, because several commits during implementation or review touch em-workflow/ | High | Low | Commit discipline (Conventions). Verification checks "strictly greater, same major/minor" rather than an exact value (D2) |
| main bumps the em-workflow version while this feature is open, so plugin.json / marketplace.json conflict at completion | Medium | Low | Resolved at completion: take main's value and raise the patch again from that HEAD (core-plugin-version-bump rule) |
| A pathological command makes the hook slow or makes it crash | Low | Low | Fixed maximum nesting depth, a catch-all silent exit, and a bounded-time test (THREAT-MODEL.md TM-5) |

## Open Questions
- [ ] FR2 does not list some command positions: after the `time` reserved
      word at top level, inside process substitution, in a case arm, and
      after `coproc`. These are not required, and no test pins their outcome.
- [ ] With an unquoted delimiter, command substitutions inside a heredoc body
      fed to a non-shell command run in the outer shell. FR4 excludes the
      whole body from detection, so the plan follows FR4 and does not read
      them.
- [ ] The README's opening guard count ("4 本") and the missing rows for
      muse_guard.py / heredoc-stdin-guard.py are outside FR12 and stay
      unchanged. Only the loop-command-guard row and the execution-order
      sentence change.
