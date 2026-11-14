# Threat Model: design-mock-hot-reload

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at the full tier (DESIGN.md is absent; the design step was skipped). The feature changes two Markdown documents: the design skill procedure (`em-workflow/skills/design/SKILL.md`), which gains a local dev server started in the background, its URL guidance and its stop, and the designer agent's mock rules (`em-workflow/agents/designer.md`), which gain a URL-query state switch run by an inline script inside each mock. Two trust boundaries result: the dev server as a separate process that serves the mocks over local HTTP and whose output is read back and relayed to the user (TB-1), and the URL query read by the mock's script (TB-2). Both are analyzed at deep depth: task0001 declares external-io (TB-1) and task0002 declares input-handling (TB-2).

Considered and not recorded: the update client a dev server injects while serving is a property of the server and not part of the mock file (REQUIREMENTS.md A-1); the feature adds no write destination (NFR4), so no tampering with project files is recorded; the mock paths given to the server are the feature's own mock files chosen by the skill, so no command-line injection is recorded.

Domain consistency after task decomposition: every task that declares auth, input-handling, external-io or data-persistence has a file on a Boundary files line (task0001 on TB-1, task0002 on TB-2).

## Trust Boundaries

### TB-1: Local dev server process
Crossing: the target feature's mock files, served by a separate background process (the local dev server) to the browser over HTTP; that process's output (its `url` / `Routes` lines) read back into the session and relayed to the user; the process lifecycle controlled from the session (start in Step 4, stop before a restart and in Step 6).
Boundary files: `em-workflow/skills/design/SKILL.md`
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | The served mocks reach parties beyond the local machine when the server is started with a wider listening address, or when a non-local URL from its output is relayed to the user (NFR5) | TM-1 | Step 4 presents the server as local development use, starts it with no fixed port and no option or address that widens where it listens, and relays only the local URL taken from the server output | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1) |
| Denial of service | Stopping the server with a signal-sending command matched by name or pattern can terminate unrelated processes, the session's own ancestors included; a server that is never stopped keeps holding its port and serving after the loop (NFR1, FR2) | TM-2 | The server is stopped only with `TaskStop` on the task that `run_in_background` started, before a restart and in Step 6; no signal-sending command appears anywhere in design SKILL.md; a task that has already ended is not stopped by any other means, and Step 6 continues | task0001 AC-3, AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-2, TS-6) |

### TB-2: URL query read by the mock's script
Crossing: the value of the `state` query parameter, set by whoever composes the mock URL, read by the inline script inside the mock page, whether served by the dev server or opened from the file.
Boundary files: `em-workflow/agents/designer.md`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A crafted `state` value that the script inserts into the page, or uses to compose markup, a selector or code, injects content into the mock page, or makes the switch fail with every section hidden instead of the all-states fallback (FR4; SPEC.md Security Considerations, Input Validation) | TM-3 | The designer.md Mockups item requires the script to use the value only in a literal equality comparison with each section's `data-state` value, never inserting it into the document or composing markup, selectors or code from it, and to hide nothing unless at least one section matches | task0002 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-3) |
