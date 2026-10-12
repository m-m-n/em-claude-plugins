# Threat Model: sca-go-replace-direct-deps

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at tier `full`; the design step was
skipped. The feature's only new input handling is the parsing of `replace`
directives from the reviewed project's go.mod, which is attacker-influenceable
content. task0001 declares `input-handling`, so that boundary is analysed at
deep depth. The govulncheck stream is also untrusted, but its parsing is not
changed by this feature (only the direct set its module paths are matched
against grows), so no new threat arises at that boundary and it is not
recorded. Replace can only add paths to the direct set (FR4), so a crafted
replace cannot hide a require that was direct before.

## Trust Boundaries

### TB-1: reviewed project's go.mod -> Go direct-set parser
Crossing: go.mod content from the reviewed project (outside the plugin's
control) is read by `scan-dependencies.py`, whose direct set decides which
advisories become findings in a result consumed by the reviewer LLM.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A crafted or malformed replace line (glued `=>`, missing right side, extra tokens, odd quoting) raises during parsing or makes the go.mod unreadable, so the whole Go unit loses its findings (FR1, NFR3) | TM-1 | Replace recognition is total: a line not shaped as source [version] `=>` replacement [version] is ignored, no exception escapes, go.mod readability is decided as before and no skip reason is added | task0001 AC-5 | VERIFICATION.md Performance / Security Verification TM-1 (TS7, TS11) |
| Information disclosure | A local-directory replacement path (`../x`, `/x`, `C:\x`) steers the scanner into reading a file outside the reviewed project, such as another go.mod (FR3, NFR3) | TM-2 | Replacement paths are compared as strings only; nothing is resolved or opened from a replace directive; the only file read is the go.mod reached through the existing project-relative confinement | task0001 AC-3 | VERIFICATION.md Performance / Security Verification TM-2 (TS12) |
| Tampering | Text taken from go.mod replace directives is placed into a note, skip reason or other output field and reaches the reviewer LLM prompt as untrusted text (NFR3) | TM-3 | No new note or skip reason; notes stay counts-only; no text from replace directives appears in any output field | task0001 AC-6 | VERIFICATION.md Performance / Security Verification TM-3 (TS11) |
