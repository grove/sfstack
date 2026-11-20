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
             "--template", str(self.directory / "context/change-template.json"),
             "--specification", str(self.bundle / "specification.json")],
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
        (self.submission.parent / "proposal.json").write_text(duplicate, encoding="utf-8")
        self.write(self.submission, {"items": [
            {"type": "submit_change",
             "change_sha256": hashlib.sha256(duplicate.encode("utf-8")).hexdigest()}]})
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

    def test_duplicate_keys_still_fail_without_optional_jsonschema_dependency(self):
        """Copilot's isolated Python may not include controller-side packages."""
        self.prepare()
        response = self.response()
        raw = json.dumps(response)
        duplicate = raw[:-1] + ', "limitations": ["duplicate"]}'
        source = self.directory / "proposal.json"
        command = [
            sys.executable, "-S", str(PREFLIGHT),
            "--proposal", str(source),
            "--schema", str(self.directory / "context/change.schema.json"),
            "--template", str(self.directory / "context/change-template.json"),
            "--specification", str(self.bundle / "specification.json"),
        ]
        source.write_text(duplicate, encoding="utf-8")
        rejected = subprocess.run(command, cwd=self.repo, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("Duplicate JSON key.", rejected.stderr)

        source.write_text(raw, encoding="utf-8")
        allowed = subprocess.run(command, cwd=self.repo, capture_output=True, text=True, timeout=15)
        self.assertEqual(0, allowed.returncode, allowed.stderr)
        self.assertIn("Full schema validation deferred", allowed.stdout)
        self.assertIn("unique JSON keys", allowed.stdout)


    def test_second_pilot_unknown_ids_are_rejected_before_candidate_execution(self):
        """Replay run #44760120706's criterion-* versus acceptance-* mismatch."""
        self.prepare(acceptance_criteria=[
            "A dummy PYTHON-prefixed variable is not inherited.",
            "A new regression proves RED then GREEN.",
            "The full suite remains green.",
        ])
        response = self.response()
        self.assertEqual(["acceptance-1", "acceptance-2", "acceptance-3"],
                         response["criteria_addressed"])
        response["criteria_addressed"] = ["criterion-1", "criterion-2", "criterion-3"]
        raw = json.dumps(response)
        preflight = self.run_preflight(raw)
        self.assertNotEqual(0, preflight.returncode)
        self.assertIn("Unknown acceptance criterion ID", preflight.stderr)
        self.assertNotIn("PYTHON-prefixed variable", preflight.stderr)
        self.assertNotIn("answer = 42", preflight.stderr)

        self.submit(response)
        with self.assertRaisesRegex(ValueError, "Unknown acceptance criterion"):
            self.verify()
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertEqual("", self.git("status", "--porcelain"))
        self.assertFalse((self.result / "candidate.json").exists())
        self.assertFalse((self.result / "logs/answer-behavior.txt").exists())

    def test_preflight_requires_all_pinned_ids_for_a_passing_response(self):
        self.prepare(acceptance_criteria=["First", "Second"])
        response = self.response()
        self.assertEqual(0, self.run_preflight(json.dumps(response)).returncode)
        response["criteria_addressed"] = ["acceptance-1"]
        blocked = self.run_preflight(json.dumps(response))
        self.assertNotEqual(0, blocked.returncode)
        self.assertIn("must address all pinned acceptance IDs", blocked.stderr)

        response["status"] = "inconclusive"
        response["remaining_work"] = ["Second criterion still incomplete."]
        # A nonpassing, honest partial response remains reportable; it
        # cannot claim a completed repair or authorize a PR.
        allowed = self.run_preflight(json.dumps(response))
        self.assertEqual(0, allowed.returncode, allowed.stderr)

    def test_preflight_rejects_unbound_or_invalid_host_specification(self):
        self.prepare()
        response = self.response()
        raw = json.dumps(response)
        pinned = self.bundle / "specification.json"
        original = pinned.read_bytes()
        for variant in ("wrong-run", "missing", "duplicates"):
            with self.subTest(variant=variant):
                data = json.loads(original)
                if variant == "wrong-run":
                    data["run_id"] = "other-run"
                elif variant == "missing":
                    data["payload"]["criteria"] = []
                else:
                    data["payload"]["criteria"].append(dict(data["payload"]["criteria"][0]))
                pinned.write_text(json.dumps(data), encoding="utf-8")
                rejected = self.run_preflight(raw)
                self.assertNotEqual(0, rejected.returncode)
                self.assertIn("specification", rejected.stderr.lower())
        pinned.write_bytes(original)
        self.assertEqual(0, self.run_preflight(raw).returncode)

    def test_pinned_criteria_enforced_without_optional_jsonschema(self):
        self.prepare()
        response = self.response()
        source = self.directory / "proposal.json"
        source.write_text(json.dumps({**response, "criteria_addressed": ["criterion-1"]}),
                          encoding="utf-8")
        command = [
            sys.executable, "-S", str(PREFLIGHT),
            "--proposal", str(source),
            "--schema", str(self.directory / "context/change.schema.json"),
            "--template", str(self.directory / "context/change-template.json"),
            "--specification", str(self.bundle / "specification.json"),
        ]
        blocked = subprocess.run(command, cwd=self.repo, capture_output=True,
                                 text=True, timeout=15)
        self.assertNotEqual(0, blocked.returncode)
        self.assertIn("Unknown acceptance criterion ID", blocked.stderr)
        source.write_text(json.dumps(response), encoding="utf-8")
        allowed = subprocess.run(command, cwd=self.repo, capture_output=True,
                                 text=True, timeout=15)
        self.assertEqual(0, allowed.returncode, allowed.stderr)
        self.assertIn("Full schema validation deferred", allowed.stdout)

    def test_rendered_instruction_requires_exact_raw_preflight_and_single_key(self):
        self.prepare()
        self.response()
        guidance = (self.directory / "context/invocation.md").read_text()
        self.assertIn("preflight_change.py", guidance)
        self.assertIn("change-template.json", guidance)
        self.assertIn("change.schema.json", guidance)
        self.assertIn("--proposal /tmp/gh-aw/agent/sfstack-software/proposal.json", guidance)
        self.assertIn("--specification /tmp/gh-aw/sfstack-software/inputs/specification.json", guidance)
        self.assertIn("never invent criterion-1", guidance)
        self.assertIn("Exact IDs for this run: acceptance-1", guidance)
        self.assertIn("ALREADY has a `limitations` property", guidance)
        self.assertIn("Duplicate keys, including nested ones", guidance)
        self.assertIn("json.dumps", guidance)
        self.assertIn("Do not submit the source JSON as a safe-output string", guidance)
        self.assertIn("Quality Factory, and human approval", guidance)
