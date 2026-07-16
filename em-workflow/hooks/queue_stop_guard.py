#!/usr/bin/env python3
"""em-workflow Stop hook: queue loop guard (queue_stop_guard.py).

Deterministic net for the implement-phase work-queue loop
(IMPLEMENTATION.md, "Journal contract" / "Conventions" sections). Fires on
every Stop event; blocks the orchestrator from ending its turn while a
refillable implementer slot exists for an in-progress feature, naming the
tasks to launch. This hook is a NET, not an authority: any unexpected
condition (unreadable/malformed files, non-JSON stdin, validation failure,
no active feature) exits 0 silently rather than risk wedging the session
(fail-open convention, contrasted with bash_guard.py's fail-closed security
boundary).

Decision (per the first in-progress feature, stable ordering by feature
name, that has refillable work):
  - Any task's last journal event is `failed`         -> exit 0 (no block;
    user decision pending).
  - No unlaunched tasks, or no free slot (>= MAX_PARALLEL_IMPLEMENTERS
    in-flight) -> exit 0.
  - Otherwise -> BLOCK: exit 2, stderr names the feature, the free-slot
    count, and the task ids to launch (ascending id order, bounded by the
    free-slot count).

Loop cap: a sidecar file (stop-guard-state.json, sibling of the journal)
persists a fingerprint (the derived unlaunched+in-flight task-id sets) and a
consecutive-block counter. Three consecutive blocks in the same derived
state are allowed; every FURTHER stop in that same state does NOT block
(warns on stderr and exits 0 instead) so the user stays in charge — the
over-cap counter is persisted, so the guard never resumes blocking an
unchanged state (FR4 "stop blocking … let the user take over"). Any state
change resets the counter to 1 and re-arms blocking.

Only Python stdlib is imported (NFR1).
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile

MAX_PARALLEL_IMPLEMENTERS = 6  # SSOT duplicated per IMPLEMENTATION.md; also
                                # pinned in implement-phase.md (task0005).
MAX_CONSECUTIVE_BLOCKS = 3

FEATURE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TASK_ID_RE = re.compile(r"^task[0-9]+$")
TASK_NUM_RE = re.compile(r"^task([0-9]+)$")

# workflow.yaml is read line-based on purpose (bash_guard.py pattern; NFR1 —
# no YAML library). The `workflow:` list uses `- id: <name>` items followed
# by their own indented keys; the `tasks:` mapping uses bare `taskNNNN:`
# keys at a fixed indent under the top-level `tasks:` key.
STEP_ID_RE = re.compile(r"^\s*-\s*id:\s*(\S+)\s*$")
STEP_STATUS_RE = re.compile(r"^\s*status:\s*(\S+)\s*$")
TASKS_SECTION_RE = re.compile(r"^tasks:\s*$")
TASK_KEY_RE = re.compile(r"^\s+(task[0-9]+):\s*$")

KNOWN_EVENTS = ("launched", "merged", "failed")


def find_project_root():
    """Stop hooks run with cwd = the session's project directory; a git
    toplevel probe refines it when available (worktrees, subdirectories)."""
    cwd = os.getcwd()
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            top = proc.stdout.strip()
            if top and os.path.isdir(top):
                return top
    except (OSError, subprocess.SubprocessError):
        pass
    return cwd


def implement_in_progress(workflow_yaml_path):
    """True iff the `implement` step's own `status:` line reads in_progress."""
    try:
        with open(workflow_yaml_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return False

    current_step = None
    implement_status = None
    for line in lines:
        step_match = STEP_ID_RE.match(line)
        if step_match:
            current_step = step_match.group(1)
            continue
        if current_step == "implement" and implement_status is None:
            status_match = STEP_STATUS_RE.match(line)
            if status_match:
                implement_status = status_match.group(1)
    return implement_status == "in_progress"


def task_ids_from_workflow(workflow_yaml_path):
    """Task ids declared as keys under the top-level `tasks:` mapping."""
    try:
        with open(workflow_yaml_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return []

    ids = []
    in_tasks = False
    for line in lines:
        if TASKS_SECTION_RE.match(line):
            in_tasks = True
            continue
        if not in_tasks:
            continue
        if line.strip() == "":
            continue
        if not line[0].isspace():
            # Dedent to another top-level key: the tasks: mapping ended.
            in_tasks = False
            continue
        match = TASK_KEY_RE.match(line)
        if match and TASK_ID_RE.match(match.group(1)):
            ids.append(match.group(1))
    return ids


def read_journal(journal_path):
    """Last event per task.

    - Journal file absent but its directory exists (implement phase started,
      no launch recorded yet): return {} — every declared task counts as
      unlaunched, so a forgotten INITIAL launch is still caught (FR4).
    - Journal directory absent (phase's worktree layout not created), or the
      file exists but is unopenable: return None — the feature is not
      evaluable; fail-open and skip it.
    """
    try:
        with open(journal_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        if os.path.isdir(os.path.dirname(journal_path)):
            return {}
        return None
    except OSError:
        return None

    last = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue  # malformed line: skip (fail-safe read)
        if not isinstance(record, dict):
            continue
        task = record.get("task")
        event = record.get("event")
        if not isinstance(task, str) or not TASK_ID_RE.match(task):
            continue
        if event not in KNOWN_EVENTS:
            continue
        last[task] = event
    return last


def task_sort_key(task_id):
    match = TASK_NUM_RE.match(task_id)
    return int(match.group(1)) if match else task_id


def fingerprint_for(unlaunched, in_flight):
    return json.dumps(
        {"unlaunched": sorted(unlaunched, key=task_sort_key),
         "in_flight": sorted(in_flight, key=task_sort_key)},
        sort_keys=True,
    )


def evaluate_feature(root, feature):
    """Return a decision dict for `feature` if it currently has refillable
    work to report, else None (nothing actionable / not evaluable)."""
    if not FEATURE_RE.match(feature):
        return None

    workflow_yaml_path = os.path.join(root, "feature-docs", feature, "workflow.yaml")
    if not implement_in_progress(workflow_yaml_path):
        return None

    task_ids = task_ids_from_workflow(workflow_yaml_path)
    if not task_ids:
        return None

    journal_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", feature)
    journal_path = os.path.join(journal_dir, "journal.jsonl")
    last_events = read_journal(journal_path)
    if last_events is None:
        return None

    unlaunched, in_flight, failed = [], [], []
    for task_id in task_ids:
        state = last_events.get(task_id)
        if state is None:
            unlaunched.append(task_id)
        elif state == "launched":
            in_flight.append(task_id)
        elif state == "failed":
            failed.append(task_id)
        # "merged" tasks need no further tracking (terminal).

    if failed:
        return None  # user decision pending; never block on this feature

    free_slots = MAX_PARALLEL_IMPLEMENTERS - len(in_flight)
    if not unlaunched or free_slots <= 0:
        return None

    to_launch = sorted(unlaunched, key=task_sort_key)[:free_slots]
    return {
        "feature": feature,
        "journal_dir": journal_dir,
        "free_slots": free_slots,
        "to_launch": to_launch,
        "fingerprint": fingerprint_for(unlaunched, in_flight),
    }


def active_features(root):
    docs_dir = os.path.join(root, "feature-docs")
    paths = sorted(glob.glob(os.path.join(docs_dir, "*", "workflow.yaml")))
    return [os.path.basename(os.path.dirname(path)) for path in paths]


def read_sidecar(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def write_sidecar(path, fingerprint, counter):
    """Atomic sidecar write via a RANDOMIZED exclusive temp file.

    mkstemp opens with O_CREAT|O_EXCL (never follows a pre-planted symlink,
    never truncates an existing target) — a repository cannot predict the
    temp name nor redirect the write. os.replace then swaps it in without
    following symlinks at the destination.
    """
    tmp_path = None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(path), prefix=".stop-guard-state.", suffix=".tmp"
        )
        try:
            os.write(
                fd,
                json.dumps({"fingerprint": fingerprint, "counter": counter}).encode("utf-8"),
            )
        finally:
            os.close(fd)
        os.replace(tmp_path, path)
        tmp_path = None
    except OSError:
        pass  # sidecar persistence is best-effort; never break the merge/turn
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def hook_main():
    try:
        raw = sys.stdin.read()
    except OSError:
        return 0
    try:
        data = json.loads(raw)
    except ValueError:
        return 0  # malformed stdin: fail-open
    if not isinstance(data, dict):
        return 0

    # Claude Code's re-entry flag (true once the session is already
    # continuing due to a stop hook). Read for completeness/fail-open
    # tolerance; deliberately NOT folded into the fingerprint-reset decision
    # below — this flag stays true for the whole continuation sequence
    # regardless of our derived state, so ORing it into the counter would
    # defeat "a state change resets the cap". It is never used to force an
    # unconditional block: blocking is decided solely by evaluate_feature().
    _ = bool(data.get("stop_hook_active"))

    root = find_project_root()

    for feature in active_features(root):
        result = evaluate_feature(root, feature)
        if result is None:
            continue

        sidecar_path = os.path.join(result["journal_dir"], "stop-guard-state.json")
        sidecar = read_sidecar(sidecar_path)
        prev_fingerprint = sidecar.get("fingerprint")
        prev_counter = sidecar.get("counter")
        if not isinstance(prev_counter, int):
            prev_counter = 0

        if result["fingerprint"] == prev_fingerprint:
            counter = prev_counter + 1
        else:
            counter = 1

        if counter > MAX_CONSECUTIVE_BLOCKS:
            # Persist the over-cap counter: further stops in this SAME
            # derived state keep passing (FR4 — the user has taken over).
            # A real state change flips the fingerprint and resets the
            # counter to 1 on its own, re-arming blocking.
            write_sidecar(sidecar_path, result["fingerprint"], counter)
            print(
                "queue_stop_guard: WARNING feature={feature} blocked {cap} "
                "consecutive times in the same state; letting the turn end "
                "— check on the implement phase.".format(
                    feature=result["feature"], cap=MAX_CONSECUTIVE_BLOCKS
                ),
                file=sys.stderr,
            )
            return 0

        write_sidecar(sidecar_path, result["fingerprint"], counter)
        print(
            "queue_stop_guard: BLOCK feature={feature} free_slots={slots} "
            "launch={tasks}".format(
                feature=result["feature"],
                slots=result["free_slots"],
                tasks=",".join(result["to_launch"]),
            ),
            file=sys.stderr,
        )
        return 2

    return 0


def main():
    try:
        return hook_main()
    except Exception:  # noqa: BLE001 - fail-open convention: never crash
        return 0


if __name__ == "__main__":
    sys.exit(main())
