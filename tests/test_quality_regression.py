"""Run actual candidate tests through the local quality adapter and retain failure."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
from run_quality_regression import ADAPTER, WORKFLOW, prepare_case, run_regression, write_json
from common import load_json, now
from local_slice import run_one
from python_unittest import snapshot_digest


class ExecutedQualityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_real_failure_survives_quality_and_incomplete_checks_never_pass(self):
        output = self.directory / "results"
        summary = run_regression(output)
        self.assertEqual("failed", summary["cases"]["boundary"]["quality"])
        self.assertEqual("passed", summary["cases"]["fixed"]["verification"])
        self.assertEqual("inconclusive", summary["cases"]["fixed"]["quality"])
        for variant in ("skipped", "empty"):
            self.assertEqual("inconclusive", summary["cases"][variant]["verification"])
        report = load_json(output / "boundary" / "quality" / "quality-assessment.json")
        finding = report["payload"]["findings"][0]
        self.assertTrue(finding["blocking"])
        self.assertEqual("open", finding["disposition"])
        stderr = (output / "boundary" / "verification" / "evidence" / "stderr.txt").read_text()
        self.assertIn("test_exact", stderr)
        self.assertIn("FAILED", stderr)
        self.assertTrue(summary["stale_evidence_rejected"])
        self.assertTrue(summary["tampered_evidence_rejected"])

    def test_candidate_change_after_pinning_prevents_checkpoint(self):
        at = now()
        run, _ = prepare_case(self.directory / "case", "fixed", at)
        candidate = run.parent / "records" / "candidate" / "inventory.py"
        candidate.write_text(candidate.read_text() + "\n# changed after pinning\n")
        with self.assertRaisesRegex(ValueError, "Adapter exited"):
            run_one(WORKFLOW, run, "verify", ADAPTER, "next.json", "verification", at)
        self.assertFalse((run.parent / "next.json").exists())
        self.assertFalse((run.parent / "verification").exists())

    def test_test_change_after_pinning_prevents_checkpoint(self):
        at = now()
        run, _ = prepare_case(self.directory / "case", "fixed", at)
        test = run.parent / "records" / "tests" / "test_inventory.py"
        test.write_text("# A green empty suite must not replace the pinned checks.\n")
        with self.assertRaisesRegex(ValueError, "Adapter exited"):
            run_one(WORKFLOW, run, "verify", ADAPTER, "next.json", "verification", at)
        self.assertFalse((run.parent / "next.json").exists())

    def repin_tests(self, run):
        path = run.parent / "records" / "test-plan.json"
        record = load_json(path)
        record["payload"]["python_unittest"]["tests_sha256"] = snapshot_digest(path.parent / "tests")
        write_json(path, record)

    def test_test_helper_cannot_shadow_the_pinned_candidate(self):
        at = now()
        run, _ = prepare_case(self.directory / "collision", "boundary", at)
        tests = run.parent / "records" / "tests"
        grader = tests / "test_inventory.py"
        body = grader.read_text().split("class InventoryContract", 1)[1]
        grader.write_text("import unittest\nimport inventory as module\n\nclass InventoryContract" + body)
        source = (run.parent / "records" / "candidate" / "inventory.py").read_text()
        (tests / "inventory.py").write_text(source.replace("requested >= available", "requested > available"))
        self.repin_tests(run)
        result = run_one(WORKFLOW, run, "verify", ADAPTER, "next.json", "verification", at)
        record = load_json(result["artifact"])
        self.assertEqual("failed", record["status"])
        self.assertEqual(6, record["payload"]["executed_count"])
        self.assertEqual(1, record["payload"]["failed_count"])
        self.assertIn("test_exact", (Path(result["artifact"]).parent / "evidence" / "stderr.txt").read_text())

    def test_suite_and_discovery_errors_keep_valid_negative_evidence(self):
        at = now()
        for variant in ("setup", "teardown", "discovery"):
            with self.subTest(variant=variant):
                run, _ = prepare_case(self.directory / variant, "fixed", at)
                grader = run.parent / "records" / "tests" / "test_inventory.py"
                if variant == "discovery":
                    grader.write_text("raise RuntimeError('fixture discovery failed')\n")
                else:
                    method = "setUpClass" if variant == "setup" else "tearDownClass"
                    grader.write_text(grader.read_text().replace(
                        "class InventoryContract(unittest.TestCase):",
                        "class InventoryContract(unittest.TestCase):\n"
                        f"    @classmethod\n    def {method}(cls):\n"
                        f"        raise RuntimeError('fixture {variant} failed')\n",
                    ))
                self.repin_tests(run)
                result = run_one(WORKFLOW, run, "verify", ADAPTER, "next.json", "verification", at)
                record = load_json(result["artifact"])
                self.assertEqual("inconclusive", record["status"])
                self.assertEqual(6 if variant == "teardown" else 0, record["payload"]["executed_count"])
                self.assertEqual(0, record["payload"]["failed_count"])
                self.assertTrue(record["payload"]["suite_errors"])
                stderr = Path(result["artifact"]).parent / "evidence" / "stderr.txt"
                self.assertIn(f"fixture {variant} failed", stderr.read_text())
                self.assertTrue(Path(result["checkpoint"]).is_file())

    def git_case(self, label, at):
        run, _ = prepare_case(self.directory / label, "fixed", at)
        candidate = run.parent / "records" / "candidate"

        def git(*args):
            return subprocess.run([
                "git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args,
            ], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip()

        git("init", "--quiet")
        git("add", "inventory.py")
        git("commit", "--quiet", "-m", "Pin regression candidate")
        revision = git("rev-parse", "HEAD")
        self.set_revision(run, revision)
        return run, candidate

    def set_revision(self, run, revision):
        for path in [run, *sorted((run.parent / "records").glob("*.json"))]:
            data = load_json(path)
            data["subject"]["revision"] = revision
            if data.get("artifact_type") == "change-set":
                data["payload"]["candidate_revision"] = revision
            write_json(path, data)

    def test_clean_git_candidate_uses_exact_commit_identity(self):
        at = now()
        run, _ = self.git_case("git-clean", at)
        result = run_one(WORKFLOW, run, "verify", ADAPTER, "next.json", "verification", at)
        self.assertEqual("passed", load_json(result["artifact"])["status"])

    def test_wrong_git_head_or_pinned_dirty_checkout_cannot_verify(self):
        at = now()
        for variant in ("wrong-head", "dirty"):
            with self.subTest(variant=variant):
                run, candidate = self.git_case(variant, at)
                if variant == "wrong-head":
                    self.set_revision(run, "0" * 40)
                else:
                    source = candidate / "inventory.py"
                    source.write_text(source.read_text() + "\n# Dirty bytes are pinned but not committed.\n")
                    path = run.parent / "records" / "test-plan.json"
                    test_plan = load_json(path)
                    test_plan["payload"]["python_unittest"]["candidate_sha256"] = snapshot_digest(candidate)
                    write_json(path, test_plan)
                with self.assertRaisesRegex(ValueError, "Adapter exited"):
                    run_one(WORKFLOW, run, "verify", ADAPTER, "next.json", "verification", at)
                self.assertFalse((run.parent / "next.json").exists())


if __name__ == "__main__":
    unittest.main()
