"""Independent runs can share exact approved proof without relabeling history."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from common import load_json, now
from factory import evaluate_gate, inspect_proof
from quality_report import consolidate

AT = now("2026-11-19T12:00:00Z")


class QualityImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "examples"
        shutil.copytree(ROOT / "examples", self.directory)
        self.policy = load_json(self.directory / "policy.json")
        self.policy["require_independent_review"] = False
        self.save("policy.json", self.policy)
        result = consolidate(ROOT / "workflows/quality.json", self.directory / "quality-ready-run.json",
                             "assessment", AT)
        self.assessment = Path(result["assessment"])
        self.original = self.assessment.read_bytes()
        self.request = load_json(self.directory / "gate-request.json")
        self.request["run_id"] = "delivery-run"
        self.request["artifacts"] = ["assessment/quality-assessment.json"]
        self.policy["required_artifacts"][self.request["effect"]] = ["quality-assessment"]
        for grant in self.policy["grants"]:
            grant["run_id"] = "delivery-run"
        self.policy["quality_imports"] = [{
            "source_run_id": "tutorial-run", "target_run_id": "delivery-run",
            "sha256": hashlib.sha256(self.original).hexdigest(), "expires_at": "2026-11-19T13:00:00Z",
        }]

    def save(self, path, value):
        (self.directory / path).write_text(json.dumps(value), encoding="utf-8")

    def gate(self):
        self.save("gate-request.json", self.request)
        self.save("policy.json", self.policy)
        return evaluate_gate(self.directory / "gate-request.json", self.directory / "policy.json", AT)

    def test_approved_import_preserves_original_run_and_bytes(self):
        result = self.gate()
        self.assertEqual("allowed", result["decision"], result["reasons"])
        self.assertEqual(self.original, self.assessment.read_bytes())
        record, errors = inspect_proof(self.assessment, self.request["subject"], "delivery-run", AT,
                                      self.policy, "quality-assessment")
        self.assertFalse(errors)
        self.assertEqual("tutorial-run", record["run_id"])

    def test_no_import_approval_cannot_reuse_an_independent_run(self):
        self.policy.pop("quality_imports")
        self.assertEqual("blocked", self.gate()["decision"])

    def test_import_is_bound_to_hash_runs_and_expiry(self):
        original = deepcopy(self.policy["quality_imports"][0])
        for field, value in (("sha256", "0" * 64), ("source_run_id", "another-source"),
                             ("target_run_id", "another-consumer"), ("expires_at", "2026-11-19T12:00:00Z")):
            with self.subTest(field=field):
                self.policy["quality_imports"] = [{**original, field: value}]
                self.assertEqual("blocked", self.gate()["decision"])

    def test_import_does_not_relax_exact_subject_or_evidence_age(self):
        original = deepcopy(self.request["subject"])
        for field, value in (("revision", "another-revision"), ("input_digest", "0" * 64),
                             ("environment", "another-environment")):
            with self.subTest(field=field):
                self.request["subject"] = {**original, field: value}
                for grant in self.policy["grants"]:
                    grant["subject"] = deepcopy(self.request["subject"])
                result = self.gate()
                self.assertEqual("blocked", result["decision"])
                self.assertIn("stale subject", " ".join(result["reasons"]))
        self.request["subject"] = original
        self.policy["max_evidence_age_seconds"] = 60
        self.assertIn("evidence age", " ".join(self.gate()["reasons"]))

    def test_import_never_grants_effects_or_independence(self):
        self.policy["grants"] = []
        self.assertIn("authorization", " ".join(self.gate()["reasons"]))
        self.policy["require_independent_review"] = True
        self.assertIn("independent review", " ".join(self.gate()["reasons"]))

    def test_policy_requirements_cannot_be_removed_by_the_summary(self):
        self.policy["required_quality_reports"] = ["verification-report", "security-assessment"]
        result = self.gate()
        self.assertEqual("blocked", result["decision"])
        self.assertIn("security-assessment", " ".join(result["reasons"]))

    def test_only_quality_assessments_can_be_imported(self):
        self.request["artifacts"] = ["records/verification-report.json"]
        self.policy["required_artifacts"][self.request["effect"]] = ["verification-report"]
        self.policy["quality_imports"][0]["sha256"] = hashlib.sha256(
            (self.directory / "records/verification-report.json").read_bytes()).hexdigest()
        self.assertIn("wrong run_id", " ".join(self.gate()["reasons"]))


if __name__ == "__main__":
    unittest.main()
