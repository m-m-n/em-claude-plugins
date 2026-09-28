# Implementation Plan: destructive-guard-heredoc-reset-hard

## Overview
Change destructive-guard.py so that it decides, heredoc by heredoc, whether
a heredoc body is rescanned as shell statements. The decision rests on that
heredoc's own destination instead of on a sink word appearing anywhere in
the chunk. The guard should also strip every heredoc body when one line
opens several heredocs. The whole feature is delivered as a single task
(see Cross-task Design Decisions).

## Technology Stack
- **Language**: Python 3, standard library only (NFR2).
- **New dependencies**: none, so there is no license to record.
  `project.license` is `none`.
- **Test harness**: the existing expectation suite. The runner is
  `em-workflow/hooks/tests/run-destructive-guard.py` and stays unchanged
  (NFR4). Cases live in
  `em-workflow/hooks/tests/destructive-guard-cases.json`.

## Layer Structure
destructive-guard.py is a single-file PreToolUse(Bash) hook. The feature
touches only the front of its statement pipeline:

1. `statements()` pops a chunk from its rescan queue.
2. **Heredoc extraction** (changed): bodies are removed.
3. **Destination and rescan decision** (changed): decides which removed
   bodies go back on the queue.
4. Command-substitution collection, lexing (`lex_segments()`) and shaping
   (unchanged).
5. The per-statement checks in `main()` (unchanged).

Stages 4 and 5 keep their current contracts. The stage-3 decision may read
lexing and shaping results, such as the command word found through the
existing assignment / wrapper / grouping skip, but it must not change them.

## Shared Components
The feature is one task, so there are no cross-task components.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | - | - | - |

## Conventions
- **Version bump**: every commit that touches `em-workflow/` includes the
  em-workflow version bump at the patch position. `plugin.json` and
  `marketplace.json` carry the same value
  (`.claude/rules/core-plugin-version-bump.md`). The concrete value comes
  from HEAD at commit time, and plans never state it.
- **Expectation cases**: cases are added before the guard is changed
  (`.claude/rules/hook-tests.md`). Existing deny / ask cases are never
  removed or given a different expected verdict.

## Cross-task Design Decisions

### D1: Single-task decomposition
- **Decision**: one task (task0001) covers the whole change:
  - the heredoc extraction in destructive-guard.py
  - the destination decision in destructive-guard.py
  - the new expectation cases
  - the version bump
- **Rationale**:
  - All behavioural change sits in one function pair of one file.
  - The new allow cases cannot pass without the fix, so a cases-only task
    would fail its own suite.
  - The plugin-version guard rejects any commit under `em-workflow/`
    without a version bump. Parallel tasks would each have to bump, which
    would overshoot FR8's single patch step.
  - The task's 8 acceptance criteria are slightly above the usual split
    threshold. This is accepted because the reasons above block a split.
- **Affected tasks**: task0001.

### D2: Interpretation of FR5, resolved in batch through Codex consultation (decision B and its follow-up)

**Decision.** A heredoc that FR1 (i)-(iii) does not make sink-bound has an
undeterminable destination when any of the following holds:
- Its host statement has one of these command words, where the command
  word is taken after the existing assignment / `WRAPPERS` / grouping skip:
  - a word that is neither a shell sink nor a known data command. This
    includes execution-prefix commands outside `WRAPPERS`, such as
    `timeout`, `exec`, `stdbuf`, `setsid` and `xargs`, and unknown commands;
  - a word that cannot be known statically;
  - no word at all (the operator is attached to a compound command's closer).
- A statement enclosing the command substitution that holds the heredoc has
  a command word, taken after the same skip, that is neither a shell sink
  nor a known data command. This covers `timeout 10 bash -c "$(cat <<'EOF'
  ... EOF)"`.
  - An enclosing statement made only of variable assignments is exempt,
    because it only stores the output.
- The host statement or an enclosing statement contains a process
  substitution, as in `tee >(bash)` or `cat > >(bash)`. The planner added
  this rule under the same premise.

How undeterminable heredocs are handled:
- An undeterminable heredoc falls back to the current conservative match,
  which is a sink word anywhere in the heredoc-stripped chunk.
- The fallback applies to that heredoc only. A data heredoc in the same
  chunk is never rescanned because of a neighbour, so `cat > file <<EOF ...`
  followed by `run_codex_exec.sh readonly "$(cat file)"` stays allowed.

Other parts of the decision:
- FR1 (iii) also applies (ii) to the enclosing statement.
  `echo "$(cat <<'EOF' ... EOF)" | bash` is therefore sink-bound, and the
  same form without `| bash` is data.
- The destination is decided before the substitution body is queued on its
  own, while the association with the enclosing statement still exists.
- `WRAPPERS` is not widened.
- The closed list of known data commands, which includes `echo` and
  `printf`, is pinned in the task plan.

**Rationale.**
- Decision B's premise is that nothing becomes less detected than today,
  and FR5 forbids leaning toward missed detection. Treating any of these
  shapes as data would deliberately allow shapes the current guard denies.
- Positively resolving what `timeout` and similar prefixes run would need
  per-command argument parsing, which is beyond scope.
- The orchestrator confirmed through Codex that no existing case covers
  these shapes, so there is no FR7 conflict.

**Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The operator-to-statement mapping goes wrong when the operator sits inside a quoted word or a command substitution | Medium | High | Deny-side cases pin the substitution and pipeline shapes (TS-6, TS-9, TS-13, TS-23, TS-26). An undeterminable destination falls back conservatively (D2, TM-3) |
| The fallback spills onto a data heredoc in the same chunk and brings back the original false positive | Medium | High (stalls unattended runs) | The per-heredoc association is kept, and the TS-25 allow control pins it |
| The closed data-command list is too narrow, so a heredoc sent to an unlisted but harmless command is still denied when the chunk mentions a sink word | Medium | Low (a remaining false positive, no detection loss) | The list covers the commands commonly used with heredocs: `cat`, `tee`, `git`, `gh`, `echo`, `printf` and the text filters. Extending the list is a reviewed change |
| A listed data command runs a program named in one of its own options, for example an inline `git -c alias.x='!bash' x <<'EOF'`, and the heredoc is judged data | Low | High | Command-word-level judgment is decision B's scope, and option parsing is out of it. `sort` and `rg` were left off the list because they have such options. Recorded in THREAT-MODEL.md |
| Rewriting the heredoc stripping shifts the verdicts of existing cases | Low | High | Single-operator lines strip exactly as today, and the full suite must pass with no case removed (TM-4) |
| Heredoc processing becomes super-linear on adversarial input | Low | Medium | An ad-hoc stress measurement against the 10-second hook timeout (TM-5, TS-20) |
| A commit under `em-workflow/` is rejected by the plugin-version guard | Medium | Low | Land the task's `em-workflow/` changes together with the version bump in one commit |

## Open Questions
None. The earlier questions about execution-prefix commands and the
enclosing statement's downstream pipeline were resolved by D2.
