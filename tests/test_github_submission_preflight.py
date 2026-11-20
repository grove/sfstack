"""Builder-side raw JSON preflight is advisory; host verification stays decisive."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from test_github_software import SoftwareFixture
from common import load_json

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "integrations/github/preflight_change.py"


class SubmissionPreflightTests(SoftwareFixture):
    def run_preflight(self, raw):
        source = self.directory / "proposal.json"
        source.write_text(raw, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(PREFLIGHT), "--proposal", str(source),
             "--schema", str(self.directory / "context/change.schema.json"),
             "--template", str(self.directory / "context/change-template.json")],
            cwd=self.repo, capture_output=True, text=True, timeout=15, check=False,
        )

    def test_third_live_pilot_duplicate_limitations_fails_before_submit(self):
        """Replay the malformed shape in workflow run 44700503624."""
        self.prepare()
        response = self.response(limitations=["Advisory limitation stated once."])
        valid = json.dumps(response, ensure_ascii=False)
        duplicate = valid[:-1] + ', "limitations": ["Second advisory copy."]}'
        result = self.run_preflight(duplicate)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Duplicate JSON key.", result.stderr)
        self.assertNotIn("Advisory limitation stated once.", result.stderr)

        # Exact host transport remains fail-closed, with no candidate applied.
        self.write(self.submission, {"items": [
            {"type": "submit_change", "change_json": duplicate}]})
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            self.verify()
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertEqual("", self.git("status", "--porcelain"))
        self.assertFalse((self.result / "candidate.json").exists())

    def test_one_limitations_field_passes_preflight_but_host_also_verifies(self):
        self.prepare()
        response = self.response(
            limitations=["Independent quality review remains required."])
        raw = json.dumps(response, ensure_ascii=False)
        result = self.run_preflight(raw)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("unique JSON keys", result.stdout)
        self.assertIn(hashlib.sha256(raw.encode("utf-8")).hexdigest(), result.stdout)
        self.assertIn("Advisory only", result.stdout)
        # A preflight success is NOT a host verdict. Only real host checks can pass.
        gate = self.verify()
        self.assertTrue(gate["passed"])
        change = load_json(self.result / "change-set.json")
        self.assertEqual(response["limitations"],
                         change["payload"]["builder_limitations"])
        self.assertEqual("passed", load_json(
            self.result / "verification-report.json")["status"])

    def test_nested_duplicates_and_malformed_schema_are_rejected(self):
        self.prepare()
        response = self.response()
        original = json.dumps(response)
        variants = [
            (original.replace('"observed":', '"observed": "shadow", "observed":', 1),
             "Duplicate JSON key."),
            (json.dumps({**response, "merge_authorized": True}),
             "Closed schema rejected"),
            (json.dumps({**response, "run_id": "wrong-run"}),
             "pinned template"),
            (json.dumps({**response, "status": "passed",
                         "remaining_work": ["Required test is not done."]}),
             "remaining_work"),
            (original + " garbage", "Extra data"),
        ]
        for raw, message in variants:
            with self.subTest(message=message):
                result = self.run_preflight(raw)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(message, result.stderr)
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_rendered_instruction_requires_exact_raw_preflight_and_single_key(self):
        self.prepare()
        self.response()
        guidance = (self.directory / "context/invocation.md").read_text()
        self.assertIn("preflight_change.py", guidance)
        self.assertIn("change-template.json", guidance)
        self.assertIn("change.schema.json", guidance)
        self.assertIn("--proposal /tmp/gh-aw/sfstack-software/proposal.json", guidance)
        self.assertIn("ALREADY has a `limitations` property", guidance)
        self.assertIn("Duplicate keys, including nested ones", guidance)
        self.assertIn("json.dumps", guidance)
        self.assertIn("Submit exactly the validated file contents", guidance)
        self.assertIn("Quality Factory, and human approval", guidance)
