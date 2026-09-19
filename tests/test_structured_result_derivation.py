"""Tests for task0005 (batch-structured-result-output): the derivation-site
guard (TS4) pinning FR9-FR12's `feature`, `branch`, `pr_url` and
`resume_conditions` rules across every named site of IMPLEMENTATION.md's
"Canonical derivation outcomes" table (SC4). Per IMPLEMENTATION.md D5, this
module declares that table's values here as its own canonical expectation
set and exercises a derivation checker against them; it never reads
`batch-terminal-line.md` or `batch-mode.md` -- task0001 and task0002 own the
binding assertions that those SSOT/pointer documents state the same rules
(Out of Scope).

Covers task0005 Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0005.md):

- AC-1: `TestCaseListCoversAllTenSites` asserts the case list has exactly
  ten members and covers every canonical site name; `TestCanonicalDerivationSites`
  asserts the derivation checker produces, for each site, exactly the four
  values IMPLEMENTATION.md's table states.
- AC-2: `TestNeitherValueIsGuessed` -- a confirmed slug with no branch
  confirmation yields an empty `branch`; a site that carries a
  branch-confirmation signal with no confirmed slug yields an empty
  `feature` (and, by the same construction, an empty `branch`, since branch
  construction requires a slug).
- AC-3: covered by the first three rows of `TestCanonicalDerivationSites`
  (the three Step 0 abort variants), pinned again individually in
  `TestStep0SuppliedNameRule` for direct traceability, plus a fourth case
  proving the supplied-name rule never applies outside a Step 0 abort.
- AC-4: `TestPrUrlSurvivesAStop` -- `pr_url` survives a stop following a
  successful PR creation, for both the cleanup-failure-shaped case (row 9)
  and the verify cap-reached case (row 10, re-derived here with a PR
  created); empty for every site where Step C created no PR this run.
- AC-5: `TestResumeConditionsPresenceRule` -- non-whitespace exactly when
  `state` is `stopped`; a whitespace-only value is rejected by `_is_present`
  as not satisfying "non-whitespace".
- AC-7 (this module's own half): `TestModuleIsStdlibOnly` -- the sibling
  module, test_structured_result_reporting_containment.py, covers its own
  half plus the workflow.yaml scan.

Every site's expected values are declared inline in `CASES` rather than
derived from a shared formula, so a copy-paste mistake in one row cannot
silently propagate to another. TDD order (Test Notes): this module first
existed with `derive`/`_is_present` stubbed to wrong/placeholder values,
confirmed red against every case below, then implemented to green -- see
this task's test record.
"""

import inspect
import re
import unittest
from collections import namedtuple
from pathlib import Path

# --- FR9's slug pattern and FR10's branch name template -- declared here
# independently of the SSOT (D5); task0001 binds the real document against
# the same literals.
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
INTEGRATION_BRANCH_TEMPLATE = "em-workflow/{feature}/integration"

RESUME_GUIDANCE_TEXT = (
    "Resume by re-running the batch command once the blocking condition "
    "named above is resolved."
)
PR_URL_EXAMPLE = "https://github.com/example-org/example-repo/pull/42"

Site = namedtuple(
    "Site",
    [
        "name",
        "slug_confirmed",  # confirmed feature slug (str) or None
        "branch_confirmed_or_created",  # bool: this run confirmed/created it
        "is_step0_abort",  # bool: a Step 0 git-setup abort context
        "supplied_name",  # explicitly supplied name (str) or None
        "pr_created_this_run",  # bool: Step C created a PR this run
        "pr_url_value",  # the bare URL Step C would report, if created
    ],
)

DerivedValues = namedtuple(
    "DerivedValues", ["feature", "branch", "pr_url", "resume_conditions"]
)


def _integration_branch_name(slug):
    return INTEGRATION_BRANCH_TEMPLATE.format(feature=slug)


def derive(site, state):
    """FR9-FR12 derivation checker. `state` is one of 'completed',
    'stopped', 'phase_done' (FR13's domain).

    - `feature` (FR9): the confirmed slug; or, only at a Step 0 abort, an
      explicitly supplied name that matches SLUG_PATTERN; otherwise "".
      Never derived from a task description or from an existing branch --
      there is no such parameter for either to travel through.
    - `branch` (FR10): the integration branch name, only when this run
      confirmed the branch exists or created it AND a slug was confirmed
      (constructing the name requires the slug); otherwise "".
    - `pr_url` (FR11): the bare URL, only when Step C created a PR this
      run; otherwise "". Retained regardless of `state`.
    - `resume_conditions` (FR12): non-whitespace guidance only when
      `state` is 'stopped'; otherwise "".
    """
    if site.slug_confirmed:
        feature = site.slug_confirmed
    elif (
        site.is_step0_abort
        and site.supplied_name
        and SLUG_PATTERN.match(site.supplied_name)
    ):
        feature = site.supplied_name
    else:
        feature = ""

    if site.branch_confirmed_or_created and site.slug_confirmed:
        branch = _integration_branch_name(site.slug_confirmed)
    else:
        branch = ""

    pr_url = site.pr_url_value if site.pr_created_this_run else ""

    resume_conditions = RESUME_GUIDANCE_TEXT if state == "stopped" else ""

    return DerivedValues(feature, branch, pr_url, resume_conditions)


def _is_present(value):
    """FR12: 'non-whitespace' -- a whitespace-only string does not satisfy
    presence."""
    return bool(value.strip())


# ---------------------------------------------------------------------------
# AC-1 / TS4: the ten canonical sites, declared inline (IMPLEMENTATION.md's
# Canonical derivation outcomes table, SC4 -- D5: canonical values live
# here, never read from the SSOT).
# ---------------------------------------------------------------------------

CANONICAL_SITE_NAMES = [
    "Step 0 git-setup abort, no name supplied",
    "Step 0 git-setup abort, supplied name matches the slug pattern",
    "Step 0 git-setup abort, supplied name fails the slug pattern",
    "Step A feature-resolution abort",
    "Integration branch created by this run",
    "Integration branch confirmed existing by this run",
    "Step C keep-branch after worktree removal",
    "Step C --pr success",
    "Step C --pr success then a later stop",
    "Verify cap-reached run",
]

Case = namedtuple("Case", ["site", "state", "expected"])

CASES = [
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[0],
            slug_confirmed=None,
            branch_confirmed_or_created=False,
            is_step0_abort=True,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="stopped",
        expected=DerivedValues("", "", "", RESUME_GUIDANCE_TEXT),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[1],
            slug_confirmed=None,
            branch_confirmed_or_created=False,
            is_step0_abort=True,
            supplied_name="wheel-report-notch-clamp",
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="stopped",
        expected=DerivedValues(
            "wheel-report-notch-clamp", "", "", RESUME_GUIDANCE_TEXT
        ),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[2],
            slug_confirmed=None,
            branch_confirmed_or_created=False,
            is_step0_abort=True,
            supplied_name="Wheel_Report!",
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="stopped",
        expected=DerivedValues("", "", "", RESUME_GUIDANCE_TEXT),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[3],
            slug_confirmed=None,
            branch_confirmed_or_created=False,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="stopped",
        expected=DerivedValues("", "", "", RESUME_GUIDANCE_TEXT),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[4],
            slug_confirmed="my-feature",
            branch_confirmed_or_created=True,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="completed",
        expected=DerivedValues(
            "my-feature", _integration_branch_name("my-feature"), "", ""
        ),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[5],
            slug_confirmed="other-feature",
            branch_confirmed_or_created=True,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="phase_done",
        expected=DerivedValues(
            "other-feature", _integration_branch_name("other-feature"), "", ""
        ),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[6],
            slug_confirmed="my-feature",
            branch_confirmed_or_created=True,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="completed",
        expected=DerivedValues(
            "my-feature", _integration_branch_name("my-feature"), "", ""
        ),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[7],
            slug_confirmed="my-feature",
            branch_confirmed_or_created=True,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=True,
            pr_url_value=PR_URL_EXAMPLE,
        ),
        state="completed",
        expected=DerivedValues(
            "my-feature",
            _integration_branch_name("my-feature"),
            PR_URL_EXAMPLE,
            "",
        ),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[8],
            slug_confirmed="my-feature",
            branch_confirmed_or_created=True,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=True,
            pr_url_value=PR_URL_EXAMPLE,
        ),
        state="stopped",
        expected=DerivedValues(
            "my-feature",
            _integration_branch_name("my-feature"),
            PR_URL_EXAMPLE,
            RESUME_GUIDANCE_TEXT,
        ),
    ),
    Case(
        site=Site(
            name=CANONICAL_SITE_NAMES[9],
            slug_confirmed="my-feature",
            branch_confirmed_or_created=True,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        ),
        state="stopped",
        expected=DerivedValues(
            "my-feature",
            _integration_branch_name("my-feature"),
            "",
            RESUME_GUIDANCE_TEXT,
        ),
    ),
]


class TestCaseListCoversAllTenSites(unittest.TestCase):
    """AC-1: the case list holds exactly ten members and covers every
    canonical site name -- a dropped site fails here."""

    def test_exactly_ten_cases(self):
        self.assertEqual(len(CASES), 10)

    def test_case_names_cover_every_canonical_site(self):
        self.assertEqual({c.site.name for c in CASES}, set(CANONICAL_SITE_NAMES))

    def test_no_duplicate_site_names(self):
        names = [c.site.name for c in CASES]
        self.assertEqual(len(names), len(set(names)))

    def test_ten_distinct_canonical_names_declared(self):
        self.assertEqual(len(CANONICAL_SITE_NAMES), 10)
        self.assertEqual(len(CANONICAL_SITE_NAMES), len(set(CANONICAL_SITE_NAMES)))


class TestCanonicalDerivationSites(unittest.TestCase):
    """AC-1: for each of the ten sites, `derive` yields exactly the four
    values IMPLEMENTATION.md's table states."""

    def test_each_site_yields_its_table_values(self):
        for case in CASES:
            with self.subTest(site=case.site.name):
                actual = derive(case.site, case.state)
                self.assertEqual(actual, case.expected)


class TestNeitherValueIsGuessed(unittest.TestCase):
    """AC-2: a confirmed slug with no branch confirmation yields an empty
    `branch`; a site that carries a branch-confirmation signal with no
    confirmed slug yields an empty `feature` (and, by the same
    construction, an empty `branch` too, since branch construction
    requires a slug)."""

    def test_confirmed_slug_without_branch_confirmation_yields_empty_branch(self):
        site = Site(
            name="adjunct: confirmed slug, unconfirmed branch",
            slug_confirmed="confirmed-feature",
            branch_confirmed_or_created=False,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        )
        result = derive(site, state="completed")
        self.assertEqual(result.feature, "confirmed-feature")
        self.assertEqual(result.branch, "")

    def test_branch_signal_without_confirmed_slug_yields_empty_feature(self):
        # Models "a plausible existing branch" as a branch-confirmation
        # signal arriving with no confirmed slug attached to it -- proving
        # `feature` is never reverse-engineered from that signal (or from
        # any branch-name text, since `derive` never accepts one at all).
        site = Site(
            name="adjunct: branch signal without a confirmed slug",
            slug_confirmed=None,
            branch_confirmed_or_created=True,
            is_step0_abort=False,
            supplied_name=None,
            pr_created_this_run=False,
            pr_url_value="",
        )
        result = derive(site, state="completed")
        self.assertEqual(result.feature, "")
        self.assertEqual(result.branch, "")

    def test_derive_accepts_no_task_description_or_branch_name_parameter(self):
        # Structural proof: there is no parameter through which a raw task
        # description or an existing branch-name string could reach
        # `derive` at all.
        params = set(inspect.signature(derive).parameters)
        self.assertEqual(params, {"site", "state"})


class TestStep0SuppliedNameRule(unittest.TestCase):
    """AC-3: direct traceability for the three Step 0 abort variants
    (already exercised as CASES[0:3] above), plus the rule's scope limit."""

    def test_matching_supplied_name_is_used(self):
        case = CASES[1]
        self.assertEqual(
            derive(case.site, case.state).feature, "wheel-report-notch-clamp"
        )

    def test_non_matching_supplied_name_yields_empty(self):
        case = CASES[2]
        self.assertEqual(derive(case.site, case.state).feature, "")

    def test_no_supplied_name_yields_empty(self):
        case = CASES[0]
        self.assertEqual(derive(case.site, case.state).feature, "")

    def test_supplied_name_is_never_used_outside_a_step0_abort(self):
        # FR9: "usable even at a Step 0 abort" implies NOT usable at other
        # abort sites (e.g. the Step A feature-resolution abort).
        site = Site(
            name="adjunct: supplied name at a non-Step-0 abort",
            slug_confirmed=None,
            branch_confirmed_or_created=False,
            is_step0_abort=False,
            supplied_name="a-valid-slug",
            pr_created_this_run=False,
            pr_url_value="",
        )
        self.assertEqual(derive(site, state="stopped").feature, "")


class TestPrUrlSurvivesAStop(unittest.TestCase):
    """AC-4: `pr_url` survives a stop following a successful PR creation --
    the cleanup-failure-shaped case (row 9) and the verify cap-reached case
    (row 10, re-derived here with a PR created) -- and is empty for every
    site where Step C created no PR this run."""

    def test_pr_url_survives_cleanup_failure_after_pr_creation(self):
        case = CASES[8]  # "Step C --pr success then a later stop"
        self.assertEqual(case.state, "stopped")
        self.assertEqual(derive(case.site, case.state).pr_url, PR_URL_EXAMPLE)

    def test_pr_url_survives_a_verify_cap_reached_stop_after_pr_creation(self):
        base_site = CASES[9].site  # "Verify cap-reached run"
        site_with_pr = base_site._replace(
            pr_created_this_run=True, pr_url_value=PR_URL_EXAMPLE
        )
        self.assertEqual(derive(site_with_pr, state="stopped").pr_url, PR_URL_EXAMPLE)

    def test_pr_url_empty_for_every_site_where_no_pr_was_created(self):
        for case in CASES:
            if not case.site.pr_created_this_run:
                with self.subTest(site=case.site.name):
                    self.assertEqual(derive(case.site, case.state).pr_url, "")


class TestResumeConditionsPresenceRule(unittest.TestCase):
    """AC-5: non-whitespace exactly when `state` is `stopped`; a
    whitespace-only value is rejected by `_is_present` as not satisfying
    "non-whitespace"."""

    def test_present_when_stopped(self):
        site = CASES[4].site
        self.assertTrue(_is_present(derive(site, "stopped").resume_conditions))

    def test_absent_when_completed(self):
        site = CASES[4].site
        self.assertEqual(derive(site, "completed").resume_conditions, "")

    def test_absent_when_phase_done(self):
        site = CASES[4].site
        self.assertEqual(derive(site, "phase_done").resume_conditions, "")

    def test_whitespace_only_value_is_rejected_as_not_present(self):
        self.assertFalse(_is_present("   \n\t  "))

    def test_non_whitespace_value_is_accepted_as_present(self):
        self.assertTrue(_is_present(RESUME_GUIDANCE_TEXT))


class TestModuleIsStdlibOnly(unittest.TestCase):
    """AC-7 (this module's own half)."""

    def test_module_filename(self):
        self.assertEqual(
            Path(__file__).name, "test_structured_result_derivation.py"
        )

    def test_only_imports_standard_library_modules(self):
        own_source = Path(__file__).read_text(encoding="utf-8")
        allowed_top_level_modules = {"inspect", "re", "unittest", "collections", "pathlib"}
        imported = set(
            re.findall(
                r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                own_source,
                re.MULTILINE,
            )
        )
        offenders = imported - allowed_top_level_modules
        self.assertEqual(offenders, set(), f"non-stdlib import(s): {offenders}")


if __name__ == "__main__":
    unittest.main()
