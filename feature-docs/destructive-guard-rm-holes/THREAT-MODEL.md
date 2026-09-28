# Threat Model: destructive-guard-rm-holes

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR8, NFR1-NFR5, assumptions a1-a6) and the
workflow.yaml goal block. Tier is `reduced`: REQUIREMENTS.md and DESIGN.md do
not exist, so SPEC.md is the only requirement source cited below. The single
task (task0001) declares `input-handling`, so both boundaries are analysed at
deep depth.

The feature's subject is a PreToolUse hook that stands between an
agent-authored Bash command and its execution. Two boundaries exist: the
command string entering the hook's verdict logic (TB-1), and the hook's reason
text flowing back into the agent's context, where it is read as hook-authored
guidance (TB-2). Both are crossed by text the agent may have copied from
attacker-influenced sources (file names in a repository, tool output).

Not modelled as threats, with the reason:
- The rm-root reason and the safety-bypass reason render only tokens drawn
  from fixed sets (SPEC.md a2, a4), so no attacker-chosen text reaches them.
- The fixed substitution stand-in is hook-authored text, not target-derived
  text (SPEC.md a3).
- Denial of service and Repudiation: the change alters only how reasons are
  rendered; it adds no loop, no I/O and no audit duty (NFR1), and nothing in
  SPEC.md records such a threat.
- The test modules, the case table and the two version manifests in
  task0001's file set carry no trust boundary: they are test fixtures and
  release metadata, never inputs to the hook at run time.

## Trust Boundaries

### TB-1: Bash command string -> destructive-guard verdict
Crossing: an agent-authored Bash command (which may embed path text the agent
took from repository contents or tool output) enters the hook's rm analysis,
which decides allow / ask / deny before the command runs.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A non-scratch target passes the SAFE_DELETE exception because the exception is matched as a raw prefix, before normalization or without a path-component boundary, so a destructive delete runs without approval (FR1); a fix that over-corrects re-opens bare scratch roots (FR5) | TM-1 | The exception is matched per path component on the normalized target (existing behaviour, left unchanged); the hole-1 forms and the bare / trailing-slash scratch-root forms are pinned as deny cases, and no existing deny / ask case changes | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Elevation of privilege | An rm target made only of command substitution is blanked out of the parent command, reaches the rm check with no target and is allowed (FR2) | TM-2 | A substitution-only target yields ask, downgraded to deny under CLAUDE_BATCH with the existing downgrade wording (NFR4); both the dollar-paren and the backtick forms are pinned | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, item TM-2 |

### TB-2: destructive-guard reason text -> agent context
Crossing: the hook's permissionDecisionReason is returned to the agent, which
reads it as trusted hook guidance; today rm target text (attacker-choosable
file names) is interpolated into it, and the alternative commands it suggests
are commands the agent may execute on the local filesystem.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | Instruction text planted in an rm target name is echoed into the reason and reaches the agent as if the hook had authored it (FR4) | TM-3 | The rm-unresolvable, rm-recursive, joined multi-target reasons and the deletion alternative designate each target only by a unique position and show alternatives only as templates with a fixed placeholder; no target-derived text enters the reason except the fixed substitution stand-in | task0001 AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, item TM-3 |
| Tampering | Newlines or other control characters in a target alter the structure of the hook's stdout, e.g. forging an additional line that carries a fake hook prefix (NFR3) | TM-4 | The hook's stdout never contains control characters, and neither a newline nor a forged prefix from target text appears in the reason | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, item TM-4 |
| Information disclosure | A reason that tells the agent to create the trash directory yields a umask-dependent (e.g. group/world-readable) directory, exposing trashed files to other local users (FR3) | TM-5 | No rm reason presents a command that creates or modifies the trash directory, whether or not gio is on PATH | task0001 AC-7 | VERIFICATION.md Performance / Security Verification, item TM-5 |
