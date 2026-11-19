"""A clean checkout can become an inspectable, non-authorizing quality run."""
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from common import load_json, now
from factory import plan
from sfstack import initialize, main

AT = now("2026-11-19T12:00:00Z")


class LocalCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.repo = self.directory / "candidate"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "example.py").write_text("value = 1\n", encoding="utf-8")
        self.git("add", "example.py")
        self.git("-c", "user.name=Test Author", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "Candidate")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def init(self, **options):
        return initialize(self.repo, self.directory / "quality", "Assess the public behavior", "test-python",
                          at=AT, **options)

    def test_initialize_is_ready_and_grants_no_effects(self):
        head = self.git("rev-parse", "HEAD")
        result = self.init()
        run = load_json(result["checkpoint"])
        policy = load_json(self.directory / "quality/policy.json")
        self.assertEqual(head, run["subject"]["revision"])
        self.assertEqual([], policy["grants"])
        self.assertTrue(policy["require_independent_review"])
        self.assertEqual({}, run["effect_scopes"])
        self.assertFalse(any(capability.endswith(".write") and capability != "artifact.write"
                             for capability in run["capabilities"]))
        state = plan(result["workflow"], result["checkpoint"], AT)
        self.assertEqual(["orient"], state["ready"])
        self.assertEqual("", self.git("status", "--porcelain"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["status", "--run", result["checkpoint"], "--at", AT.isoformat()]))
        self.assertIn("Ready: orient", output.getvalue())

    def test_risk_profile_selects_and_requires_existing_specialists(self):
        result = self.init(profile="risk")
        policy = load_json(self.directory / "quality/policy.json")
        self.assertIn("security-assessment", policy["required_quality_reports"])
        self.assertIn("compatibility-report", policy["required_quality_reports"])
        workflow = load_json(result["workflow"])
        self.assertIn("security", [step["id"] for step in workflow["steps"]])

    def test_dirty_or_untracked_candidate_is_not_misidentified(self):
        for path in ("example.py", "untracked.py"):
            with self.subTest(path=path):
                (self.repo / path).write_text("changed\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "clean"):
                    self.init()
                self.assertFalse((self.directory / "quality").exists())
                if path == "example.py":
                    self.git("restore", "example.py")
                else:
                    (self.repo / path).unlink()

    def test_init_does_not_overwrite_or_write_into_candidate(self):
        result = self.init()
        original = Path(result["checkpoint"]).read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.init()
        self.assertEqual(original, Path(result["checkpoint"]).read_bytes())
        with self.assertRaisesRegex(ValueError, "outside"):
            initialize(self.repo, self.repo / "run", "goal", "environment", at=AT)

    def test_base_is_resolved_and_unknown_base_leaves_no_run(self):
        with self.assertRaisesRegex(ValueError, "Git candidate"):
            self.init(base="does-not-exist")
        self.assertFalse((self.directory / "quality").exists())
        self.init(base="HEAD")
        target = load_json(self.directory / "quality/target.json")
        self.assertEqual(target["candidate_revision"], target["base_revision"])
        self.assertEqual("pull-request", target["target_kind"])

    def test_negative_assessment_has_readable_output_and_nonzero_exit(self):
        examples = self.directory / "examples"
        shutil.copytree(ROOT / "examples", examples)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["assess", "--run", str(examples / "quality-failed-run.json"),
                         "--workflow", str(ROOT / "workflows/quality.json"), "--at", AT.isoformat()])
        self.assertEqual(2, code)
        self.assertIn("Quality: failed", output.getvalue())
        self.assertIn("Findings: 1", output.getvalue())
        self.assertTrue((examples / "run-assessed.json").is_file())

    def test_completed_negative_run_keeps_checkpoint_and_nonzero_exit(self):
        examples = self.directory / "examples"
        shutil.copytree(ROOT / "examples", examples)
        original = (examples / "quality-failed-run.json").read_bytes()
        workflow = ROOT / "workflows/quality.json"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["run", "--run", str(examples / "quality-failed-run.json"),
                         "--workflow", str(workflow), "--max-steps", "1", "--at", AT.isoformat()])
        self.assertEqual(2, code)
        self.assertIn("Status: complete", output.getvalue())
        self.assertIn("quality-assessment=failed", output.getvalue())
        checkpoint = Path(next(line.removeprefix("Checkpoint: ")
                               for line in output.getvalue().splitlines()
                               if line.startswith("Checkpoint: ")))
        saved = checkpoint.read_bytes()
        state = plan(workflow, checkpoint, AT)
        self.assertEqual("complete", state["status"])
        self.assertEqual("failed", state["outcomes"]["consolidate"]["quality-assessment"])
        self.assertEqual(original, (examples / "quality-failed-run.json").read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            resumed = main(["run", "--run", str(checkpoint), "--workflow", str(workflow),
                            "--max-steps", "1", "--at", AT.isoformat()])
        self.assertEqual(2, resumed)
        self.assertEqual(saved, checkpoint.read_bytes())


if __name__ == "__main__":
    unittest.main()
