# Threat Model: codex-guard-backquote-comment-undecidable

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR6, NFR1-NFR3), and the decision path of
`codex-hook-interactive-guard.py` (both copies) that this feature changes: how the reader ends
on `_Undecidable`, the nested `-c` walk and the top-level entry. Tier: full. The design step was
skipped (no UI). The only task, task0001, declares `input-handling`, which sets TB-1 to deep
depth; no task declares `auth`, `external-io` or `data-persistence`.

The guard is a policy control. It reads a command string that the Codex agent composed (LLM
output, which content the agent has read can steer) and decides whether to deny an interactive
launch. That string entering the parser is the only trust boundary. The feature adds no file,
network, process or environment access (NFR2) and leaves the deny output unchanged (NFR3), so it
creates or changes no other boundary. No Information disclosure row: the deny reason text does not
change and does not echo the command. `tests/test_codex_hook_interactive_guard.py`, also in
task0001's files, runs the hooks as child processes inside the test suite only. It is not a
boundary of the shipped guard, so no `Boundary files` line names it.

Three threats are recorded at TB-1:
- A launch placed before an undecidable fragment escapes the deny. This is the defect the feature
  fixes.
- Crafted input exhausts the guard's resources through the new checkpoint path.
- A checkpoint placed before the shell has finished a command causes a false deny.

## Trust Boundaries

### TB-1: Codex-composed command string into the guard parser
Crossing: the `tool_input.command` string of a Codex PreToolUse(Bash) call. The Codex agent
composes it, and untrusted content the agent read can influence it. It enters the guard process on
standard input. The reader and the nested `-c` walk read it and decide between a deny and no
output.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An interactive launch on a line before a fragment that makes the string undecidable passes with no output, so a launch the policy forbids runs. Examples are the FR1 reproduction, or an unbalanced quote added after the launch line. bash runs the earlier line before it reaches the later syntax error (A1). This applies to the hook command and to every nested literal `-c` string (FR2). | TM-1 | When reading stops at `_Undecidable`, the guard judges the commands settled up to the last checkpoint, in the normal walk order. Nested `-c` strings and NESTED_READ_LIMIT apply to them as usual. This holds at the top level and at every nesting level (FR2). | task0001 AC-1, AC-2 | VERIFICATION.md TS-1, TS-2, TS-3; Performance / Security Verification item TM-1 |
| Denial of service | A crafted string makes the new path expensive, so the guard runs past its time budget or exhausts the call stack (NFR1, NFR2). Ways to do this: very many checkpoint newlines; very many or deeply nested groups to settle before the last checkpoint; nested undecidable strings whose checkpoint commands hold further `-c` strings. | TM-2 | Recording a checkpoint stores counts only, in constant time per newline. The groups opened before the checkpoint are settled in one pass that visits each group once. No recursion is used. An undecidable nested string is counted at its full length toward NESTED_READ_LIMIT before it is parsed. An unexpected error on the new path is contained as before: the nested handler for the general exception class neither returns nor raises, and at the top level the hook gives no output. | task0001 AC-5 | VERIFICATION.md TS-6, TS-7; Performance / Security Verification item TM-2 |
| Denial of service | A checkpoint is placed before the shell has finished a command: a pipe still pending, a `&&` / `||` continuation, an open group, or a heredoc body not yet read. Or the commands before the checkpoint take connection and skip differently from a full read. Either way a connected launch, a function body or a heredoc body line is judged as a standalone launch. The false deny blocks a legitimate command and stalls the Codex run (FR2, FR3). | TM-3 | A newline is a checkpoint only when all four FR2 conditions hold. A pending pipe or a `&&` / `||` continuation persists over blank lines, comment-only lines and heredoc bodies until the next command is settled. The commands before the checkpoint take connection and skip from the groups opened before it, by the same rule as a full read. A string with no checkpoint, and every existing CASES row, keep their verdict (FR3). | task0001 AC-3, AC-4 | VERIFICATION.md TS-4, TS-5; Performance / Security Verification item TM-3 |
