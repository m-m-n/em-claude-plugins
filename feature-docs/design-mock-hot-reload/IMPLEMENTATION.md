# Implementation Plan: design-mock-hot-reload

## Overview

Two Markdown documents of the em-workflow plugin change. The design skill's agreement loop (Step 4) and closing step (Step 6) gain a local dev server started in the background, its URL guidance, a fallback when the server cannot be used, and its stop through `TaskStop`. The designer agent's mock rules gain a `?state=<name>` state switch. New static tests under `tests/` pin both.

## Technology Stack

- **Documents**: Markdown skill definition (`em-workflow/skills/design/SKILL.md`) and Markdown agent definition (`em-workflow/agents/designer.md`).
- **Tests**: Python 3 standard-library `unittest`, run by `python3 -m unittest discover -s tests`.
- **New dependencies**: none. bun is named only as an example of a dev server command on the user's machine; the repository neither bundles nor requires it. `project.license` is `none`, so no license constraint applies.

## Layer Structure

| Layer | Document | Responsibility | May refer to |
|-------|----------|----------------|--------------|
| Procedure | `em-workflow/skills/design/SKILL.md` | What the main session does in Step 4 and Step 6: start, guide, fall back, restart, stop | Mock rules (by reference only) |
| Mock rules | `em-workflow/agents/designer.md` (Design Artifact Rules, Mockups item) | What a mock file contains, including the state switch | Nothing in the procedure layer |
| Tests | `tests/` | Static assertions on the two documents | Both documents, read-only |

Dependency direction: the procedure refers to the mock rules; the mock rules never mention the dev server or its lifecycle.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Mock state switch rule | Lets one mock show a single SPEC state chosen by the URL query | Owner: the Mockups item of designer.md (task0002). Pre: the mock lays out each SPEC state as a sibling section carrying `data-state="<name>"`. Post: with the query `state=<name>`, only the sections whose `data-state` value equals the query value literally are shown; with no query, or with a value no section carries, every state section is shown side by side as before. The value is used only for that literal comparison. The switch is one small inline plain script inside the mock, with no framework and no external request. design SKILL.md Step 4 (task0001) tells the user that `?state=<name>` shows one state and names designer.md's mock rules as where the rule lives; it does not restate the rule's details. | task0001 (reference), task0002 (owner) |
| Mock reload stance | Keeps the mock file self-contained while the browser updates on edit | The browser update on a mock edit comes only from the dev server's own update feature. A mock file holds no reload code. The update client a dev server injects while serving is not part of the file, so "no external requests" stays a rule about the file content. | task0001, task0002 |

## Conventions

- **Language**: new text follows the language of the section it is added to.
- **Protected wording**: wording that existing tests pin stays unchanged. In design SKILL.md this includes the occurrence count of the literal tool name `AskUserQuestion` (2, pinned by `tests/test_muse_consent_no_new_questions.py`); new text never contains that literal name. In designer.md this includes every phrase `tests/test_refitted_worker_agents.py` pins (autonomy declaration, Boundaries, write policy sentences, and the rest it checks).
- **Test files**: each task creates its own new test module; no new test file is shared between tasks. Tests read the documents from the repository, locate them the same way existing modules under `tests/` do, and scope each assertion to the section its acceptance criterion names. No test starts a process.
- **Pinned phrase that must change**: when an existing test pins a phrase the SPEC requires to change, the implementer reports it as a plan deviation instead of editing a test outside the task's files.

## Cross-task Design Decisions

### D1: designer.md owns the state switch rule

The rule is defined once, in designer.md's Mockups item. design SKILL.md Step 4 mentions `?state=<name>` to the user and points to designer.md for the rule. Affected tasks: task0001, task0002.

### D2: one new test module per task

task0001 creates `tests/test_design_skill_dev_server.py`; task0002 creates `tests/test_designer_mock_state_switch.py`. The two tasks share no file. Affected tasks: task0001, task0002.

### D3: reload comes from the server, never from the mock

Both documents state the Mock reload stance above: design SKILL.md when it describes the agreement loop, designer.md in the Mockups item. Affected tasks: task0001, task0002.

### D4: the designer agent starts no server

Starting and stopping the dev server lives only in design SKILL.md. designer.md gains no server step, and the designer agent's tools do not gain Bash. Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing test pins a phrase that Step 4 (FR1) or the Mockups item (FR4) must change | Low | Medium | Run the whole suite; report a conflicting pinned phrase as a plan deviation (Conventions) |
| New text adds a literal `AskUserQuestion` or a signal-sending command name to design SKILL.md | Medium | Medium | Conventions; task0001 acceptance criteria pin both |
| The example dev server listens beyond the local machine by default | Unknown | Medium | THREAT-MODEL.md TM-1 covers what the procedure controls; recorded as an open question |
| Hot reload cannot be checked by a unit test | High | Low | TS-7 is a manual check in VERIFICATION.md |

## Open Questions

- [ ] SPEC.md does not state whether the example dev server listens only on the local machine by default. TM-1 limits the procedure to not widening the listening address and to guiding only the local URL from the server output.
- [ ] NFR2 and NFR4 have no SPEC.md test scenario. VERIFICATION.md adds TS-9 and TS-10 for them.
