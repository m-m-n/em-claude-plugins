# Feature: destructive-guard-write-target-scoping

## Overview

`check_self_modification` in `em-workflow/hooks/destructive-guard.py` currently matches the `SELF_CONFIG` and `TRANSCRIPT` patterns against the whole command segment, so read-only commands that merely mention `~/.claude` are judged as writes. This feature rewrites that check to build a set of write-target paths and match the two patterns only against the members of that set, after first adding the false-positive cases to the expectation suite. Detection strength for self-config writes (ask) and transcript writes (deny) is preserved unchanged.

Requirement source: `feature-docs/destructive-guard-write-target-scoping/REQUIREMENTS.md`.

## Objectives

- Eliminate the cases where `check_self_modification` misjudges read-only commands and halts unattended runs.
- Resolve the transcript-write false positive first: it is a `deny` (never routed through the auto-mode classifier), so the session-log-recall skill's own `2>/dev/null` procedure is stopped by it.
- Keep the existing detection strength for self-config writes and transcript writes intact — the false-positive fix must not weaken detection.

## User Stories

### US1: Read-only commands are not falsely flagged
As an unattended (`claude-batch`) run operator, I want read-only commands that reference `~/.claude` to be allowed, so that a false positive does not end the run on the spot.

**Acceptance Criteria:**
- [ ] AC-2: The five FR1 cases exist in `destructive-guard-cases.json` with an `allow` expectation and all five are judged `allow`.
- [ ] AC-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case and exits 0.

### US2: Transcript reads are not denied
As a session-log-recall skill user, I want reading `~/.claude/projects/**/*.jsonl` to be allowed, so that the skill's documented procedure completes instead of being denied.

**Acceptance Criteria:**
- [ ] AC-5: `cat ~/.claude/projects/foo/bar.jsonl 2>/dev/null` and `grep -l needle ~/.claude/projects/foo/*.jsonl 2>/dev/null` are judged `allow`, not `deny`.

### US3: Existing detection is preserved
As an unattended run operator, I want writes to `~/.claude` to keep their current judgement, so that the safety net still catches self-config and transcript writes.

**Acceptance Criteria:**
- [ ] AC-6: `echo x > ~/.claude/projects/a/b.jsonl` stays `deny`, `echo x > ~/.claude/settings.json` stays `ask`, `rm -rf ~/.claude/skills/foo` stays `ask`.
- [ ] AC-4: All 34 existing cases in `destructive-guard-cases.json` are neither deleted nor altered and all return their expected judgement.
- [ ] AC-7: The unattended-demotion case at the end of `run-destructive-guard.py` (`CLAUDE_BATCH=1` with `echo x > ~/.claude/settings.json` → `deny`) passes.

## Technical Requirements

### Functional Requirements

- **FR1 - Add the false-positive cases to the test suite first:** Add the following five cases to `em-workflow/hooks/tests/destructive-guard-cases.json` with an expected judgement of `allow`: `grep -rn "x" ~/.claude/skills/ 2>/dev/null`, `ls ~/.claude/skills/ 2>/dev/null | head -40`, `cat ~/.claude/settings.json > /tmp/copy.json`, `cat ~/.claude/projects/foo/bar.jsonl 2>/dev/null`, `grep -l needle ~/.claude/projects/foo/*.jsonl 2>/dev/null`. Delete none of the existing `deny` / `ask` cases. This addition comes before the FR2 implementation, and the suite must be confirmed red at that point.
- **FR2 - Build a write-target path set and apply SELF_CONFIG / TRANSCRIPT only to its members:** Rewrite `check_self_modification` from a regex search over the whole segment into a match against a set of write-target paths. The set is drawn from three sources: (a) output-redirect targets (`split_redirects()` puts both the operator and the target into `redirects`, so take the side that is not the operator; input redirects `<` and friends are not included); (b) the target arguments of `INPLACE_WRITERS` (tee / truncate / shred / install / patch) and of `sed -i`; (c) the target arguments of rm / mv / cp / ln / chmod / chown (for cp / mv / ln the destination is the last argument). `SELF_CONFIG` and `TRANSCRIPT` apply only to the members of this set.
- **FR3 - Do not judge when there is no write target:** A segment whose assembled write-target set is empty returns without performing either the self-modification or the transcript-write judgement. Commands whose only redirect target is `/dev/null` (`ls ... 2>/dev/null`, `rm -rf /tmp/x > /dev/null`) end up with a set containing only `/dev/null` and, for `2>&1`, a file-descriptor number, matching neither `SELF_CONFIG` nor `TRANSCRIPT`.
- **FR4 - Allow commands whose only `~/.claude` path is a read source:** Even for commands where writes are derived from arguments, do not fire when the `~/.claude` path is only on the source side. Both `cat ~/.claude/settings.json > /tmp/copy.json` and `cp ~/.claude/settings.json /tmp/` become `allow`.
- **FR5 - Preserve existing detection:** Keep the current judgements: `cat foo > ~/.claude/settings.json` → `ask` (self-modification); `sed -i s/a/b/ ~/.claude/rules/x.md` → `ask`; `rm ~/.claude/hooks/foo.py` → `ask`; `rm -rf ~/.claude/skills/foo` → `ask`; `echo x > ~/.claude/projects/a/b.jsonl` → `deny` (transcript-write); under unattended execution `echo x > ~/.claude/settings.json` → `deny` (demoted from `ask`). Every existing `deny` / `ask` case in `destructive-guard-cases.json` and the demotion case at the end of `run-destructive-guard.py` must pass.
- **FR6 - Leave the rm judgement untouched:** Thanks to `SAFE_DELETE` and the existing false-positive fixes, rm has no false positives (`rm /tmp/foo`, `rm -rf node_modules`, `rm -rf /tmp/x 2>/dev/null`, `grep -rn "rm -rf /" ~/.claude/hooks/` are all `allow`). `check_rm` and `SAFE_DELETE` are out of scope for this change.
- **FR7 - Bump the plugin version in two places to the same value (patch):** Following `.claude/rules/core-plugin-version-bump.md`, raise the `version` in `em-workflow/.claude-plugin/plugin.json` and the `version` of the em-workflow entry in `.claude-plugin/marketplace.json` to the same value. This is a behaviour fix, so the bump is a patch. Both currently read 0.1.55; the target is 0.1.56.

### Non-Functional Requirements

- **NFR1 - Static analysis only, deterministic judgement:** The judgement is made purely by static analysis of the command string; no command is executed. The same command always yields the same judgement.
- **NFR2 - Standard library only:** Neither the hook itself nor its tests depend on third-party packages. `destructive-guard.py` imports only json / os / re / shlex / shutil / sys, and `test/README.md` forbids external dependencies in test code.
- **NFR3 - Test first, keep existing cases:** Per `.claude/rules/hook-tests.md`, a false positive gets a case added before it is fixed. Existing `deny` / `ask` cases are never deleted.
- **NFR4 - Asymmetric cost of false positives:** One false positive costs the same order of magnitude as one miss (`ask` is demoted to `deny` under `claude-batch`, ending an unattended run on the spot). The fix must remove false positives without lowering detection.

## Implementation Approach

### Architecture

**System Architecture:**

Not applicable as a layered system diagram. The change is contained in one function of a single PreToolUse(Bash) hook script:

```
PreToolUse(Bash) → destructive-guard.py
                     ├── statements()            # split the command into segments
                     ├── split_redirects()       # separate redirect operators and targets
                     ├── check_rm()              # unchanged (FR6)
                     └── check_self_modification()  # rewritten (FR2/FR3/FR4)
                           ├── build write-target set  (a) redirect targets
                           │                           (b) INPLACE_WRITERS / sed -i args
                           │                           (c) rm / mv / cp / ln / chmod / chown args
                           └── match SELF_CONFIG / TRANSCRIPT against set members only
```

**Component Diagram:**

```
destructive-guard.py            — hook body; check_self_modification is the only function changed
destructive-guard-cases.json    — [expected judgement, label, command] case table
run-destructive-guard.py        — runner; also holds the trailing unattended-demotion case
plugin.json / marketplace.json  — version fields (FR7)
```

### Data Flow

```
command string → statements() → per-segment: split_redirects()
              → write-target set (empty ⇒ return without judging, FR3)
              → SELF_CONFIG match ⇒ ask   (demoted to deny under CLAUDE_BATCH)
              → TRANSCRIPT match  ⇒ deny  (always)
              → no match          ⇒ allow (ALLOW_NON_DESTRUCTIVE)
```

Pipe stages become separate segments in `statements()` (`ls ~/.claude/skills/ 2>/dev/null | head -40` is two segments), and the judgement runs per segment.

### API Design

Not applicable. This feature exposes no API.

### Database Schema

Not applicable. This feature has no persistent data store.

#### Entity Relationship Diagram

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: the hook whose `check_self_modification` is rewritten; its only caller is `main()`, so the function signature may change.
- `em-workflow/hooks/tests/destructive-guard-cases.json`: the case table FR1 extends.
- `em-workflow/hooks/tests/run-destructive-guard.py`: the runner that executes the case table and the trailing unattended-demotion case.
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: the two version fields FR7 raises to the same value.

**External Dependencies:**
- None. Standard library only (NFR2): `destructive-guard.py` imports json / os / re / shlex / shutil / sys.

### File Structure

```
em-workflow/
├── .claude-plugin/
│   └── plugin.json                       # version 0.1.55 → 0.1.56 (FR7)
└── hooks/
    ├── destructive-guard.py              # check_self_modification rewritten (FR2/FR3/FR4)
    └── tests/
        ├── destructive-guard-cases.json  # five allow cases added (FR1)
        └── run-destructive-guard.py      # unchanged; runner + demotion case (FR5)
.claude-plugin/
└── marketplace.json                      # em-workflow version 0.1.55 → 0.1.56 (FR7)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-write-target-scoping/**`
- `test-docs/destructive-guard-write-target-scoping/**`

`feature-docs/destructive-guard-write-target-scoping/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/destructive-guard-write-target-scoping/**` covers `test-docs/destructive-guard-write-target-scoping/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/destructive-guard-write-target-scoping/` directory at all; the declared
`test-docs/destructive-guard-write-target-scoping/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` - Confirms the false-positive fix and the retained detection strength in one run. Red right after FR1 is applied, green after FR2. Covers FR1, FR2, FR3, FR4, FR5, FR6.

### Integration Tests
- [ ] TS-2: `python3 -m unittest discover -s tests` - Confirms no regression in the repository-wide unit tests. Covers FR2, FR7.
- [ ] TS-3: `python3 em-workflow/hooks/tests/run-destructive-guard.py <path-to-installed-guard-copy>` - After the version bump, confirms the fix reached the installed cache copy (optional). Covers FR7.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression - not applicable; no E2E infrastructure exists.

### Edge Cases
- [ ] `2>&1`: `split_redirects` puts the fd number `1` on the target side. It is not a path, but it matches neither `SELF_CONFIG` nor `TRANSCRIPT`, so it is harmless. Write the code assuming non-path tokens can appear in the set.
- [ ] Append redirects `>>` / `2>>`: these are writes, so a target under `~/.claude` keeps its `ask`.
- [ ] Input redirects `<` / `<<` / `<<<`: these are reads and are not put into the set (this keeps the existing here-string `allow` case intact).
- [ ] `tee -a ~/.claude/settings.json`: the flag must not be mistaken for the target argument. `ask` is kept.
- [ ] `cp ~/.claude/settings.json /tmp/` (destination `/tmp`) → `allow`; `cp /tmp/x ~/.claude/settings.json` (destination `~/.claude`) → `ask`. The destination is the last argument.
- [ ] `mv a b c dir/` with multiple sources: only the last one is the destination.
- [ ] `ln -sf x ~/.claude/hooks/y`: what gets created is the last argument.
- [ ] `sed -i.bak` / `sed -i ''` variants of `-i`: the current judgement is `a.startswith("-i")`. Even if the script argument (`s/a/b/`) ends up in the extracted target arguments, it does not match `SELF_CONFIG`, so the judgement is unchanged.
- [ ] Write targets that cannot be statically resolved because of variables or globs (`rm -rf ~/.claude/skills/*` etc.): for rm, the existing rm-unresolvable / rm-recursive rules produce `ask`/`deny` first. The set match on the self-modification side must not open a new hole.
- [ ] A segment with an empty write-target set returns without raising.
- [ ] Pipe stages become separate segments in `statements()` (`ls ~/.claude/skills/ 2>/dev/null | head -40` is two segments); the judgement runs per segment.

### Performance Tests
Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** The judgement is a static analysis of the command string only; no command is executed (NFR1). Write targets are extracted from redirect targets and from the target arguments of the writer commands enumerated in FR2.
- **Data Protection:** This hook is a safety net; the false-positive fix must not lower detection. Self-modification (`ask`) and transcript-write (`deny`) detection is preserved across every FR5 case.
- **Detection-gap risk:** Because `ALLOW_NON_DESTRUCTIVE=True`, a command matching no rule is allowed and skips the auto-mode classifier entirely. Any omission from the write-target set becomes a detection gap directly.
- **Demotion asymmetry:** `ask` is demoted to `deny` only under unattended execution (`CLAUDE_BATCH`). Transcript-write is always `deny` and cannot be waved through by a human, so its false positives do the most damage.
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

Not applicable. This hook emits a judgement (`allow` / `ask` / `deny`), not error codes.

### Error Flow

```
Empty write-target set → return without judging (FR3) → no exception raised
Non-path token in the set (fd number) → no SELF_CONFIG / TRANSCRIPT match → allow
```

## Performance Optimization

Not applicable. No performance goals, optimization strategies, or caching are part of this feature.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case and exits 0.
- [ ] AC-2: The five FR1 cases exist in `destructive-guard-cases.json` with an `allow` expectation and all are judged `allow`.
- [ ] AC-3: With only the FR1 cases added (FR2 not yet applied), running the suite is red.
- [ ] AC-4: The 34 existing cases in `destructive-guard-cases.json` are neither deleted nor altered and all return their expected judgement.
- [ ] AC-5: `cat ~/.claude/projects/foo/bar.jsonl 2>/dev/null` and `grep -l needle ~/.claude/projects/foo/*.jsonl 2>/dev/null` are `allow`, not `deny`.
- [ ] AC-6: `echo x > ~/.claude/projects/a/b.jsonl` is `deny`, `echo x > ~/.claude/settings.json` is `ask`, and `rm -rf ~/.claude/skills/foo` is `ask`.
- [ ] AC-7: The unattended-demotion case at the end of `run-destructive-guard.py` (`CLAUDE_BATCH=1`, `echo x > ~/.claude/settings.json` → `deny`) passes.
- [ ] AC-8: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the identical em-workflow version 0.1.56.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement is resolved.

## Implementation Phases (if applicable)

### Phase 1: Failing cases first
**Goals:** FR1 — add the five `allow`-expected cases and confirm the suite is red (AC-3).
**Deliverables:**
- The five added cases in `em-workflow/hooks/tests/destructive-guard-cases.json`
- A red run of TS-1

### Phase 2: Write-target scoping
**Goals:** FR2, FR3, FR4, FR5, FR6 — rewrite `check_self_modification` to the write-target set model and turn the suite green.
**Deliverables:**
- The rewritten `check_self_modification` in `em-workflow/hooks/destructive-guard.py`
- A green run of TS-1 (AC-1, AC-2, AC-4, AC-5, AC-6, AC-7)

### Phase 3: Version bump
**Goals:** FR7 — raise both version fields to 0.1.56.
**Deliverables:**
- `em-workflow/.claude-plugin/plugin.json` at 0.1.56
- `.claude-plugin/marketplace.json` em-workflow entry at 0.1.56 (AC-8)

## References

- Requirements document: `feature-docs/destructive-guard-write-target-scoping/REQUIREMENTS.md`
- Hook under change: `em-workflow/hooks/destructive-guard.py`
- Case table: `em-workflow/hooks/tests/destructive-guard-cases.json`
- Test runner: `em-workflow/hooks/tests/run-destructive-guard.py`
- Hook test rules: `.claude/rules/hook-tests.md`
- Plugin version bump rules: `.claude/rules/core-plugin-version-bump.md`
- Test dependency policy: `test/README.md`
