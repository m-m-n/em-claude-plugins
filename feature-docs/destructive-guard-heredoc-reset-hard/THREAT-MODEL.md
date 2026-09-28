# Threat Model: destructive-guard-heredoc-reset-hard

## Verdict
threats-identified

## Rationale
Inspected inputs:
- SPEC.md (FR1-FR8, NFR1-NFR4, Assumptions)
- REQUIREMENTS.md
- IMPLEMENTATION.md D2, the batch-resolved interpretation of FR5
- the current heredoc handling in `em-workflow/hooks/destructive-guard.py`:
  `strip_heredocs()` and the rescan condition in `statements()`

The tier is `full`. The single implementing task declares `input-handling`
and `auth`, so TB-1 is analysed at deep depth.

destructive-guard.py is a permission gate. Its `allow` skips the auto-mode
classifier entirely, and its `deny` or `ask` stops the command. This feature
narrows which heredoc bodies the guard treats as executable. Today, a sink
word anywhere in the chunk makes a body executable. After the change, each
heredoc's own destination decides, with a conservative fallback whenever the
destination cannot be determined. So every recorded threat is a loss of
detection, plus the processing-cost threat that NFR3 names.

The task's other three files carry no trust boundary.
`destructive-guard-cases.json` is test data read only by the local test
runner. `plugin.json` and `marketplace.json` carry version metadata.

Accepted residuals, with no mitigation in this feature:
- Out of scope per the SPEC.md Assumptions:
  - A body written to a file and run by a later statement, such as
    `cat > s.sh <<'EOF' ... EOF` followed by `bash s.sh`.
  - Command substitutions inside an unquoted heredoc body.
- Outside decision B's command-word scope: a listed data command that runs
  a program named in one of its own options. An example is an inline
  `git -c alias.x='!bash' x <<'EOF'`. Parsing options per command is out of
  scope. Commands known to carry such options (`sort`, `rg`) were left off
  the data-command list.

## Trust Boundaries

### TB-1: Agent-issued Bash command text -> destructive-guard static permission decision
Crossing: the Bash command string that Claude Code hands to the PreToolUse
hook. The agent composes it, and untrusted content the agent has read can
steer it through prompt injection. The string crosses into the guard, where
an `allow` bypasses the auto-mode classifier and a `deny` or `ask` stops
execution.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling, auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A heredoc body that a shell executes is misclassified as data. The destructive statement inside it passes with an outright `allow` and the classifier is skipped (FR1, FR2, FR3) | TM-1 | The body is rescanned when any of these is a sink: the host statement's command word (the basename after the assignment / wrapper / grouping skip), a later stage of the same pipeline, an enclosing statement's command word, or a later stage of an enclosing statement's pipeline. The sink vocabulary is no smaller than the current SHELL_SINK, including versioned spellings. Each heredoc on a line is judged separately | task0001 AC-2, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Elevation of privilege | Body consumption over-reaches. A real statement after a heredoc's closing delimiter line, or the sink-bound body of a later heredoc on the same line, is swallowed as part of an earlier body and never checked (FR3, FR4) | TM-2 | Operators consume body lines in the order they appear, each only up to its own delimiter line. Text after the last delimiter line stays in the chunk and is checked as commands. An operator whose delimiter line never appears consumes nothing | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Elevation of privilege | The destination cannot be established, and defaulting to data would open a bypass that the current chunk-wide match closes (FR5, IMPLEMENTATION.md D2). This happens when the text does not lex; when the host command word is missing or statically unknown; when the host or an enclosing command word is neither a sink nor a known data command (an execution prefix outside the wrapper set such as `timeout` or `exec`, or an unknown command); or when a process substitution such as `tee >(bash)` could consume the body | TM-3 | An undeterminable heredoc falls back to the current chunk-wide sink match. A heredoc is data only when its host command word, and every enclosing command word, is on the closed data-command list (an enclosing statement made only of assignments is exempt) | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Elevation of privilege | Rewriting the heredoc stripping changes verdicts for shapes already pinned by existing deny / ask cases, silently weakening unrelated detection (FR7) | TM-4 | A line with a single heredoc operator strips exactly as it does today. No pre-existing case is removed or re-expected. The full expectation suite passes | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Denial of service | A command carrying many heredoc operators, terminated or not, makes heredoc processing super-linear. The hook exceeds its 10-second timeout and the guard's verdict for that command is lost (NFR3) | TM-5 | Heredoc processing cost stays proportional to input size. Body consumption only moves forward, and an operator whose delimiter line never appears does not trigger a re-search of the rest of the input for each operator | task0001 AC-8 | VERIFICATION.md Performance / Security Verification, TM-5 |
