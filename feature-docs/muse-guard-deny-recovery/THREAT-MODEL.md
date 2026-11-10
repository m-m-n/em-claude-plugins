# Threat Model: muse-guard-deny-recovery

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at the full tier (design step skipped).
The change rewrites the agent-facing deny text of the muse_guard consent gate
(task0001, domains `auth`, `api-contract`: deep analysis of that boundary) and
adds a retryable `skip_reason` that lets a reviewer's result select the
orchestrator's next dispatch (task0002 to task0004, domain `api-contract`:
standard depth). No network call, persistence format or consent-store write
path is added or changed. The README and the test modules carry no boundary.
Every task declaring `auth` has its files in a Boundary files line below.

## Trust Boundaries

### TB-1: muse_guard deny output into the agent context
Crossing: an agent-issued Bash payload (untrusted command text and working directory) enters the PreToolUse hook; on a contributor-tier call without recorded consent the hook returns a deny plus DENY_CONTEXT, which the agent's model reads as guidance. At stake is the privilege of sending repository content to the contributor tier, which only the user may grant.
Boundary files: em-workflow/hooks/muse_guard.py, em-review/hooks/muse_guard.py
Depth: deep (auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | The rewritten deny text steers the agent to grant consent itself (the consent CLI's record mode) or to a workaround that reaches the contributor tier without the user's consent (FR6; REQUIREMENTS.md UC02) | TM-1 | DENY_CONTEXT keeps the clause that consent is recorded only by the user's interactive consent-skill run and the prohibition on the agent running the record mode; the reviewer branch ends with the `contributor_consent_missing` skip object, the other branch continues without the contributor tier and without a workaround; no instruction to switch entries or models remains. The Skip Semantics bullet forbids the reviewer recording or re-judging consent. | task0001 AC-1, AC-2; task0002 AC-3 | VERIFICATION.md TM-1 |
| Tampering | Hook input (command text, working directory) or values derived from it (project key, store path) embedded in DENY_CONTEXT would reflect agent-controlled text back into the agent context as hook-authored guidance (FR6; SPEC.md Security Considerations, Input Validation) | TM-2 | DENY_CONTEXT stays a constant whose only embedded value is `PLUGIN_SLUG` | task0001 AC-3 | VERIFICATION.md TM-2 |
| Elevation of privilege | Editing the deny path weakens the gate itself: a changed classification, a lost fail-open bound or an `ask` / `allow` decision lets a contributor-tier call through without consent (NFR1) | TM-3 | Only the DENY_CONTEXT constant and its comment change; classification, store read, fail-open, deny-only decisions, the four-field payload and DENY_REASON stay as at base | task0001 AC-5 | VERIFICATION.md TM-3 |

### TB-2: Reviewer skip object into orchestrator routing
Crossing: a reviewer subagent's result is untrusted output (the reviewer reads attacker-influenceable diff content); its `skip_reason` selects the orchestrator's next dispatch in Phase R2b.
Boundary files: em-workflow/references/review-protocol.md, em-review/references/review-protocol.md, em-workflow/references/review-phase.md, em-review/references/review-phase.md
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A reviewer, misbehaving or steered by text in the reviewed diff, returns `contributor_consent_missing` without a real deny to drop its perspective's review, or the walk keeps re-dispatching the denied entry (FR3, FR4, FR5) | TM-4 | R2b routes the value only to the next chain entry, never re-dispatches the same entry as plain `muse-spark`, counts the hop against the existing 2-hop budget; an exhausted chain takes the existing Claude fallback (em-workflow) or leaves the Claude reviewer standing (em-review); a result without a valid skip object takes the harness-level path | task0003 AC-2, AC-3; task0004 AC-2 | VERIFICATION.md TM-4 |
