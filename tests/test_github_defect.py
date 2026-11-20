"""Executed RED/GREEN defect-repair contract and fail-closed publication tests."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from pathlib import Path
import sys

from test_github_software import SoftwareFixture, SoftwareGitHub
from integrations.github import software
from common import load_json


BASELINE_TEST = """import unittest
from examples.inventory import reserve

class ExistingBehavior(unittest.TestCase):
    def test_partial_reservation(self):
        self.assertEqual(3, reserve(5, 2))

    def test_excess_reservation(self):
        self.assertIsNone(reserve(5, 6))
"""

REGRESSION_TEST = """import unittest
from examples.inventory import reserve

class ExactReservation(unittest.TestCase):
    def test_exact_quantity(self):
        self.assertEqual(0, reserve(5, 5))
"""

# Reproduces the exact shape of issue #15 run 44692099960: an outer
# assertion quotes a failing subprocess/inner unittest report. The outer
# runner alone supplies the authoritative RED count and verdict.
NESTED_REGRESSION_TEST = """import io
import unittest
from examples.inventory import reserve


class NestedAdapterRegression(unittest.TestCase):
    def test_nested_assertion(self):
        class InnerCheck(unittest.TestCase):
            def test_partial(self):
                self.assertEqual(3, reserve(5, 2))

            def test_exact(self):
                self.assertEqual(0, reserve(5, 5))

        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(InnerCheck))
        self.assertTrue(result.wasSuccessful(), stream.getvalue())
"""


DIAGNOSIS = {
    "symptom": "Exact stock reservations return None.",
    "expected_behavior": "Reserving all five units must leave zero.",
    "reproduction": "On the pinned base, reserve(5, 5) returns None.",
    "observations": ["Partial reservations succeed, exact reservations fail."],
    "hypotheses": ["The >= boundary incorrectly rejects equality.",
                   "A caller could be sending the wrong quantity."],
    "experiments": ["Compare reserve(5, 4), reserve(5, 5), and reserve(5, 6)."],
    "causal_mechanism": "The >= guard incorrectly rejects equality.",
    "repair_direction": "Replace >= with >; preserve all other behavior.",
    "regression_check": "tests/test_exact_quantity.py with unittest discovery."
}


class DefectRepairTests(SoftwareFixture):
    def setUp(self):
        super().setUp()
        self.source = ("def reserve(available, requested):\n"
                       "    if requested <= 0:\n"
                       "        raise ValueError('Quantity must be positive')\n"
                       "    if requested >= available:\n"
                       "        return None\n"
                       "    return available - requested\n")
        (self.repo / "examples/inventory.py").write_text(self.source, encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests/test_existing.py").write_text(BASELINE_TEST, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Pin a real exact-quantity defect with healthy existing checks")
        self.base = self.git("rev-parse", "HEAD")
        self.issue["title"] = "Fix exact-quantity reservations"
        self.issue["body"] = "reserve(5, 5) returns None, but should return 0."
        self.regression = "tests/test_exact_quantity.py"
        self.plan = [{"id": "regressions", "kind": "unittest",
                      "command": ["python", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
                      "criterion": "Existing tests and the new regression must pass."}]

    def prepare_defect(self, **changes):
        parameters = {
            "repo": self.repo, "issue": self.issue, "repository": "fixture/software",
            "run_id": "1234", "run_attempt": "1",
            "allowed_paths": ["examples/inventory.py", self.regression],
            "acceptance_criteria": ["Exact-quantity reservations leave zero units."],
            "output": self.bundle, "at": self.at, "checks": self.plan,
            "mode": "defect", "regression_file": self.regression,
        }
        parameters.update(changes)
        return software.prepare(**parameters)

    def propose(self, source=None, regression=REGRESSION_TEST, diagnosis=DIAGNOSIS):
        context = self.directory / ("defect-context-" + self.bundle.name)
        software.render(self.bundle, self.repo, context, at=self.at)
        invocation = (context / "invocation.md").read_text(encoding="utf-8")
        self.assertIn("sf-diagnose-defect", invocation)
        self.assertIn("sf-build-change", invocation)
        response = load_json(context / "change-template.json")
        response.update({
            "status": "passed", "summary": "Repair the exact-reservation comparison.",
            "criteria_addressed": ["acceptance-1"],
            "behavior_changes": ["Exact stock may be reserved."],
            "checks_run": [{"command": "python -m unittest", "observed": "Synthetic builder claim."}],
            "remaining_work": [],
            "diagnosis": deepcopy(diagnosis),
            "edits": [
                {"path": self.regression, "content": regression},
                {"path": "examples/inventory.py", "content": source if source is not None
                 else self.source.replace("requested >= available", "requested > available")},
            ],
        })
        self.submit(response)
        return response

    def published_host(self):
        candidate = load_json(self.result / "candidate.json")
        api = SoftwareGitHub(self.base, self.issue, candidate)
        context = {"repository": "fixture/software", "run_id": "1234", "run_attempt": "1",
                   "workflow_sha": self.base, "ref": "refs/heads/main", "event_name": "workflow_dispatch"}
        host = software.SoftwareHost(api, context)
        self.git("checkout", "--quiet", "--detach", self.base)
        return api, host

    def test_real_defect_is_red_then_green_before_draft_and_quality_dispatch(self):
        self.prepare_defect()
        self.propose()
        gate = self.verify()
        self.assertTrue(gate["passed"])
        evidence = load_json(self.result / "defect-evidence.json")
        report = load_json(self.result / "verification-report.json")
        diagnosis = load_json(self.result / "diagnosis.json")
        self.assertEqual("passed", evidence["status"])
        self.assertEqual(self.base, evidence["base_sha"])
        self.assertNotEqual(evidence["red_head_sha"], evidence["candidate_sha"])
        self.assertEqual("failed", evidence["red"]["status"])
        self.assertEqual(1, evidence["red"]["tests_run"])
        self.assertEqual("passed", evidence["green"]["status"])
        self.assertEqual(1, evidence["green"]["tests_run"])
        self.assertEqual(1, len(evidence["baseline"]))
        self.assertEqual("passed", evidence["baseline"][0]["status"])
        self.assertEqual(2, evidence["baseline"][0]["tests_run"])
        self.assertEqual("passed", report["status"])
        self.assertEqual(3, report["payload"]["check_results"][0]["tests_run"])
        self.assertEqual("sf-diagnose-defect", diagnosis["producer"]["skill"])
        self.assertEqual(DIAGNOSIS, diagnosis["payload"]["agent_report"])
        self.assertIn("FAIL: test_exact_quantity", (self.result / "logs/red-regression.txt").read_text())
        self.assertIn("\nOK\n", (self.result / "logs/green-regression.txt").read_text())
        self.assertIn("\nOK\n", (self.result / "logs/regressions.txt").read_text())
        self.assertIn("test_exact_quantity.py", (self.result / "red.patch").read_text())
        api, host = self.published_host()
        published = host.publish(self.bundle, self.result, self.repo, at=self.at)
        self.assertTrue(published["draft"])
        self.assertTrue(published["quality_requested"])
        self.assertFalse(published["quality_passed"])
        self.assertFalse(published["merge_authorized"])
        body = api.pulls[0]["body"]
        self.assertIn("Defect repair (independent RED", body)
        self.assertIn(evidence["red_head_sha"], body)
        self.assertIn("logs", body)
        self.assertFalse(any("merge" in path for _, path, _ in api.mutations))

    def test_nested_unittest_failure_accepts_outer_assertion_only(self):
        """Pilot #15: inner FAIL + outer FAIL must count as one real RED test."""
        self.prepare_defect()
        self.propose(regression=NESTED_REGRESSION_TEST)
        gate = self.verify()
        self.assertTrue(gate["passed"])
        proof = load_json(self.result / "defect-evidence.json")
        self.assertEqual("passed", proof["status"])
        self.assertEqual("failed", proof["red"]["status"])
        self.assertEqual(1, proof["red"]["tests_run"])
        self.assertEqual("passed", proof["green"]["status"])
        self.assertEqual(1, proof["green"]["tests_run"])
        red_log = self.result / "logs/red-regression.txt"
        content = red_log.read_text(encoding="utf-8")
        self.assertEqual(2, len(re.findall(r"^Ran \d+ tests? in ", content, re.MULTILINE)))
        self.assertIn("Ran 2 tests in ", content)
        self.assertIn("Ran 1 test in ", content)
        self.assertIn("FAILED (failures=1)", content)
        self.assertEqual("passed", load_json(self.result / "verification-report.json")["status"])
        api, host = self.published_host()
        publication = host.publish(self.bundle, self.result, self.repo, at=self.at)
        self.assertTrue(publication["draft"])
        self.assertTrue(publication["quality_requested"])
        self.assertFalse(publication["merge_authorized"])

    def test_nested_inner_failure_cannot_disguise_outer_error_as_red(self):
        self.prepare_defect()
        self.propose(regression=NESTED_REGRESSION_TEST.replace(
            "self.assertTrue(result.wasSuccessful(), stream.getvalue())",
            "raise RuntimeError(stream.getvalue())"))
        gate = self.verify()
        self.assertFalse(gate["passed"])
        self.assertEqual("failed", gate["status"])
        self.assertIn("RED", gate["reasons"][0])
        red_log = (self.result / "logs/red-regression.txt").read_text(encoding="utf-8")
        self.assertIn("FAILED (errors=1)", red_log)
        self.assertFalse((self.result / "candidate.json").exists())

    def test_nested_red_requires_intact_terminal_runner_verdict(self):
        """Appended diagnostic text cannot supply missing final runner evidence."""
        from integrations.github import defect
        self.prepare_defect()
        self.propose(regression=NESTED_REGRESSION_TEST)
        gate = self.verify()
        self.assertTrue(gate["passed"])
        evidence = load_json(self.result / "defect-evidence.json")
        log = self.result / "logs/red-regression.txt"
        original = log.read_bytes()
        try:
            log.write_bytes(original + b"\ntrailing untrusted output\n")
            self.assertFalse(defect.red_assertion(evidence["red"], log))
        finally:
            log.write_bytes(original)
        self.assertTrue(defect.red_assertion(evidence["red"], log))

    def test_defect_mode_requires_new_exact_regression_and_implementation_scope(self):
        for changes in (
            {"regression_file": ""},
            {"regression_file": "tests/../test_escape.py"},
            {"regression_file": "tests/test_existing.py",
             "allowed_paths": ["examples/inventory.py", "tests/test_existing.py"]},
            {"allowed_paths": ["docs/recovery.md", self.regression]},
            {"allowed_paths": ["examples/inventory.py", self.regression, "tests/test_existing.py"]},
            {"mode": "untrusted"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.prepare_defect(**changes)
                self.assertEqual("", self.git("status", "--porcelain"))

    def test_missing_or_forged_diagnosis_is_rejected_before_candidate_changes(self):
        self.prepare_defect()
        valid = self.propose()
        for diagnosis in (None, {}, {**DIAGNOSIS, "observations": []},
                          {**DIAGNOSIS, "merge_authorized": True}):
            with self.subTest(diagnosis=diagnosis):
                proposed = {**valid, "diagnosis": diagnosis}
                self.submit(proposed)
                with self.assertRaises(ValueError):
                    self.verify()
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
                self.assertEqual("", self.git("status", "--porcelain"))

    def test_unreproduced_red_rejects_a_previously_passing_behavior(self):
        self.prepare_defect()
        self.propose(regression=REGRESSION_TEST.replace("reserve(5, 5)", "reserve(5, 2)")
                     .replace("self.assertEqual(0", "self.assertEqual(3"))
        gate = self.verify()
        self.assertFalse(gate["passed"])
        self.assertEqual("failed", gate["status"])
        self.assertIn("RED", gate["reasons"][0])
        self.assertFalse((self.result / "candidate.json").exists())
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_import_error_and_skipped_or_empty_tests_do_not_count_as_red(self):
        for test_code in (
            "import nonexistent_module_for_defect_test\n",
            REGRESSION_TEST.replace("    def test_exact_quantity", "    @unittest.skip('unavailable')\n    def test_exact_quantity"),
            "import unittest\n",
        ):
            with self.subTest(test_code=test_code[:35]):
                self.bundle = self.directory / ("inputs-" + str(len(list(self.directory.glob("inputs-*")))))
                self.result = self.directory / ("result-" + str(len(list(self.directory.glob("result-*")))))
                self.prepare_defect()
                self.propose(regression=test_code)
                gate = self.verify()
                self.assertFalse(gate["passed"])
                self.assertNotEqual("passed", gate["status"])
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_failed_preexisting_baseline_blocks_before_red(self):
        (self.repo / "tests/test_existing.py").write_text(
            BASELINE_TEST.replace("self.assertEqual(3, reserve(5, 2))", "self.assertEqual(0, reserve(5, 5))"),
            encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Preexisting suite is unhealthy")
        self.base = self.git("rev-parse", "HEAD")
        self.prepare_defect()
        self.propose()
        gate = self.verify()
        self.assertFalse(gate["passed"])
        self.assertIn("existing suite", gate["reasons"][0])
        self.assertFalse((self.result / "red.patch").exists())
        self.assertFalse((self.result / "candidate.json").exists())

    def test_passing_builder_claim_cannot_override_unfixed_green(self):
        self.prepare_defect()
        self.propose(source="# A comment is not a fix.\n" + self.source)
        gate = self.verify()
        self.assertFalse(gate["passed"])
        self.assertEqual("failed", gate["status"])
        record = load_json(self.result / "defect-evidence.json")
        self.assertEqual("failed", record["green"]["status"])
        self.assertEqual("failed", load_json(self.result / "verification-report.json")["status"])

    def test_negative_evidence_cannot_be_published_even_if_agent_says_passed(self):
        self.prepare_defect()
        self.propose(source="# A comment is not a fix.\n" + self.source)
        self.verify()
        api, host = self.published_host()
        with self.assertRaises(ValueError):
            host.publish(self.bundle, self.result, self.repo, at=self.at)
        self.assertEqual([], api.mutations)

    def test_tampered_red_log_and_diagnosis_prevent_remote_publication(self):
        self.prepare_defect()
        self.propose()
        self.verify()
        api, host = self.published_host()
        for name in ("logs/red-regression.txt", "diagnosis.json", "defect-evidence.json", "red.patch"):
            with self.subTest(name=name):
                file = self.result / name
                original = file.read_bytes()
                file.write_bytes(original + b"forged")
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    host.publish(self.bundle, self.result, self.repo, at=self.at)
                self.assertEqual([], api.mutations)
                file.write_bytes(original)
