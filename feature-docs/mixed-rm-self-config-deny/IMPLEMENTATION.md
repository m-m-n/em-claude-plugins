# Implementation Plan: mixed-rm-self-config-deny

## Overview
The self-modification exclusion in `em-workflow/hooks/destructive-guard.py` leaves out the rm records of the protected targets only, instead of every record of the rm invocation. The case table, the unit tests and the hook-tests rule document follow the new verdicts. The three statements of the destructive-guard-mixed-rm-precedence SPEC.md that FR7 names were amended during create-plan, so no task carries FR7.

## Technology Stack
- **Language**: Python 3, standard library only, as the hook, the case runner and the unit tests already are.
- **New dependencies**: none.

## Layer Structure
- **Hook** (`em-workflow/hooks/destructive-guard.py`): decides. It depends on nothing new.
- **Case table and runner** (`em-workflow/hooks/tests/`): run the hook as a subprocess and compare the decision and the reason id.
- **Unit tests** (`tests/`): run the hook as a subprocess, or read its source as text; they never import it to judge a command.
- **Rule document** (`.claude/rules/hook-tests.md`): describes the precedence the rule-pinned cases fix.

Dependencies point one way: the tests and the rule document depend on the hook's observable behavior, never the reverse.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Per-target exclusion | Decides which rm records of one statement join the pool that the resolution step chooses from | **Pre**: one statement as the statement scan yields it once; the statement's rm invocation (plain or substitution-headed) with the operand basis `check_rm()` judged for it; whether this statement reached the self-modification ask (the condition is unchanged). **Post**: (a) not reached: every record of the invocation joins the pool, as today. (b) Reached: a record is left out exactly when its operand number is in the invocation's protected set. The protected set holds the numbers, counted on the same operand basis by the same operand numbering, of the operands that do not start with `-` and whose raw form or normalized form matches the protected self-config pattern. Every other record of the invocation joins the pool. (c) The invocation keeps its place among the invocations, so ordinals and target numbers in reasons still count the left-out targets. (d) The resolution step is unchanged: an rm deny in the pool wins over every held ask whatever the order; the CLAUDE_BATCH demotion applies after the choice; a winning rm deny's reason is built from the pooled winners only. | task0001 (implements and pins it), task0002 (describes it in the rule document) |

## Conventions
- Paths in cases, tests and documents are generic placeholders (`/home/user/valuable`, `~/.claude/skills/foo`); no machine-specific path and no real home directory.
- Case labels and the rule document stay in Japanese; code comments and docstrings stay in English, as today.
- No task's files hold a feature-docs path, a plugin manifest or the marketplace file (NFR5).

## Cross-task Design Decisions

### D1: The exclusion unit becomes the target; the condition stays
The unit changes from the rm invocation to the rm target (SPEC.md FR1). The condition, that the statement reached the self-modification ask, does not change (SPEC.md A3). The protected-path test does not change either (SPEC.md FR2). task0001 implements the change; task0002 states it in the rule document. Both follow the Shared Components contract above.

### D2: The other feature's SPEC.md is not a task file
FR7's three statements in the destructive-guard-mixed-rm-precedence SPEC.md (the known-impact sentence of FR8, the third sentence of AC9 and the TS-15 line) were amended by the planner during create-plan. That feature's REQUIREMENTS.md and VERIFICATION.md are not changed. No task touches any of them.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The protected set and the records are numbered on different bases, so a denied target is left out instead of the protected one (THREAT-MODEL.md TM-2) | Low | High | Shared Components contract (b): same operand basis, same numbering, both routes; pinned by TS-10, TS-13 and TS-14 |
| The rewritten hook comments drop a word or add a phrase that existing description tests pin | Medium | Low | task0001 keeps the pinned words and adds none of the stale phrases; the full unit suite runs |
| The rewritten rule bullet loses the sentence an existing document test looks for | Medium | Low | task0002 keeps one sentence with the terms that test requires; the full unit suite runs |
| On the substitution-headed route, whether the self-modification ask is reached today is unknown (SPEC.md A7) | Medium | Low | task0001 pins the actual output of TS-13 and records which way it went |

## Open Questions
- [ ] A non-recursive rm with a protected operand and a root-shaped operand (for example `rm ~/.claude/skills/foo ~`) is an ask today. Under the per-target exclusion, its rm-root record joins the pool and the verdict becomes deny / rm-root. That change goes from ask to deny, the direction NFR1 allows. SPEC.md FR3 says a non-recursive rm stays an ask; this plan reads that clause as "the remaining targets give no deny record". No scenario pins this form.
