"""An actual failing candidate and its fix traverse the GitHub evidence bridge."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
from run_github_regression import run_regression
from common import load_json


class GitHubExecutedRegressionTests(unittest.TestCase):
    def test_failure_then_fix_uses_the_same_checks_with_distinct_candidate_commits(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "regression"
            result = run_regression(output)
            failed, fixed = (result["cases"][variant] for variant in ("defective", "fixed"))
            self.assertEqual("failed", failed["quality"])
            self.assertEqual("passed", fixed["quality"])
            self.assertNotEqual(failed["head_sha"], fixed["head_sha"])
            self.assertEqual(failed["base_sha"], fixed["base_sha"])
            self.assertEqual(6, failed["tests_run"])
            self.assertEqual(6, fixed["tests_run"])
            self.assertGreater(failed["failed_reports"], 0)
            self.assertEqual(0, fixed["failed_reports"])
            self.assertFalse(failed["mutation_authorized"])
            self.assertFalse(fixed["mutation_authorized"])
            plans = [load_json(output / variant / "inputs/target.json")["checks"]
                     for variant in ("defective", "fixed")]
            self.assertEqual(plans[0], plans[1])
            self.assertIn("FAIL: test_exact", (output / failed["verification_log"]).read_text())
            self.assertIn("\nOK\n", (output / fixed["verification_log"]).read_text())
            for variant in ("defective", "fixed"):
                assessment = load_json(output / result["cases"][variant]["assessment"])
                self.assertFalse(assessment["payload"]["independence"]["established"])
            self.assertEqual(result, load_json(output / "summary.json"))


if __name__ == "__main__":
    unittest.main()
