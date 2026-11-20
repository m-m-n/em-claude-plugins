# Threat Model: args-json-quoting-bypass

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier `reduced`, so SPEC.md is the requirements source;
no DESIGN.md) and the `mcp-bridge run --args-json` step of
`em-workflow/hooks/destructive-guard.py` that the SPEC changes: the
notion-pair exclusion, the `=`-form name reading, the two word readers and the
anchor lookup of the collaborator. Every task declares `input-handling`, so the
one boundary below is analysed at deep depth.

The feature is a fix to a security gate: each threat below is one of the
review findings the SPEC takes in (FR1 to FR5) or the regression its goal
names (legitimate notion calls turned into denies). Mitigations exist only for
those recorded threats.

Accepted residual risks, recorded and not mitigated here:

- O2 (8) (FR6, A6): a value word whose expansion yields a word count other
  than one shifts where mcp-bridge reads flags and values and can hide a later
  `--args-json` value. The SPEC records it as out of scope; it keeps its
  current verdict and is not sent to ask. TS-12 pins that verdict.
- A flag-position word holding the FR3 form keeps the existing FR11
  flag-word behaviour (A10, finding 328945641695048d, out of scope).
- The round-4 medium findings the SPEC lists as not handled.

Domain consistency: all four tasks declare `input-handling`, and each of them
lists `em-workflow/hooks/destructive-guard.py`, the boundary file of TB-1. Their
other files (the runner case table and the unit-test module) hold tests only
and implement no boundary.

## Trust Boundaries

### TB-1: Bash command text into the destructive-guard reading of `mcp-bridge run`
Crossing: a Bash command string written by the agent, whose output can be
steered by untrusted text it has read, crosses into the hook's static
analysis. The hook decides whether the command runs unattended, including the
shell command that the `--args-json` value hands through mcp-bridge to an MCP
tool that runs it in another process.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A `--format`, `--session` or `--args-json` value word of a notion-pair statement written as an unquoted expansion, a brace form or an `@`-form array expansion splits into extra flag words, so the hook excludes the statement as the notion pair while mcp-bridge sends the value to another MCP tool that runs a shell (finding 3f7145c6c8c0b26a; FR1) | TM-1 | The notion-pair exclusion applies only when every such value word is single-word-certain; any other statement goes to the normal flag reading, which decodes and inspects its `--args-json` value | task0001 AC-1, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Denial of service | Narrowing the exclusion too far turns legitimate notion-comment calls into denies, which stops unattended runs (the review-loop regression on legitimate calls; FR1, SPEC AC-2) | TM-2 | Quoted expansions, single-quoted values and ANSI-C values stay single-word-certain; the existing notion-pair allow cases stay allow | task0001 AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-2 |
| Elevation of privilege | An unquoted backslash-escaped `=` in a flag word whose value part is not static is not taken as the separator, so the flag reading stops and a later static `--args-json` value is not inspected (finding f16e5bb8d5da2621; FR2) | TM-3 | The name-part reading takes an unquoted backslash-escaped `=` as the separator, skips only the non-static value and reads on | task0002 AC-1, AC-2 | VERIFICATION.md, Performance / Security Verification, TM-3 |
| Tampering | A `$` followed by line continuations and a character that starts an expansion is restored as a literal `$`, so the hook inspects a command text that differs from what Bash passes on (finding dc2fdf65ce30d198; FR3, FR7) | TM-4 | Such a word is Unrestorable and holds the `args-json-unrestorable` ask (deny under batch); the masking-stop reading treats it as undeterminable | task0003 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-4 |
| Elevation of privilege | A `$` followed by a non-ASCII character is read as an expansion, so a static value carrying a destructive top-level `command` is skipped as not static (finding f35ed060564bcf20; FR4) | TM-5 | Both word readers treat `$` before a non-ASCII character as a literal `$`, so the value is restored, decoded and inspected | task0003 AC-4, AC-5 | VERIFICATION.md, Performance / Security Verification, TM-5 |
| Denial of service | Many `--args-json` values make the per-value anchor lookup quadratic in the statement size, which can push one hook evaluation past its timeout (findings 0379cf2eb7ad4e92 / 9981fd673b28e7e4; FR5, NFR1) | TM-6 | The anchor is looked up only for values that queue something, through a span-to-index map built at most once per call | task0004 AC-1, AC-2 | VERIFICATION.md, Performance / Security Verification, TM-6 |
