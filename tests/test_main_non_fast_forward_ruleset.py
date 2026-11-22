"""Tests for task0002 (version-bump-missing-base): the repository-held ruleset
definition that forbids non-fast-forward updates of main, and the document
that tells a maintainer how to create it with gh api and confirm it.

Covers task0002 Acceptance Criteria
(feature-docs/version-bump-missing-base/tasks/task0002.md):

- AC-1 (FR7, FR10, TS-3, TM-5): `.github/rulesets/main-non-fast-forward.json`
  parses as JSON and holds exactly the settings of the C2 contract: name,
  target branch, enforcement active, an empty bypass list, a ref-name
  condition that includes exactly refs/heads/main and excludes nothing, and
  exactly one rule of type non_fast_forward with no parameters
  (TestRulesetDefinition). The checker is shown to fire on forged
  definitions (TestDefinitionCheckFiresOnForgedDefinitions).
- AC-2, AC-3 (FR8 (a), TS-20): `.github/rulesets/README.md` holds the gh api
  command that creates the ruleset from the definition file, a check for an
  existing ruleset of the same name before the creation, confirmation steps
  for the created ruleset, the statement that the existing main ruleset is
  not changed, and a step after the creation that confirms it is unchanged.
  Those checks are narrow and name the missing element
  (TestRulesetProcedureDocument, TestProcedureCheckFiresOnForgedText); TS-20
  stays a manual review item for the document as a whole.
- AC-4 (C4, NFR3, TS-19): this module uses only the Python standard library,
  finds the repository root from its own file's location, runs no git, opens
  no network connection and reads nothing under ~/.claude
  (TestModuleIsolation). That the full suite exits 0 is not a property this
  module can assert about itself; it is verified by running
  `python3 -m unittest discover -s tests`.
- AC-5 (NFR4, TS-22): no version field changes. A diff check of the task's
  changes against its base, not a unit test.

NFR5: this module and the documents it reads carry no concrete version value;
the procedure document is checked for the absence of one.
"""

import ast
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULESETS_DIR = REPO_ROOT / ".github" / "rulesets"
DEFINITION_PATH = RULESETS_DIR / "main-non-fast-forward.json"
README_PATH = RULESETS_DIR / "README.md"
DEFINITION_REL = ".github/rulesets/main-non-fast-forward.json"

EXPECTED_NAME = "main-non-fast-forward"
EXISTING_RULESET_NAME = "main"
EXPECTED_TOP_LEVEL_KEYS = {
    "name",
    "target",
    "enforcement",
    "bypass_actors",
    "conditions",
    "rules",
}


# ---------------------------------------------------------------------------
# AC-1: the ruleset definition (C2 contract)
# ---------------------------------------------------------------------------


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssertionError(
            f"{path.relative_to(REPO_ROOT).as_posix()} cannot be read: {exc}"
        ) from exc


def _load_definition():
    text = _read_text(DEFINITION_PATH)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{DEFINITION_REL} did not parse as JSON: {exc}") from exc


def definition_problems(data):
    """Check one parsed definition against the C2 contract.

    Returns a dict that maps an item id to a short message for every item
    that is violated; an empty dict means the definition is exactly the
    contract. The ids are the keys the tests assert on.
    """
    if not isinstance(data, dict):
        return {"object": "the definition is not a JSON object"}
    problems = {}
    if set(data) != EXPECTED_TOP_LEVEL_KEYS:
        problems["keys"] = (
            f"top-level keys are {sorted(data)}, expected "
            f"{sorted(EXPECTED_TOP_LEVEL_KEYS)}"
        )
    if data.get("name") != EXPECTED_NAME:
        problems["name"] = f"name is {data.get('name')!r}, expected {EXPECTED_NAME!r}"
    if data.get("target") != "branch":
        problems["target"] = f"target is {data.get('target')!r}, expected 'branch'"
    if data.get("enforcement") != "active":
        problems["enforcement"] = (
            f"enforcement is {data.get('enforcement')!r}, expected 'active'"
        )
    if data.get("bypass_actors") != []:
        problems["bypass_actors"] = (
            f"bypass_actors is {data.get('bypass_actors')!r}, expected an empty list"
        )

    conditions = data.get("conditions")
    if not isinstance(conditions, dict) or set(conditions) != {"ref_name"}:
        problems["conditions"] = (
            f"conditions is {conditions!r}, expected an object holding only ref_name"
        )
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
    if not isinstance(ref_name, dict):
        problems["ref_name.include"] = "conditions.ref_name is missing"
        problems["ref_name.exclude"] = "conditions.ref_name is missing"
    else:
        if ref_name.get("include") != ["refs/heads/main"]:
            problems["ref_name.include"] = (
                f"ref_name.include is {ref_name.get('include')!r}, "
                "expected exactly ['refs/heads/main']"
            )
        if ref_name.get("exclude") != []:
            problems["ref_name.exclude"] = (
                f"ref_name.exclude is {ref_name.get('exclude')!r}, "
                "expected an empty list"
            )

    rules = data.get("rules")
    if not isinstance(rules, list) or len(rules) != 1:
        problems["rules.count"] = f"rules is {rules!r}, expected exactly one rule"
    else:
        rule = rules[0]
        if not isinstance(rule, dict) or rule.get("type") != "non_fast_forward":
            problems["rules.type"] = (
                f"the rule is {rule!r}, expected type 'non_fast_forward'"
            )
        elif "parameters" in rule:
            problems["rules.parameters"] = (
                f"the rule carries parameters {rule['parameters']!r}, expected none"
            )
        elif set(rule) != {"type"}:
            problems["rules.parameters"] = (
                f"the rule has keys {sorted(rule)}, expected only 'type'"
            )
    return problems


class TestRulesetDefinition(unittest.TestCase):
    """AC-1: the definition file holds exactly the C2 contract."""

    def _assert_item_holds(self, item):
        problems = definition_problems(_load_definition())
        self.assertNotIn(item, problems, problems.get(item))

    def test_definition_parses_as_a_json_object(self):
        self.assertIsInstance(_load_definition(), dict)

    def test_name_is_main_non_fast_forward(self):
        self._assert_item_holds("name")

    def test_name_differs_from_the_existing_main_ruleset(self):
        # The new ruleset is separate from the existing one named main (D2).
        self.assertNotEqual(_load_definition().get("name"), EXISTING_RULESET_NAME)

    def test_name_matches_the_file_stem(self):
        self.assertEqual(_load_definition().get("name"), DEFINITION_PATH.stem)

    def test_target_is_branch(self):
        self._assert_item_holds("target")

    def test_enforcement_is_active(self):
        self._assert_item_holds("enforcement")

    def test_bypass_actors_is_an_empty_list(self):
        self._assert_item_holds("bypass_actors")

    def test_conditions_hold_only_the_ref_name_condition(self):
        self._assert_item_holds("conditions")

    def test_ref_name_includes_exactly_refs_heads_main(self):
        self._assert_item_holds("ref_name.include")

    def test_ref_name_excludes_nothing(self):
        self._assert_item_holds("ref_name.exclude")

    def test_rules_hold_exactly_one_rule(self):
        self._assert_item_holds("rules.count")

    def test_the_rule_type_is_non_fast_forward(self):
        self._assert_item_holds("rules.type")

    def test_the_rule_has_no_parameters(self):
        self._assert_item_holds("rules.parameters")

    def test_top_level_keys_are_exactly_the_creation_payload_keys(self):
        self._assert_item_holds("keys")

    def test_definition_has_no_problems_at_all(self):
        self.assertEqual(definition_problems(_load_definition()), {})


def _good_definition():
    return {
        "name": EXPECTED_NAME,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [{"type": "non_fast_forward"}],
    }


class TestDefinitionCheckFiresOnForgedDefinitions(unittest.TestCase):
    """The checker is not vacuous: each forged definition is flagged on the
    item it forges, and the forged-good reference is not flagged at all."""

    def test_the_reference_definition_has_no_problems(self):
        self.assertEqual(definition_problems(_good_definition()), {})

    def _flagged(self, mutate, item):
        data = _good_definition()
        mutate(data)
        self.assertIn(item, definition_problems(data))

    def test_a_different_name_is_flagged(self):
        self._flagged(lambda d: d.update(name="main"), "name")

    def test_a_tag_target_is_flagged(self):
        self._flagged(lambda d: d.update(target="tag"), "target")

    def test_evaluate_enforcement_is_flagged(self):
        self._flagged(lambda d: d.update(enforcement="evaluate"), "enforcement")

    def test_disabled_enforcement_is_flagged(self):
        self._flagged(lambda d: d.update(enforcement="disabled"), "enforcement")

    def test_a_bypass_actor_is_flagged(self):
        self._flagged(
            lambda d: d.update(
                bypass_actors=[
                    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
                ]
            ),
            "bypass_actors",
        )

    def test_a_missing_bypass_actors_key_is_flagged(self):
        self._flagged(lambda d: d.pop("bypass_actors"), "bypass_actors")

    def test_an_extra_included_ref_is_flagged(self):
        self._flagged(
            lambda d: d["conditions"]["ref_name"].update(
                include=["refs/heads/main", "refs/heads/dev"]
            ),
            "ref_name.include",
        )

    def test_a_pattern_include_is_flagged(self):
        self._flagged(
            lambda d: d["conditions"]["ref_name"].update(include=["~DEFAULT_BRANCH"]),
            "ref_name.include",
        )

    def test_a_non_empty_exclude_is_flagged(self):
        self._flagged(
            lambda d: d["conditions"]["ref_name"].update(exclude=["refs/heads/x"]),
            "ref_name.exclude",
        )

    def test_a_second_condition_is_flagged(self):
        self._flagged(
            lambda d: d["conditions"].update(repository_name={"include": ["~ALL"]}),
            "conditions",
        )

    def test_an_extra_rule_is_flagged(self):
        self._flagged(lambda d: d["rules"].append({"type": "deletion"}), "rules.count")

    def test_no_rule_is_flagged(self):
        self._flagged(lambda d: d.update(rules=[]), "rules.count")

    def test_another_rule_type_is_flagged(self):
        self._flagged(lambda d: d.update(rules=[{"type": "deletion"}]), "rules.type")

    def test_a_rule_with_parameters_is_flagged(self):
        self._flagged(
            lambda d: d.update(
                rules=[{"type": "non_fast_forward", "parameters": {"x": 1}}]
            ),
            "rules.parameters",
        )

    def test_an_extra_top_level_setting_is_flagged(self):
        self._flagged(lambda d: d.update(bypass_mode="always"), "keys")

    def test_a_non_object_definition_is_flagged(self):
        self.assertIn("object", definition_problems([]))


# ---------------------------------------------------------------------------
# AC-2, AC-3: the procedure document (FR8 (a))
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
VERSION_LIKE_RE = re.compile(r"(?<![\d.])\d+\.\d+\.\d+(?!\.?\d)")
RULESETS_LIST_ENDPOINT_RE = re.compile(r"repos/\{owner\}/\{repo\}/rulesets(?![\w/])")
SELECT_NEW_BY_NAME = f'.name == "{EXPECTED_NAME}"'
SELECT_EXISTING_BY_NAME = f'.name == "{EXISTING_RULESET_NAME}")'
CONFIRMED_ITEMS = ("name", "target", "enforcement", "bypass_actors", "rules")
MAIN_NOT_CHANGED_RE = re.compile(
    rf"existing\s+`?{EXISTING_RULESET_NAME}`?\s+ruleset\s+is\s+not\s+changed",
    re.IGNORECASE,
)


def _command_lines(text):
    """(offset, line) for every non-blank line inside a fenced code block;
    the offset is the line's position in `text`, so lines can be ordered."""
    lines = []
    for block in FENCE_RE.finditer(text):
        start = block.start(1)
        for line in block.group(1).splitlines(keepends=True):
            if line.strip():
                lines.append((start, line.strip()))
            start += len(line)
    return lines


def _create_offset(commands):
    """Offset of the first command that POSTs the definition file to the
    repository rulesets endpoint, or None."""
    for offset, line in commands:
        if (
            "gh api" in line
            and re.search(r"(--method|-X)\s+POST\b", line)
            and RULESETS_LIST_ENDPOINT_RE.search(line)
            and re.search(rf"--input\s+\S*{re.escape(DEFINITION_REL)}(?!\S)", line)
        ):
            return offset
    return None


def readme_problems(text):
    """Check the procedure document text. Returns a dict that maps an item
    id to a short message for every missing element."""
    problems = {}
    commands = _command_lines(text)
    create = _create_offset(commands)
    if create is None:
        problems["create"] = (
            "no gh api command POSTs .github/rulesets/main-non-fast-forward.json "
            "to repos/{owner}/{repo}/rulesets with --input"
        )
    if not any(
        "gh api" in line
        and RULESETS_LIST_ENDPOINT_RE.search(line)
        and SELECT_NEW_BY_NAME in line
        and (create is None or offset < create)
        for offset, line in commands
    ):
        problems["check-before-create"] = (
            "no gh api command that looks for a ruleset named main-non-fast-forward "
            "comes before the creation command"
        )
    after = [(o, line) for o, line in commands if create is not None and o > create]
    confirm_text = " ".join(line for _, line in after if "gh api" in line)
    missing = [item for item in CONFIRMED_ITEMS if item not in confirm_text]
    if create is None or missing:
        problems["confirm"] = (
            "the gh api commands after the creation do not inspect: "
            + ", ".join(missing or list(CONFIRMED_ITEMS))
        )
    after_text = text[create:] if create is not None else ""
    if "non_fast_forward" not in after_text:
        problems["confirm-rule"] = (
            "the confirmation after the creation does not name the non_fast_forward rule"
        )
    if not MAIN_NOT_CHANGED_RE.search(text):
        problems["main-statement"] = (
            "the document does not state that the existing main ruleset is not changed"
        )
    if not any(
        "gh api" in line and SELECT_EXISTING_BY_NAME in line
        and (create is None or offset < create)
        for offset, line in commands
    ):
        problems["main-record"] = (
            "no gh api command before the creation records the existing main ruleset"
        )
    if not any("diff" in line for _, line in after):
        problems["main-unchanged-step"] = (
            "no diff command after the creation compares the existing main ruleset"
        )
    if VERSION_LIKE_RE.search(text):
        problems["no-version-value"] = "the document carries a concrete version value"
    return problems


class TestRulesetProcedureDocument(unittest.TestCase):
    """AC-2, AC-3: .github/rulesets/README.md holds procedure (a)."""

    @classmethod
    def setUpClass(cls):
        cls.problems = None
        cls.error = None
        try:
            cls.text = _read_text(README_PATH)
        except AssertionError as exc:
            cls.text = ""
            cls.error = str(exc)

    def _assert_item_holds(self, item):
        if self.error:
            self.fail(self.error)
        problems = readme_problems(self.text)
        self.assertNotIn(item, problems, problems.get(item))

    def test_readme_exists_and_is_not_empty(self):
        if self.error:
            self.fail(self.error)
        self.assertTrue(self.text.strip())

    def test_ac2_gh_api_command_creates_the_ruleset_from_the_definition_file(self):
        self._assert_item_holds("create")

    def test_ac2_existing_ruleset_of_the_same_name_is_checked_before_creating(self):
        self._assert_item_holds("check-before-create")

    def test_ac2_confirmation_inspects_name_target_enforcement_bypass_and_rules(self):
        self._assert_item_holds("confirm")

    def test_ac2_confirmation_names_the_non_fast_forward_rule(self):
        self._assert_item_holds("confirm-rule")

    def test_ac3_states_the_existing_main_ruleset_is_not_changed(self):
        self._assert_item_holds("main-statement")

    def test_ac3_existing_main_ruleset_is_recorded_before_the_creation(self):
        self._assert_item_holds("main-record")

    def test_ac3_a_step_after_the_creation_confirms_main_is_unchanged(self):
        self._assert_item_holds("main-unchanged-step")

    def test_nfr5_the_document_carries_no_concrete_version_value(self):
        self._assert_item_holds("no-version-value")

    def test_the_document_has_no_problems_at_all(self):
        if self.error:
            self.fail(self.error)
        self.assertEqual(readme_problems(self.text), {})


class TestProcedureCheckFiresOnForgedText(unittest.TestCase):
    """The procedure checks are not vacuous: text without the elements is
    flagged, and removing one element flags that element."""

    CREATE = (
        "gh api --method POST repos/{owner}/{repo}/rulesets "
        f"--input {DEFINITION_REL}"
    )
    CHECK = (
        "gh api repos/{owner}/{repo}/rulesets --jq "
        f"'.[] | select({SELECT_NEW_BY_NAME}) | .id'"
    )
    RECORD = (
        "gh api repos/{owner}/{repo}/rulesets --jq "
        f"'.[] | select({SELECT_EXISTING_BY_NAME} | .id'"
    )
    CONFIRM = (
        'gh api "repos/{owner}/{repo}/rulesets/$NEW_ID" --jq '
        "'{name, target, enforcement, bypass_actors, rules}'"
    )
    DIFF = 'gh api "repos/{owner}/{repo}/rulesets/$MAIN_ID" | diff before.json -'

    def _document(self, **overrides):
        parts = {
            "statement": "The existing `main` ruleset is not changed.",
            "check": self.CHECK,
            "record": self.RECORD,
            "create": self.CREATE,
            "confirm": self.CONFIRM,
            "rule": "The rules are exactly one: non_fast_forward.",
            "diff": self.DIFF,
        }
        parts.update(overrides)
        fenced = lambda body: f"```sh\n{body}\n```\n"
        return "\n".join(
            [
                parts["statement"],
                fenced(parts["check"]),
                fenced(parts["record"]),
                fenced(parts["create"]),
                fenced(parts["confirm"]),
                parts["rule"],
                fenced(parts["diff"]),
            ]
        )

    def test_the_reference_document_has_no_problems(self):
        self.assertEqual(readme_problems(self._document()), {})

    def test_an_empty_text_is_flagged_on_every_item(self):
        self.assertEqual(
            set(readme_problems("")),
            {
                "create",
                "check-before-create",
                "confirm",
                "confirm-rule",
                "main-statement",
                "main-record",
                "main-unchanged-step",
            },
        )

    def test_a_missing_input_flag_is_flagged_as_create(self):
        text = self._document(create="gh api --method POST repos/{owner}/{repo}/rulesets")
        self.assertIn("create", readme_problems(text))

    def test_a_create_command_for_another_file_is_flagged_as_create(self):
        text = self._document(create=self.CREATE.replace("main-non-fast-forward", "other"))
        self.assertIn("create", readme_problems(text))

    def test_a_get_command_is_not_a_create_command(self):
        text = self._document(create="gh api repos/{owner}/{repo}/rulesets")
        self.assertIn("create", readme_problems(text))

    def test_a_check_placed_after_the_creation_is_flagged(self):
        text = self._document(check="echo none")
        self.assertIn("check-before-create", readme_problems(text))
        late = text + f"\n```sh\n{self.CHECK}\n```\n"
        self.assertIn("check-before-create", readme_problems(late))

    def test_a_confirmation_without_the_bypass_list_is_flagged(self):
        text = self._document(confirm=self.CONFIRM.replace("bypass_actors, ", ""))
        problems = readme_problems(text)
        self.assertIn("confirm", problems)
        self.assertIn("bypass_actors", problems["confirm"])

    def test_a_confirmation_without_enforcement_is_flagged(self):
        text = self._document(confirm=self.CONFIRM.replace("enforcement, ", ""))
        self.assertIn("confirm", readme_problems(text))

    def test_a_document_without_the_rule_name_after_the_creation_is_flagged(self):
        text = self._document(rule="The rules are exactly one.")
        self.assertIn("confirm-rule", readme_problems(text))

    def test_a_missing_main_statement_is_flagged(self):
        text = self._document(statement="Nothing else is said.")
        self.assertIn("main-statement", readme_problems(text))

    def test_a_missing_main_record_is_flagged(self):
        text = self._document(record="echo none")
        self.assertIn("main-record", readme_problems(text))

    def test_a_missing_diff_step_is_flagged(self):
        text = self._document(diff="echo done")
        self.assertIn("main-unchanged-step", readme_problems(text))

    def test_a_concrete_version_value_is_flagged(self):
        text = self._document(rule="The rules are exactly one: non_fast_forward. Use 1.2.3.")
        self.assertIn("no-version-value", readme_problems(text))

    def test_a_path_in_the_document_is_not_a_version_value(self):
        text = self._document()
        self.assertNotIn("no-version-value", readme_problems(text))


# ---------------------------------------------------------------------------
# AC-4: C4 isolation of this module
# ---------------------------------------------------------------------------

ALLOWED_IMPORTS = {"ast", "json", "re", "unittest", "pathlib"}


class TestModuleIsolation(unittest.TestCase):
    """AC-4 (C4, NFR3, TS-19): standard library only, no git, no network."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    def test_imports_are_a_small_standard_library_allowlist(self):
        imported = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative import")
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, ALLOWED_IMPORTS)

    def test_repository_root_comes_from_this_files_location(self):
        self.assertEqual(REPO_ROOT, Path(__file__).resolve().parent.parent)
        self.assertTrue((REPO_ROOT / "tests").is_dir())


if __name__ == "__main__":
    unittest.main()
