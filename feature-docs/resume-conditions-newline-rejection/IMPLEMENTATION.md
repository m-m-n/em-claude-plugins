# Implementation Plan: resume-conditions-newline-rejection

## Overview

Split the self-contradicting shared own-rule bullet in the batch
structured-result SSOT into per-field rules, so a multi-line recovery
procedure inside `resume_conditions` becomes a legal, normal-form value,
and re-anchor the text-conformance matchers on the new wording. The change
is documentation-and-test only, plus the paired plugin version bump the
repository's rules require.

## Technology Stack

- **Prose SSOT**: Markdown, English, matching the surrounding prose style of
  the document under change.
- **Test framework**: Python standard library `unittest` (Python 3.14) —
  discovered from the repository-root `tests/` directory. No third-party
  import in test code (`test/README.md`).
- **Manifests**: JSON, parsed as JSON by tests — never pattern-matched.
- **New dependencies**: none. No library is added by this feature, so the
  license check has nothing to evaluate; `project.license` is `none`, which
  imposes no constraint on dependency licenses. No dependency license line
  is recorded because no dependency is introduced.

## Layer Structure

Three layers, with a one-directional dependency:

| Layer | Contents | Depends on |
|---|---|---|
| Prose SSOT | `em-workflow/references/batch-terminal-line.md` | nothing |
| Conformance tests | modules under `tests/` that read the SSOT and the manifests as text/JSON and assert on them | Prose SSOT, Distribution manifests |
| Distribution manifests | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | nothing |

Allowed direction: tests read documents and manifests. A document never
refers to a test module, and a manifest never refers to either. No runtime
script, hook or skill participates in this feature (see D3).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Matcher authoring convention | Every assertion helper that pins new wording or a new value is a named matcher paired with a negative proof and a non-vacuity guard | Precondition: the matcher receives raw text (or parsed JSON) read from the real artifact. Postcondition: for each matcher there exists (a) a forged sample that is otherwise well-formed and is rejected, and (b) a guard establishing the forged sample fails for the property under test — see D5 | task0001, task0002 |
| Plugin version value | The single version string both distribution manifests carry | Precondition: current value reads `0.1.84` in both. Postcondition: both carry the identical new string, on the `0.1.x` line, with patch strictly greater than `84`. Exactly one task writes it (D2) | task0002 (sole writer); task0001 must not touch either manifest |
| Declared file-set disjointness | The two tasks' file sets do not intersect | Precondition: each task plan lists its complete file set. Postcondition: neither task creates or modifies a file listed by the other; a needed file outside a task's own set is a reportable plan deviation, never a licence to expand | task0001, task0002 |

## Conventions

- **Document language**: English prose in the SSOT, matching its surrounding
  sections. Bullet style under the OWN-rules label, never renumbering into
  the five carried-over numbered constraints.
- **Test module naming**: `tests/test_<target>.py`; classes
  `Test<Behavior>`; methods `test_<condition>_<expected_result>`
  (`test/README.md`).
- **Assertion input**: assertions read the raw artifact from disk at test
  time and normalize whitespace through the module's existing helpers, so a
  literal inside a fenced block is still seen and the source file's
  line-wrap position never matters (NFR2).
- **Error-handling policy**: not applicable — this feature introduces no
  runtime error path. A malformed artifact surfaces as an assertion failure
  with the offending value in the message, never as a silent pass.
- **Logging policy**: not applicable.

## Cross-task Design Decisions

### D1: The SSOT wording and its conformance matchers ship in one task

The conformance module asserts literal substrings of the SSOT text. Splitting
the document edit and the matcher update into two tasks would leave each
task's worktree red on its own — the matcher task would assert wording that
its worktree's document does not carry — and would require pinning the exact
prose character-for-character as a cross-task contract. Both therefore belong
to task0001. Affected tasks: task0001 (owns both), task0002 (must not touch
either file).

### D2: The version bump is owned by exactly one task

task0002 is the sole writer of `em-workflow/.claude-plugin/plugin.json` and
of the em-workflow entry in `.claude-plugin/marketplace.json`. No other task
edits either file, so the two manifests cannot diverge through a merge.
Rationale: the pair must carry an identical value
(`.claude/rules/core-plugin-version-bump.md`), and a single writer makes that
structural rather than a convention two implementers must coordinate on.
Affected tasks: task0001 (must not touch), task0002 (owns).

### D3: No executable module changes

The executable consumer-constraint model that lives in the test suite applies
its line-terminator / terminal-control rejection to `branch` and `pr_url`
only — the five carried-over numbered constraints. It never applies that
rejection to `detail` or `resume_conditions`, so relaxing the OWN-rules
bullet needs no executable change and no emitter change. This is the concrete
content of NFR4's scope containment: the change set is the SSOT, the text
conformance module, the two manifests, and one new test module. Affected
tasks: task0001, task0002 (both state it as Out of Scope).

### D4: File-set derivation against the SPEC's File Structure

The SPEC's File Structure section lists four files. This plan derives one
additional file — a per-feature version-bump regression module under
`tests/` — because the SPEC's own TS7 requires the new version to compare
strictly greater than the base revision's value (`0.1.84`), and no existing
module pins a baseline that high (the highest existing baseline is `0.1.82`).
Without it, a forgotten bump would go undetected by the suite. Raising a
prior feature's baseline in place was rejected: each such module documents
its own feature's bump, and editing it would falsify that record. The added
file is test-only, so NFR4 still holds. Affected tasks: task0002 (adds the
file), task0001 (its declared file set stays as the SPEC lists it).

### D5: A forged sample must fail for the property under test

Every negative proof in this feature pairs with a guard establishing that
its forged sample is otherwise well-formed, so the rejection is attributable
to the property the matcher exists to check — never to an incidental defect
such as a missing anchor, an absent lookup key, or an unparseable value. A
forged sample therefore carries every structural element the matcher depends
on to locate what it inspects, and differs from the real artifact only in
the property under test. Affected tasks: task0001 (its matchers locate their
subject by a label anchor, so each forged sample carries that label),
task0002 (its matchers locate their subject by a manifest entry name and
parse a version string, so each forged sample is a well-formed entry with a
parseable version).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| New wording drifts from the matcher's expected literals, leaving the suite green against text that still contradicts itself | Medium | High | D1 keeps both in one task; the new negative proof uses the pre-change bullet verbatim, so a matcher too weak to reject the contradictory form fails its own proof |
| A negative proof passes for the wrong reason, so the matcher is never actually exercised | Medium | High | D5: every negative proof is paired with a well-formedness guard over the same forged sample |
| An edit reaches `## Result format` or `## Escaping` through a careless section boundary | Low | High | Both sections are pinned byte-identical by an existing regression test that must pass unmodified; task0001 states them as Out of Scope |
| The five carried-over numbered constraints get renumbered when the split bullet grows | Low | Medium | All new wording stays in bullets under the OWN-rules label; an existing test counts the numbered items in the carried-over half and requires exactly five |
| A pinned literal in the `## Field values` `resume_conditions` bullet is lost while rewording for consistency | Low | Medium | The bullet is preferably left untouched; if touched, task0001 enumerates the six literals that must survive |
| The version bump is forgotten, so the installed plugin cache keeps stale files | Medium | Medium | D4's new regression module pins a baseline of `0.1.84`, so an un-bumped tree goes red |
| The exemption is read as also relaxing U+2028 / U+2029 or the C0/C1 ranges | Low | High | The exemption set is stated as exactly CR, LF and TAB with their code points spelled out; everything else stays rejected (assumption A1) |

## Open Questions

- [ ] None blocking. The SPEC records no `tbd` requirement and no open
      question; assumptions A1-A8 are carried unchanged and all are
      reversible.
