"""Local execution preserves negative results and resumable, bounded progress."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from common import load_json, now
from local_run import run_local
from local_slice import run_one


AT = now("2026-11-19T12:00:00Z")


class LocalRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.examples = self.directory / "examples"
        shutil.copytree(ROOT / "examples", self.examples)
        self.adapter = self.directory / "adapter.py"
        self.write_adapter()

    def write_adapter(self, statuses=None, fail_step=None, invalid_step=None, sleep=0):
        # A transport fixture, deliberately not a behavioral/agent evaluation.
        script = '''import argparse
import json
from pathlib import Path
import shutil
import time

parser = argparse.ArgumentParser()
parser.add_argument("--invocation")
parser.add_argument("--output")
args = parser.parse_args()
ctx = json.loads(Path(args.invocation).read_text())
with Path("adapter-calls.txt").open("a") as file:
    file.write(ctx["step"] + "\\n")
if ctx["step"] == FAIL_STEP:
    raise SystemExit(17)
time.sleep(SLEEP)
folder = Path(args.output).parent
record = json.loads((EXAMPLES / "records/project-context.json").read_text())
record.update(artifact_id="fixture-" + ctx["step"], artifact_type=ctx["output_type"],
              producer={"skill": ctx["skill"], "version": ctx["contract"]["version"]},
              run_id=ctx["run_id"], subject=ctx["subject"], created_at=ctx["observed_at"],
              status=STATUSES.get(ctx["step"], "passed"))
record["checks"][0]["status"] = record["status"]
if ctx["output_type"] == "verification-report":
    record["evidence"][0]["kind"] = "test"
    record["payload"] = {"required_count": 1, "executed_count": 1,
                         "failed_count": int(record["status"] == "failed"),
                         "skipped_required": []}
elif ctx["output_type"] == "review-report":
    record["payload"] = {"reviewer": "fixture-reviewer", "change_author": "fixture-author",
                         "independence_basis": "Fixture only", "findings": []}
for item in record["evidence"]:
    output = folder / item["uri"]
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXAMPLES / "records" / item["uri"], output)
if ctx["step"] == INVALID_STEP:
    record["evidence"][0]["sha256"] = "0" * 64
Path(args.output).write_text(json.dumps(record))
'''
        settings = (f"from pathlib import Path\nEXAMPLES = Path({str(self.examples)!r})\n"
                    f"STATUSES = {statuses or {}!r}\nFAIL_STEP = {fail_step!r}\n"
                    f"INVALID_STEP = {invalid_step!r}\nSLEEP = {sleep!r}\n")
        self.adapter.write_text(settings + script, encoding="utf-8")

    def calls(self):
        path = self.examples / "adapter-calls.txt"
        return path.read_text().splitlines() if path.exists() else []

    def run_factory(self, filename="feature-run.json", max_steps=1, adapter=True, at=AT):
        return run_local(
            ROOT / "workflows" / ("quality.json" if filename.startswith("quality") else "feature.json"),
            self.examples / filename, self.adapter if adapter else None,
            at, max_steps=max_steps,
        )

    def ready_to_verify(self):
        path = self.examples / "quality-ready-run.json"
        run = load_json(path)
        del run["completed"]["verify"]
        del run["completed"]["review"]
        path.write_text(json.dumps(run), encoding="utf-8")
        return path

    def test_step_limit_and_resume_do_not_repeat_completed_work(self):
        first = self.run_factory()
        self.assertEqual("step-limit", first["stop_reason"])
        self.assertEqual(["clarify"], first["ready"])
        self.assertEqual(["orient"], self.calls())
        self.assertEqual({}, load_json(self.examples / "feature-run.json")["completed"])
        second = run_local(ROOT / "workflows/feature.json", first["checkpoint"],
                           self.adapter, AT, max_steps=1)
        self.assertEqual(["orient", "clarify"], self.calls())
        self.assertEqual("checkpoint-0002-clarify.json", Path(second["checkpoint"]).name)
        self.assertTrue(Path(first["checkpoint"]).is_file())

    def test_adapter_failure_returns_last_checkpoint_without_retry(self):
        self.write_adapter(fail_step="clarify")
        result = self.run_factory(max_steps=3)
        self.assertEqual("error", result["status"])
        self.assertEqual("clarify", result["failed_step"])
        self.assertEqual(["orient", "clarify"], self.calls())
        self.assertEqual(["orient"], list(load_json(result["checkpoint"])["completed"]))
        self.assertFalse((self.examples / "checkpoint-0002-clarify.json").exists())
        self.write_adapter()
        resumed = run_local(ROOT / "workflows/feature.json", result["checkpoint"],
                            self.adapter, AT, max_steps=1)
        self.assertEqual("ready", resumed["status"])
        self.assertEqual(["orient", "clarify", "clarify"], self.calls())

    def test_adapter_error_includes_only_bounded_stderr_tail(self):
        self.adapter.write_text(
            'import sys\nsys.stderr.write("start-of-large-log" + "x" * 5000 '
            '+ "\\nMissing required test-plan configuration.\\n")\nraise SystemExit(9)\n',
            encoding="utf-8",
        )
        result = self.run_factory()
        self.assertEqual("error", result["status"])
        self.assertIn("Missing required test-plan configuration.", result["error"])
        self.assertNotIn("start-of-large-log", result["error"])
        self.assertLess(len(result["error"]), 4300)
        self.write_adapter()
        self.adapter.write_text('import sys\nprint("successful diagnostic", file=sys.stderr)\n'
                                + self.adapter.read_text(), encoding="utf-8")
        success = self.run_factory()
        artifact_dir = Path(success["completed_steps"][0]["artifact"]).parent
        self.assertEqual(["evidence/fixture.txt", "result.json"],
                         sorted(str(path.relative_to(artifact_dir)) for path in artifact_dir.rglob("*")
                                if path.is_file()))

    def test_existing_output_prevents_duplicate_dispatch(self):
        first = self.run_factory()
        checkpoint_bytes = Path(first["checkpoint"]).read_bytes()
        repeated = self.run_factory()
        self.assertEqual("error", repeated["status"])
        self.assertIn("already exists", repeated["error"])
        self.assertEqual(["orient"], self.calls())
        self.assertEqual(checkpoint_bytes, Path(first["checkpoint"]).read_bytes())

    def test_interrupted_publication_prevents_ambiguous_repeat_dispatch(self):
        with patch("local_slice.shutil.copytree", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_factory()
        self.assertEqual(["orient"], self.calls())
        self.assertTrue((self.examples / "artifacts/.0001-orient.attempt.json").is_file())
        self.assertFalse((self.examples / "checkpoint-0001-orient.json").exists())
        resumed = self.run_factory()
        self.assertEqual("error", resumed["status"])
        self.assertIn("Interrupted or concurrent attempt", resumed["error"])
        self.assertEqual(["orient"], self.calls())

    def test_missing_adapter_is_actionable_and_does_not_dispatch(self):
        result = self.run_factory(adapter=False)
        self.assertEqual("blocked", result["status"])
        self.assertEqual("adapter-required", result["stop_reason"])
        self.assertIn("--adapter-script", result["error"])
        self.assertEqual([], self.calls())

    def test_valid_negative_quality_reports_reach_review_and_consolidation(self):
        self.ready_to_verify()
        self.write_adapter(statuses={"verify": "failed", "review": "failed"})
        result = self.run_factory("quality-ready-run.json", max_steps=2)
        self.assertEqual(["verify", "review"], self.calls())
        self.assertEqual(["consolidate"], result["ready"])
        self.assertEqual("failed", result["outcomes"]["verify"]["verification-report"])
        self.assertEqual(["failed", "failed"], [item["status"] for item in result["completed_steps"]])
        final = run_local(ROOT / "workflows/quality.json", result["checkpoint"],
                          at=AT, max_steps=1)
        self.assertEqual("complete", final["status"])
        self.assertEqual("failed", final["outcomes"]["consolidate"]["quality-assessment"])
        self.assertEqual(["verify", "review"], self.calls())

    def test_quality_slice_retains_each_valid_nonpassing_status(self):
        path = self.ready_to_verify()
        for status in ("failed", "blocked", "inconclusive"):
            with self.subTest(status=status):
                self.write_adapter(statuses={"verify": status})
                result = run_one(ROOT / "workflows/quality.json", path, "verify", self.adapter,
                                 f"{status}.json", f"results/{status}", AT)
                self.assertEqual(status, result["artifact_status"])
                self.assertIn("review", result["next_ready"])

    def test_failed_scope_is_saved_but_does_not_enable_verification(self):
        path = self.examples / "quality-ready-run.json"
        run = load_json(path)
        for step in ("scope", "tests", "impact", "verify", "review"):
            del run["completed"][step]
        path.write_text(json.dumps(run), encoding="utf-8")
        self.write_adapter(statuses={"scope": "failed"})
        result = self.run_factory("quality-ready-run.json", max_steps=3)
        self.assertEqual("blocked", result["status"])
        self.assertEqual("failed", result["outcomes"]["scope"]["change-set"])
        self.assertEqual(["scope"], self.calls())

    def test_software_still_rejects_nonpassing_output(self):
        self.write_adapter(statuses={"orient": "failed"})
        result = self.run_factory(max_steps=2)
        self.assertEqual("error", result["status"])
        self.assertEqual([], result["completed_steps"])
        self.assertFalse((self.examples / "checkpoint-0001-orient.json").exists())

    def test_negative_quality_output_with_invalid_evidence_does_not_advance(self):
        self.ready_to_verify()
        self.write_adapter(statuses={"verify": "failed"}, invalid_step="verify")
        result = self.run_factory("quality-ready-run.json", max_steps=3)
        self.assertEqual("error", result["status"])
        self.assertEqual([], result["completed_steps"])
        self.assertNotIn("verify", load_json(result["checkpoint"])["completed"])
        self.assertEqual(["verify"], self.calls())

    def test_live_run_rechecks_evidence_age_before_each_step(self):
        with patch("local_run.now", side_effect=[AT, now("2026-11-21T12:00:00Z")]):
            result = self.run_factory(max_steps=3, at=None)
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["orient"], self.calls())

    def test_budgets_are_bounded_before_dispatch(self):
        for count in (0, 101, True):
            with self.subTest(max_steps=count), self.assertRaises(ValueError):
                self.run_factory(max_steps=count)
        self.assertEqual([], self.calls())

    def test_adapter_timeout_does_not_create_a_checkpoint(self):
        self.write_adapter(sleep=2)
        self.adapter.write_text('import sys\nprint("waiting for fixture", file=sys.stderr, flush=True)\n'
                                + self.adapter.read_text(), encoding="utf-8")
        result = run_local(ROOT / "workflows/feature.json", self.examples / "feature-run.json",
                           self.adapter, AT, max_steps=1, timeout=1)
        self.assertEqual("error", result["status"])
        self.assertIn("time limit", result["error"])
        self.assertIn("waiting for fixture", result["error"])
        self.assertFalse((self.examples / "checkpoint-0001-orient.json").exists())


if __name__ == "__main__":
    unittest.main()
