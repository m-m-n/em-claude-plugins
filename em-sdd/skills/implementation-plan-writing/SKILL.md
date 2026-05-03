---
name: implementation-plan-writing
description: IMPLEMENTATION.md and VERIFICATION.md writing rules, templates, and self-verification checklists. Preloaded by implementation-planner agent.
disable-model-invocation: true
---

# Implementation Plan Writing Guide

## Absolute Rule: No Concrete Code

**CRITICAL: Implementation plans describe WHAT to build and contracts, NEVER HOW to code it.**

### Allowed

- **Function signatures with contracts** (preconditions/postconditions):
  ```
  extractSubdirName(path) -> baseName
    Precondition: path is not root "/"
    Postcondition: Returns the last segment of path
    Example: "/home/user/docs" -> "docs"
  ```
- **Diagram-convertible flow descriptions** (numbered steps, branch notation)
- **Behavioral-level condition descriptions** ("if X then Y behavior")
- **Component responsibility tables** (Component, Responsibility, Pre/Postcondition)

### Not Allowed

- Language-specific code blocks (`rust`, `go`, `typescript`, etc.)
- Specific library/API calls (`filepath.Base`, `Channel`, `wasm_bindgen`, `invoke`, `js_sys::Function`, etc.)
- Copy-paste-ready snippets, struct/enum definitions, match/switch arms
- Exhaustive step-by-step implementation order (use phases with 5-7 high-level steps max)

### Conversion Guide

| Bad (NOT ALLOWED) | Good (ALLOWED) |
|-------------------|----------------|
| `filepath.Base(p.path)` | "extract last segment of path" |
| `filepath.Dir(p.path)` | "derive parent directory path" |
| `for i, entry := range entries` | "iterate through entries to find matching name" |
| `tea.Cmd` | "async command for background loading" |
| `filterHiddenFiles(entries)` | "filter entries based on visibility settings" |
| `Channel<Vec<u8>>` | "binary data channel from backend to frontend" |
| `#[wasm_bindgen] impl Foo { pub fn bar() {} }` | "expose bar method to JS via WASM binding" |

---

## IMPLEMENTATION.md Template

```markdown
# Implementation Plan: {Feature Name}

## Overview
{1-2 sentence summary of what will be implemented}

## Objectives
- {Primary objective 1}
- {Primary objective 2}

## Prerequisites

### Development Environment
- {Required tools and versions}

### Dependencies
- {External dependencies that must be installed}
- {Internal components that must exist}

## Architecture Overview

### Technology Stack
- **Language**: {detected from project}
- **Framework**: {detected from project}
- **Key Libraries**: {name - purpose}

### Design Approach
{High-level architectural decisions}

### Component Interaction
{How components communicate and depend on each other}

## Implementation Phases

### Phase N: {Phase Name}

**Goal**: {What this phase achieves - specific and measurable}

**Files to Create**:
- `path/to/file` - {Responsibility description}

**Files to Modify**:
- `path/to/existing` - {What changes}

**Key Components**:

| Component | Responsibility | Precondition | Postcondition |
|-----------|----------------|--------------|---------------|
| {Name} | {Responsibility} | {Precondition} | {Postcondition} |

**Processing Flow** (diagram-convertible):
1. {Step}
   - Condition A -> {Process A}
   - Condition B -> {Process B}
2. {Step}

**Implementation Steps** (5-7 max per phase):
1. **{Step Title}** - {What to implement at responsibility level}
2. **{Step Title}** - {What to implement at responsibility level}

**Dependencies**: Requires {X}, Blocks {Y}

**Testing Approach**:
- Unit: {scenario descriptions}
- Integration: {scenario descriptions}
- E2E: {automatable scenarios}
- Manual: {human-judgment scenarios}

**Acceptance Criteria**:
- [ ] {Verifiable criterion}

**Estimated Effort**: {small/medium/large}

---

## Complete File Structure
{project-root tree with purpose descriptions}

## Testing Strategy
- Unit: core logic 80%+, critical 90%+
- Integration: end-to-end workflows
- E2E: project-specific E2E framework (if any)
- Manual: items requiring human judgment

## Dependencies
| Package | Version | Purpose |
|---------|---------|---------|

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|

## Open Questions
- [ ] {From specification}
- [ ] {Implementation-specific}

## Success Metrics
- [ ] Functional completeness
- [ ] Quality metrics
- [ ] Performance metrics
```

---

## VERIFICATION.md Template

```markdown
# Verification Document: {Feature Name}

## Overview
**Feature**: {name}
**SPEC.md**: `{path}`
**IMPLEMENTATION.md**: `{path}`

## Build Verification
- Command: {from sdd.yaml or project detection}
- Expected: exit code 0, no errors

## Test Verification
- Command: {from sdd.yaml or project detection}
- Coverage target: minimum {X}%, target {Y}%

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-N | {scenario} | {outcome} | Unit/Integration |

## Code Quality Verification
- Format: {command}
- Static analysis: {command}

## File Structure Verification
### Files to Create
- `{path}` - {purpose}

### Files to Modify
- `{path}` - {changes}

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-N | {criterion} | {method} |

### Functional Requirements Coverage
| Requirement | Phase | Verification |
|-------------|-------|--------------|
| FR-N | Phase N | {method} |

## E2E Testing
{Project-specific E2E framework, if any. Otherwise omit this section.}
- [ ] {automatable scenario}

## Manual Testing (E2E Not Possible)
- [ ] {human-judgment scenario}

## Performance Verification (if applicable)
- {requirement}: expected {threshold}

## Security Verification (if applicable)
- [ ] {security check}

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|--------------|--------|
```

---

## Pre-Save Self-Verification Checklist

**MANDATORY: Verify ALL before saving. If any check fails, rewrite before saving.**

### Code Rules Compliance
- [ ] No language-specific code blocks with function bodies
- [ ] No specific library API calls (e.g., `filepath.Base`, `tea.Cmd`, `Channel`)
- [ ] No copy-paste-ready code snippets
- [ ] No detailed loop/conditional structures in code form
- [ ] Implementation steps describe WHAT, not HOW to code

### Abstraction Level
- [ ] Processing flows are diagram-convertible (boxes and arrows style)
- [ ] Function descriptions use contracts (precondition/postcondition format)
- [ ] Conditions described at behavioral level ("if X then Y behavior")
- [ ] No exhaustive step-by-step implementation order (use phases instead)
- [ ] No more than 5-7 high-level implementation steps per phase

### Content Quality
- [ ] Each phase has clear goal and deliverables
- [ ] Components described by responsibility, not implementation details
- [ ] Test strategy describes scenarios in table format, not test function signatures
- [ ] Dependencies described at component level, not code level
- [ ] No "Change History" section (git provides version history)
