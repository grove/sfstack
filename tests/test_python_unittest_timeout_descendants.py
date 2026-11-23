"""A unittest worker timeout must not leave descendant processes running."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "examples" / "adapters"))
from python_unittest import snapshot_digest, verify

TEST_ID = "test_hang.Hang.test_spawns_descendant_and_blocks"
TEST_SOURCE = '''import subprocess
import sys
import time
import unittest

PID_FILE = {pid_file!r}


class Hang(unittest.TestCase):
    def test_spawns_descendant_and_blocks(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        with open(PID_FILE, "w", encoding="utf-8") as handle:
            handle.write(str(child.pid))
        time.sleep(300)
'''


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            return handle.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


class TimeoutDescendantTests(unittest.TestCase):
    def test_timeout_leaves_no_live_descendant(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            pid_file = directory / "child.pid"
            candidate, tests = directory / "candidate", directory / "tests"
            candidate.mkdir()
            tests.mkdir()
            (candidate / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            (tests / "test_hang.py").write_text(
                TEST_SOURCE.format(pid_file=str(pid_file)), encoding="utf-8")
            digest = snapshot_digest(candidate)
            plan = directory / "test-plan.json"
            plan.write_text(json.dumps({"payload": {"python_unittest": {
                "candidate_dir": "candidate", "tests_dir": "tests",
                "candidate_sha256": digest, "tests_sha256": snapshot_digest(tests),
                "required_tests": [TEST_ID], "timeout_seconds": 2}}}), encoding="utf-8")
            invocation = directory / "invocation.json"
            invocation.write_text(json.dumps({
                "skill": "sf-verify-change", "output_type": "verification-report",
                "bindings": {"test-plan": str(plan)}, "run_id": "timeout-descendants",
                "subject": {"revision": "sha256:" + digest, "input_digest": "0" * 64,
                            "environment": "test"},
                "contract": {"version": "1.0.0"}, "observed_at": "2026-01-01T00:00:00Z",
            }), encoding="utf-8")
            output = directory / "out" / "report.json"
            output.parent.mkdir()
            pid = None
            try:
                verify(invocation, output)
                self.assertTrue(pid_file.is_file(), "fixture did not record a descendant")
                pid = int(pid_file.read_text(encoding="utf-8"))
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertNotEqual("passed", report["status"])
                self.assertFalse(alive(pid), f"descendant {pid} is still running after timeout")
            finally:
                if pid is None and pid_file.is_file():
                    pid = int(pid_file.read_text(encoding="utf-8"))
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
