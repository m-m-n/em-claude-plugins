# Threat Model: codex-guard-reserved-word-funcdef

## Verdict
threats-identified

## Rationale
Inspected: REQUIREMENTS.md, SPEC.md (FR1-FR9, NFR1-NFR6, Security
Considerations), and the guard's input path. The feature runs at the `full`
tier and has one task (task0001), declaring `input-handling`, so the boundary
below is analysed at deep depth.

The guard reads a PreToolUse JSON object on standard input. The command
string inside it is produced by Codex, a separate process whose output can
be shaped by repository content, so the command string is untrusted input.
The guard's only output is a deny decision or silence. This feature widens
which word sequences the parser accepts as a function-definition head, and
a function body is never judged. Getting that wider rule wrong lets a
launch slip through, so the change touches the boundary directly.

Two Denial of service threats apply. Spoofing, Repudiation and Information
disclosure do not apply: the guard handles no identity, keeps no audit
record, and the change does not touch the deny output, which already names
only a matched interpreter. Tampering and Elevation of privilege do not
apply as separate categories either. The guard writes nothing (NFR2), and
the impact of a bypass is an orphaned REPL, which is recorded under Denial
of service.

A launch written as a simple command right after a reserved word, such as
`then python3 -i`, is not judged today, because the command word read is
the reserved word. That gap already exists and FR4 freezes it. This feature
does not introduce it, so it gets no row here.

## Trust Boundaries

### TB-1: Codex Bash command string -> guard parser
Crossing: the command string of a Codex Bash tool call, which Codex (another process, LLM-driven, influenceable by repository content) sends through the PreToolUse hook's standard input. It reaches the guard's parser, and the parser decides whether a group is a function body (not judged) or is executed (judged).
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | After reserved-word removal, a group that bash actually executes is read as a function body. The interactive launch inside it is never judged, and the REPL keeps spinning as an orphan in Codex's pseudo terminal. Example inputs: an array assignment, `export a=`, a dynamic name, a multi-word head, a reserved word in the middle of the sequence, or a sequence made only of reserved words (relates to FR3, FR4, FR5, NFR5) | TM-1 | Only the leading run of the nine reserved words is removed, plus a non-dynamic `-p` right after `time`. Removal happens inside function-name recognition only. When nothing remains, the unstripped sequence is judged. The name conditions after removal are the existing ones. Deny cases pin that the group following each non-definition shape is still judged | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | A command with a very long run of leading reserved words before `()` makes the new removal step slow enough that the hook does not answer in time (relates to NFR3, NFR4) | TM-2 | Removal walks the leading words in one pass and never rebuilds the remaining sequence for each removed word, so its cost stays linear in the number of words. Such a command is answered within the existing deep-input time limit | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-2 |
