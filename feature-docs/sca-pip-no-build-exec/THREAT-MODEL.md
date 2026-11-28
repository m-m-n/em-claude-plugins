# Threat Model: sca-pip-no-build-exec

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md of this feature (tier `full`, no DESIGN.md), the pip route of `em-workflow/scripts/scan-dependencies.py` (job construction, the requirements and pyproject readers, the lockfile route and the prepared-file scope) and the pip entry of `em-workflow/references/vuln-scanners.yaml`. The single task declares `input-handling` and `external-io`, so the boundary that the reviewed manifests cross into the scanner process is analysed at deep depth.

The feature reads files written by the author of the reviewed project, derives a scanner input from them, starts an external process (pip-audit) as the reviewer, writes a file into the shared system temporary directory, and returns text that the review pipeline passes to an LLM evaluator. Each of these is a trust boundary, and threats apply realistically at each, so the verdict is `threats-identified`.

Out of scope:
- The npm, cargo and go scans: their behavior is unchanged (FR9 asks only for a check and a record). The check is recorded in SPEC.md, not here.
- The location of the system temporary directory: it comes from the reviewer's own environment. Neither pip route checks whether it lies inside the reviewed tree, and no mitigation is invented for it. It is listed as an open question in IMPLEMENTATION.md.

Domain consistency: the boundary files below cover the files of task0001 that implement behavior, namely the script and the registry. Its remaining files are test modules, which cross no boundary at run time.

## Trust Boundaries

### TB-1: Reviewed pip manifests to the pip-audit process
Crossing: the content of `requirements.txt` (and the files it includes), `pyproject.toml`, `poetry.lock` and `Pipfile.lock`, written by the reviewed project's author, is read by the reviewer's scan script. A scanner input derived from it is then handed to a pip-audit child process running with the reviewer's privileges, with the reviewed project root as its working directory.
Boundary files: `em-workflow/scripts/scan-dependencies.py`, `em-workflow/references/vuln-scanners.yaml`
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A reviewed file or directory handed to pip-audit makes it resolve dependencies. A local, editable, URL or sdist dependency then runs the reviewed project's build backend, `setup.py` or PEP 517 hooks as the reviewer (FR1, NFR1) | TM-1 | pip-audit is started only on a prepared file of validated pins, with the registry form's `--no-deps` and `--disable-pip`. Job construction refuses a pip job without a prepared file. No code path builds the directory form or the reviewed-file form, and editable, local, URL and VCS items never reach the prepared file | task0001 AC-3, AC-6 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Tampering | Crafted manifest text smuggles an extra requirement line, an option or a non-pin specifier into the prepared file: an embedded line break, a marker, a wildcard or `===` version, extra per-requirement options, or a poetry value that is not an exact pin (FR2, NFR1) | TM-2 | Only items matching the strict pin rule are written. Each is written as one canonical `name==version` line, after its extras and hashes are dropped, and only when the pair also passes `_pip_pin_is_valid`. Every other item is excluded and counted | task0001 AC-4, AC-5, AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Information disclosure | A `-r` include that leaves the project root (`..`, an absolute path, a symlink), a URL include, a `-c` constraint file, or a manifest path outside the root makes the scan read a file outside the reviewed tree. Its pins would then reach pip-audit and the review output (FR2, NFR2) | TM-3 | Every opened file is resolved through the existing project-root confinement. URL includes are never fetched, `-c` files are never opened, and an include that cannot be opened is counted as excluded | task0001 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Denial of service | Crafted content raises or loops inside extraction and aborts the whole scan, losing the other ecosystems' results too. Examples are invalid TOML, non-UTF-8 bytes, a byte-order mark, an unsplittable option line, an include cycle, a directory in place of a file, or an unexpected TOML shape (FR3, NFR5) | TM-4 | Extraction never raises for any content, shape or path. It opens each file at most once per walk, so cycles end, and every failure becomes a fixed outcome (excluded items, or no auditable item) | task0001 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Tampering | Configuration in the reviewed tree or the inherited environment, such as a pip configuration file or an index URL, redirects or extends what the pip-audit child does (NFR3) | TM-5 | The existing child environment is kept unchanged: the sanitized environment, the `PIP_CONFIG_FILE` and `PIP_INDEX_URL` pins, the absolute path of an allowlisted executable and the argv-array launch | task0001 AC-9 | VERIFICATION.md Performance / Security Verification, TM-5 |

### TB-2: Scan result text to the review pipeline and the LLM evaluator
Crossing: the scan's `skip_reason` and `summary` leave the script as JSON. The review phase passes them into the security reviewer's prompt.
Boundary files: `em-workflow/scripts/scan-dependencies.py`
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A package name, a path or other text from a reviewed manifest reaches `skip_reason` or `summary`. Instruction-shaped text then steers the LLM evaluator, or the reason vocabulary becomes ambiguous (FR6, NFR4) | TM-6 | The two new reasons are fixed module-level tokens that carry no name, path or count. No new summary text is added. The manifest route's exclusions never feed the lockfile note | task0001 AC-7 | VERIFICATION.md Performance / Security Verification, TM-6 |

### TB-3: Prepared file in the shared system temporary directory
Crossing: the scan writes each prepared file into the system temporary directory, which other local processes can also reach. pip-audit then reads the file back by path.
Boundary files: `em-workflow/scripts/scan-dependencies.py`
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Another local process pre-creates or replaces a prepared file under a predictable name, so pip-audit reads lines other than the validated pins. Or a prepared file outlives the scan, or one is created inside the reviewed tree (NFR2) | TM-7 | Each prepared file is created with a unique, unpredictable name and owner-only access in the system temporary directory. Every file is removed when the scope exits, normally or by exception, and nothing is created or changed under the project root | task0001 AC-8 | VERIFICATION.md Performance / Security Verification, TM-7 |
