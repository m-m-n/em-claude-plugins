# Task Plan: {taskNNNN} — {short title}

<!--
Template for feature-docs/{feature}/tasks/taskNNNN.md.
Written by implementation-planner. Read by exactly one implementer agent
together with IMPLEMENTATION.md (cross-task decisions).
Rules:
- Acceptance Criteria is MANDATORY and is the implementer's TDD contract:
  each criterion maps to at least one test; all tests passing = task done.
- No concrete code (same rule as IMPLEMENTATION.md): contracts, flows,
  responsibilities — never language-specific snippets or API calls.
-->

## Goal

{1-2 sentences: what this task delivers, stated as an outcome}

## Requirements

{SPEC.md requirement IDs this task implements, e.g. FR1, NFR2 — must match
workflow.yaml tasks.{taskNNNN}.requirements}

## Scope

### Files to Create
- `{path}` — {responsibility}

### Files to Modify
- `{path}` — {what changes}

<!-- The union of both lists must match workflow.yaml tasks.{taskNNNN}.files.
     The implementer stays within this file set; discovering a needed file
     outside it is a reportable plan deviation, not a license to expand. -->

## Design

{Component responsibilities, contracts (precondition/postcondition), and
processing flows for THIS task only. Cross-task decisions belong in
IMPLEMENTATION.md — reference them, do not restate them.}

## Acceptance Criteria (MANDATORY)

<!-- Each criterion must be objectively verifiable and translatable into a
     test. The implementer writes the tests FIRST (tdd-testing skill), then
     implements until all pass. -->

- [ ] AC-1: {verifiable criterion}
- [ ] AC-2: {verifiable criterion}

## Test Notes

{Task-level test strategy: which criteria map to unit vs integration tests,
edge cases worth covering, anything TDD-awkward (with the planned handling)}

## Out of Scope

{Explicit non-goals to keep the implementer from gold-plating}
