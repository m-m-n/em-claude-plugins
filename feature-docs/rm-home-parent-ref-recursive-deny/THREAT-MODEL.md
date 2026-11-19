# Threat Model: rm-home-parent-ref-recursive-deny

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR5, NFR1-NFR4, A1-A7) and the PreToolUse hook
`em-workflow/hooks/destructive-guard.py` — main()'s per-statement collection
and its resolution order, check_rm(), rm_protected_operand_numbers(),
check_self_modification() and decide(). Tier: reduced. task0001 declares
`input-handling` and `auth`, so TB-1 is analysed at deep depth.

The feature adds no input surface: the hook still reads one Bash command
string and the `HOME` at hook start. It changes which held `ask` reaches the
approver for one class of statements, so the boundary that matters is the one
between the agent-issued command and the approval decision, where the reason
ID is what the approver relies on.

Residual risk, accepted by SPEC.md FR1 (no mitigation recorded): an `ask` held
earlier by another statement of the same command keeps its rank. A command
such as `git commit --amend ; rm -rf "$HOME/.claude/skills/../../valuable"`
still shows only the earlier statement's reason. This is the existing
selection order for every non-rm `ask` placed before an rm `ask`, and it is
outside this feature's scope.

Not applicable at TB-1: Repudiation (the hook keeps no log and this feature
adds none) and Information disclosure (no character of a target reaches any
reason; unchanged by this feature).

task0001's other files (the case table, `.claude/rules/hook-tests.md` and the
new unittest module) are test data and documentation; they carry no runtime
decision and so appear in no `Boundary files` line.

## Trust Boundaries

### TB-1: Agent-issued Bash command to the destructive-guard verdict and the approver
Crossing: a Bash command string written by the agent, whose text untrusted
content (a prompt injection in a file, a web page or tool output) can steer,
crosses into the hook's static analysis. The hook's verdict and reason cross
to the human approver in an interactive run, or become a denial under
`CLAUDE_BATCH`. An approval authorizes execution with the user's privileges.
Boundary files: `em-workflow/hooks/destructive-guard.py`
Depth: deep (input-handling, auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An rm operand whose raw form matches the protected self-config pattern, that leaves the protected area once `..` is folded, and that contains an unresolved expansion (`$HOME/.claude/skills/../../valuable`, or the `~` / `/home/user` spellings with an expansion) yields only the same statement's self-modification `ask`. The approver grants what reads as a self-config write and so also grants a recursive delete outside the protected area (FR1, FR2, A2, A3). | TM-1 | In a statement with such a qualifying operand, main() selects the rm `ask` (reason ID `rm-unresolvable`) in place of that statement's self-modification `ask` at the first-held-ask step, on both the plain rm path and the substitution-headed path. `CLAUDE_BATCH` demotes it to `deny` with the same reason ID. | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Elevation of privilege | A selection change broader than the qualifying-operand rule would weaken the guard. Examples: the rule outranking the rm `deny`, the rule reordering `ask`s held by other statements, or `$HOME` being expanded with the hook's `HOME`, which would let a `HOME=` reassignment inside the command steer the verdict. Each of these turns a current `deny` into an `ask` or changes a verdict outside this feature (FR1, FR3, NFR1, A5). | TM-2 | The exception only swaps the same statement's self-modification `ask` for the rm `ask`. The rm `deny` stays first, `ask`s of other statements keep their rank, and statements without a qualifying operand are unchanged. The functions FR3 names and decide() are not changed, and `$HOME` stays an unresolved expansion. | task0001 AC-4, AC-7 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Denial of service | A crafted statement with many operands makes the added per-statement check costly enough to pass the hook's time limit, so the command gets no verdict (NFR3). | TM-3 | The qualifying-operand check reuses the records and the protected-operand set already computed for the statement. Its work is linear in the operand and record count, it reads no file-system state, and it runs inside the existing scan budget. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 |
