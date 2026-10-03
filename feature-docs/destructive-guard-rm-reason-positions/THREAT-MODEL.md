# Threat Model: destructive-guard-rm-reason-positions

## Verdict
threats-identified

## Rationale

**What was inspected:**

- SPEC.md and REQUIREMENTS.md (tier: full; the design step was skipped, so there is no DESIGN.md);
- the rm pipeline of `em-workflow/hooks/destructive-guard.py` that the feature changes.

The only task declares `input-handling`, so the boundary below was analysed at deep depth.

**What the feature changes:** how the hook numbers rm invocations and operands, how it collects rm judgments across its two routes, and the reason text it returns. It adds no input source, no output channel and no filesystem or network access.

**The trust boundary:** one boundary is crossed. Bash command text, which can carry text planted by untrusted content, enters the hook. The hook's reason text goes back into the agent's context as guidance.

**STRIDE categories recorded.** Two categories realistically apply to the changed code at that boundary:

- **Spoofing:** planted text reaching the reason as if the hook wrote it.
- **Elevation of privilege:** the restructure weakening a verdict, so a destructive rm passes the guard.

**STRIDE categories not recorded:**

- **Repudiation:** no audit trail is in scope.
- **Information disclosure:** the reason only describes the agent's own command, and the feature adds no target text to it.
- **Denial of service:** numbering adds work linear in the number of rm invocations, the scanned text and the existing scan budget are unchanged.
- **Tampering:** the hook writes nothing.

## Trust Boundaries

### TB-1: Agent-supplied Bash command → destructive-guard → reason text read by the agent
Crossing: The command string of a PreToolUse event enters the hook. The agent authors it, and it can carry text from untrusted sources such as file names or fetched content. The hook's permission-decision reason goes back to the agent, which acts on it as guidance.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | Text planted in an rm target reaches the reason and is read by the agent as hook-authored guidance. The planted text can be an instruction string, a newline followed by a forged hook prefix, or control characters. The new risk is mainly the combined reason, which FR4 extends with per-target templates (NFR2, FR4). | TM-1 | Every reason, single or combined, is built only from hook-authored text: fixed sentences, position designations, the fixed substitution stand-in, the rm-root token from its fixed shape vocabulary, and deletion templates with the fixed placeholder. No other character of a target's text is copied into a reason. The hook's stdout carries no raw control character. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-6, TS-11) |
| Elevation of privilege | Any of the following could drop or weaken a decision: merging the two routes' judgments of a substitution-headed rm, deduplicating records by position, deferring rendering, or renumbering operands after `--`. A crafted command that is denied or asked today would then be allowed or downgraded (FR5, FR2, FR3). | TM-2 | Deduplication collapses only records for the same token of the same invocation, which carry identical tier and rule by construction. Tier and rule selection keeps today's priority. The set of judged targets and each target's judgment are unchanged; only numbers and reason text change. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-7; verdict and rule assertions of TS-1 to TS-6 and TS-12 to TS-15) |
