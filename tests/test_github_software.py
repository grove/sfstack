"""Real candidate execution and bounded handoffs govern the software pilot."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from common import load_json, now
from integrations.github import software


class SoftwareFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.repo = self.directory / "candidate"
        self.repo.mkdir()
        self.git("init", "--quiet")
        (self.repo / "examples").mkdir()
        (self.repo / "examples/answer.py").write_text("answer = 41\n", encoding="utf-8")
        (self.repo / "README.md").write_text("Bounded software fixture.\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Pin the initial fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.issue = {
            "number": 7, "state": "open", "title": "Return the expected answer",
            "body": "The public answer should be 42.", "updated_at": "2026-11-19T12:00:00Z",
            "html_url": "https://github.com/fixture/software/issues/7",
        }
        self.at = now()
        self.bundle = self.directory / "inputs"
        self.result = self.directory / "result"
        self.submission = self.directory / "submission.json"

    def git(self, *arguments):
        return subprocess.run([
            "git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            *arguments,
        ], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    @staticmethod
    def write(path, value):
        Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def checks(variant="normal"):
        test = (
            "import unittest\nfrom examples.answer import answer\n"
            "class Behavior(unittest.TestCase):\n"
            + ("    @unittest.skip('required behavior unavailable')\n" if variant == "skipped" else "")
            + "    def test_answer(self):\n        self.assertEqual(answer, 42)\n"
            "unittest.main(verbosity=2)\n"
        )
        if variant == "empty":
            test = "import unittest\nunittest.main(verbosity=2)\n"
        if variant == "mutate":
            test = (
                "from pathlib import Path\n"
                "Path('examples/answer.py').write_text('answer = 99\\n')\n"
            ) + test
        return [{"id": "answer-behavior", "kind": "unittest",
                 "command": [sys.executable, "-B", "-c", test],
                 "criterion": "The independently selected behavioral test observes answer 42."}]

    def prepare(self, variant="normal", **changes):
        arguments = {
            "repo": self.repo, "issue": self.issue, "repository": "fixture/software",
            "run_id": "1234", "run_attempt": "1", "allowed_paths": ["examples/answer.py"],
            "acceptance_criteria": ["The public answer is 42."], "output": self.bundle,
            "at": self.at, "checks": self.checks(variant),
        }
        arguments.update(changes)
        return software.prepare(**arguments)

    def response(self, value=42, **changes):
        context = self.directory / "context"
        software.render(self.bundle, self.repo, context, at=self.at)
        response = load_json(context / "change-template.json")
        response.update({
            "status": "passed", "summary": "Change the public answer to its required value.",
            "criteria_addressed": [c["id"] for c in load_json(self.bundle / "target.json")["criteria"]],
            "behavior_changes": ["The public answer is 42."],
            "checks_run": [{"command": "python -m unittest",
                            "observed": "Synthetic agent claim; the fresh host must verify it."}],
            "remaining_work": [],
            "edits": [{"path": "examples/answer.py", "content": f"answer = {value}\n"}],
        })
        response.update(changes)
        self.submit(response)
        return response

    def submit(self, response):
        raw = json.dumps(response)
        self.write(self.submission, {"items": [{
            "type": "submit_change", "change_json": raw,
            "change_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}]})

    def verify(self, agent_result="success"):
        if self.result.exists():
            # Each rejected handoff gets its own result directory so a later
            # subcase cannot pass just because an earlier attempt made it.
            self.result = self.directory / (self.result.name + "-next")
        return software.verify(self.repo, self.bundle, self.submission, agent_result,
                               self.result, at=self.at)


class GitHubSoftwareTests(SoftwareFixture):
    def test_fixed_candidate_is_executed_and_retains_distinct_base_and_candidate_identity(self):
        self.prepare()
        original = load_json(self.bundle / "run.json")
        self.response()
        result = self.verify()
        self.assertTrue(result["passed"])
        self.assertEqual("passed", result["status"])
        manifest = load_json(self.result / "candidate.json")
        report = load_json(self.result / "verification-report.json")
        change = load_json(self.result / "change-set.json")
        self.assertEqual(self.base, manifest["base_sha"])
        self.assertNotEqual(self.base, manifest["head_sha"])
        self.assertEqual(manifest["head_sha"], result["candidate_sha"])
        self.assertEqual(manifest["head_sha"], report["subject"]["revision"])
        self.assertEqual(original["subject"], change["subject"])
        self.assertEqual(manifest["head_sha"], change["payload"]["candidate_revision"])
        self.assertEqual("sf-build-change", change["producer"]["skill"])
        self.assertEqual("sf-verify-change", report["producer"]["skill"])
        self.assertEqual("passed", report["status"])
        self.assertEqual(1, report["payload"]["executed_count"])
        self.assertEqual(0, report["payload"]["failed_count"])
        self.assertEqual([], report["payload"]["skipped_required"])
        self.assertEqual("", self.git("status", "--porcelain"))
        self.assertEqual("answer = 42", self.git("show", manifest["head_sha"] + ":examples/answer.py"))
        for retained in report["evidence"]:
            raw = (self.result / retained["uri"]).read_bytes()
            self.assertEqual(retained["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(original, load_json(self.bundle / "run.json"))

    def test_optimistic_agent_cannot_override_real_behavioral_failure(self):
        self.prepare()
        self.response(value=99)
        result = self.verify()
        self.assertFalse(result["passed"])
        self.assertEqual("failed", result["status"])
        report = load_json(self.result / "verification-report.json")
        self.assertEqual("failed", report["status"])
        self.assertEqual(1, report["payload"]["failed_count"])
        self.assertTrue(any("FAIL: test_answer" in path.read_text()
                            for path in (self.result / "logs").glob("*")))

    def test_zero_tests_and_skipped_required_checks_cannot_pass(self):
        for variant in ("empty", "skipped"):
            with self.subTest(variant=variant):
                self.bundle = self.directory / (variant + "-inputs")
                self.result = self.directory / (variant + "-result")
                self.git("checkout", "--quiet", "--detach", self.base)
                self.prepare(variant)
                # Render directly to a variant-specific destination.
                context = self.directory / (variant + "-context")
                software.render(self.bundle, self.repo, context, at=self.at)
                response = load_json(context / "change-template.json")
                response.update({"status": "passed", "summary": "Synthetic fixed proposal.",
                                 "criteria_addressed": [c["id"] for c in load_json(self.bundle / "target.json")["criteria"]],
                                 "behavior_changes": ["The public answer is 42."],
                                 "checks_run": [{"command": "unittest", "observed": "Synthetic claim."}],
                                 "remaining_work": [],
                                 "edits": [{"path": "examples/answer.py", "content": "answer = 42\n"}]})
                self.submit(response)
                result = self.verify()
                self.assertFalse(result["passed"])
                # Python versions differ on whether empty discovery exits
                # successfully. Either observed failure or inconclusive is
                # nonpassing; skipped required work is always inconclusive.
                if variant == "skipped":
                    self.assertEqual("inconclusive", result["status"])
                else:
                    self.assertIn(result["status"], {"failed", "inconclusive"})

    def test_closed_issue_or_pull_request_cannot_authorize_work(self):
        for key, value in (("state", "closed"), ("pull_request", {"url": "untrusted"})):
            with self.subTest(key=key):
                issue = {**self.issue, key: value}
                with self.assertRaises(ValueError):
                    self.prepare(issue=issue)
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_authorized_paths_are_exact_bounded_files(self):
        for selected in (
            [], [".github/workflows/ci.yml"], ["integrations/github/software.py"],
            ["requirements-dev.txt"], ["docs/*"], ["docs/../README.md"],
            ["/tmp/escape.md"], ["docs\\escape.md"], ["examples/.git/config"],
            ["examples/answer.py", "examples/answer.py"],
            [f"docs/{index}.md" for index in range(9)],
        ):
            with self.subTest(paths=selected):
                with self.assertRaises(ValueError):
                    self.prepare(allowed_paths=selected)

    def test_empty_acceptance_criteria_cannot_become_a_ready_work_item(self):
        with self.assertRaises(ValueError):
            self.prepare(acceptance_criteria=[])

    def test_dirty_candidate_is_not_accepted_as_the_pinned_base(self):
        (self.repo / "examples/answer.py").write_text("answer = 99\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.prepare()

    def test_wrong_agent_run_or_subject_is_rejected_before_editing(self):
        self.prepare()
        response = self.response()
        for field, value in (("run_id", "github-software-9999-1"),
                             ("subject", {**response["subject"], "revision": "f" * 40})):
            with self.subTest(field=field):
                self.submit({**response, field: value})
                with self.assertRaises(ValueError):
                    self.verify()
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
                self.assertEqual("answer = 41\n", (self.repo / "examples/answer.py").read_text())

    def test_missing_or_duplicate_acceptance_criteria_cannot_pass(self):
        self.prepare()
        response = self.response()
        criterion = response["criteria_addressed"][0]
        for values in ([], [criterion, criterion], ["unapproved-criterion"]):
            with self.subTest(criteria=values):
                self.submit({**response, "criteria_addressed": values})
                with self.assertRaises(ValueError):
                    self.verify()
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_out_of_scope_or_duplicate_edits_are_rejected_before_writing(self):
        self.prepare()
        response = self.response()
        for edits in (
            [{"path": "README.md", "content": "Outside the selected exact file.\n"}],
            [{"path": "examples/../README.md", "content": "Traversal.\n"}],
            [{"path": ".github/workflows/write.yml", "content": "permissions: write-all\n"}],
            response["edits"] * 2,
        ):
            with self.subTest(edits=edits):
                self.submit({**response, "edits": edits})
                with self.assertRaises(ValueError):
                    self.verify()
                self.assertEqual("answer = 41\n", (self.repo / "examples/answer.py").read_text())
                self.assertEqual("", self.git("status", "--porcelain"))

    def test_noop_submission_does_not_create_a_candidate(self):
        self.prepare()
        self.response(value=41)
        with self.assertRaises(ValueError):
            self.verify()
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_unresolved_work_or_missing_builder_observations_cannot_claim_pass(self):
        self.prepare()
        response = self.response()
        for field, value in (("remaining_work", ["Required criterion is unresolved."]),
                             ("checks_run", []), ("behavior_changes", []), ("edits", [])):
            with self.subTest(field=field):
                self.submit({**response, field: value})
                with self.assertRaises(ValueError):
                    self.verify()
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_actual_pilot_advisory_remaining_work_still_blocks_publication(self):
        """Run #44689746001: passed agent with nonempty work must fail closed."""
        self.prepare()
        response = self.response(remaining_work=[
            "A stronger policy could be considered separately.",
            "Independent verification and human PR review remain necessary.",
        ])
        with self.assertRaisesRegex(ValueError, "Passing build lacks complete criteria"):
            self.verify()
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertEqual("", self.git("status", "--porcelain"))
        self.assertFalse((self.result / "candidate.json").exists())
        self.assertEqual("passed", response["status"])

    def test_optional_limitations_are_retained_but_require_independent_checks(self):
        self.prepare()
        context = self.directory / "context"
        software.render(self.bundle, self.repo, context, at=self.at)
        instructions = (context / "invocation.md").read_text(encoding="utf-8")
        self.assertIn("remaining_work=[]", instructions)
        self.assertIn("non-blocking residual risks", instructions)
        response = load_json(context / "change-template.json")
        self.assertEqual([], response["limitations"])
        response.update({
            "status": "passed", "summary": "Repair a bounded behavior.",
            "criteria_addressed": ["acceptance-1"], "behavior_changes": ["Answer is 42."],
            "checks_run": [{"command": "python -m unittest", "observed": "Builder claim only."}],
            "remaining_work": [],
            "limitations": ["The quality reviewer must still inspect the scope.",
                            "More hardening may be useful outside this issue."],
            "edits": [{"path": "examples/answer.py", "content": "answer = 42" + chr(10)}],
        })
        self.submit(response)
        gate = self.verify()
        self.assertTrue(gate["passed"])
        change = load_json(self.result / "change-set.json")
        self.assertEqual(response["limitations"], change["payload"]["builder_limitations"])
        summary = (self.result / "summary.md").read_text()
        self.assertIn("More hardening may be useful outside this issue.", summary)
        self.assertEqual("passed", load_json(self.result / "verification-report.json")["status"])

    def test_limitations_cannot_smuggle_authority_or_unbounded_text(self):
        self.prepare()
        response = self.response()
        for value in ("review later", ["x" * 2001],
                      [{"grant": "contents:write"}]):
            with self.subTest(value=value):
                self.submit({**response, "limitations": value})
                with self.assertRaisesRegex(ValueError, "closed schema"):
                    self.verify()
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_transport_checksum_rejects_fourth_pilot_redaction_before_execution(self):
        """The upstream sanitizer's three n/redacted markers cannot run as code."""
        self.prepare()
        response = self.response()
        outer = load_json(self.submission)
        submitted = outer["items"][0]
        original = submitted["change_json"]
        original_sha = submitted["change_sha256"]

        # Mimic v1.2.2's loss of escaped newline source, without real secrets.
        code = response["edits"][0]["content"]
        response["edits"][0]["content"] = (
            code + 'write_text("one\\\\n")\\n'
                   + 'write_text("two\\\\n")\\n'
                   + 'write_text("three\\\\n")\\n')
        clean = json.dumps(response)
        altered = clean.replace("\\\\n", "(n/redacted)", 3)
        self.assertNotEqual(clean, altered)
        self.assertEqual(3, altered.count("(n/redacted)"))
        submitted["change_json"] = altered
        submitted["change_sha256"] = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        self.write(self.submission, outer)

        # The fixture's synthetic run_id must not impersonate this real CI
        # workflow's GITHUB_RUN_ID. Only disable that external provenance
        # comparison inside this unit test, not in the production controller.
        with patch.object(software.quality, "check_actions_run"):
            status = software.main([
                "verify", "--repo", str(self.repo), "--bundle", str(self.bundle),
                "--submission", str(self.submission), "--agent-result", "success",
                "--out", str(self.result),
            ])
        self.assertEqual(1, status)
        gate = load_json(self.result / "gate.json")
        self.assertFalse(gate["passed"])
        self.assertEqual("blocked", gate["status"])
        self.assertIn("Safe-output transport changed", gate["reasons"][0])
        self.assertFalse((self.result / "candidate.json").exists())
        self.assertFalse((self.result / "logs" / "answer-behavior.txt").exists())
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertEqual("answer = 41\n", (self.repo / "examples/answer.py").read_text())

    def test_checksum_is_required_and_verified_independently_of_builder_claim(self):
        self.prepare()
        self.response()
        envelope = load_json(self.submission)
        original = envelope["items"][0]["change_sha256"]
        for digest in (None, "", "X" * 64, "0" * 64, 123):
            with self.subTest(checksum=digest):
                corrupted = deepcopy(envelope)
                if digest is None:
                    del corrupted["items"][0]["change_sha256"]
                else:
                    corrupted["items"][0]["change_sha256"] = digest
                self.write(self.submission, corrupted)
                with self.assertRaisesRegex(ValueError, "SHA-256|Safe-output transport|change_sha256"):
                    software.load_response(self.submission, load_json(self.bundle / "run.json"),
                                           load_json(self.bundle / "target.json"))
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertRegex(original, r"^[0-9a-f]{64}$")
        self.write(self.submission, envelope)
        self.assertTrue(self.verify()["passed"])

    def test_unknown_response_authority_field_is_rejected(self):
        self.prepare()
        response = self.response()
        response["merge_authorized"] = True
        self.submit(response)
        with self.assertRaises(ValueError):
            self.verify()

    def test_failed_cancelled_or_skipped_agent_cannot_clear_the_gate(self):
        self.prepare()
        self.response()
        for state in ("failure", "cancelled", "skipped"):
            with self.subTest(state=state):
                self.result = self.directory / ("result-" + state)
                result = self.verify(agent_result=state)
                self.assertFalse(result["passed"])
                self.assertNotEqual("passed", result["status"])
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_agent_negative_result_is_retained_without_applying_proposed_edits(self):
        self.prepare()
        self.response(status="inconclusive", remaining_work=["Cannot establish the required behavior."])
        result = self.verify()
        self.assertFalse(result["passed"])
        self.assertNotEqual("passed", result["status"])
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_duplicate_transport_json_keys_are_rejected(self):
        self.prepare()
        self.response()
        self.submission.write_text('{"items":[],"items":[]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.verify()

    def test_live_gh_aw_output_id_is_allowed_but_unrecognized_metadata_fails_closed(self):
        self.prepare()
        response = self.response()
        envelope = load_json(self.submission)
        envelope["items"][0]["output_id"] = "so_qPWeylbZTcqh"
        self.write(self.submission, envelope)
        result = self.verify()
        self.assertTrue(result["passed"])
        self.assertEqual(self.base, load_json(self.result / "candidate.json")["base_sha"])
        # The host retains the original transport bytes, including output_id.
        self.assertEqual(envelope, load_json(self.result / "submission.json"))
        for metadata in ({"output_id": 3}, {"output_id": "not-a-safe-output-id"},
                         {"output_id": "so_" + "x" * 200}, {"untrusted_override": True}):
            with self.subTest(metadata=metadata):
                self.submit(response)
                wrapper = load_json(self.submission)
                wrapper["items"][0].update(metadata)
                self.write(self.submission, wrapper)
                with self.assertRaises(ValueError):
                    software.load_response(self.submission, load_json(self.bundle / "run.json"),
                                           load_json(self.bundle / "target.json"))

    def test_live_gh_aw_noop_after_submission_is_advisory_not_a_second_change(self):
        # Reproduces the real 44621190636 transport shape (one submit_change,
        # a terminal noop, and a separate empty errors array).
        self.prepare()
        self.response()
        wrapper = load_json(self.submission)
        wrapper["items"][0]["output_id"] = "so_tdQh6myFQEKy"
        wrapper["items"].append({
            "type": "noop", "output_id": "so_qiZt5Q-GSrqu",
            "message": "submit_change was called with the completed documentation change; no further action needed.",
        })
        wrapper["errors"] = []
        self.write(self.submission, wrapper)
        result = self.verify()
        self.assertTrue(result["passed"])
        self.assertEqual("passed", result["status"])
        self.assertEqual(wrapper, load_json(self.result / "submission.json"))
        self.assertEqual(self.base, load_json(self.result / "candidate.json")["base_sha"])

    def test_noop_transport_cannot_smuggle_an_extra_change_or_an_error(self):
        self.prepare()
        self.response()
        original = load_json(self.submission)
        original["items"][0]["output_id"] = "so_change"
        noop = {"type": "noop", "output_id": "so_noop", "message": "Done."}
        run = load_json(self.bundle / "run.json")
        target = load_json(self.bundle / "target.json")
        cases = {
            "duplicate-change": {"items": [original["items"][0], original["items"][0]]},
            "noop-only": {"items": [noop]},
            "noop-before-change": {"items": [noop, original["items"][0]]},
            "unknown-output": {"items": [original["items"][0], {"type": "create_issue", "message": "bad"}]},
            "extra-noop-field": {"items": [original["items"][0], {**noop, "permissions": "write"}]},
            "duplicate-output-id": {"items": [original["items"][0], {**noop, "output_id": "so_change"}]},
            "invalid-noop-id": {"items": [original["items"][0], {**noop, "output_id": "not-gh-aw"}]},
            "invalid-noop-message": {"items": [original["items"][0], {**noop, "message": 17}]},
            "oversized-noop-message": {"items": [original["items"][0], {**noop, "message": "x" * 2001}]},
            "three-noops": {"items": [original["items"][0], noop, noop, noop]},
            "reported-errors": {"items": [original["items"][0], noop], "errors": ["failed"]},
            "invalid-error-envelope": {"items": [original["items"][0]], "errors": None},
            "extra-envelope-field": {"items": [original["items"][0]], "override": True},
        }
        for name, wrapper in cases.items():
            with self.subTest(name=name):
                self.write(self.submission, wrapper)
                with self.assertRaises(ValueError):
                    software.load_response(self.submission, run, target)
                self.assertEqual(self.base, self.git("rev-parse", "HEAD"))

    def test_two_documented_noops_can_follow_one_change(self):
        self.prepare()
        self.response()
        wrapper = load_json(self.submission)
        wrapper["items"].extend([
            {"type": "noop", "output_id": "so_a", "message": "Complete."},
            {"type": "noop", "output_id": "so_b", "message": "No more work."},
        ])
        self.write(self.submission, wrapper)
        self.assertTrue(self.verify()["passed"])

    def test_multiple_submissions_are_not_silently_selected(self):
        self.prepare()
        self.response()
        wrapper = load_json(self.submission)
        wrapper["items"] *= 2
        self.write(self.submission, wrapper)
        with self.assertRaises(ValueError):
            self.verify()

    def test_original_input_tampering_is_rejected(self):
        self.prepare()
        target_path = self.bundle / "target.json"
        target = load_json(target_path)
        target["untrusted_extra_scope"] = "all files"
        self.write(target_path, target)
        with self.assertRaises(ValueError):
            software.load_bundle(self.bundle, self.at)

    def test_stale_original_inputs_cannot_be_reused(self):
        self.prepare()
        with self.assertRaises(ValueError):
            software.load_bundle(self.bundle, self.at + timedelta(hours=3))

    def test_symlink_file_and_parent_cannot_escape_the_candidate(self):
        outside = self.directory / "outside.txt"
        outside.write_text("Do not modify.\n", encoding="utf-8")
        (self.repo / "examples/link.txt").symlink_to(outside)
        (self.repo / "examples/outside").symlink_to(self.directory, target_is_directory=True)
        self.git("add", "examples/link.txt", "examples/outside")
        self.git("commit", "--quiet", "-m", "Add tracked symlink boundaries")
        for path in ("examples/link.txt", "examples/outside/outside.txt"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.prepare(allowed_paths=[path])
        self.assertEqual("Do not modify.\n", outside.read_text())

    def test_candidate_mutation_during_verification_invalidates_proof(self):
        self.prepare("mutate")
        self.response()
        with self.assertRaises(ValueError):
            self.verify()


class SoftwareGitHub:
    """Metadata API fixture; it never executes submitted candidate contents."""

    def __init__(self, base, issue, candidate):
        self.base, self.issue, self.candidate = base, deepcopy(issue), deepcopy(candidate)
        self.repository = {"full_name": "fixture/software", "default_branch": "main"}
        self.workflow = {"id": 50, "path": ".github/workflows/sfstack-software.yml"}
        self.run = {"id": 1234, "run_attempt": 1, "workflow_id": self.workflow["id"],
                    "path": self.workflow["path"], "event": "workflow_dispatch",
                    "head_sha": base, "head_branch": "main", "actor": {"login": "maintainer"},
                    "triggering_actor": {"login": "maintainer"}, "status": "in_progress",
                    "repository": self.repository, "head_repository": self.repository}
        self.permission = "maintain"
        self.artifacts = [{"id": 812, "name": "sfstack-software-result-1", "expired": False,
                           "workflow_run": {"id": 1234, "head_sha": base}}]
        self.refs, self.pulls, self.calls = [], [], []
        self.fail_dispatch = False
        self.lose_pull_response = False
        self.wrong_blob = self.wrong_tree = self.wrong_commit = False
        self.issue_reads = 0
        self.change_issue_on_read = None
        self.change_pull_on_read = None

    @property
    def mutations(self):
        return [call for call in self.calls if call[0] != "GET"]

    def get(self, path):
        self.calls.append(("GET", path, None))
        parsed = urlsplit(path)
        prefix = "repos/fixture/software"
        if not parsed.path.startswith(prefix):
            raise AssertionError("Unexpected repository: " + path)
        suffix = unquote(parsed.path[len(prefix):])
        if suffix == "":
            value = self.repository
        elif suffix == "/git/ref/heads/main":
            value = {"object": {"sha": self.base}}
        elif suffix == "/actions/workflows/sfstack-software.yml":
            value = self.workflow
        elif suffix == "/actions/runs/1234":
            value = self.run
        elif suffix == "/collaborators/maintainer/permission":
            value = {"permission": self.permission}
        elif suffix == "/issues/7":
            self.issue_reads += 1
            if self.issue_reads == self.change_issue_on_read:
                self.issue["body"] = "Issue requirements changed after preparation."
            value = self.issue
        elif suffix == "/actions/runs/1234/artifacts":
            value = {"artifacts": self.artifacts}
        elif suffix.startswith("/git/matching-refs/heads/"):
            value = self.refs
        elif suffix == "/pulls/21":
            value = deepcopy(self.pulls[0])
            if self.change_pull_on_read:
                section, field, changed = self.change_pull_on_read
                if section:
                    value[section][field] = changed
                else:
                    value[field] = changed
        elif suffix == "/pulls":
            if parse_qs(parsed.query).get("state") != ["all"]:
                raise AssertionError("Publication must inspect existing PRs, including closed ones.")
            value = self.pulls
        else:
            raise AssertionError("Unexpected read: " + path)
        return deepcopy(value)

    def post(self, path, body):
        self.calls.append(("POST", path, deepcopy(body)))
        prefix = "repos/fixture/software"
        if not path.startswith(prefix):
            raise AssertionError("Unexpected repository: " + path)
        suffix = path[len(prefix):]
        if suffix == "/git/blobs":
            raw = body["content"].encode("utf-8")
            identity = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            return {"sha": "f" * 40 if self.wrong_blob else identity}
        if suffix == "/git/trees":
            return {"sha": "f" * 40 if self.wrong_tree else self.candidate["tree_sha"]}
        if suffix == "/git/commits":
            return {"sha": "f" * 40 if self.wrong_commit else self.candidate["head_sha"]}
        if suffix == "/git/refs":
            if self.refs:
                raise AssertionError("A factory branch must not be recreated or overwritten.")
            reference = {"ref": body["ref"], "object": {"sha": body["sha"]}}
            self.refs.append(reference)
            return deepcopy(reference)
        if suffix == "/pulls":
            if self.pulls:
                raise AssertionError("Existing draft PR must be reconciled before creating another.")
            pull = {"number": 21, "state": "open", "draft": body["draft"],
                    "title": body["title"],
                    "head": {"sha": self.refs[0]["object"]["sha"], "ref": body["head"],
                             "repo": {"full_name": "fixture/software"}},
                    "base": {"ref": body["base"], "repo": {"full_name": "fixture/software"}},
                    "body": body["body"]}
            self.pulls.append(pull)
            if self.lose_pull_response:
                raise ValueError("Fixture lost the PR creation response after the write.")
            return deepcopy(pull)
        if suffix == "/actions/workflows/sfstack-quality.yml/dispatches":
            if self.fail_dispatch:
                raise ValueError("Fixture quality dispatch is unavailable.")
            return None
        raise AssertionError("Unexpected mutation: " + path)


class GitHubSoftwarePublicationTests(SoftwareFixture):
    def prepared_host(self, value=42, **response_updates):
        self.prepare()
        self.response(value=value, **response_updates)
        self.verify()
        candidate = load_json(self.result / "candidate.json")
        self.api = SoftwareGitHub(self.base, self.issue, candidate)
        self.context = {"repository": "fixture/software", "run_id": "1234", "run_attempt": "1",
                        "workflow_sha": self.base, "ref": "refs/heads/main", "event_name": "workflow_dispatch"}
        self.host = software.SoftwareHost(self.api, self.context)
        # Publication works from the unchanged controller/base checkout. Its
        # only interaction with candidate code is creating immutable Git data.
        self.git("checkout", "--quiet", "--detach", self.base)
        return candidate

    def publish(self):
        return self.host.publish(self.bundle, self.result, self.repo, at=self.at)

    def assert_no_remote_reference_mutations(self):
        self.assertFalse(any(path.endswith(("/git/refs", "/pulls", "/dispatches"))
                             for _, path, _ in self.api.mutations))

    def test_publish_creates_exact_draft_and_requests_quality_for_verified_head(self):
        candidate = self.prepared_host()
        published = self.publish()
        self.assertTrue(published["published"])
        self.assertTrue(published["draft"])
        self.assertTrue(published["quality_requested"])
        self.assertFalse(published["quality_passed"])
        self.assertFalse(published["merge_authorized"])
        self.assertEqual(candidate["head_sha"], published["candidate_sha"])
        self.assertEqual(self.base, self.git("rev-parse", "HEAD"))
        self.assertEqual("answer = 41\n", (self.repo / "examples/answer.py").read_text())
        branch = next(body for _, path, body in self.api.mutations if path.endswith("/git/refs"))
        self.assertEqual("refs/heads/sfstack/issue-7-1234-1", branch["ref"])
        self.assertEqual(candidate["head_sha"], branch["sha"])
        commit = next(body for _, path, body in self.api.mutations if path.endswith("/git/commits"))
        self.assertEqual([self.base], commit["parents"])
        self.assertEqual(candidate["identity"], commit["author"])
        self.assertEqual(commit["author"], commit["committer"])
        self.assertEqual(candidate["message"], commit["message"])
        self.assertEqual(candidate["tree_sha"], commit["tree"])
        pull = next(body for _, path, body in self.api.mutations if path.endswith("/pulls"))
        self.assertTrue(pull["draft"])
        self.assertEqual("main", pull["base"])
        self.assertIn("/artifacts/812", pull["body"])
        dispatch = next(body for _, path, body in self.api.mutations if path.endswith("/dispatches"))
        self.assertEqual({"ref": "main", "inputs": {
            "pr-number": "21", "expected-head": candidate["head_sha"], "expected-base": self.base,
        }}, dispatch)
        self.assertFalse(any("merge" in path for _, path, _ in self.api.mutations))

    def test_builder_limitations_survive_into_the_draft_pr_without_approval(self):
        candidate = self.prepared_host(limitations=[
            "Future hardening outside this issue may be needed.",
            "Independent human review is still required.",
        ])
        published = self.publish()
        self.assertTrue(published["draft"])
        self.assertTrue(published["quality_requested"])
        self.assertFalse(published["merge_authorized"])
        body = self.api.pulls[0]["body"]
        self.assertIn("Builder-reported limitations (unverified)", body)
        self.assertIn("Future hardening outside this issue may be needed.", body)
        self.assertEqual(candidate["head_sha"], published["candidate_sha"])

    def test_negative_host_verification_never_creates_remote_objects_or_refs(self):
        self.prepared_host(value=99)
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual([], self.api.mutations)

    def test_changed_issue_and_advanced_base_reject_before_remote_writes(self):
        self.prepared_host()
        original_issue = deepcopy(self.api.issue)
        for field, value in (("title", "Changed requirement"), ("body", "Different acceptance"),
                             ("updated_at", "2026-11-19T13:00:00Z"), ("state", "closed")):
            with self.subTest(field=field):
                self.api.issue = {**original_issue, field: value}
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual([], self.api.mutations)
        self.api.issue = original_issue
        self.api.base = "f" * 40
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual([], self.api.mutations)

    def test_replayed_attempt_or_untrusted_workflow_cannot_publish(self):
        self.prepared_host()
        original = deepcopy(self.api.run)
        for field, value in (("run_attempt", 2), ("workflow_id", 999),
                             ("event", "pull_request"), ("head_sha", "f" * 40),
                             ("path", ".github/workflows/untrusted.yml")):
            with self.subTest(field=field):
                self.api.run = {**original, field: value}
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual([], self.api.mutations)

    def test_nonwriter_or_bot_cannot_publish_maintainer_authorized_work(self):
        self.prepared_host()
        for permission in ("read", "triage", "none"):
            with self.subTest(permission=permission):
                self.api.permission = permission
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual([], self.api.mutations)
        self.api.permission = "write"
        self.api.run["triggering_actor"] = {"login": "github-actions[bot]"}
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual([], self.api.mutations)

    def test_modified_host_log_cannot_be_republished_as_passing_proof(self):
        self.prepared_host()
        log = self.result / "logs/answer-behavior.txt"
        log.write_text("Replaced the actual observation.\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual([], self.api.mutations)

    def test_tampered_candidate_or_gate_cannot_select_different_published_content(self):
        self.prepared_host()
        candidate_path = self.result / "candidate.json"
        candidate = load_json(candidate_path)
        candidate["edits"][0]["content"] = "answer = 99\n"
        self.write(candidate_path, candidate)
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual([], self.api.mutations)

    def test_missing_expired_or_previous_attempt_artifact_cannot_publish(self):
        self.prepared_host()
        artifact = deepcopy(self.api.artifacts[0])
        for value in ([], [{**artifact, "expired": True}], [{**artifact, "name": "sfstack-software-result-2"}],
                      [{**artifact, "workflow_run": {"id": 9999, "head_sha": self.base}}],
                      [artifact, deepcopy(artifact)]):
            with self.subTest(artifacts=value):
                self.api.artifacts = value
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertEqual([], self.api.mutations)

    def test_mismatched_github_git_objects_never_create_a_branch_or_pr(self):
        self.prepared_host()
        for attribute in ("wrong_blob", "wrong_tree", "wrong_commit"):
            with self.subTest(attribute=attribute):
                setattr(self.api, attribute, True)
                with self.assertRaises(ValueError):
                    self.publish()
                self.assert_no_remote_reference_mutations()
                setattr(self.api, attribute, False)

    def test_issue_change_while_creating_objects_stops_before_referencing_them(self):
        self.prepared_host()
        self.api.change_issue_on_read = 2
        with self.assertRaises(ValueError):
            self.publish()
        self.assert_no_remote_reference_mutations()

    def test_retry_reconciles_existing_exact_branch_and_draft(self):
        self.prepared_host()
        first = self.publish()
        second = self.publish()
        self.assertEqual(first["pull_request"], second["pull_request"])
        self.assertEqual(1, sum(path.endswith("/git/refs") for _, path, _ in self.api.mutations))
        self.assertEqual(1, sum(path.endswith("/pulls") for _, path, _ in self.api.mutations))

    def test_changed_factory_branch_or_reviewed_pr_is_never_overwritten(self):
        candidate = self.prepared_host()
        self.api.refs = [{"ref": "refs/heads/sfstack/issue-7-1234-1", "object": {"sha": "f" * 40}}]
        with self.assertRaises(ValueError):
            self.publish()
        self.assert_no_remote_reference_mutations()
        self.api.refs[0]["object"]["sha"] = candidate["head_sha"]
        self.api.pulls = [{"number": 21, "state": "open", "draft": False,
                           "head": {"sha": candidate["head_sha"]}, "base": {"ref": "main"}}]
        with self.assertRaises(ValueError):
            self.publish()
        self.assert_no_remote_reference_mutations()

    def test_failed_quality_dispatch_leaves_exact_draft_for_safe_recovery(self):
        self.prepared_host()
        self.api.fail_dispatch = True
        with self.assertRaisesRegex(ValueError, "dispatch"):
            self.publish()
        self.assertEqual(1, len(self.api.refs))
        self.assertEqual(1, len(self.api.pulls))
        self.assertTrue(self.api.pulls[0]["draft"])
        self.assertTrue(self.host.publication_state["published"])
        self.assertFalse(self.host.publication_state["quality_requested"])
        self.assertEqual("https://github.com/fixture/software/pull/21", self.host.publication_state["url"])
        self.api.fail_dispatch = False
        result = self.publish()
        self.assertTrue(result["quality_requested"])
        self.assertFalse(result["quality_passed"])
        self.assertEqual(1, sum(path.endswith("/pulls") for _, path, _ in self.api.mutations))

    def test_pr_drift_after_creation_is_rechecked_before_quality_dispatch(self):
        self.prepared_host()
        self.api.change_pull_on_read = ("head", "sha", "f" * 40)
        with self.assertRaises(ValueError):
            self.publish()
        self.assertTrue(self.api.pulls[0]["draft"])
        self.assertFalse(any(path.endswith("/dispatches") for _, path, _ in self.api.mutations))
        self.assertTrue(self.host.publication_state["published"])
        self.assertFalse(self.host.publication_state["quality_requested"])

    def test_current_pr_identity_includes_its_branch_repositories_and_draft_state(self):
        self.prepared_host()
        # Start with an exact existing result, then simulate live PR changes
        # visible only in the final metadata refresh before dispatch.
        self.publish()
        self.api.calls.clear()
        for change in (("head", "ref", "some-other-branch"),
                       ("head", "repo", {"full_name": "fixture/another-repository"}),
                       ("base", "repo", {"full_name": "fixture/another-repository"}),
                       (None, "draft", False), (None, "state", "closed"),
                       (None, "title", "Different purpose"),
                       (None, "body", "Changed the acceptance criteria after creation.")):
            with self.subTest(change=change):
                self.api.change_pull_on_read = change
                with self.assertRaises(ValueError):
                    self.publish()
                self.assert_no_remote_reference_mutations()

    def test_lost_pr_creation_response_is_uncertain_and_reconciled_on_retry(self):
        self.prepared_host()
        self.api.lose_pull_response = True
        with self.assertRaisesRegex(ValueError, "lost"):
            self.publish()
        self.assertIsNone(self.host.publication_state["published"])
        self.assertFalse(self.host.publication_state["quality_requested"])
        self.assertEqual(1, len(self.api.pulls))
        self.api.lose_pull_response = False
        published = self.publish()
        self.assertTrue(published["published"])
        self.assertEqual(21, published["pull_request"])
        self.assertEqual(1, sum(path.endswith("/pulls") for _, path, _ in self.api.mutations))


class GitHubSoftwareExecutedRegressionTests(unittest.TestCase):
    def test_same_behavioral_oracle_rejects_the_unfixed_candidate_and_accepts_the_fix(self):
        sys.path.insert(0, str(ROOT / "evals"))
        from run_software_regression import run_regression
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "retained"
            result = run_regression(output)
            unfixed, fixed = (result["cases"][variant] for variant in ("unfixed", "fixed"))
            self.assertFalse(unfixed["passed"])
            self.assertTrue(fixed["passed"])
            self.assertEqual(unfixed["base_sha"], fixed["base_sha"])
            self.assertNotEqual(unfixed["candidate_sha"], fixed["candidate_sha"])
            self.assertEqual(6, unfixed["tests_run"])
            self.assertEqual(6, fixed["tests_run"])
            self.assertIn("FAIL: test_exact", (output / unfixed["verification_log"]).read_text())
            self.assertIn("\nOK\n", (output / fixed["verification_log"]).read_text())
            plans = [load_json(output / variant / "inputs/target.json")["checks"]
                     for variant in ("unfixed", "fixed")]
            self.assertEqual(plans[0], plans[1])
            self.assertEqual(result, load_json(output / "summary.json"))


if __name__ == "__main__":
    unittest.main()
