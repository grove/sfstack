"""Byte-exact, fail-closed declared-agent-artifact transport tests.

These fixtures simulate gh-aw v1.2.2's *post secret-redaction* artifact
download. They make no paid model calls and cannot replace an actual live pilot.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from common import load_json
from test_github_software import SoftwareFixture
from integrations.github import software


ROOT = Path(__file__).resolve().parents[1]
STAGER = ROOT / "integrations/github/stage_change_artifact.py"


class DeclaredProposalArtifactTests(SoftwareFixture):
    def downloaded_agent(self):
        root = self.directory / "download"
        proposal = root / "agent" / "sfstack-software" / "proposal.json"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        (root / "agent_output.json").write_bytes(self.submission.read_bytes())
        proposal.write_bytes((self.submission.parent / "proposal.json").read_bytes())
        return root

    def stage(self, root):
        out = self.directory / "staged"
        return subprocess.run([
            sys.executable, str(STAGER),
            "--agent-output", str(root / "agent_output.json"),
            "--out", str(out),
        ], capture_output=True, text=True, check=False, timeout=15), out

    def test_exact_source_survives_declared_file_handoff_and_host_verifies(self):
        self.prepare()
        response = self.response()
        response["edits"][0]["content"] = (
            "answer = 42\n"
            "# escaped newline: \\\\n, another literal \\\\n, third \\\\n\n"
            "# non-https text: http://sample.invalid/no-op\n"
            "# script string: javascript:local-expression\n"
        )
        self.submit(response)
        expected = (self.submission.parent / "proposal.json").read_bytes()
        root = self.downloaded_agent()
        process, path = self.stage(root)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual(expected, (path / "proposal.json").read_bytes())
        self.assertNotIn(b"change_json", (path / "submission.json").read_bytes())
        self.assertEqual(hashlib.sha256(expected).hexdigest(),
                         load_json(path / "submission.json")["items"][0]["change_sha256"])

        gate = software.verify(self.repo, self.bundle, path / "submission.json",
                               "success", self.result, at=self.at)
        self.assertTrue(gate["passed"])
        self.assertEqual(expected, (self.result / "proposal.json").read_bytes())
        self.assertEqual(hashlib.sha256(expected).hexdigest(),
                         gate["digests"]["proposal.json"])
        self.assertEqual("passed", load_json(self.result / "verification-report.json")["status"])

    def test_secret_redaction_that_changes_source_bytes_blocks_before_execution(self):
        self.prepare()
        self.response()
        root = self.downloaded_agent()
        # Simulate the compiler's required secret-redaction pass modifying a
        # published agent file. Do not embed or print any real secret.
        proposal = root / "agent" / "sfstack-software" / "proposal.json"
        proposal.write_bytes(proposal.read_bytes().replace(b"answer = 42", b"answer = ***REDACTED***"))
        process, path = self.stage(root)
        self.assertEqual(0, process.returncode, process.stderr)
        with patch.object(software.quality, "check_actions_run"):
            exit_code = software.main([
                "verify", "--repo", str(self.repo), "--bundle", str(self.bundle),
                "--submission", str(path / "submission.json"),
                "--agent-result", "success", "--out", str(self.result),
            ])
        self.assertEqual(1, exit_code)
        negative = load_json(self.result / "gate.json")
        self.assertFalse(negative["passed"])
        self.assertEqual("blocked", negative["status"])
        self.assertIn("changed after preflight", negative["reasons"][0])
        self.assertFalse((self.result / "candidate.json").exists())
        self.assertFalse((self.result / "logs" / "answer-behavior.txt").exists())
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_missing_compiler_declared_artifact_never_mints_a_handoff(self):
        self.prepare()
        self.response()
        root = self.downloaded_agent()
        (root / "agent" / "sfstack-software" / "proposal.json").unlink()
        process, out = self.stage(root)
        self.assertNotEqual(0, process.returncode)
        self.assertIn("staging blocked", process.stderr)
        self.assertFalse((out / "proposal.json").exists())

    def test_symlink_hardlink_and_nonregular_input_files_are_rejected(self):
        for case in ("symlink", "hardlink", "directory"):
            with self.subTest(case=case):
                self.prepare() if not self.bundle.exists() else None
                self.response() if not self.submission.exists() else None
                root = self.downloaded_agent() if not (self.directory / "download").exists() else self.directory / "download"
                proposal = root / "agent" / "sfstack-software" / "proposal.json"
                original = (self.submission.parent / "proposal.json").read_bytes()
                proposal.unlink() if proposal.is_file() or proposal.is_symlink() else None
                if proposal.is_dir():
                    proposal.rmdir()
                if case == "symlink":
                    proposal.symlink_to(self.submission.parent / "proposal.json")
                elif case == "hardlink":
                    os.link(self.submission.parent / "proposal.json", proposal)
                else:
                    proposal.mkdir()
                process, out = self.stage(root)
                self.assertNotEqual(0, process.returncode)
                self.assertIn("staging blocked", process.stderr)
                self.assertFalse(out.exists())
                self.assertEqual(original, (self.submission.parent / "proposal.json").read_bytes())

    def test_oversized_agent_artifact_does_not_cross_the_boundary(self):
        self.prepare()
        self.response()
        root = self.downloaded_agent()
        proposal = root / "agent" / "sfstack-software" / "proposal.json"
        proposal.write_bytes(b"p" * 120001)
        process, out = self.stage(root)
        self.assertNotEqual(0, process.returncode)
        self.assertFalse(out.exists())

    def test_old_inline_json_transport_is_no_longer_authorized(self):
        self.prepare()
        response = self.response()
        payload = (self.submission.parent / "proposal.json").read_text()
        envelope = load_json(self.submission)
        envelope["items"][0]["change_json"] = payload
        self.write(self.submission, envelope)
        with self.assertRaisesRegex(ValueError, "without inline code"):
            self.verify()
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertFalse((self.result / "candidate.json").exists())
