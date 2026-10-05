# Threat Model: consult-litellm-contributor-tier

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md only (tier `reduced`, so no REQUIREMENTS.md; the design
step was skipped, so no DESIGN.md). The feature changes one orchestrator
procedure, the Codex consultation procedure in
`em-workflow/references/question-resolution.md` (steps 1 and 2). After the
change, the model of the litellm entry is chosen from the result of a local
consent check (FR1, FR2, FR4). It also adds unit tests (FR5). task0001
declares `auth` and `external-io`, which set TB-1's depth to deep.

The feature crosses one trust boundary. Consultation content leaves the
local machine for the external model service behind the litellm entry, and
the tier that receives it is now chosen from another process's output.
Information disclosure applies there (TB-1).

Categories considered at TB-1 and not recorded:
- Spoofing / Tampering of the consent signal: the consent record and
  `muse_guard.py` are local artifacts of the same party, and this feature
  does not change them (NFR4). The orchestrator fills in `{project_root}`
  from its own run state, not from external input.
- Elevation of privilege: no privilege changes hands.
- Repudiation: the feature adds no action whose attribution matters.
- Denial of service: if the consent value were wrongly derived as true, the
  worst outcome is that the existing muse_guard hook denies the call. TM-1's
  fail-closed rule also removes that path.

Accepted residual risk, with no new mitigation: if consent is revoked between
the step-1 check and a later litellm turn, the procedure does not check it
again (FR4, SPEC.md A-7). The existing muse_guard hook, which this feature
does not change (NFR4), is the backstop for that case.

## Trust Boundaries

### TB-1: Consultation content to the external model service, tier chosen by the consent check
Crossing: Consultation prompt content (feature documents and repository
excerpts) goes from the orchestrator through the wrapper to the external
model service behind the litellm entry. The tier it is sent under (the
contributor model or the standard model) is chosen from the output of
another local process, the consent check `muse_guard.py --list`.
Boundary files: `em-workflow/references/question-resolution.md`
Depth: deep (auth, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | Consultation content is sent under the contributor tier for a repository with no recorded consent because the consent result is derived wrongly. Examples: a failed check whose single-line error message is counted as the one-line consent output, or the contributor-tier invocation used without running the check (FR1, FR2, FR4) | TM-1 | Step 1 sets `contributor_consented` to true only when the check succeeds and prints one line. Empty output or any failure sets it to false, and failure takes precedence over the one-line rule. Step 2 then uses the standard-tier invocation. Step 2 offers the contributor-tier invocation only under the `contributor_consented` true condition | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, item TM-1 |
