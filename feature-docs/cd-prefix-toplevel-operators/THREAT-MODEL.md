# Threat Model: cd-prefix-toplevel-operators

## Verdict
threats-identified

## Rationale
Inspected: REQUIREMENTS.md and SPEC.md (FR1–FR10, NFR1–NFR7, assumptions
A1–A6), the current `em-workflow/hooks/bash_guard.py`, and the documents the
implementer follows. Tier: full. Depth: deep for TB-1, driven by the `auth`
and `input-handling` domains of task0001 (the hook's allow grants execution
without a prompt, and it parses a shell string). The feature changes when a
permission hook grants a prompt-free run, so there is one trust boundary and
STRIDE applies to it.

Domain consistency: task0001 (`auth`, `input-handling`), task0002 (`auth`)
and task0003 (`auth`) each have at least one file on TB-1's Boundary files
line. task0002's `em-workflow/README.md` and
`em-workflow/references/workflow-schema.md` are not on that line: they only
summarize the rule for human readers, and the implementer is not instructed
from them.

Not applicable at TB-1: Spoofing (the hook does not authenticate a party;
the cwd and the approval store keying are unchanged), Repudiation (the allow
reasons stay distinct and unchanged), Information disclosure (no data leaves
the hook).

Inside the table, a pipe character of a shell token is written escaped so
the table renders; the token itself is a plain pipe.

## Trust Boundaries

### TB-1: Implementer Bash command → bash_guard.py permission decision → prompt-free shell run
Crossing: a Bash command string written by the implementer subagent (an LLM
whose context holds repository-controlled text, so its output can be
influenced by an attacker) crosses into the PreToolUse hook. An `allow` from
the hook is a privilege change: the command runs without a user prompt. The
remainder after the cd prefix is compared with user-approved strings that
come from repository-controlled workflow.yaml.
Boundary files: em-workflow/hooks/bash_guard.py, em-workflow/references/command-execution-protocol.md, em-workflow/agents/implementer.md, em-workflow/skills/worktree-task-workflow/SKILL.md
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An approved string with a lone `&`, `;`, `\|\|` or a line break at its top level, run in the allowed cd prefix form, runs part of itself in the original cwd (the main working tree) instead of the worktree; `&&` binds tighter than `&` and `;`, and `\|\|` or `;` let the rest run after a failed `cd` (FR1, FR2; REQUIREMENTS.md 1.1) | TM-1 | A quote- and escape-aware scan of the trimmed remainder; any lone `&`, `;`, `\|\|` or line break at the top level makes the form ineligible for the cd prefix allow (IMPLEMENTATION.md C1, E1–E4) | task0001 AC-1, AC-2 | VERIFICATION.md TM-1 (TS1, TS2) |
| Elevation of privilege | A construct the scan cannot classify without parsing nesting — unclosed quote, trailing backslash, `$'…'` / `$"…"`, `#`, grouping or subshell, command or parameter substitution — hides or forges a top-level operator, so the scan's reading of the string differs from Bash's and an unsafe string is allowed (FR3) | TM-2 | Safe-side exclusions: any such construct makes the form ineligible, without nesting being parsed (IMPLEMENTATION.md C1, E4–E10) | task0001 AC-3 | VERIFICATION.md TM-2 (TS3) |
| Elevation of privilege | If ineligibility also removed the form from the hook's workflow-relevant set, a refusal-pattern string (for example `sudo`) placed in the approval store together with a top-level operator would fall from deny to no decision and reach the normal permission flow (FR5) | TM-3 | Workflow relevance is computed as before the change, independent of C1, and the refusal patterns are applied to the whole command before the cd prefix allow (IMPLEMENTATION.md C2, steps 2 and 4) | task0001 AC-5 | VERIFICATION.md TM-3 (TS5) |
| Elevation of privilege | An implementer whose cd prefix form gets no decision falls back to running the approved string without the prefix — which FR4 still allows by exact match — or rewrites it, so the string runs in the subagent's original cwd (FR4, FR6, FR7) | TM-4 | The protocol and both implementer procedure documents state that such an approved string is not run and is reported in `notes` (IMPLEMENTATION.md C4) | task0002 AC-3; task0003 AC-1, AC-2, AC-3 | VERIFICATION.md TM-4 (TS7) |
| Denial of service | The scan counts the `&` of a redirection or pipe token (`2>&1`, `\|&`, `&>`, `&>>`, `<&`, `>&`) or a quoted or escaped `;` / `&` as a top-level operator, so legitimate approved strings lose the allow and unattended implementers stop; or an ineligible form is turned into a new deny (FR2, FR4; SPEC AC3) | TM-5 | Longest-match recognition of the `&`-bearing tokens and `\|\|` outside quotes; quoted and escaped characters are not counted; an ineligible form is judged by the unchanged decision table and never gets a new deny (IMPLEMENTATION.md C1 scan model, C2 steps 7 and 8) | task0001 AC-2, AC-4 | VERIFICATION.md TM-5 (TS2, TS4, TS6) |
