"""The GitHub bridge retains real observations and fails closed at handoffs."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from common import load_json, now
from integrations.github import quality as github_quality


class GitHubQualityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.repo = self.directory / "candidate"
        self.repo.mkdir()
        self.git("init", "--quiet")
        (self.repo / "example.py").write_text("answer = 41\n", encoding="utf-8")
        self.git("add", "example.py")
        self.git("commit", "--quiet", "-m", "Base candidate")
        self.base = self.git("rev-parse", "HEAD")
        (self.repo / "example.py").write_text("answer = 42\n", encoding="utf-8")
        self.git("add", "example.py")
        self.git("commit", "--quiet", "-m", "Proposed candidate")
        self.head = self.git("rev-parse", "HEAD")
        self.pr = {
            "number": 7, "state": "open", "title": "Return the expected answer",
            "body": "The public answer must be 42.", "user": {"login": "author"},
            "html_url": "https://github.com/example/project/pull/7",
            "head": {"sha": self.head, "repo": {"full_name": "example/project"}},
            "base": {"sha": self.base, "repo": {"full_name": "example/project"}},
        }
        self.pr_path = self.directory / "pr.json"
        self.write(self.pr_path, self.pr)
        self.at = now()

    def git(self, *arguments):
        return subprocess.run([
            "git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            *arguments,
        ], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    @staticmethod
    def write(path, value):
        Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def prepare(self, variant="passed", independent=False):
        test = (
            "import unittest, example\n"
            "class Behavior(unittest.TestCase):\n"
            + ("    @unittest.skip('required observation unavailable')\n" if variant == "skipped" else "")
            + ("    @unittest.expectedFailure\n" if variant == "expected-failure" else "")
            + "    def test_answer(self):\n"
            + f"        self.assertEqual(example.answer, {99 if variant in ('failed', 'expected-failure') else 42})\n"
            + "unittest.main(verbosity=2)\n"
        )
        if variant == "empty":
            test = "import unittest\nunittest.main(verbosity=2)\n"
        checks = [{
            "id": "regressions", "kind": "unittest",
            "command": [sys.executable, "-B", "-c", test],
            "criterion": "The public answer is 42 and the behavioral check executes without skips.",
        }]
        if variant == "unavailable":
            checks[0]["command"] = [str(self.directory / "no-such-runner")]
        self.bundle = self.directory / "bundle"
        self.verification = self.directory / "verification"
        github_quality.prepare(self.repo, self.pr_path, "example/project", "1234", "1",
                               self.bundle, at=self.at, checks=checks)
        if independent:
            path = self.bundle / "policy.json"
            policy = load_json(path)
            policy["require_independent_review"] = True
            self.write(path, policy)
        self.run = load_json(self.bundle / "run.json")
        github_quality.verify(self.repo, self.bundle, self.verification, at=self.at)
        self.report = load_json(self.verification / "verification-report.json")
        return self.report

    def review(self, **changes):
        output = self.directory / "review-inputs"
        github_quality.render(self.bundle, self.verification, self.repo, output, at=self.at)
        response = load_json(output / "review-template.json")
        response.update({
            "run_id": self.run["run_id"], "subject": self.run["subject"],
            "status": "passed", "summary": "The pinned candidate satisfies the selected criteria.",
            "engineering_quality": "The small change preserves the public interface.",
            "findings": [], "limitations": [],
        })
        for criterion in response["criteria"]:
            criterion.update({"status": "passed", "detail": "Inspected the fixed candidate and retained execution result.",
                              "evidence": ["candidate-diff", "verification-report"]})
        response.update(changes)
        self.review_path = self.directory / "review.json"
        self.write(self.review_path, {"items": [{"type": "submit_review", "review_json": json.dumps(response)}]})
        return response

    def finalize(self, review_path=None, agent_result="success", current_pr_path=None):
        return github_quality.finalize(
            self.bundle, self.verification,
            review_path if review_path is not None else self.review_path,
            current_pr_path if current_pr_path is not None else self.pr_path,
            agent_result, self.directory / "result", at=self.at,
        )

    def test_real_verification_and_review_produce_inspectable_non_authorizing_assessment(self):
        self.prepare()
        self.assertEqual("passed", self.report["status"])
        self.review()
        result = self.finalize()
        self.assertEqual("passed", result["status"])
        self.assertFalse(result["mutation_authorized"])
        assessment = load_json(result["assessment"])
        self.assertEqual(self.head, assessment["subject"]["revision"])
        self.assertEqual("passed", assessment["status"])
        self.assertFalse(assessment["payload"]["independence"]["established"])
        self.assertFalse(assessment["payload"]["remediation_authorized"])
        self.assertEqual([], load_json(self.bundle / "policy.json")["grants"])
        authorization = load_json(self.directory / "result" / "authorization-gate.json")
        self.assertEqual("blocked", authorization["decision"])
        self.assertTrue(any("authorization" in reason for reason in authorization["reasons"]))
        self.assertTrue(assessment["evidence"])
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_agent_success_cannot_override_a_real_test_failure(self):
        self.prepare("failed")
        self.assertEqual("failed", self.report["status"])
        self.review()
        result = self.finalize()
        self.assertEqual("failed", result["status"])
        assessment = load_json(result["assessment"])
        self.assertTrue(any(report["artifact_type"] == "verification-report" and report["status"] == "failed"
                            for report in assessment["payload"]["reports"]))

    def test_zero_tests_cannot_become_a_passing_quality_result(self):
        self.prepare("empty")
        self.assertNotEqual("passed", self.report["status"])
        self.review()
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_skipped_required_tests_cannot_pass(self):
        self.prepare("skipped")
        self.assertNotEqual("passed", self.report["status"])
        self.review()
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_expected_failures_do_not_count_as_a_satisfied_criterion(self):
        self.prepare("expected-failure")
        self.assertNotEqual("passed", self.report["status"])
        self.review()
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_missing_runner_keeps_an_explicit_nonpassing_observation(self):
        self.prepare("unavailable")
        self.assertNotEqual("passed", self.report["status"])
        self.review()
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_missing_review_is_not_an_implicit_approval(self):
        self.prepare()
        result = self.finalize(review_path=self.directory / "missing-review.json")
        self.assertNotEqual("passed", result["status"])
        self.assertTrue(Path(result["assessment"]).is_file())

    def test_failed_agent_cannot_publish_a_passing_review(self):
        self.prepare()
        self.review()
        self.assertNotEqual("passed", self.finalize(agent_result="failure")["status"])

    def test_new_pr_head_invalidates_the_old_assessment(self):
        self.prepare()
        self.review()
        current = deepcopy(self.pr)
        current["head"]["sha"] = "f" * 40
        current_path = self.directory / "current-pr.json"
        self.write(current_path, current)
        self.assertNotEqual("passed", self.finalize(current_pr_path=current_path)["status"])

    def test_pr_diff_excludes_unrelated_changes_on_an_advanced_base(self):
        self.git("checkout", "--quiet", "-b", "advanced-base", self.base)
        (self.repo / "unrelated.txt").write_text("An unrelated base-only change.\n", encoding="utf-8")
        self.git("add", "unrelated.txt")
        self.git("commit", "--quiet", "-m", "Advance the target branch independently")
        advanced_base = self.git("rev-parse", "HEAD")
        self.git("checkout", "--quiet", "--detach", self.head)
        self.pr["base"]["sha"] = advanced_base
        self.write(self.pr_path, self.pr)
        self.prepare()
        target = load_json(self.bundle / "target.json")
        self.assertEqual(advanced_base, target["base_sha"])
        self.assertEqual(self.base, target["merge_base_sha"])
        diff = (self.bundle / "diff.patch").read_text(encoding="utf-8")
        self.assertIn("+answer = 42", diff)
        self.assertNotIn("unrelated.txt", diff)

    def test_actions_transport_rejects_another_run_or_attempt(self):
        self.prepare()
        github_quality.check_actions_run(self.bundle, environment={})
        github_quality.check_actions_run(self.bundle, environment={
            "GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "1",
        })
        for environment in (
            {"GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "2"},
            {"GITHUB_RUN_ID": "9999", "GITHUB_RUN_ATTEMPT": "1"},
            {"GITHUB_RUN_ID": "1234"},
        ):
            with self.subTest(environment=environment):
                with self.assertRaisesRegex(ValueError, "another GitHub run or attempt"):
                    github_quality.check_actions_run(self.bundle, environment=environment)

    def test_tampered_execution_evidence_is_rejected(self):
        self.prepare()
        self.review()
        evidence = self.report["evidence"][0]
        path = self.verification / evidence["uri"]
        path.write_bytes(path.read_bytes() + b"\nmodified after verification\n")
        with self.assertRaises(ValueError):
            self.finalize()

    def test_a_different_check_cannot_replace_a_required_criterion(self):
        self.prepare()
        self.review()
        report_path = self.verification / "verification-report.json"
        record = load_json(report_path)
        record["checks"][0]["id"] = "unrequired-check"
        record["payload"]["check_results"][0]["id"] = "unrequired-check"
        self.write(report_path, record)
        with self.assertRaisesRegex(ValueError, "required criterion"):
            self.finalize()

    def test_agent_cannot_waive_its_own_blocking_finding(self):
        self.prepare()
        self.review(findings=[{
            "id": "self-waiver", "severity": "high", "blocking": True,
            "disposition": "accepted-risk", "mechanism": "A defect the agent claims to waive.",
            "evidence": ["candidate-diff"],
        }])
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_supported_blocking_review_finding_survives_consolidation(self):
        self.prepare()
        self.review(findings=[{
            "id": "public-contract", "severity": "high", "blocking": True,
            "disposition": "open", "mechanism": "The reviewed diff violates a required public behavior.",
            "evidence": ["candidate-diff"],
        }])
        result = self.finalize()
        self.assertEqual("failed", result["status"])
        assessment = load_json(result["assessment"])
        self.assertEqual(1, len(assessment["payload"]["findings"]))
        finding = assessment["payload"]["findings"][0]
        self.assertTrue(finding["blocking"])
        self.assertEqual("open", finding["disposition"])
        self.assertEqual(["candidate-diff"], finding["source_evidence"])

    def test_report_from_another_run_is_rejected(self):
        self.prepare()
        self.review(run_id="another-workflow-attempt")
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_missing_review_criteria_cannot_satisfy_the_host_plan(self):
        self.prepare()
        self.review(criteria=[])
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_ambiguous_multiple_review_outputs_are_rejected(self):
        self.prepare()
        self.review()
        wrapper = load_json(self.review_path)
        wrapper["items"].append(deepcopy(wrapper["items"][0]))
        self.write(self.review_path, wrapper)
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_report_cannot_replace_the_host_subject(self):
        self.prepare()
        self.review(subject={**self.run["subject"], "revision": "f" * 40})
        self.assertNotEqual("passed", self.finalize()["status"])

    def test_independent_review_policy_remains_inconclusive_without_attestation(self):
        self.prepare(independent=True)
        self.review()
        result = self.finalize()
        self.assertEqual("inconclusive", result["status"])
        assessment = load_json(result["assessment"])
        self.assertFalse(assessment["payload"]["independence"]["established"])


class GitHubWorkflowBoundaryTests(unittest.TestCase):
    def test_compiled_workflow_has_no_write_permissions_and_gate_runs_after_failures(self):
        # Both authored Actions and compiler output are part of the trust
        # boundary. Check their emitted permission scalars without introducing
        # a YAML dependency into sfstack's portable test environment.
        paths = [ROOT / ".github/workflows/sfstack-quality.yml",
                 ROOT / ".github/workflows/sfstack-review.lock.yml"]
        for path in paths:
            with self.subTest(workflow=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"(?m)^\s+[a-z-]+:\s*['\"]?write['\"]?\s*(?:#.*)?$", source))
                self.assertIsNone(re.search(r"(?m)^\s*permissions:\s*['\"]?write-all", source))
        source = paths[0].read_text(encoding="utf-8")
        gate = re.search(r"(?ms)^  quality_gate:\n(.*?)(?=^  [a-z_]+:\n|\Z)", source)
        self.assertIsNotNone(gate, "The deterministic final gate must remain a workflow job.")
        self.assertRegex(gate.group(1), r"(?m)^    if: always\(\)\s*$")
        self.assertIn("quality.py finalize", gate.group(1))


if __name__ == "__main__":
    unittest.main()
