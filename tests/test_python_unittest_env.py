"""The unittest adapter must not pass host credentials to candidate tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "examples" / "adapters"))
from python_unittest import snapshot_digest, verify

CANARY = "sfstack-nonsecret-canary"
SENSITIVE = ("GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN", "AWS_SECRET_ACCESS_KEY",
             "MY_SERVICE_PASSWORD")
TEST_ID = "test_env.EnvironmentBoundary.test_sensitive_variables_absent"
TEST_SOURCE = f'''import os
import unittest


class EnvironmentBoundary(unittest.TestCase):
    def test_sensitive_variables_absent(self):
        for name in {SENSITIVE!r}:
            self.assertNotIn(name, os.environ)

    def test_path_is_kept(self):
        self.assertIn("PATH", os.environ)
'''


class AdapterEnvironmentTests(unittest.TestCase):
    def run_verify(self, directory):
        directory = Path(directory)
        candidate, tests = directory / "candidate", directory / "tests"
        candidate.mkdir()
        tests.mkdir()
        (candidate / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tests / "test_env.py").write_text(TEST_SOURCE, encoding="utf-8")
        candidate_digest = snapshot_digest(candidate)
        config = {
            "candidate_dir": "candidate", "tests_dir": "tests",
            "candidate_sha256": candidate_digest, "tests_sha256": snapshot_digest(tests),
            "required_tests": [TEST_ID, TEST_ID.replace("sensitive_variables_absent", "path_is_kept")],
            "timeout_seconds": 20,
        }
        plan = directory / "test-plan.json"
        plan.write_text(json.dumps({"payload": {"python_unittest": config}}), encoding="utf-8")
        invocation = directory / "invocation.json"
        invocation.write_text(json.dumps({
            "skill": "sf-verify-change", "output_type": "verification-report",
            "bindings": {"test-plan": str(plan)}, "run_id": "env-boundary",
            "subject": {"revision": "sha256:" + candidate_digest, "input_digest": "0" * 64,
                        "environment": "test"},
            "contract": {"version": "1.0.0"}, "observed_at": "2026-01-01T00:00:00Z",
        }), encoding="utf-8")
        output = directory / "out" / "report.json"
        output.parent.mkdir()
        with mock.patch.dict(os.environ, {name: CANARY for name in SENSITIVE}):
            verify(invocation, output)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_candidate_tests_do_not_inherit_credential_variables(self):
        with tempfile.TemporaryDirectory() as temp:
            report = self.run_verify(temp)
        self.assertEqual("passed", report["status"], report["unresolved"])
        self.assertEqual(2, report["payload"]["executed_count"])
        self.assertEqual(0, report["payload"]["failed_count"])


if __name__ == "__main__":
    unittest.main()
