"""Independent Quality Factory, report integrity, and composition regressions."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from common import contracts, inspect_artifact, load_json, now, workflow_errors
from factory import evaluate_gate, plan
from quality_report import consolidate

AT = now("2026-11-19T12:00:00Z")


class QualityWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / "examples"
        shutil.copytree(ROOT / "examples", self.dir)

    def planned(self, name="quality", manifest="quality-ready-run.json"):
        return plan(ROOT / "workflows" / f"{name}.json", self.dir / manifest, AT)

    def edit(self, path, callback):
        target = self.dir / path
        obj = load_json(target)
        callback(obj)
        target.write_text(json.dumps(obj), encoding="utf-8")

    def test_quality_runs_independently_from_a_request(self):
        result = self.planned(manifest="quality-run.json")
        self.assertEqual(["orient"], result["ready"])
        self.assertEqual("ready", result["status"])
        steps = load_json(ROOT / "workflows" / "quality.json")["steps"]
        self.assertNotIn("sf-build-change", {step["skill"] for step in steps})
        self.assertNotIn("sf-prepare-review", {step["skill"] for step in steps})

    def test_snapshot_and_external_pr_can_both_reach_reporting(self):
        for manifest in ("quality-ready-run.json", "quality-pr-ready-run.json"):
            with self.subTest(manifest=manifest):
                result = self.planned(manifest=manifest)
                self.assertEqual(["consolidate"], result["ready"])
                self.assertEqual("passed", result["outcomes"]["scope"]["change-set"])

    def test_failing_verification_and_review_remain_consumable_as_reports(self):
        result = self.planned(manifest="quality-failed-run.json")
        self.assertEqual(["consolidate"], result["ready"])
        self.assertEqual("failed", result["outcomes"]["verify"]["verification-report"])
        self.assertEqual("failed", result["outcomes"]["review"]["review-report"])
        self.assertEqual("ready", result["status"])

    def test_failed_scope_cannot_be_passed_to_verification_or_review(self):
        def fail_scope(record):
            record["status"] = "failed"
            record["checks"][0]["status"] = "failed"
            record["unresolved"].append("Candidate identity was contradicted.")
        self.edit("records/quality-change-set.json", fail_scope)
        result = self.planned()
        self.assertEqual("failed", result["outcomes"]["scope"]["change-set"])
        self.assertNotIn("verify", result["ready"])
        self.assertNotIn("review", result["ready"])
        self.assertNotIn("consolidate", result["ready"])
        self.assertIn("status failed", " ".join(result["blocked"]["tests"]))

    def test_stale_or_modified_evidence_does_not_get_accepted(self):
        self.edit("records/quality-review-failed.json",
                  lambda r: r["subject"].update(revision="other"))
        result = self.planned(manifest="quality-failed-run.json")
        self.assertNotIn("consolidate", result["ready"])
        self.assertIn("stale subject", " ".join(result["blocked"]["review"]))

    def test_explicit_security_compatibility_risk_recipe(self):
        result = self.planned(name="quality-risk", manifest="quality-risk-ready-run.json")
        self.assertEqual(["consolidate"], result["ready"])
        self.assertEqual("passed", result["outcomes"]["security"]["security-assessment"])
        self.assertEqual("passed", result["outcomes"]["compatibility"]["compatibility-report"])

    def test_quality_mode_rejects_mutation_capabilities_and_effects(self):
        wf = load_json(ROOT / "workflows" / "quality.json")
        wf["steps"][3]["skill"] = "sf-build-change"
        self.assertIn("quality workflows cannot declare mutations",
                      " ".join(workflow_errors(wf, contracts())))

    def test_nonpass_acceptance_is_quality_only_and_scoped_to_dependency(self):
        wf = load_json(ROOT / "workflows" / "quality.json")
        wf["mode"] = "software"
        self.assertIn("only permitted in quality workflows",
                      " ".join(workflow_errors(wf, contracts())))
        wf["mode"] = "quality"
        wf["steps"][-1]["accept_statuses"]["not-a-parent"] = ["failed"]
        self.assertIn("accept_statuses names a non-dependency",
                      " ".join(workflow_errors(wf, contracts())))

    def test_mutation_gate_still_rejects_failing_verification(self):
        self.edit("gate-request.json", lambda r: r["artifacts"].__setitem__(
            0, "records/quality-verification-failed.json"))
        result = evaluate_gate(self.dir / "gate-request.json", self.dir / "policy.json", AT)
        self.assertEqual("blocked", result["decision"])
        self.assertIn("status is failed", " ".join(result["reasons"]))


class QualitySummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / "examples"
        shutil.copytree(ROOT / "examples", self.dir)

    def summarize(self, run="quality-ready-run.json", workflow="quality", out="quality-output"):
        return consolidate(
            ROOT / "workflows" / f"{workflow}.json",
            self.dir / run, out, AT, out_run="quality-after.json",
        )

    def test_rehearsal_emits_inconclusive_assessment_without_fake_independence(self):
        result = self.summarize()
        self.assertEqual("inconclusive", result["status"])
        report_path = self.dir / "quality-output" / "quality-assessment.json"
        assessment = load_json(report_path)
        self.assertFalse(assessment["payload"]["remediation_authorized"])
        self.assertFalse(assessment["payload"]["independence"]["established"])
        self.assertIn("security-assessment", assessment["payload"]["coverage"]["omitted"])
        self.assertEqual("inconclusive", assessment["status"])
        self.assertTrue((report_path.parent / "support" / "verification-report" / "evidence" / "fixture.txt").exists())
        _, errs = inspect_artifact(report_path, assessment["subject"],
                                   assessment["run_id"], AT, 3600,
                                   "quality-assessment", allow_nonpassing=True)
        self.assertEqual([], errs)
        resumed = plan(ROOT / "workflows" / "quality.json",
                       self.dir / "quality-after.json", AT)
        self.assertEqual("complete", resumed["status"])
        self.assertEqual("inconclusive",
                         resumed["outcomes"]["consolidate"]["quality-assessment"])

    def test_known_failure_stays_failed_with_its_finding(self):
        result = self.summarize(run="quality-failed-run.json")
        self.assertEqual("failed", result["status"])
        report = load_json(self.dir / "quality-output" / "quality-assessment.json")
        self.assertEqual("failed", report["status"])
        self.assertEqual(1, len(report["payload"]["findings"]))
        self.assertTrue(report["payload"]["findings"][0]["blocking"])
        self.assertEqual("open", report["payload"]["findings"][0]["disposition"])
        self.assertIn("verification-report", report["payload"]["coverage"]["required"])

    def test_external_pr_target_is_not_rebuilt(self):
        result = self.summarize(run="quality-pr-ready-run.json")
        report = load_json(self.dir / "quality-output" / "quality-assessment.json")
        self.assertEqual("pull-request", report["payload"]["target"]["kind"])
        self.assertEqual("base-123", report["payload"]["target"]["base_revision"])
        self.assertEqual("inconclusive", result["status"])

    def test_external_change_reuses_the_same_quality_workflow(self):
        scope = self.dir / "records" / "quality-change-set.json"
        artifact = load_json(scope)
        artifact["payload"]["target_kind"] = "external-change"
        artifact["payload"]["source_reference"] = "synthetic/supplied-patch@demo-candidate-7b4a"
        scope.write_text(json.dumps(artifact))
        self.summarize()
        result = load_json(self.dir / "quality-output" / "quality-assessment.json")
        self.assertEqual("external-change", result["payload"]["target"]["kind"])

    def test_passing_quality_cannot_list_a_failed_selected_report(self):
        policy_path = self.dir / "policy.json"
        policy = load_json(policy_path)
        policy["require_independent_review"] = False
        policy_path.write_text(json.dumps(policy))
        self.summarize()
        path = self.dir / "quality-output" / "quality-assessment.json"
        artifact = load_json(path)
        target = next(x for x in artifact["payload"]["reports"]
                      if x["artifact_type"] == "verification-report")
        target["status"] = "failed"
        path.write_text(json.dumps(artifact))
        _, problems = inspect_artifact(
            path, artifact["subject"], artifact["run_id"], AT, 3600,
            allow_nonpassing=True,
        )
        self.assertIn("selected quality report", " ".join(problems))

    def test_risk_checks_are_included_and_other_checks_not_assumed(self):
        self.summarize(run="quality-risk-ready-run.json", workflow="quality-risk")
        report = load_json(self.dir / "quality-output" / "quality-assessment.json")
        evaluated = report["payload"]["coverage"]["evaluated"]
        self.assertIn("security-assessment", evaluated)
        self.assertIn("compatibility-report", evaluated)
        self.assertNotIn("privacy-assessment", evaluated)
        self.assertIn("privacy-assessment", report["payload"]["coverage"]["omitted"])

    def test_unselected_required_dimension_blocks_clearance(self):
        p = self.dir / "records" / "quality-request.json"
        request = load_json(p)
        request["payload"]["required_assessments"].append("security-assessment")
        p.write_text(json.dumps(request))
        result = self.summarize()
        self.assertEqual("blocked", result["status"])
        artifact = load_json(self.dir / "quality-output" / "quality-assessment.json")
        self.assertIn("security-assessment", artifact["payload"]["coverage"]["required"])
        self.assertNotIn("security-assessment", artifact["payload"]["coverage"]["evaluated"])

    def test_report_tampering_is_detected_by_gate(self):
        self.summarize()
        path = self.dir / "quality-output" / "quality-assessment.json"
        artifact = load_json(path)
        raw = path.parent / "support" / "review-report" / "evidence" / "fixture.txt"
        raw.write_text("tampered")
        _, problems = inspect_artifact(
            path, artifact["subject"], artifact["run_id"], AT, 3600,
            "quality-assessment", allow_nonpassing=True,
        )
        self.assertIn("digest mismatch", " ".join(problems))

    def test_software_factory_gate_can_require_quality_but_not_bypass_it(self):
        self.summarize()
        policy_path = self.dir / "policy.json"
        policy = load_json(policy_path)
        policy["required_artifacts"]["integration.modify"].append("quality-assessment")
        policy_path.write_text(json.dumps(policy))
        gate_path = self.dir / "gate-request.json"
        gate = load_json(gate_path)
        gate["artifacts"].append("quality-output/quality-assessment.json")
        gate_path.write_text(json.dumps(gate))
        decision = evaluate_gate(gate_path, policy_path, AT)
        self.assertEqual("blocked", decision["decision"])
        self.assertIn("status is inconclusive", " ".join(decision["reasons"]))

    def test_authorized_scoped_pass_can_satisfy_optional_quality_gate(self):
        policy_path = self.dir / "policy.json"
        policy = load_json(policy_path)
        policy["require_independent_review"] = False
        policy["required_artifacts"]["integration.modify"].append("quality-assessment")
        policy_path.write_text(json.dumps(policy))
        result = self.summarize()
        self.assertEqual("passed", result["status"])
        gate_path = self.dir / "gate-request.json"
        gate = load_json(gate_path)
        gate["artifacts"].append("quality-output/quality-assessment.json")
        gate_path.write_text(json.dumps(gate))
        decision = evaluate_gate(gate_path, policy_path, AT)
        self.assertEqual("allowed", decision["decision"], decision)

    def test_no_report_overwrite(self):
        self.summarize()
        with self.assertRaisesRegex(ValueError, "must be new"):
            self.summarize()

    def test_invalid_quality_payload_blocks_without_crashing(self):
        self.summarize()
        path = self.dir / "quality-output" / "quality-assessment.json"
        artifact = load_json(path)
        artifact["payload"]["coverage"] = "invalid"
        path.write_text(json.dumps(artifact))
        _, problems = inspect_artifact(
            path, artifact["subject"], artifact["run_id"], AT, 3600,
            allow_nonpassing=True,
        )
        self.assertIn("invalid payload-quality-assessment", " ".join(problems))


if __name__ == "__main__":
    unittest.main()
