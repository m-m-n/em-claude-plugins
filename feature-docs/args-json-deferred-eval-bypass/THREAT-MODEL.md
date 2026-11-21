# Threat Model: args-json-deferred-eval-bypass

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR8, NFR1-NFR5, the attack forms of
SPEC.md Overview), and in `em-workflow/hooks/destructive-guard.py` the
notion-pair exclusion, the per-chunk nameref answer with its outward walk and
cache, and the heredoc-body removal that precedes the per-chunk reading. Tier
full. Both tasks declare `input-handling`, so the one boundary is analysed at
deep depth.

The hook judges a Bash command string that the model proposes and that
untrusted content can steer, before Bash runs it and mcp-bridge hands it to an
MCP server process. This feature changes how that string is judged, so the
boundary is real and the SPEC.md attack forms are concrete. Nothing crossing it
identifies a party, needs an audit trail or carries a secret, so Spoofing,
Repudiation and Information disclosure get no row. The case table and the unit
tests are verification data, not boundary code.

Outside this feature: a function defined under the name of the command it
replaces (a function named `mcp-bridge` that hands the call's arguments to
another MCP tool) bypasses the exclusion without any shell-state change. It is
a different class from FR1-FR8, exists before this feature, and is listed under
IMPLEMENTATION.md Open Questions; no mitigation is recorded for it here.

## Trust Boundaries

### TB-1: Bash command text into the static judgment of the notion-pair exclusion
Crossing: a Bash command string proposed by the model, steerable by untrusted content, enters destructive-guard; the judgment decides whether the `--args-json` of an `mcp-bridge run --mcp notion --tool notion-create-comment` call is inspected before Bash runs the command and mcp-bridge passes it to an MCP server process.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A value stored in quoted or ANSI-C form is re-evaluated later in the current shell by an expansion (arithmetic or bracket arithmetic, a variable array subscript, `@P`, indirect, assigning or substring expansion), placed where a token-level reading does not look (double quotes, a here-string, an unquoted heredoc body, a nested expansion), and creates a nameref the static reading does not see; the exclusion then lets a destructive `--args-json` reach another MCP tool (FR1, FR4; SPEC.md Overview, first attack form) | TM-1 | The expansion-level reading counts these constructs over every lexer region of the chunk and over unquoted heredoc bodies, leaving out subshell bodies and data positions, and marks the chunk uncertain; the round-3 literal check stays in front of it | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Elevation of privilege | A command whose name the old denylist does not hold evaluates a string or writes a variable named by its argument (`fc`, `history`, `enable`, `compgen`, `complete`, `bind`, `read`, `printf -v`, `getopts`, `wait -p`, `unset`, `test -v`, a function defined in the chunk, an unclassified name), or an arithmetic command evaluates a stored value, and the exclusion still holds (FR2, FR3; SPEC.md Overview, second and third attack forms) | TM-2 | Command names are classified by a closed allowlist with conditional members; every other name, a name after `builtin` / `command` / `exec` / `time` / `!` included, the arithmetic command and any word that cannot be restored are uncertain | task0002 AC-1, AC-2, AC-4, AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Elevation of privilege | An allowed or declaration command re-evaluates a value as arithmetic or prompt text: `[[ ]]` arithmetic comparisons and `-v`, `declare` / `local` / `typeset` with `i`, assignment to an integer-attribute variable such as `OPTIND` or to `PS4` with xtrace enabled, a variable subscript in a declaration-builtin argument (FR1) | TM-3 | The command-level reading marks each of these triggers uncertain, in skipped assignment words and in declaration-builtin arguments as well as in the command itself | task0002 AC-3 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Denial of service | A crafted command (deep substitution nesting, many chunks, a large or unreadable unquoted heredoc body) makes the new readings raise or run long; a hook that fails does not deliver its deny (NFR1, NFR2) | TM-4 | Lexer failures in the new readings, the heredoc removal step included, read as uncertain without raising; the per-chunk answer is computed once and cached; the outward walk stays iterative | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-4 |
