"""Tests for typed claims, revalidation impact, paired evaluation, and local dispatch."""
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

from common import load_json, now
from evidence_impact import plan_impact
from compare_trials import compare_trials
from factory import evaluate_gate
from local_slice import run_one


class TypedPayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.examples = Path(self.tmp.name) / "examples"
        shutil.copytree(ROOT / "examples", self.examples)

    def gate(self):
        return evaluate_gate(
            self.examples / "gate-request.json",
            self.examples / "policy.json",
            now("2026-11-19T12:00:00Z"),
        )

    def edit(self, filename, transform):
        path = self.examples / "records" / filename
        artifact = load_json(path)
        transform(artifact["payload"])
        path.write_text(json.dumps(artifact), encoding="utf-8")

    def test_verification_missing_core_field_is_blocked_without_crashing(self):
        self.edit("verification-report.json", lambda p: p.pop("required_count"))
        result = self.gate()
        self.assertEqual("blocked", result["decision"])
        self.assertIn("invalid payload-verification-report", " ".join(result["reasons"]))

    def test_verification_noninteger_count_is_blocked(self):
        self.edit("verification-report.json", lambda p: p.update(executed_count="1"))
        result = self.gate()
        self.assertEqual("blocked", result["decision"])
        self.assertIn("invalid payload-verification-report", " ".join(result["reasons"]))

    def test_review_wrong_disposition_is_blocked(self):
        self.edit("review-report.json", lambda p: p.update(findings=[{
            "blocking": False, "disposition": "waived"
        }]))
        result = self.gate()
        self.assertEqual("blocked", result["decision"])
        self.assertIn("invalid payload-review-report", " ".join(result["reasons"]))


class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(ROOT / "examples" / "evidence-impact.json")

    def test_changed_source_invalidates_downstream_but_not_specification(self):
        result = plan_impact(self.manifest)
        self.assertEqual(["source:inventory"], result["changed_inputs"])
        self.assertEqual(["specification"], [x["id"] for x in result["reuse_candidates"]])
        self.assertEqual(["implementation", "verification", "review"],
                         [x["id"] for x in result["revalidate"]])
        self.assertTrue(result["advisory_only"])

    def test_missing_input_forces_revalidation(self):
        self.manifest["after"]["inputs"].pop("spec")
        result = plan_impact(self.manifest)
        self.assertIn("specification", [x["id"] for x in result["revalidate"]])
        self.assertEqual([], result["reuse_candidates"])

    def test_incomplete_inventory_forces_all(self):
        self.manifest["complete_inventory"] = False
        self.assertEqual(4, len(plan_impact(self.manifest)["revalidate"]))

    def test_environment_change_forces_all(self):
        self.manifest["after"]["subject"]["environment"] = "ci-macos"
        self.assertEqual(4, len(plan_impact(self.manifest)["revalidate"]))

    def test_unaccounted_digest_change_forces_all(self):
        self.manifest["after"]["inputs"] = deepcopy(self.manifest["before"]["inputs"])
        self.assertEqual(4, len(plan_impact(self.manifest)["revalidate"]))

    def test_cycles_and_unknown_references_fail_closed(self):
        self.manifest["claims"][0]["needs"] = ["review"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            plan_impact(self.manifest)
        self.manifest["claims"][0]["needs"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown upstream"):
            plan_impact(self.manifest)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.data = load_json(ROOT / "examples" / "comparative-trials-synthetic.json")

    def test_paired_summary_is_labeled_descriptive(self):
        result = compare_trials(self.data)
        self.assertEqual(1, result["paired_trials"])
        self.assertEqual(1.0, result["means"]["contracts"]["correct"])
        self.assertEqual(0.24, result["means"]["contracts"]["cost_usd"])
        self.assertIn("Descriptive only", result["interpretation"])

    def test_missing_variant_cannot_be_misrepresented(self):
        self.data["trials"].pop()
        with self.assertRaisesRegex(ValueError, "Unpaired trial"):
            compare_trials(self.data)

    def test_duplicate_and_agent_mismatch_are_rejected(self):
        self.data["trials"].append(deepcopy(self.data["trials"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate trial"):
            compare_trials(self.data)
        self.data["trials"].pop()
        self.data["trials"][0]["agent"] = "different-agent"
        with self.assertRaisesRegex(ValueError, "Agent mismatch"):
            compare_trials(self.data)


class LocalSliceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.examples = Path(self.tmp.name) / "examples"
        shutil.copytree(ROOT / "examples", self.examples)

    def run_slice(self, script):
        return run_one(
            ROOT / "workflows" / "feature.json",
            self.examples / "feature-run.json",
            "orient", script, "step-1.json", "generated/orient",
            now("2026-11-19T12:00:00Z"),
        )

    def test_effect_free_adapter_produces_valid_artifact_and_next_checkpoint(self):
        result = self.run_slice(ROOT / "tools" / "fixtures" / "synthetic_map_agent.py")
        self.assertEqual("orient", result["completed_step"])
        self.assertEqual(["clarify"], result["next_ready"])
        updated = load_json(self.examples / "step-1.json")
        self.assertEqual(["generated/orient/result.json"], updated["completed"]["orient"])
        self.assertEqual("project-context", load_json(self.examples / "generated/orient/result.json")["artifact_type"])

    def test_invalid_adapter_does_not_advance_manifest(self):
        script = Path(self.tmp.name) / "bad_agent.py"
        script.write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[-1]).write_text('{}')\n")
        with self.assertRaises(ValueError):
            self.run_slice(script)
        self.assertFalse((self.examples / "step-1.json").exists())
        self.assertFalse((self.examples / "generated" / "orient").exists())

    def test_existing_output_is_not_overwritten(self):
        (self.examples / "step-1.json").write_text("already there")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_slice(ROOT / "tools" / "fixtures" / "synthetic_map_agent.py")


if __name__ == "__main__":
    unittest.main()
