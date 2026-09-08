# Feature: destructive-guard-var-resolution

## Overview

em-workflow's destructive-guard PreToolUse hook currently judges a command that assigns a literal path to a shell variable and then deletes through that variable as unresolvable (rule `rm-unresolvable`, verdict `ask`), even when the literal value is plainly inside SAFE_DELETE. This feature makes the hook statically resolve plain `VAR=value` assignments and substitute the resolved literal into target tokens before every target-path judgment runs, so such a command is judged exactly as though the literal path had been written. Resolution never weakens detection: a resolved value that lands outside SAFE_DELETE, on root/home, on SELF_CONFIG or on TRANSCRIPT produces the same verdict the literal spelling would.

Requirements document: `feature-docs/destructive-guard-var-resolution/REQUIREMENTS.md`.

## Objectives

- Remove a false-positive class in em-workflow's destructive-guard PreToolUse hook: a command that assigns a literal path to a shell variable and then deletes through that variable is currently judged unresolvable (rule `rm-unresolvable`, `ask`), even when the literal value is plainly inside SAFE_DELETE.
- Keep unattended runs moving. Under claude-batch an `ask` is demoted to `deny`, so each such false positive halts a batch run that nobody can unblock.
- Do not weaken detection while doing so: resolving a variable must make the guard see MORE real targets, never fewer.

## User Stories

### US1: A resolvable delete through a variable is not falsely blocked
As an agent running under the destructive-guard hook, I want a plain literal assignment followed by a delete through that variable to be judged on the literal path, so that a command whose target is plainly inside SAFE_DELETE is allowed instead of being stopped as unresolvable.

**Acceptance Criteria:**
- [ ] The reported false-positive command — a plain literal assignment followed, at the same nesting level, by a recursive delete through that variable to a SAFE_DELETE path — is allowed. (AC-1)
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes, with all pre-existing deny/ask cases still present and still passing. (AC-6)

### US2: Resolution never hides a real target
As the owner of the guard, I want every resolved value to flow into every target-path check, so that resolution increases the set of real targets the guard sees rather than shrinking it.

**Acceptance Criteria:**
- [ ] The same shape aimed at a path outside SAFE_DELETE is denied with rule `rm-recursive` and a reason carrying the `deletion_alternative` command for the resolved path. (AC-2)
- [ ] A resolved value that reaches a root/home target is denied with rule `rm-root`. (AC-3)
- [ ] A resolved value flowing into a write target that matches SELF_CONFIG asks (`self-modification`); one matching TRANSCRIPT denies (`transcript-write`). (AC-4)
- [ ] Every unresolvable form of FR5, FR6 and FR7 keeps its pre-change verdict; the reassignment case's reason text contains the split-the-variables hint. (AC-5)

## Technical Requirements

### Functional Requirements

- **FR1 - Collect plain assignments from the command string:** The hook collects, from the command string it is judging, every standalone assignment statement of the plain form `VAR=value` whose right-hand side is a single literal token, and builds a name-to-value resolution map from them.
- **FR2 - Substitute resolved values into target tokens:** Before a target-path judgment runs, each target token's `$VAR` and `${VAR}` references are replaced with the mapped literal value. A token whose value is fully resolved this way is judged as though the literal path had been written in the command. A token that still contains any dynamic construct after substitution — a glob (`*`, `?`, `[`), a command substitution (`$(`, backtick), or an unmapped variable reference — is not resolved and keeps today's behaviour.
- **FR3 - Apply resolved values to every target-path check:** Resolved values feed every judgment that inspects a target path, not only `check_rm`. This covers `check_rm`'s rm-root and SAFE_DELETE / rm-recursive paths, and the `write_targets`-derived candidates that `check_self_modification` tests against SELF_CONFIG (self-modification) and TRANSCRIPT (transcript-write).
- **FR4 - Verdict for a resolved path outside SAFE_DELETE:** When a resolved literal path falls outside SAFE_DELETE under a recursive delete, the verdict is the same deny the literal spelling would produce today — rule `rm-recursive` — and its reason includes the `deletion_alternative(target)` replacement command built from the resolved path.
- **FR5 - Assignment forms in scope:** Only the plain, single-stage, literal `VAR=value` form is resolved. Out of scope and left unresolvable: chained references whose value is built from an already-resolved variable; `export VAR=value`; and a command-prefix assignment (`VAR=/tmp/x rm -rf "$VAR"`), which in shell semantics does not affect the same command's own word expansion and therefore must never be resolved.
- **FR6 - Reassignment excludes the variable, with a rewrite hint:** A variable assigned two or more times anywhere in the same command string is excluded from the resolution map entirely; references to it stay unresolvable and keep today's `ask` (rule `rm-unresolvable`). That verdict's reason text states that assigning the two values to separate variables makes the command resolvable, so the calling agent can rewrite and retry.
- **FR7 - Same-nesting-level scope only:** An assignment resolves a reference only when the two sit at the same nesting level. A reference is left unresolvable when the assignment and the use are separated by a subshell, a `bash -c` (or other SHELL_WORDS `-c`) payload, a command-substitution body, a pipe element, or a here-document body.
- **FR8 - Test cases per the project rule:** Cases covering the new behaviour are added to `em-workflow/hooks/tests/destructive-guard-cases.json` in the `[expected_verdict, label, command]` three-element form, per `.claude/rules/hook-tests.md`. Every existing deny/ask case is retained unchanged, so the run demonstrates that suppressing this false positive did not reduce detection.
- **FR9 - Plugin version bump:** The em-workflow plugin version is raised 0.1.56 -> 0.1.57 in both `em-workflow/.claude-plugin/plugin.json` and the matching entry of `.claude-plugin/marketplace.json`, per `.claude/rules/core-plugin-version-bump.md`.

### Non-Functional Requirements

- **NFR1 - Static-only resolution:** Resolution is purely static: no filesystem access, no stat, no realpath, no subprocess, no shell invocation. It matches `normalize_candidate()`'s existing discipline of lexical-only transformation.
- **NFR2 - Fail closed:** Any case the resolver cannot settle statically keeps the pre-change verdict; the change never converts an existing deny or ask into allow other than through a fully resolved literal value.
- **NFR3 - Determinism:** Determinism preserved: the same command string always yields the same verdict, as stated in the hook's module docstring.
- **NFR4 - Bounded cost:** Resolution is a linear pass over statements that are already lexed, with no unbounded expansion loop, consistent with the `MAX_SHELL_PAYLOAD_EXPANSIONS` discipline already in the file.
- **NFR5 - Single-file, stdlib-only:** The hook stays a single-file Python 3 script using only the standard library; no new dependency is introduced.
- **NFR6 - Existing behaviour untouched:** Existing behaviour outside variable resolution is untouched: the SAFE_DELETE, SELF_CONFIG, TRANSCRIPT, and DYNAMIC pattern definitions themselves are not redefined by this feature.

## Implementation Approach

### Architecture

**System Architecture:**
```
┌─────────────────────────────────────────────────┐
│  PreToolUse(Bash) command string                │
├─────────────────────────────────────────────────┤
│  Existing lexing / statement split               │
│  (subshell, bash -c payload, command            │
│   substitution, pipe element, here-doc body)     │
├─────────────────────────────────────────────────┤
│  NEW: assignment collection  (FR1, FR5, FR6)     │
│       -> name-to-value resolution map            │
├─────────────────────────────────────────────────┤
│  NEW: target-token substitution  (FR2, FR7)      │
│       $VAR / ${VAR} -> literal; dynamic          │
│       constructs left unresolved                 │
├─────────────────────────────────────────────────┤
│  Existing target-path checks  (FR3)              │
│   check_rm: rm-root / SAFE_DELETE / rm-recursive │
│   check_self_modification: SELF_CONFIG,          │
│                            TRANSCRIPT            │
├─────────────────────────────────────────────────┤
│  Verdict: allow / ask / deny  (+ reason)         │
└─────────────────────────────────────────────────┘
```

**Component Diagram:**
```
resolution map builder  --(map)-->  target-token resolver  --(resolved literal targets)-->  check_rm
                                                            \--(resolved write_targets)-->  check_self_modification

resolution map builder reads only statements at the same nesting level as the use site (FR7);
a variable with two or more assignments is dropped from the map (FR6).
```

### Data Flow

```
command string → statement lexing → assignment collection → resolution map
                                                              ↓
        target tokens → $VAR / ${VAR} substitution → fully resolved? ──no──→ pre-change verdict (unresolvable)
                                                              │yes
                                                              ↓
                                     check_rm / check_self_modification → verdict + reason
```

### API Design

Not applicable. This feature adds no endpoint; its only interface is the existing PreToolUse hook contract (command string in, verdict out).

### Database Schema

Not applicable. No persisted data; the resolution map lives only for the duration of one command-string judgment.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: the hook whose judgment pipeline gains the resolution step; its existing SAFE_DELETE, SELF_CONFIG, TRANSCRIPT and DYNAMIC patterns, `normalize_candidate()`, `deletion_alternative(target)` and `MAX_SHELL_PAYLOAD_EXPANSIONS` are used as they stand (NFR6).
- `em-workflow/hooks/tests/destructive-guard-cases.json` and `run-destructive-guard.py`: the case set and runner that demonstrate no detection loss (FR8).
- `.claude/rules/hook-tests.md`: the case format and the retain-existing-cases rule (FR8).
- `.claude/rules/core-plugin-version-bump.md`: the two-file version bump rule (FR9).

**External Dependencies:**
- Python 3 standard library only. No new dependency is introduced (NFR5).

### File Structure

```
em-workflow/
├── hooks/
│   ├── destructive-guard.py                  # variable resolution (FR1-FR7)
│   └── tests/
│       ├── destructive-guard-cases.json      # new cases, existing cases retained (FR8)
│       └── run-destructive-guard.py          # runner (unchanged)
└── .claude-plugin/
    └── plugin.json                           # version 0.1.56 -> 0.1.57 (FR9)
.claude-plugin/
└── marketplace.json                          # em-workflow entry 0.1.56 -> 0.1.57 (FR9)
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

Every scenario below is exercised through `em-workflow/hooks/tests/destructive-guard-cases.json` in the `[expected_verdict, label, command]` form (FR8) and run by `python3 em-workflow/hooks/tests/run-destructive-guard.py`.

### Unit Tests

- [ ] TS-1 (FR1, FR2, FR3): Reported false positive is fixed — `D=/tmp/build-xyz; rm -rf "$D"` → allow
- [ ] TS-2 (FR2, FR3, FR4): Resolved path outside SAFE_DELETE is denied as the literal would be — `D=/home/sakura/src/proj; rm -rf "$D"` → deny (rule `rm-recursive`, reason includes the `deletion_alternative` command)
- [ ] TS-3 (FR6): Reassigned variable stays unresolvable, with the rewrite hint — `D=/tmp/a; D=/home/sakura/proj; rm -rf "$D"` → ask (rule `rm-unresolvable`, reason states that splitting into separate variables makes it resolvable)
- [ ] TS-4 (FR7): Cross-nesting assignment stays unresolvable — `bash -c 'D=/tmp/x'; rm -rf "$D"` and `(D=/tmp/x); rm -rf "$D"` → ask (rule `rm-unresolvable`)
- [ ] TS-5 (FR5): Command-prefix assignment stays unresolvable (shell expands the word before the assignment applies) — `D=/tmp/x rm -rf "$D"` → ask (rule `rm-unresolvable`)
- [ ] TS-8 (FR2, FR3): Resolved value reaching root/home is denied — `D=~; rm -rf "$D"` and `D=/; rm -rf "$D"` → deny (rule `rm-root`)
- [ ] TS-9 (FR3): All-target-checks decision reaches the self-modification path — `V=~/.claude/settings.json; rm "$V"` → ask (rule `self-modification`)
- [ ] TS-10 (FR3): All-target-checks decision reaches the transcript-write path — `V=~/.claude/projects/foo/bar.jsonl; tee "$V"` → deny (rule `transcript-write`)

### Integration Tests

- [ ] TS-11 (FR8): No regression — the full pre-existing case set in `destructive-guard-cases.json` keeps every recorded verdict.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS-6 (FR2): Resolved value still containing a glob stays unresolvable — `D=/home/sakura/proj/*; rm -rf "$D"` → ask (rule `rm-unresolvable`)
- [ ] TS-7 (FR2): Resolved value still containing command substitution stays unresolvable — `D=$(pwd)/out; rm -rf "$D"` → ask (rule `rm-unresolvable`)
- [ ] FR5 edge: chained references whose value is built from an already-resolved variable, and `export VAR=value`, are out of scope and stay unresolvable.
- [ ] FR7 edge: an assignment separated from its use by a command-substitution body, a pipe element, or a here-document body stays unresolvable.

### Performance Tests

Not applicable. Bounded cost is met structurally by NFR4: a linear pass over statements that are already lexed, with no unbounded expansion loop.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** The command string is analysed statically only — no filesystem access, no stat, no realpath, no subprocess, no shell invocation (NFR1). A token that still contains a glob, a command substitution, or an unmapped variable reference after substitution is not treated as resolved (FR2).
- **Data Protection:** SELF_CONFIG-matching write targets keep their `ask` (self-modification) and TRANSCRIPT-matching ones keep their `deny` (transcript-write) when reached through a resolved value (FR3).
- **Fail-closed behaviour:** Any case the resolver cannot settle statically keeps the pre-change verdict; the change never converts an existing deny or ask into allow other than through a fully resolved literal value (NFR2).
- **Detection preservation:** The SAFE_DELETE, SELF_CONFIG, TRANSCRIPT and DYNAMIC pattern definitions are not redefined (NFR6), and every existing deny/ask test case is retained (FR8).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Verdict Rules

No new rule id is introduced; the existing rule identifiers are reused.

| Rule id | Condition | Verdict | Reason content |
|---------|-----------|---------|----------------|
| `rm-recursive` | Resolved literal path falls outside SAFE_DELETE under a recursive delete | deny | Includes the `deletion_alternative(target)` replacement command built from the resolved path (FR4) |
| `rm-root` | Resolved value reaches a root/home target | deny | Existing reason (FR3) |
| `rm-unresolvable` | Reference not resolvable per FR5 / FR6 / FR7, or a dynamic construct remains after substitution per FR2 | ask (pre-change verdict) | For the reassignment case, states that assigning the two values to separate variables makes the command resolvable (FR6) |
| `self-modification` | Resolved write target matches SELF_CONFIG | ask | Existing reason (FR3) |
| `transcript-write` | Resolved write target matches TRANSCRIPT | deny | Existing reason (FR3) |

### Error Flow

```
Unresolvable construct detected → do not substitute → fall through to the pre-change judgment path → pre-change verdict
```

## Performance Optimization

### Performance Goals

- Resolution is a linear pass over statements that are already lexed, with no unbounded expansion loop (NFR4).

### Optimization Strategies

- Reuse the existing lexing output rather than re-parsing the command string (NFR4).
- Stay consistent with the `MAX_SHELL_PAYLOAD_EXPANSIONS` discipline already in the file (NFR4).

### Caching Strategy

Not applicable. The resolution map is built per command-string judgment and not retained.

## Success Criteria

- [ ] AC-1: The reported false-positive command — a plain literal assignment followed, at the same nesting level, by a recursive delete through that variable to a SAFE_DELETE path — is allowed.
- [ ] AC-2: The same shape aimed at a path outside SAFE_DELETE is denied with rule `rm-recursive` and a reason carrying the `deletion_alternative` command for the resolved path.
- [ ] AC-3: A resolved value that reaches a root/home target is denied with rule `rm-root`.
- [ ] AC-4: A resolved value flowing into a write target that matches SELF_CONFIG asks (self-modification); one matching TRANSCRIPT denies (transcript-write).
- [ ] AC-5: Every unresolvable form of FR5, FR6 and FR7 keeps its pre-change verdict; the reassignment case's reason text contains the split-the-variables hint.
- [ ] AC-6: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes, with all pre-existing deny/ask cases still present and still passing.
- [ ] AC-7: `plugin.json` and `marketplace.json` both read 0.1.57.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every functional and non-functional requirement above has `status: confirmed`; no requirement carries `status: tbd`.

## Implementation Phases (if applicable)

Not applicable. The change is confined to one existing Python hook and its test-case JSON, plus the two version files, and is not split into phases.

## Assumptions

- The em-workflow plugin version at the base revision is 0.1.56, per the dispatch note; the implementer confirms this before bumping.
- Existing rule identifiers (`rm-recursive`, `rm-unresolvable`, `rm-root`, `self-modification`, `transcript-write`) are reused; this feature introduces no new rule id.
- The SAFE_DELETE, SELF_CONFIG, TRANSCRIPT and DYNAMIC regexes are used as they stand and are not redefined by this feature.

## References

- Requirements document (Japanese): `feature-docs/destructive-guard-var-resolution/REQUIREMENTS.md`
- Hook test rule: `.claude/rules/hook-tests.md`
- Plugin version bump rule: `.claude/rules/core-plugin-version-bump.md`
- Hook under change: `em-workflow/hooks/destructive-guard.py`
- Test cases: `em-workflow/hooks/tests/destructive-guard-cases.json`
- Hook test command: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Project test command: `python3 -m unittest discover -s tests`
- Design step: skipped (gate `create-spec.design-step`, question `design-step.decision`, option `skip`) — the change is confined to one existing Python hook and its test-case JSON, with no user-facing surface and no visual output.
- **Requirement ID mapping** — the requirements analysis spelled these IDs with a hyphen; this document and REQUIREMENTS.md use the hyphen-less form, one-to-one and order-preserving: `FR-1`→`FR1`, `FR-2`→`FR2`, `FR-3`→`FR3`, `FR-4`→`FR4`, `FR-5`→`FR5`, `FR-6`→`FR6`, `FR-7`→`FR7`, `FR-8`→`FR8`, `FR-9`→`FR9`, `NFR-1`→`NFR1`, `NFR-2`→`NFR2`, `NFR-3`→`NFR3`, `NFR-4`→`NFR4`, `NFR-5`→`NFR5`, `NFR-6`→`NFR6`. Acceptance-criterion IDs (`AC-n`) and test-scenario IDs (`TS-n`) keep the analysis spelling.
