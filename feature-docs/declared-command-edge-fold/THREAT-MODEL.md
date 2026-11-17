# Threat Model: declared-command-edge-fold

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1-FR5, NFR1-NFR7, Security Considerations, A1-A6) and REQUIREMENTS.md at the full tier; the design step was skipped. Two inputs cross into the changed code, `em-workflow/hooks/bash_guard.py`, whose allow / deny / no-decision outcome is the approval gate. The first is the text of workflow.yaml `*_command` declarations, which anyone able to change the repository can write. The second is the Bash command string the hook receives from the session. task0001 declares `auth` and `input-handling`, so both boundaries are analysed at deep depth.

The widened deny of FR3 (SPEC A2) changes availability only: an approved value padded at an end with LF, U+0085, U+2028 or U+2029 is denied in a repository that declares it. SPEC accepts this fail-closed outcome, so it carries no mitigation here. Repudiation and information disclosure do not apply: no audit record changes and no secret crosses either boundary. The out-of-scope cases of SPEC A3 keep reaching the normal permission prompt and carry no mitigation here.

Post-decomposition consistency: task0001 declares `auth` and `input-handling`; its source file `em-workflow/hooks/bash_guard.py` appears in both Boundary files lines. Its test files are not boundary files. The appends to the four documents of other features (FR5) are documentation and cross no trust boundary.

## Trust Boundaries

### TB-1: Repository-written workflow.yaml declarations into the hook's declared check
Crossing: `*_command` values in working-tree workflow.yaml files, written by anyone able to change the repository. `declared_commands` turns them into the declared set; the YAML-parsed value of the same declaration reaches the hook as a Bash command, and the hook's declared check decides between the unapproved deny and no decision.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A quoted declaration whose ends mix or repeat U+0085, U+2028 and U+2029 is folded by the YAML parser end by end, so the parsed command matches neither declared form. The declared, unapproved command gets no decision and reaches the normal permission prompt, where an existing Bash allow or auto mode can run it without an approval record (FR1, FR4; SPEC.md AC1-AC4, TS-8). | TM-1 | At each of the three declared checks in `hook_main` (early return, workflow relevance, unapproved deny), the received command with U+0020, U+0009, LF, U+0085, U+2028 and U+2029 removed from both ends is also matched against the declared set, when that form is non-empty. | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification: TM-1 (TS-2, TS-8) |

### TB-2: Session-supplied Bash command into the hook's allow decision
Crossing: the command string in the hook's stdin payload, produced by the agent session (influenceable through content the session reads). It is matched against the user-owned approval store and the declared set.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | The new six-character end strip leaks into the allow decision or into declared-set extraction, so a command padded at an end with LF, U+0085, U+2028 or U+2029, or a cd-prefixed form, is allowed without an exact approval (FR2; SPEC.md AC5, AC7). | TM-2 | The end-stripped form only decides whether a command is declared. Exact and cd-prefix allow keep judging the space/tab-trimmed command, and `declared_commands`, `DECLARED_END_STRIP`, `trim_blanks` and `is_matchable` stay unchanged. | task0001 AC-4, AC-6 | VERIFICATION.md Performance / Security Verification: TM-2 (TS-1, TS-2, TS-3, TS-7) |
