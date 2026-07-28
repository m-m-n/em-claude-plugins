# Implementation Plan: codex-reviewer temp-file isolation

## Overview

Add a temp-file uniqueness rule to both plugins' `codex-reviewer` agent
definitions, and a structural `unittest` that asserts the rule is present and
worded consistently in both.

## Technology Stack

- **Markdown**: agent definitions (`agents/codex-reviewer.md`) — the artifact
  the fix lives in.
- **Python 3 `unittest`**: the repository's only test framework
  (`test/README.md`); tests live in `tests/test_*.py` and read the markdown as
  text.
- **`mktemp` (coreutils)**: the mechanism the rule prescribes to the agent. No
  new dependency — the plugins already assume a POSIX shell environment.

New dependencies introduced: none. `project.license` is `none`, so no license
constraint applies.

## Layer Structure

Not applicable — the change is confined to plugin definition documents plus one
test file. No runtime layering is involved.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Temp-file discipline section | The prose block added to each `codex-reviewer.md` | Pre: the agent is about to write any temp file into the session scratchpad. Post: the file path was allocated per-invocation and cannot equal a concurrently-live sibling's path; on allocation failure the agent returns the standard skip object instead of proceeding | task0001 |

The section is authored once and mirrored into both plugin files with only the
plugin name adjusted, so the structural test can assert the same required
elements against both.

## Conventions

- **Section placement**: the discipline goes immediately before the existing
  "Execute Codex" step in each agent definition, because that is where the
  prompt has just been assembled and would be spilled to disk.
- **Wording parity**: the two files carry the same required elements. Only
  plugin-identifying words differ. This is what lets one test cover both.
- **Single source of truth**: the rule is stated only in the agent definitions.
  The review-phase dispatch prompts are deliberately not amended (NFR2) — a
  second copy would drift.
- **Test naming**: `tests/test_codex_reviewer_temp_file_isolation.py`, classes
  `Test<Behavior>`, methods `test_<condition>_<expected_result>`, per
  `test/README.md`.

## Cross-task Design Decisions

### D1: One task, not one task per plugin

The change spans two agent files, one new test, and two `plugin.json` version
bumps, but the test asserts over BOTH agent files. Splitting the agent edits
from the test would let the test merge into the integration branch while the
prose it asserts on is still unmerged, producing a red integration build for no
benefit. The work is small enough for one implementer session, so it is one
task.

### D2: `mktemp` rather than PID/`$RANDOM` interpolation

The incident was recovered with names modified by PID and `$RANDOM`. That makes
a collision unlikely but does not exclude it: two processes can compute the same
candidate name and both proceed, because computing a name and creating the file
are separate steps. `mktemp` with an `XXXXXX` template creates the file as part
of allocating the name, so a name is never handed out twice. The rule therefore
prescribes `mktemp` and treats PID/`$RANDOM` schemes as insufficient.

### D3: The rule is conditional, not mandatory

An agent that passes the assembled prompt straight to the wrapper as an argument
never touches the filesystem and has no collision to avoid. The rule is phrased
as "when a temp file is used" so that path stays compliant (FR6) rather than
being pushed into a pointless file write.

### D4: Version bumps

Both plugins change, so both `.claude-plugin/plugin.json` files get a patch-level
bump, per the repository's version-management rule in `CLAUDE.md`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The test asserts on exact wording and breaks on harmless rewording | Medium | Low | Assert on required elements (the mechanism name, the template marker, the prohibition, the per-invocation statement, the fail-closed route) rather than on whole sentences |
| The two files drift apart in later edits | Medium | Medium | The test checks both files against the same required-element list, so a one-sided edit fails |
| The rule is added but agents still improvise a fixed name | Low | High | Place the rule adjacent to the execution step so it is read at the moment of relevance, and state the failure it prevents so the instruction is self-justifying |

## Open Questions

- [ ] None.
