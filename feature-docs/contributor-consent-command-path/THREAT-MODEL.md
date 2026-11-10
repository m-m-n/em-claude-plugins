# Threat Model: contributor-consent-command-path

## Verdict
threats-identified

## Rationale

Inputs inspected: SPEC.md, REQUIREMENTS.md, the two contributor-consent skill
copies, and the test module that task0001 changes. The tier is full. task0001
declares the domains `auth` and `ui`, so TB-1 is analysed at deep depth.

The feature rewrites the skill's regression test, and FR1 allows it to edit both
skill copies. The skill turns the user's answer into a write to the muse-spark
consent store, made through the guard CLI. The store decides whether this
repository's diffs may go to the contributor tier. That crossing is TB-1.

FR2 removes the old exact-count assertions, which pinned where the mutating flags
may appear. The replacement checks must keep that guarantee. This is the threat
recorded under TB-1.

Not recorded:

- The test module reads only the two in-repository skill copies and strings
  built inside the module. It crosses no trust boundary of its own.
- An unresolved environment-variable reference in a user-visible line (FR4)
  breaks the consent flow but grants nothing. It is a functional defect and has
  no STRIDE category.
- The project key that the skill's commands pass to the guard is not changed by
  this feature.
- NFR5 is a project-wide documentation rule that applies to every change. This
  feature adds no path that carries local-environment text into the repository.
  NFR5 is therefore verified as a plain check (VERIFICATION.md TS-13), not as a
  mitigation.

Consistency with task domains: task0001 declares `auth`. Its files include the
two skill copies, which are the boundary files of TB-1. Its third file, the test
module, implements TM-1 and is not a boundary file.

## Trust Boundaries

### TB-1: User consent answer to consent-store write
Crossing: the interactive user answers the skill's single question (step 4).
The skill then writes or removes this repository's key in the consent store,
through the guard CLI (step 5). The store decides whether the repository's diffs
may be sent to the external contributor tier.
Boundary files: em-workflow/skills/contributor-consent/SKILL.md, em-review/skills/contributor-consent/SKILL.md
Depth: deep (auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A record command can be reached from somewhere other than the explicit consent answer: the decline or keep answer, a dismissed question (step 6), or a block outside step 5. It records consent the user did not give and lifts the contributor-tier refusal for the repository. An edit of the skill copies allowed by FR1 can introduce it. Dropping the exact-count assertions (FR2) removes the old check that caught it. Related: FR1, FR3, FR4. | TM-1 | Structural checks on both copies (FR3, FR4, NFR4). The consent branch is bound to exactly one skill-executed record command. The revoke branch is bound to exactly one remove command. The decline and keep branches and step 6 are bound to none. Every fenced block must classify as one of the two kinds, so a guard command placed anywhere else fails. Each check has a failing synthetic case. | task0001 AC-2, AC-3, AC-5 | VERIFICATION.md, Performance / Security Verification, TM-1 |
