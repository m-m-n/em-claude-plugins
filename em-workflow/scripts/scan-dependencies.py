#!/usr/bin/env python3
"""scan-dependencies.py -- axis 2 (SCA) dependency-vulnerability scan.

Co-owned by task0001 (review-sca-axis) and task0005: see IMPLEMENTATION.md
"Module co-ownership skeleton". Both subcommand names are registered here;
this task implements `scan` fully and supplies `file-tasks` as the marked
placeholder task0005 replaces with the real implementation. Whichever half
is a placeholder in a given branch MUST NEVER overwrite the other task's
real implementation at merge time (symmetric merge duty, both tasks).

`scan` (this task): reduces the caller's changed-file list to the
ecosystems the registry (references/vuln-scanners.yaml) recognises, runs
each resolvable ecosystem's registry-defined command against the existing
lockfile (read-only -- no install, no lockfile rewrite, no formatter run,
NFR2), and normalizes the tool's machine-readable output into ONE
review-output-schema.json-conformant object with `source: "tool"` and every
finding `category: "vulnerability"`. Applies the threshold (direct
dependencies only, severity high and above) at normalization time -- a
below-threshold or transitive advisory is dropped before a finding object
ever exists (IMPLEMENTATION.md D5). Never consults a model, never installs
a package, never attempts a fallback when a tool is absent (FR3, FR8).

Exit codes: 0 = exactly one result object was produced on stdout (including
`skipped: true`); 2 = execution error (missing PyYAML, unreadable/malformed
registry, malformed inputs) -- the reason is printed to stderr and NO object
is printed to stdout.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# Untrusted-text truncation (IMPLEMENTATION.md "Untrusted-text truncation"):
# every advisory-/tool-sourced string is capped at this many UTF-8 bytes,
# with a visible marker when actually cut -- the same limit review-phase.md
# R3b step 4 applies to LLM-reviewer findings.
TRUNCATION_LIMIT_BYTES = 4096
TRUNCATION_MARKER = "...[truncated]"

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "references" / "vuln-scanners.yaml"
)


class ExecutionError(Exception):
    """Raised for exit-code-2 conditions (not scan-result content)."""


# ---------------------------------------------------------------------------
# Untrusted-text truncation -- ONE helper, used by every producer of a
# title/description/suggestion field (IMPLEMENTATION.md Shared Components).
# ---------------------------------------------------------------------------

def truncate(text):
    if not text:
        return text or ""
    data = text.encode("utf-8")
    if len(data) <= TRUNCATION_LIMIT_BYTES:
        return text
    marker_bytes = TRUNCATION_MARKER.encode("utf-8")
    keep = TRUNCATION_LIMIT_BYTES - len(marker_bytes)
    cut = data[:keep]
    # Never split a multi-byte UTF-8 sequence in half.
    while cut and (cut[-1] & 0xC0) == 0x80:
        cut = cut[:-1]
    return cut.decode("utf-8", errors="ignore") + TRUNCATION_MARKER


# ---------------------------------------------------------------------------
# Registry loading (data only; see references/vuln-scanners.yaml header)
# ---------------------------------------------------------------------------

def load_registry(path):
    if yaml is None:
        raise ExecutionError("PyYAML is required (import yaml failed)")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutionError(f"cannot read registry file {path}: {exc}")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ExecutionError(f"cannot parse registry file {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("ecosystems"), list):
        raise ExecutionError(
            f"registry file {path} is missing a top-level ecosystems list"
        )
    return data


# ---------------------------------------------------------------------------
# Ecosystem selection + command assembly (AC-2: both the tool name and the
# arguments come from the registry, never hardcoded in this script).
# ---------------------------------------------------------------------------

def select_ecosystems(registry, changed_files):
    """Reduces `changed_files` to the set of manifests the registry
    recognises (matched by basename -- a manifest can live at any
    project-relative path), then to the ecosystems those manifests select.
    Returns registry ecosystem entries in registry order; empty when no
    changed file matches any registered manifest."""
    changed_basenames = {os.path.basename(f) for f in changed_files}
    selected = []
    for ecosystem in registry["ecosystems"]:
        manifests = set(ecosystem.get("manifests") or [])
        if changed_basenames & manifests:
            selected.append(ecosystem)
    return selected


def build_command(ecosystem):
    return [ecosystem["executable"]] + list(ecosystem.get("args") or [])


def resolve_executable(name):
    return shutil.which(name)


def manifest_file_for(ecosystem, changed_files):
    """The first changed file whose basename is one of this ecosystem's
    manifests -- a project-relative path, so R3b step 1's existence check
    passes. Falls back to the registry's own first manifest name (never
    reached in practice, since an ecosystem is only selected when a
    matching changed file exists -- see select_ecosystems)."""
    manifests = set(ecosystem.get("manifests") or [])
    for f in changed_files:
        if os.path.basename(f) in manifests:
            return f
    manifest_list = ecosystem.get("manifests") or ["unknown"]
    return manifest_list[0]


def run_ecosystem_command(ecosystem, project_root):
    """Runs the registry's command form against the existing lockfile, cwd
    at the project root, reading only -- nothing here writes inside the
    project root (NFR2). Returns (parsed_json_or_None, error_or_None).

    A non-zero exit is NOT itself an error -- audit tools commonly exit
    non-zero precisely when they found something to report. Only
    unparseable stdout (empty results count as `{}`, not a parse failure)
    or an OS-level failure to even launch the process is an error, and it
    is surfaced as a machine-stable skip reason -- never as an empty
    successful scan, which would silently claim the ecosystem is clean."""
    name = ecosystem.get("ecosystem", "unknown")
    command = build_command(ecosystem)
    try:
        proc = subprocess.run(
            command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return None, f"{name}_execution_failed"
    stdout = proc.stdout.strip()
    if not stdout:
        return {}, None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None, f"{name}_unparseable_output"
    return data, None


# ---------------------------------------------------------------------------
# Finding construction (IMPLEMENTATION.md "Finding text-encoding contract")
# ---------------------------------------------------------------------------

def _map_severity(ecosystem, raw_severity):
    severity_map = ecosystem.get("severity_map") or {}
    return severity_map.get(raw_severity)


def _passes_threshold(ecosystem, is_direct, mapped_severity):
    """D5: applied FIRST, before a finding object exists. Direct
    dependencies only; severity high and above (critical/high -- anything
    else, including a severity absent from the registry's severity_map, is
    below threshold)."""
    threshold = ecosystem.get("threshold") or {}
    if threshold.get("direct_only", True) and not is_direct:
        return False
    return mapped_severity in ("critical", "high")


def _build_finding(*, manifest_file, package, advisory_id, title, affected_range,
                    fixed_version, summary, severity):
    """IMPLEMENTATION.md "Finding text-encoding contract": `title` is
    `{package}: {advisory_id} — {advisory short title}`; `description`
    carries the affected range, the fixed version and the advisory summary;
    `suggestion` is prose only (D4 -- never diff-shaped, so a vulnerability
    finding can never be classified auto-applicable). Every advisory-sourced
    string passes through `truncate()`."""
    title_text = truncate(f"{package}: {advisory_id} — {title}")
    description_parts = []
    if affected_range:
        description_parts.append(f"affected: {affected_range}")
    if fixed_version:
        description_parts.append(f"fixed: {fixed_version}")
    if summary:
        description_parts.append(str(summary))
    description_text = truncate(" | ".join(description_parts) or "no further detail available")
    suggestion_text = truncate(
        f"Update {package} to {fixed_version or 'a patched version'} to resolve {advisory_id}."
    )
    return {
        "file": manifest_file,
        "line": None,
        "line_end": None,
        "severity": severity,
        "category": "vulnerability",
        "title": title_text,
        "description": description_text,
        "suggestion": suggestion_text,
    }


def _advisory_id_from_url(url):
    if not url:
        return "UNKNOWN"
    return url.rstrip("/").rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Per-ecosystem normalization. Each function reads that tool's own
# machine-readable output shape (data, below) and applies the threshold at
# normalization time (D5) -- a dropped advisory is never turned into a
# finding object at all.
# ---------------------------------------------------------------------------

def normalize_npm(ecosystem, data, manifest_file):
    findings = []
    vulnerabilities = data.get("vulnerabilities") or {}
    for pkg_name in sorted(vulnerabilities):
        entry = vulnerabilities[pkg_name]
        if not isinstance(entry, dict):
            continue
        is_direct = bool(entry.get("isDirect"))
        mapped = _map_severity(ecosystem, entry.get("severity"))
        if not _passes_threshold(ecosystem, is_direct, mapped):
            continue
        fix_available = entry.get("fixAvailable")
        fixed_version = fix_available.get("version") if isinstance(fix_available, dict) else None
        for via in entry.get("via") or []:
            if not isinstance(via, dict):
                continue
            findings.append(
                _build_finding(
                    manifest_file=manifest_file,
                    package=pkg_name,
                    advisory_id=_advisory_id_from_url(via.get("url")),
                    title=via.get("title") or pkg_name,
                    affected_range=via.get("range") or entry.get("range"),
                    fixed_version=fixed_version,
                    summary=via.get("title"),
                    severity=mapped,
                )
            )
    return findings


def normalize_cargo(ecosystem, data, manifest_file):
    findings = []
    entries = ((data.get("vulnerabilities") or {}).get("list")) or []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        advisory = entry.get("advisory") or {}
        is_direct = bool(entry.get("is_direct"))
        raw_severity = entry.get("severity") or advisory.get("severity")
        mapped = _map_severity(ecosystem, raw_severity)
        if not _passes_threshold(ecosystem, is_direct, mapped):
            continue
        package = (entry.get("package") or {}).get("name", "unknown")
        patched_versions = (entry.get("versions") or {}).get("patched") or []
        fixed_version = patched_versions[0] if patched_versions else None
        findings.append(
            _build_finding(
                manifest_file=manifest_file,
                package=package,
                advisory_id=advisory.get("id", "UNKNOWN"),
                title=advisory.get("title") or advisory.get("id") or "vulnerability",
                affected_range=None,
                fixed_version=fixed_version,
                summary=advisory.get("description"),
                severity=mapped,
            )
        )
    return findings


def normalize_pip(ecosystem, data, manifest_file):
    findings = []
    for dep in data.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        is_direct = bool(dep.get("direct"))
        package = dep.get("name", "unknown")
        for vuln in dep.get("vulns") or []:
            if not isinstance(vuln, dict):
                continue
            mapped = _map_severity(ecosystem, vuln.get("severity"))
            if not _passes_threshold(ecosystem, is_direct, mapped):
                continue
            fix_versions = vuln.get("fix_versions") or []
            findings.append(
                _build_finding(
                    manifest_file=manifest_file,
                    package=package,
                    advisory_id=vuln.get("id", "UNKNOWN"),
                    title=vuln.get("description") or vuln.get("id") or "vulnerability",
                    affected_range=dep.get("version"),
                    fixed_version=fix_versions[0] if fix_versions else None,
                    summary=vuln.get("description"),
                    severity=mapped,
                )
            )
    return findings


def normalize_go(ecosystem, data, manifest_file):
    findings = []
    for entry in data.get("vulns") or []:
        if not isinstance(entry, dict):
            continue
        osv = entry.get("osv") or {}
        is_direct = bool(entry.get("is_direct"))
        mapped = _map_severity(ecosystem, entry.get("severity"))
        if not _passes_threshold(ecosystem, is_direct, mapped):
            continue
        fixed_version = None
        for affected in osv.get("affected") or []:
            for rng in affected.get("ranges") or []:
                for event in rng.get("events") or []:
                    if isinstance(event, dict) and "fixed" in event:
                        fixed_version = event["fixed"]
        findings.append(
            _build_finding(
                manifest_file=manifest_file,
                package=entry.get("package") or "unknown",
                advisory_id=osv.get("id", "UNKNOWN"),
                title=osv.get("summary") or osv.get("id") or "vulnerability",
                affected_range=None,
                fixed_version=fixed_version,
                summary=osv.get("details"),
                severity=mapped,
            )
        )
    return findings


NORMALIZERS = {
    "npm": normalize_npm,
    "cargo": normalize_cargo,
    "pip": normalize_pip,
    "go": normalize_go,
}


# ---------------------------------------------------------------------------
# Result object shapes (IMPLEMENTATION.md "Normalized result object")
# ---------------------------------------------------------------------------

def _empty_result():
    return {
        "findings": [],
        "summary": "No dependency manifests recognised by the registry in this change.",
        "skipped": False,
        "skip_reason": None,
        "source": "tool",
    }


def _skip_result(skip_reason, summary):
    return {
        "findings": [],
        "summary": summary,
        "skipped": True,
        "skip_reason": skip_reason,
        "source": "tool",
    }


def _findings_result(findings, summary):
    return {
        "findings": findings,
        "summary": summary,
        "skipped": False,
        "skip_reason": None,
        "source": "tool",
    }


def run_scan(project_root, changed_files, registry_path):
    """AC-1..AC-7 flow: select ecosystems, resolve each on PATH, run its
    registry command, normalize with a threshold applied at normalization
    time, and emit exactly one review-output-schema.json-conformant object.

    - No manifest in the change: an empty, non-skipped result.
    - A selected ecosystem's executable is not resolvable on PATH: that
      ecosystem contributes a skip reason (no fallback of any kind).
    - Tool-execution failure that is not "tool absent" (unparseable
      output, a process that cannot be launched) contributes its own
      machine-stable skip reason.
    - When every selected ecosystem skipped/failed and nothing was found,
      the whole result is `skipped: true` with the combined reasons. When
      at least one ecosystem produced findings (even zero), the result is
      NOT skipped -- any other ecosystem's skip is folded into `summary`
      prose instead (the schema has one `skipped`/`skip_reason` pair for
      the whole object, never per-ecosystem).
    """
    registry = load_registry(registry_path)
    selected = select_ecosystems(registry, changed_files)
    if not selected:
        return _empty_result()

    all_findings = []
    skip_reasons = []
    ran_ecosystems = []
    for ecosystem in selected:
        name = ecosystem.get("ecosystem", "unknown")
        executable_path = resolve_executable(ecosystem.get("executable"))
        if executable_path is None:
            skip_reasons.append(f"{name}_tool_not_found")
            continue
        data, error = run_ecosystem_command(ecosystem, project_root)
        if error is not None:
            skip_reasons.append(error)
            continue
        normalizer = NORMALIZERS.get(name)
        if normalizer is None:
            skip_reasons.append(f"{name}_no_normalizer")
            continue
        manifest_file = manifest_file_for(ecosystem, changed_files)
        all_findings.extend(normalizer(ecosystem, data, manifest_file))
        ran_ecosystems.append(name)

    if not ran_ecosystems:
        combined_reason = "+".join(sorted(skip_reasons)) if skip_reasons else "no_ecosystem_ran"
        summary = "Scan skipped: " + "; ".join(sorted(skip_reasons)) if skip_reasons else "Scan skipped."
        return _skip_result(combined_reason, summary)

    summary = f"Scanned {', '.join(sorted(ran_ecosystems))}; {len(all_findings)} finding(s) at or above threshold."
    if skip_reasons:
        summary += " Skipped: " + "; ".join(sorted(skip_reasons)) + "."
    return _findings_result(all_findings, summary)


# ---------------------------------------------------------------------------
# `file-tasks` -- PLACEHOLDER in this branch (IMPLEMENTATION.md "Module
# co-ownership skeleton"). Implemented by task0005. This half MUST NEVER be
# allowed to overwrite task0005's real implementation at merge time.
# ---------------------------------------------------------------------------

def cmd_file_tasks(args):
    print(
        "execution error: file-tasks is implemented by task0005 "
        "(placeholder in this branch)",
        file=sys.stderr,
    )
    return None, 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="scan-dependencies.py",
        description="Axis 2 dependency-vulnerability scan/normalize "
        "(`scan`, task0001) and triage-filing (`file-tasks`, task0005).",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    scan_parser = subparsers.add_parser(
        "scan", help="Run axis 2's detection pass over the changed-file list."
    )
    scan_parser.add_argument("--project-root", required=True, type=Path, dest="project_root")
    scan_parser.add_argument(
        "--changed-files",
        required=True,
        type=Path,
        dest="changed_files_path",
        help="Path to a JSON file holding an array of changed file paths "
        "(project-relative).",
    )
    scan_parser.add_argument(
        "--registry", type=Path, dest="registry_path", default=None,
        help="Registry path override (default: the plugin's own "
        "references/vuln-scanners.yaml).",
    )

    file_tasks_parser = subparsers.add_parser(
        "file-tasks",
        help="PLACEHOLDER in this branch -- implemented by task0005.",
    )
    file_tasks_parser.add_argument("--project-root", type=Path, dest="project_root")
    file_tasks_parser.add_argument("--feature", dest="feature")
    file_tasks_parser.add_argument("--findings", type=Path, dest="findings_path")
    file_tasks_parser.add_argument(
        "--ntd-entrypoint", type=Path, dest="ntd_entrypoint", default=None
    )

    return parser


def cmd_scan(args):
    try:
        changed_text = args.changed_files_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read --changed-files: {exc}"
    try:
        changed_files = json.loads(changed_text)
    except json.JSONDecodeError as exc:
        return None, f"--changed-files is not valid JSON: {exc}"
    if not isinstance(changed_files, list):
        return None, "--changed-files must be a JSON array of strings"

    registry_path = args.registry_path or DEFAULT_REGISTRY_PATH
    try:
        result = run_scan(args.project_root, changed_files, registry_path)
    except ExecutionError as exc:
        return None, str(exc)
    return result, None


def main(argv=None):
    if yaml is None:
        print("execution error: PyYAML is required (import yaml failed)", file=sys.stderr)
        return 2

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "scan":
        result, error = cmd_scan(args)
        if error is not None:
            print(f"execution error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(result, sort_keys=True))
        return 0
    elif args.subcommand == "file-tasks":
        result, code = cmd_file_tasks(args)
        if result is not None:
            print(json.dumps(result, sort_keys=True))
        return code
    else:  # pragma: no cover - argparse `required=True` already prevents this
        print(f"execution error: unknown subcommand {args.subcommand!r}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
