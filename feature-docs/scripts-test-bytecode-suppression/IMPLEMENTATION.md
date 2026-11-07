# Implementation Plan: scripts-test-bytecode-suppression

## Overview

Every place in `tests/` that loads a file under `em-workflow/scripts/` into the
test process turns bytecode writing on only for that load and puts the
caller's value back, and the one child-process launch that loads a sibling
script carries bytecode suppression in its own arguments. Each task also adds
probe checks that prove the behavior of its own load sites.

## Technology Stack

- **Language / Framework**: Python 3, standard-library `unittest`
  (test/README.md).
- **Key libraries**: none. No new dependency is introduced; every change uses
  the standard library only (NFR3). `project.license` is `none`, so there is
  no license constraint, and there is no new dependency license to record.

## Layer Structure

| Layer | Responsibility | May depend on |
|-------|----------------|---------------|
| Scripts under `em-workflow/scripts/` | The code under test. Read-only for this feature (NFR1). | — |
| Existing test modules in `tests/` | Load a script by file path (an "in-process load", REQUIREMENTS.md section 13) and test it. Each loader gains bytecode suppression. | Scripts (by file path) |
| Probe test modules in `tests/` (new, one per family task) | Load existing test modules by file path and drive each listed loader against a probe module in a test-owned temporary directory. | Existing test modules (by file path), never the scripts directly |

No layer imports another by module name; every cross-layer use is a load by
file path.

## Shared Components

No code component is used by more than one task. Each task edits a disjoint
set of files, and each probe test module covers only the load sites of its
own task. The rules every task applies to its own files are pinned under
Conventions below so the four tasks produce the same shape independently.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| None shared | — | — | — |

## Conventions

### C1. Suppression form at an in-process load site

- Pre: the caller's bytecode-writing flag (`sys.dont_write_bytecode`) holds
  any value, True or False.
- During: the flag is True for the whole execution of the loaded module's
  body.
- Post: on every exit — normal return or an exception raised by the module
  body — the flag holds exactly the value it had when the loader was
  entered, and the exception, if any, reaches the caller unchanged.
- Form: record the current value, set True, run the module body in a
  protected block, restore the recorded value when the block exits. This is
  the form of the existing precedents (`load_hook` in
  `tests/test_destructive_guard_extglob_units.py`, `load_hook` in
  `tests/test_codex_hook_tty_reaper.py`). Building the spec and the empty
  module object may stay outside the protected block; the restore must cover
  the body execution.
- Placement: written inline in each loader (decision D1). Each load site does
  its own suppression and never relies on a value another module left behind
  (FR3).

### C2. Loader interface is preserved

A loader's name, parameters, default values, the module name it passes to the
spec, its memoization (a module-level cache it fills on first use), and its
return value (a module object of the loaded file) stay exactly as at the base
commit. Only the body of the loader changes. The path constant a loader reads
keeps its name and is still read when the loader runs, so a probe check can
redirect it for one call.

### C3. Probe-check observations

Every probe check (the three family probe modules and the in-file probe of
the report-name-entry task) makes the same observations for each load site,
each for the starting values False and True:

- O1: a probe whose body records the flag sees True.
- O2: after a normal return, the flag equals the starting value.
- O3: a probe whose body raises makes the loader raise that same error, the
  error text shows the flag was True inside the body, and afterwards the flag
  equals the starting value.
- O4: after the loads, the probe's own directory holds no `__pycache__`.

Rules for every probe check:

- The test sets the starting value itself before each call; it never relies
  on the inherited value (in a whole run the inherited value is already True,
  because `tests/test_merge_ci_wait.py` sets it at module level and never
  restores it).
- The flag value found at test start is restored on every exit of the test —
  pass, fail or error — by a cleanup registered before anything else.
- Probes live in a temporary directory owned by the test. A probe is never
  placed under, and a loader is never aimed at, any path under `em-workflow/`.
- The redirect (a path constant, a root constant, a path argument, a memo
  cache) is replaced for the duration of one loader call only.

### C4. Loading existing test modules from a probe module

- Lazy: nothing is loaded when the probe module is imported (the record check
  in `tests/test_tests_yaml_id_resolution.py` imports test modules without
  running them). Targets are loaded when the probe tests run, once per class.
- By file path, under a private module name that no discover run, no
  `tests.`-prefixed run and no other test uses.
- With the flag forced True while the target module's body runs and the
  previous value restored afterwards, so a target's module-level load of a
  real script writes nothing even while that target's loader is still
  broken, and a target that sets the flag at module level does not leak it.
- The listing of `em-workflow/scripts/` (recursive) taken before the probe
  class loads its targets equals the listing taken after its tests.
- The site table is not allowed to be silently empty: the probe module checks
  that its table has exactly the row count its task plan states and that
  every named loader and redirect attribute exists on the loaded target.

### C5. Boundaries every task keeps

- Changes are confined to `tests/`; no file under `em-workflow/` changes
  (NFR1).
- The process-wide `os.environ` is never written, deleted from or patched,
  not even temporarily (NFR2).
- Only standard-library modules are imported; no test module imports another
  test module by name (NFR3, and the existing checks described in D1).
- No existing assertion and no existing tested behavior changes (NFR4).
  Allowed edits to an existing module: the loader body, an added
  standard-library import the loader needs, and (task0004 only) the launch
  arguments of its child-process helper plus new test classes.
- New file names start with `test_`, are not prefixed `test_sca_`, and do
  not match the report-artifact name rule.

## Cross-task Design Decisions

### D1. Inline suppression, no shared helper module

Decision: each loader carries the C1 form inline; no helper module is added
under `tests/`.

Rationale: many existing test modules statically assert that their own
imports are standard-library modules only, checking import names against the
interpreter's standard-library name list (for example
`tests/test_sca_axis_skill_and_version.py` scans every `tests/test_sca_*.py`,
and `tests/test_sca_run_scan_plan_units.py` also rejects any imported name
starting with `test_` for four sibling modules). A helper imported by name
would be reported by those checks, and changing the checks would change
existing verification content (NFR4). The existing precedents already use
the inline form.

Affected tasks: task0001, task0002, task0003, task0004.

### D2. Tasks split by the loaded script, with disjoint file sets

Decision: task0001 owns the loaders of `scan-dependencies.py`, task0002 the
loaders of `validate-worker-output.py`, task0003 the loaders of every other
script, and task0004 everything in `tests/test_report_name_entry.py`
(its in-process load and its child-process launch). Where one test module
loads two scripts (`tests/test_self_write_digest.py`), the whole module
belongs to one task (task0003). No file appears in two tasks.

Rationale: a task's probe tests must pass in that task's own worktree, so
the probe checks for a load site live in the same task as the edit of that
site.

Affected tasks: all.

### D3. Probes for the flag contract, command runs for the real scripts

Decision: the flag contract (SPEC AC3, TS-2) is unit-tested against probe
modules (C3). That no `__pycache__` appears under `em-workflow/scripts/` for
the real scripts (SPEC AC1, AC4, TS-1, TS-3, TS-4) is checked by running the
test modules — the whole suite and each module on its own — from a state
where the directory has no `__pycache__`, and looking at the directory
afterwards.

Rationale: a probe keeps a broken loader from writing under `em-workflow/`;
a test suite cannot assert the outcome of its own whole run, and a unit test
that loads a real script with suppression off would write under
`em-workflow/` exactly when it fails.

Affected tasks: all.

### D4. Explicitly unchanged

- Loads of files under `em-workflow/hooks/` (for example the
  `queue_stop_guard.py` load in `tests/test_report_name_entry.py`) — another
  feature's scope.
- The module-level flag assignment in `tests/test_merge_ci_wait.py` (it sets
  the flag and never restores it) — left as is; its `load_module` loader
  still gets C1.
- `tests/test_codex_hook_tty_reaper.py` — its loader of
  `em-workflow/scripts/codex-hook-tty-reaper.py` already has the C1 form; the
  file is not edited, and task0003's probe table drives it as a
  reference-only row.
- Script bodies under `em-workflow/scripts/`, and the production run of
  `report-name-entry.py`.

Affected tasks: all.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A load site is missed. In a whole run a missed load that happens during test execution is hidden, because the flag leaked by `tests/test_merge_ci_wait.py` is already True then. | Medium | Medium | Every task plan lists its sites by file and loader; each listed module is run on its own (TS-3); VERIFICATION.md has a load-site enumeration check against the union of the site tables. |
| Loading existing test modules a second time from a probe module has side effects or costs time. | Low | Low | C4: lazy, once per class, private names, flag forced True and restored. |
| An edit changes an existing assertion or the behavior under test. | Low | High | C2 and C5 restrict edits to loader bodies; reviewed by diff (TS-8). |
| An added import trips an existing standard-library import check. | Low | Medium | D1 and C5: standard-library imports only, no test-module imports by name. |
| A run-alone check is polluted by a `__pycache__` left by a red-phase run. | Medium | Low | Each run-alone check starts by confirming the directory is absent and moving any leftover to the trash first. |

## Open Questions

None.
