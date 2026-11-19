# Threat Model: rm-parent-ref-self-config-deny

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier reduced; REQUIREMENTS.md and DESIGN.md are not
produced). The feature changes how destructive-guard, a PreToolUse hook,
decides on Bash rm commands. The command string is produced by the model and
can be steered by untrusted content the agent reads; the hook's decision
gates whether that command runs with the user's filesystem privileges, and an
ask hands the decision to the user on the strength of the reason it shows.
That is one trust boundary (TB-1). task0001 declares the domains `auth` and
`input-handling`, so TB-1 is analysed at deep depth. task0001's other files,
the case table and the new unittest under `tests/`, verify the boundary and do
not implement it, so they are not listed as boundary files.

A literal `~` segment placed after enough `..` segments to consume the leading
`~` (for example `~/.claude/skills/../../../~/.claude/hooks/x`) would fold back
into a home-anchored form under a plain lexical fold. TM-1's anchor rule
covers it: once a `..` consumes the leading `~` / `$HOME`, the folded form does
not match. With HOME under /home such an operand stays ask, because its
normalized form (`/home/~/.claude/hooks/x`) matches SELF_CONFIG through the
unchanged normalized route.

Accepted residual risks, with no mitigation in this feature:
- The judgement is lexical, so a symlink before a `..` segment can make the
  real target differ from the folded form (SPEC.md A6 keeps this out of
  scope).
- When HOME's own last segment is literally `~` (for example /srv/~), an rm
  that really targets HOME's self-config through a `..` consuming the
  leading anchor loses the raw-form protection, and can turn from the
  self-modification ask into deny / rm-recursive. The error is in the
  stricter direction (a refusal, not an unguarded delete).

## Trust Boundaries

### TB-1: agent-issued Bash command to destructive-guard decision to shell execution
Crossing: a Bash command string produced by the model (attacker-influenceable
through prompt injection in content the agent reads) enters destructive-guard's
static analysis; the resulting allow / ask / deny decides whether the command
runs with the user's filesystem privileges.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An rm operand whose raw form names a protected self-config path but whose `..` segments lead outside the protected area (for example `~/.claude/skills/../../valuable`, or `~/.claude/skills/../../../~/.claude/hooks/x`, which re-enters a home-anchored shape after leaving HOME) is taken out of the recursive-delete deny pool, so the recursive delete of an unprotected target is gated only by a self-modification ask; approving that ask interactively runs a delete the deny exists to block, on both the plain and the command-substitution-led rm path (SPEC.md FR1, FR3, AC1, AC2) | TM-1 | The protected-operand judgement counts a raw-form match only when the lexically `..`-folded form (`~` / `$HOME` not expanded) also matches SELF_CONFIG, and the folded form does not match once a `..` consumes the leading `~` / `$HOME` anchor; a `normalize_candidate()` match counts as before; the rule lives in the one function both rm call sites use | task0001 AC-1, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2, TS-5, TS-7, TS-12) |
| Repudiation | Under `CLAUDE_BATCH` the same form is denied, but with reason ID self-modification, so the recorded reason hides that a recursive delete outside the protected area was attempted (SPEC.md AC3) | TM-2 | The batch-mode decision for the form carries reason ID rm-recursive, pinned by a rule-tagged batch case | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-3) |
