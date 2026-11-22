"""The unittest adapter must not forward arbitrary LC_-prefixed host variables."""
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

CANARY_NAME = "LC_SFSTACK_CANARY_TOKEN"
CANARY = "sfstack-nonsecret-canary"
TEST_SOURCE = f'''import os
import unittest


class LocalePrefixBoundary(unittest.TestCase):
    def test_canary_absent(self):
        self.assertNotIn({CANARY_NAME!r}, os.environ)

    def test_standard_locale_preserved(self):
        self.assertEqual("C", os.environ.get("LC_ALL"))
        self.assertEqual("C", os.environ.get("LC_CTYPE"))

    def test_bytecode_disabled(self):
        self.assertEqual("1", os.environ.get("PYTHONDONTWRITEBYTECODE"))
'''
TEST_IDS = [f"test_locale.LocalePrefixBoundary.{name}"
            for name in ("test_canary_absent", "test_standard_locale_preserved",
                         "test_bytecode_disabled")]


class LocalePrefixTests(unittest.TestCase):
    def run_verify(self, directory):
        directory = Path(directory)
        candidate, tests = directory / "candidate", directory / "tests"
        candidate.mkdir()
        tests.mkdir()
        (candidate / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tests / "test_locale.py").write_text(TEST_SOURCE, encoding="utf-8")
        candidate_digest = snapshot_digest(candidate)
        config = {
            "candidate_dir": "candidate", "tests_dir": "tests",
            "candidate_sha256": candidate_digest, "tests_sha256": snapshot_digest(tests),
            "required_tests": TEST_IDS, "timeout_seconds": 20,
        }
        plan = directory / "test-plan.json"
        plan.write_text(json.dumps({"payload": {"python_unittest": config}}), encoding="utf-8")
        invocation = directory / "invocation.json"
        invocation.write_text(json.dumps({
            "skill": "sf-verify-change", "output_type": "verification-report",
            "bindings": {"test-plan": str(plan)}, "run_id": "locale-prefix",
            "subject": {"revision": "sha256:" + candidate_digest, "input_digest": "0" * 64,
                        "environment": "test"},
            "contract": {"version": "1.0.0"}, "observed_at": "2026-01-01T00:00:00Z",
        }), encoding="utf-8")
        output = directory / "out" / "report.json"
        output.parent.mkdir()
        with mock.patch.dict(os.environ, {CANARY_NAME: CANARY, "LC_ALL": "C", "LC_CTYPE": "C"}):
            verify(invocation, output)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_arbitrary_lc_host_variables_are_not_forwarded(self):
        with tempfile.TemporaryDirectory() as temp:
            report = self.run_verify(temp)
        self.assertEqual("passed", report["status"], report["unresolved"])
        self.assertEqual(3, report["payload"]["executed_count"])
        self.assertEqual(0, report["payload"]["failed_count"])


if __name__ == "__main__":
    unittest.main()
