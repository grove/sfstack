"""A summary cannot change the meaning of its retained source reports."""
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
from common import inspect_artifact, load_json, now
from quality_report import consolidate

AT = now("2026-11-19T12:00:00Z")


class QualityIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "examples"
        shutil.copytree(ROOT / "examples", self.directory)
        policy = load_json(self.directory / "policy.json")
        policy["require_independent_review"] = False
        self.write(self.directory / "policy.json", policy)

    def write(self, path, record):
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    def summarize(self, manifest="quality-ready-run.json"):
        result = consolidate(ROOT / "workflows" / "quality.json",
                             self.directory / manifest, "output", AT)
        self.path = Path(result["assessment"])
        self.assessment = load_json(self.path)
        return result

    def problems(self):
        self.write(self.path, self.assessment)
        _, errors = inspect_artifact(self.path, self.assessment["subject"],
                                     self.assessment["run_id"], AT, 3600,
                                     allow_nonpassing=True)
        return " ".join(errors)

    def replace_source(self, kind, edit):
        report = next(r for r in self.assessment["payload"]["reports"]
                      if r["artifact_type"] == kind)
        evidence = next(e for e in self.assessment["evidence"]
                        if e["id"] == report["evidence_id"])
        path = self.path.parent / evidence["uri"]
        source = load_json(path)
        edit(source)
        self.write(path, source)
        # A new summary hash alone must not legitimize a changed source claim.
        evidence["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_hash_correct_failed_source_cannot_be_relabelled_passed(self):
        self.summarize()
        def fail(record):
            record["status"] = "failed"
            record["checks"][0]["status"] = "failed"
            record["payload"]["failed_count"] = 1
        self.replace_source("verification-report", fail)
        self.assertIn("source metadata", self.problems())

    def test_retained_report_identity_is_checked(self):
        self.summarize()
        self.replace_source("review-report", lambda r: r.update(artifact_id="different-review"))
        self.assertIn("source metadata", self.problems())

    def test_retained_source_must_match_run_and_subject(self):
        self.summarize()
        self.replace_source("review-report", lambda r: r.update(run_id="other-run"))
        self.replace_source("verification-report", lambda r: r["subject"].update(revision="other-head"))
        errors = self.problems()
        self.assertIn("wrong run_id", errors)
        self.assertIn("stale subject", errors)

    def test_target_revision_cannot_differ_from_envelope(self):
        self.summarize()
        self.assessment["payload"]["target"]["revision"] = "different-head"
        self.assertIn("target revision", self.problems())

    def test_nonpassing_source_cannot_be_hidden_by_editing_coverage(self):
        self.summarize()
        self.assessment["payload"]["coverage"]["evaluated"].remove("impact-assessment")
        self.assessment["payload"]["coverage"]["required"].remove("impact-assessment")
        self.assertIn("coverage", self.problems())

    def test_nested_quality_sources_are_rejected_without_recursion(self):
        self.summarize()
        nested = deepcopy(self.assessment)
        self.replace_source("review-report", lambda r: (r.clear(), r.update(nested)))
        self.assertIn("nested quality", self.problems())

    def test_source_checks_are_validated_not_just_report_hashes(self):
        self.summarize()
        self.replace_source("verification-report", lambda r: r["payload"].update(executed_count=0))
        self.assertIn("no executed checks", self.problems())

    def test_failed_report_keeps_location_and_source_evidence(self):
        self.summarize("quality-failed-run.json")
        finding = self.assessment["payload"]["findings"][0]
        self.assertEqual("demo/name-handler.py", finding["location"])
        self.assertEqual(["fixture"], finding["source_evidence"])
        self.assertEqual("", self.problems())

    def test_finding_cannot_be_dropped_or_downgraded(self):
        self.summarize("quality-failed-run.json")
        original = deepcopy(self.assessment)
        self.assessment["payload"]["findings"] = []
        self.assertIn("source findings", self.problems())
        self.assessment = original
        self.assessment["payload"]["findings"][0]["blocking"] = False
        self.assertIn("source finding", self.problems())

    def test_finding_source_and_evidence_references_are_checked(self):
        self.summarize("quality-failed-run.json")
        finding = self.assessment["payload"]["findings"][0]
        finding["source_report"] = "invented"
        finding["evidence"] = ["missing"]
        errors = self.problems()
        self.assertIn("source report", errors)
        self.assertIn("evidence", errors)

    def test_valid_waiver_is_preserved_and_cannot_be_removed(self):
        path = self.directory / "records" / "review-report.json"
        record = load_json(path)
        record["evidence"][0]["kind"] = "approval"
        record["payload"]["findings"] = [{
            "id": "accepted-risk", "blocking": True, "disposition": "accepted-risk",
            "location": "source.py:42", "evidence": ["fixture"],
            "waiver": {"actor": "risk-owner", "decision": "Accept in this scope", "evidence": "fixture"},
        }]
        self.write(path, record)
        self.summarize()
        finding = self.assessment["payload"]["findings"][0]
        self.assertEqual("risk-owner", finding["waiver"]["actor"])
        self.assertEqual("source.py:42", finding["location"])
        self.assertEqual("", self.problems())
        del finding["waiver"]
        self.assertIn("waiver", self.problems())

    def test_policy_required_dimension_cannot_be_omitted(self):
        path = self.directory / "policy.json"
        policy = load_json(path)
        policy["required_quality_reports"] = ["security-assessment"]
        self.write(path, policy)
        self.assertEqual("blocked", self.summarize()["status"])
        self.assertIn("security-assessment", self.assessment["payload"]["coverage"]["required"])


if __name__ == "__main__":
    unittest.main()
