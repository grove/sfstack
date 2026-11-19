"""The GitHub bridge retains real observations and fails closed at handoffs."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def test_cancelled_or_skipped_agent_cannot_reuse_a_passing_submission(self):
        self.prepare()
        self.review()
        for state in ("cancelled", "skipped"):
            with self.subTest(state=state):
                result = github_quality.finalize(
                    self.bundle, self.verification, self.review_path, self.pr_path, state,
                    self.directory / ("result-" + state), at=self.at,
                )
                self.assertEqual("blocked", result["status"])
                self.assertTrue(any(state in reason for reason in result["reasons"]))
                self.assertTrue(Path(result["assessment"]).is_file())

    def test_cli_retains_failed_assessment_and_returns_a_failing_exit_status(self):
        self.prepare("failed")
        self.review()
        output = self.directory / "result"
        with patch.dict("os.environ", {"GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "1"}), redirect_stdout(io.StringIO()):
            code = github_quality.main([
                "finalize", "--bundle", str(self.bundle), "--verification", str(self.verification),
                "--review", str(self.review_path), "--current-pr", str(self.pr_path),
                "--agent-result", "success", "--out", str(output),
            ])
        self.assertEqual(2, code)
        gate = load_json(output / "quality-gate.json")
        self.assertEqual("failed", gate["status"])
        self.assertFalse(gate["success"])
        self.assertTrue((output / gate["assessment"]).is_file())

    def test_cli_missing_verification_produces_a_blocked_record(self):
        self.prepare()
        self.review()
        (self.verification / "verification-report.json").unlink()
        output = self.directory / "result"
        with patch.dict("os.environ", {"GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "1"}), redirect_stderr(io.StringIO()):
            code = github_quality.main([
                "finalize", "--bundle", str(self.bundle), "--verification", str(self.verification),
                "--review", str(self.review_path), "--current-pr", str(self.pr_path),
                "--agent-result", "success", "--out", str(output),
            ])
        self.assertNotEqual(0, code)
        gate = load_json(output / "quality-gate.json")
        self.assertEqual("blocked", gate["status"])
        self.assertFalse(gate["success"])
        self.assertTrue(gate["reasons"])
        self.assertIn("**Verdict: blocked**", (output / "summary.md").read_text())

    def test_new_pr_head_invalidates_the_old_assessment(self):
        self.prepare()
        self.review()
        current = deepcopy(self.pr)
        current["head"]["sha"] = "f" * 40
        current_path = self.directory / "current-pr.json"
        self.write(current_path, current)
        self.assertNotEqual("passed", self.finalize(current_pr_path=current_path)["status"])

    def test_advanced_base_invalidates_a_review_of_the_same_head(self):
        self.prepare()
        self.review()
        current = deepcopy(self.pr)
        current["base"]["sha"] = "f" * 40
        current_path = self.directory / "current-pr.json"
        self.write(current_path, current)
        result = self.finalize(current_pr_path=current_path)
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("base" in reason for reason in result["reasons"]))

    def test_closed_pr_cannot_receive_quality_clearance(self):
        self.prepare()
        self.review()
        current = deepcopy(self.pr)
        current["state"] = "closed"
        current_path = self.directory / "current-pr.json"
        self.write(current_path, current)
        self.assertEqual("blocked", self.finalize(current_pr_path=current_path)["status"])

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
    @staticmethod
    def jobs(source):
        return dict(re.findall(r"(?ms)^  ([a-z_]+):\n(.*?)(?=^  [a-z_]+:\n|\Z)",
                               source.split("\njobs:\n", 1)[1]))

    def test_agent_and_candidate_jobs_have_no_publication_permissions(self):
        # Job boundaries, rather than filtering the candidate's environment,
        # prevent source execution from inheriting the publisher credential.
        compiled = (ROOT / ".github/workflows/sfstack-review.lock.yml").read_text()
        source = (ROOT / ".github/workflows/sfstack-quality.yml").read_text()
        write = r"(?m)^\s+[a-z-]+:\s*['\"]?write['\"]?\s*(?:#.*)?$"
        self.assertIsNone(re.search(write, compiled))
        self.assertIsNone(re.search(write, source.split("\njobs:\n", 1)[0]))
        jobs = self.jobs(source)
        self.assertEqual({"start_check", "publish"}, {name for name, job in jobs.items() if re.search(write, job)})
        for name in ("prepare", "verify", "review", "quality_gate"):
            with self.subTest(job=name):
                self.assertIsNone(re.search(write, jobs[name]))
        self.assertNotIn("COPILOT_GITHUB_TOKEN", jobs["verify"])
        self.assertIn("needs.prepare.outputs.head-sha", jobs["verify"])
        self.assertIn("quality.py verify", jobs["verify"])
        self.assertRegex(jobs["quality_gate"], r"(?m)^    if: always\(\) && needs.start_check.outputs.eligible == 'true'\s*$")
        self.assertIn("quality.py finalize", jobs["quality_gate"])
        self.assertRegex(jobs["publish"], r"(?m)^    if: always\(\)\s*$")

    def test_all_metadata_writers_share_a_serial_lock_and_never_checkout_candidates(self):
        controller = self.jobs((ROOT / ".github/workflows/sfstack-quality.yml").read_text())
        coordinator = self.jobs((ROOT / ".github/workflows/sfstack-quality-events.yml").read_text())
        for name, job in ((name, controller[name]) for name in ("start_check", "publish")):
            with self.subTest(job=name):
                self.assertRegex(job, r"(?m)^      checks: write\s*$")
                self.assertNotIn("actions: write", job)
        self.assertIn("actions: write", coordinator["dispatch"])
        self.assertNotIn("actions: write", coordinator["reconcile"])
        for name, job in {**{key: controller[key] for key in ("start_check", "publish")}, **coordinator}.items():
            with self.subTest(job=name):
                self.assertIn("group: sfstack-quality-publication-${{ github.repository }}", job)
                self.assertIn("queue: max", job)
                self.assertNotIn("cancel-in-progress: true", job)
                self.assertNotIn("path: candidate", job)
                self.assertNotIn("quality.py", job)
                self.assertNotIn("COPILOT_GITHUB_TOKEN", job)
                self.assertEqual(job.count("uses: actions/checkout@"), job.count("ref: ${{ github.workflow_sha }}"))
                self.assertNotIn("persist-credentials: true", job)
        for job in coordinator.values():
            self.assertNotIn("download-artifact", job)

    def test_pr_signal_has_no_credentials_or_candidate_execution(self):
        source = (ROOT / ".github/workflows/sfstack-pr-signal.yml").read_text()
        self.assertIn("permissions: {}", source)
        self.assertIn("pull_request:", source)
        self.assertNotIn("pull_request_target", source)
        self.assertNotIn("uses:", source)
        self.assertNotIn("secrets.", source)
        self.assertNotIn("github.token", source)


if __name__ == "__main__":
    unittest.main()
