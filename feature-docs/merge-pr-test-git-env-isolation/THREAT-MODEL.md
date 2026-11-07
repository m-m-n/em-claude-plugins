# Threat Model: merge-pr-test-git-env-isolation

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR4, NFR1-NFR4, assumptions A1-A7), the environment
that `MergePrTestCase.setUp` in `tests/test_merge_pr.py` builds for its
fixture-building git calls and for the `merge-pr.py` child process, and the
regression test this feature adds. Tier: reduced. The feature changes test
code only. Its one trust boundary is the process environment the test suite
inherits from whoever invokes it (a developer shell, a git hook, CI), which
reaches every git child process the harness starts. task0001 declares
`external-io` (the file-system side effects of those git child processes),
which sets TB-1 to deep; it declares none of `auth`, `input-handling` or
`data-persistence`. The recorded threats are integrity threats against git
repositories outside the test's temporary directories (the protection stated
in SPEC.md Security Considerations, Data Protection). No Information
disclosure row is recorded: the token variables that could cross this
boundary are already removed by existing behavior that FR4 keeps unchanged,
and this feature adds no new path for them.

## Trust Boundaries

### TB-1: Inherited process environment into the test harness's git child processes
Crossing: environment variables of the invoking process (another process: a
developer shell, a git hook, CI) enter the unittest process, are copied by
`MergePrTestCase.setUp` into `self.env` / `self.real_env`, and reach every git
child process setUp starts and the `merge-pr.py` child process. The regression
test also writes decoy values into this same process environment.
Boundary files: tests/test_merge_pr.py
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | An inherited `GIT_DIR` / `GIT_WORK_TREE` / `GIT_INDEX_FILE`, or any other inherited `GIT_`-prefixed variable, redirects setUp's fixture-building git calls (init, local config, the initial empty commit, remote add) and the `merge-pr.py` child to the invoking repository, adding a commit and `user.name` / `user.email` entries there (FR1, SPEC.md AC1) | TM-1 | setUp removes every key whose name starts with `GIT_` from its copy of the process environment before adding its own values, so `self.env` and `self.real_env` carry no inherited `GIT_` key | task0001 AC-1, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2) |
| Tampering | The invoking user's global git configuration, still reachable after the `GIT_` removal through a variable that is kept (for example `XDG_CONFIG_HOME`, SPEC.md A3), is applied to setUp's git calls and can change what they do or where they write, for example a configured hooks path that runs the invoking user's hooks on setUp's commit (FR2) | TM-2 | setUp sets `GIT_CONFIG_GLOBAL` to `os.devnull` next to the existing `GIT_CONFIG_NOSYSTEM=1`, so no global or system configuration file is read by the harness's git calls | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-2) |
| Tampering | The regression test itself places decoy `GIT_` variables into the process environment. Built or scoped carelessly, it writes into a repository outside its own temporary directory (an outer `GIT_DIR` already present when the decoy is built), or leaves the decoy values in place for later tests in the same process, including after a failed assertion (NFR3) | TM-3 | The regression test builds every decoy path inside its own temporary directory with an environment from which every `GIT_` key is removed, and changes the process environment only through a scoped mechanism that restores it on exit, failure included | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-1, M1) |
