# Threat Model: declared-command-yaml-breaks

## Verdict
threats-identified

## Rationale
Inspected SPEC.md at the reduced tier; there is no REQUIREMENTS.md and the design step was skipped. Two inputs cross into the changed code. The first is the text of workflow.yaml `*_command` declarations, which anyone able to change the repository can write. The second is the Bash command string the hook receives from the session. Both reach `em-workflow/hooks/bash_guard.py`, whose allow / deny / no-verdict decision is the approval gate. task0001 declares `auth` and `input-handling`, so both boundaries are analysed at deep depth. task0002 edits documentation only and declares none of the four depth domains.

SPEC A5 scopes out YAML escape notation, block scalars, multi-line values, characters inside the value, `merge-preflight.py` and the approval gate procedure. Those invocations keep reaching the normal permission prompt, and FR4 records them as out of scope. They carry no mitigation here.

## Trust Boundaries

### TB-1: Repository-written workflow.yaml declarations into declared-set extraction
Crossing: `*_command` values in workflow.yaml, written by anyone able to change the repository. `declared_commands` reads them line by line to build the declared set that drives the unapproved-command deny.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A quoted declaration with U+0085, U+2028 or U+2029 at an end enters the declared set with that character kept. The YAML-parsed value that is actually executed (U+0085 becomes one space) then matches neither the declared set nor the approval store. A declared, unapproved command escapes the hook's deny and reaches the normal permission prompt, where an existing Bash allow can run it without an approval record (FR1, FR5). | TM-1 | `declared_commands` also adds each value with leading and trailing U+0020, U+0009, U+0085, U+2028 and U+2029 removed, when non-empty. The raw, YAML-parsed and end-stripped forms are then all denied as unapproved. | task0001 AC-1, AC-2, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification: TM-1 (TS-1, TS-3) |

### TB-2: Session-supplied Bash command into the hook's allow decision
Crossing: the command string in the hook's stdin payload, produced by the agent session (influenceable through content the session reads). It is matched against the approval store and the declared set.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | The wider normalization introduced for the declared set leaks into the allow decision. A command padded at an end with U+0085, U+2028 or U+2029, or an end-stripped form of a declared value, is then allowed without an exact approval (FR3). | TM-2 | Allow stays limited to the exact match against the approval store and the cd-prefix form, and neither consults the declared set. `trim_blanks` keeps removing spaces and tabs only, and no form (b) entry is used to allow. | task0001 AC-6, AC-7 | VERIFICATION.md Performance / Security Verification: TM-2 (TS-1, TS-4) |
