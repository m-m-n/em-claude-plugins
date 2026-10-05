# Threat Model: codex-repo-hook-trust

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md (tier: full) and the metadata of the
feature's single task, task0001 (domains: auth, input-handling, external-io,
config-infra). The feature sits on a trust boundary by construction: the
em-workflow and em-review Codex wrappers launch Codex inside a repository
under review while passing the hook-trust bypass, so configuration authored
by that repository can turn into commands run with the reviewing user's
privileges (TB-1). The investigation and the tests the feature adds also
handle the user's Codex credentials and trust configuration and produce a
record that is committed and pushed, which is a second boundary (TB-2).
Both boundaries are analysed at deep depth: auth (hook trust, project trust
entries, credentials), input-handling (repository-authored configuration
read by Codex) and external-io (launching the Codex process and, for the
real-Codex test, its model backend).

No boundary is recorded for the Codex model backend itself: the feature
changes neither what the wrappers send to it nor how its output is used.

TB-1's mitigations are conditional on the FR1 outcome, as SPEC.md's data
flow is: TM-1 is realized either by a launch change on every route where
repository hooks were observed executing (FR3), or by a positively
controlled, recorded observation that no route executes them (FR2, FR4).

Post-decomposition consistency: task0001's boundary-implementing files (both
wrappers, the new test module, the findings record) appear in the Boundary
files lines below. Its remaining files — the four existing wrapper test
modules and feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md — pin
or document the TB-1 outcome and implement no boundary themselves.

## Trust Boundaries

### TB-1: Repository under review → Codex launched by the wrappers
Crossing: hook definitions authored by the repository under review, placed in
the Codex configuration of the working directory the wrappers pass to Codex
(for example .codex/), are read by Codex 0.160.0 and run as processes with
the reviewing user's privileges; the wrappers pass the hook-trust bypass, so
no trust confirmation intervenes.
Boundary files: em-workflow/scripts/run_codex_exec.sh, em-review/scripts/run_codex_exec.sh, tests/test_codex_repo_hook_trust.py
Depth: deep (auth, input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Repository-authored hook definitions execute arbitrary commands with the reviewing user's privileges on a wrapper launch route without any trust confirmation, including the --litellm route when the user config trusts the project (FR1, FR3) | TM-1 | Every route on which FR1 observes repository-hook execution launches Codex with a protective specification under which working-directory hooks are not executed, in each wrapper that has the route; a route is classified as not executing only on positively controlled evidence, and the classification is recorded (FR2) and carried into codex-interactive-guard-hook TB-3 (FR4) | task0001 AC-1, AC-3, AC-5, AC-6, AC-7 | VERIFICATION.md TM-1 item (TS-1, TS-2, TS-4, TS-5, TS-6) |
| Tampering | A repository-authored definition for the same hook key displaces or merges with the wrapper's own interactive-guard PreToolUse registration, or the launch change that cuts the working-directory layer also stops the guard from firing, silently disabling the guard on a route (FR3, A1, A2) | TM-2 | The wrapper's own guard registration stays in every route's argv; the findings record states whether that registration overrides a same-key repository definition; any route on which the guard cannot fire together with the protective specification is recorded in codex-interactive-guard-hook TB-3 (A1) | task0001 AC-1, AC-4, AC-7 | VERIFICATION.md TM-2 item (TS-1, TS-4, TS-6, TS-10) |

### TB-2: User's Codex home and credentials → investigation, tests and committed record
Crossing: credentials (LITELLM_API_KEY, Codex authentication), project trust
entries and the litellm profile cross from the user's environment into the
probe and test processes; probe commands, configuration and outputs cross
into a findings record that is committed and pushed to a pull request, and
into test output.
Boundary files: tests/test_codex_repo_hook_trust.py, feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md
Depth: deep (auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | Credential values are captured into the committed findings record (recorded commands, configuration, environment) or into wrapper output and test diagnostics (NFR5) | TM-3 | Records refer to credentials only by variable name or placeholder; the stub test sets a sentinel credential value and asserts it is absent from the wrapper's captured output | task0001 AC-2, AC-5 | VERIFICATION.md TM-3 item (TS-1, TS-12) |
| Tampering | Probe or test launches write project trust entries, sessions or profile changes into the user's real Codex home, altering which directories the user's own Codex trusts (NFR1) | TM-4 | Every probe and test launch runs with HOME and CODEX_HOME pointed at temporary directories that alone hold the trust entries, profiles and credentials; the stub test asserts the environment the launched codex sees points at those directories | task0001 AC-2, AC-5, AC-6 | VERIFICATION.md TM-4 item (TS-1, TS-2, TS-8) |
