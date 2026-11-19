"""Trusted metadata, current ownership, and real evidence govern PR check writes."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))
from integrations.github.automation import (CHECK_NAME, EVENTS, QUALITY, SIGNAL,
                                            Host, check_owner, owner, owner_text)
from run_github_regression import run_regression

REPOSITORY = "fixture/inventory"
BASE = "b" * 40
HEAD = "a" * 40


class FakeGitHub:
    """In-memory API responses; unknown reads fail instead of inventing data."""

    def __init__(self):
        self.repository = {"full_name": REPOSITORY, "default_branch": "main"}
        self.tip = BASE
        self.workflows = {
            name: {"id": index, "path": ".github/workflows/" + name}
            for index, name in enumerate((QUALITY, SIGNAL, EVENTS), start=10)
        }
        self.pulls = {1: self.pull()}
        self.runs = {}
        self.checks = {}
        self.artifacts = []
        self.calls = []
        self.fail_dispatch = False
        self.add_run(100)

    @staticmethod
    def pull(number=1, head=HEAD, base=BASE, head_repository=REPOSITORY):
        return {"number": number, "state": "open", "title": "Fixture PR",
                "head": {"sha": head, "ref": "candidate", "repo": {"full_name": head_repository}},
                "base": {"sha": base, "ref": "main", "repo": {"full_name": REPOSITORY}}}

    def add_run(self, identifier, workflow=QUALITY, event="workflow_dispatch", attempt=1,
                status="in_progress", head=BASE, title=None):
        run = {
            "id": identifier, "run_attempt": attempt, "workflow_id": self.workflows[workflow]["id"],
            "path": self.workflows[workflow]["path"], "event": event,
            "repository": {"full_name": REPOSITORY}, "head_repository": {"full_name": REPOSITORY},
            "head_branch": "main", "head_sha": head, "status": status, "conclusion": None,
            "display_title": title or "sfstack quality / PR #1 / request manual", "pull_requests": [],
        }
        self.runs[identifier] = run
        return run

    @property
    def mutations(self):
        return [call for call in self.calls if call[0] != "GET"]

    def get(self, path):
        self.calls.append(("GET", path, None))
        parsed = urlsplit(path)
        base = "repos/" + REPOSITORY
        suffix = parsed.path[len(base):]
        if not parsed.path.startswith(base):
            raise AssertionError("Unexpected repository in API path: " + path)
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        if suffix == "":
            result = self.repository
        elif suffix == "/git/ref/heads/main":
            result = {"object": {"sha": self.tip}}
        elif suffix.startswith("/actions/workflows/"):
            result = self.workflows[suffix.rsplit("/", 1)[-1]]
        elif re.fullmatch(r"/actions/runs/[0-9]+", suffix):
            result = self.runs[int(suffix.rsplit("/", 1)[-1])]
        elif re.fullmatch(r"/actions/runs/[0-9]+/artifacts", suffix):
            result = {"artifacts": self.artifacts if page == 1 else []}
        elif re.fullmatch(r"/pulls/[0-9]+", suffix):
            result = self.pulls[int(suffix.rsplit("/", 1)[-1])]
        elif suffix == "/pulls":
            result = list(self.pulls.values()) if page == 1 else []
        elif re.fullmatch(r"/commits/[a-f0-9]{40}/check-runs", suffix):
            head = suffix.split("/")[2]
            result = {"check_runs": [check for check in self.checks.values() if check["head_sha"] == head] if page == 1 else []}
        elif re.fullmatch(r"/check-runs/[0-9]+", suffix):
            result = self.checks[int(suffix.rsplit("/", 1)[-1])]
        else:
            raise AssertionError("Unexpected GitHub read: " + path)
        return deepcopy(result)

    def post(self, path, body):
        self.calls.append(("POST", path, deepcopy(body)))
        if path.endswith("/check-runs"):
            identifier = max(self.checks, default=500) + 1
            check = {"id": identifier, "app": {"slug": "github-actions"}, **deepcopy(body)}
            self.checks[identifier] = check
            return deepcopy(check)
        if path.endswith("/actions/workflows/" + QUALITY + "/dispatches"):
            if self.fail_dispatch:
                raise ValueError("Dispatch unavailable")
            return None
        raise AssertionError("Unexpected GitHub mutation: " + path)

    def patch(self, path, body):
        self.calls.append(("PATCH", path, deepcopy(body)))
        if not re.fullmatch("repos/" + REPOSITORY + r"/check-runs/[0-9]+", path):
            raise AssertionError("Unexpected GitHub mutation: " + path)
        check = self.checks[int(path.rsplit("/", 1)[-1])]
        check.update(deepcopy(body))
        # GitHub uses status to distinguish an in-progress rerun from an old
        # completion. Assert status as well as conclusion in all tests below.
        return deepcopy(check)


class GitHubAutomationTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHub()
        self.context = {"repository": REPOSITORY, "run_id": "100", "run_attempt": "1",
                        "workflow_sha": BASE, "ref": "refs/heads/main", "event_name": "workflow_dispatch"}
        self.host = Host(self.api, self.context)

    def new_host(self, identifier, workflow=QUALITY, event="workflow_dispatch", attempt=1, **changes):
        run = self.api.add_run(identifier, workflow, event, attempt, **changes)
        context = {**self.context, "run_id": str(identifier), "run_attempt": str(attempt),
                   "workflow_sha": run["head_sha"], "event_name": event}
        return Host(self.api, context)

    def start(self, host=None):
        return (host or self.host).start(1)["publication"]

    def check(self, publication):
        return self.api.checks[publication["check_id"]]

    def test_start_attaches_pending_check_to_exact_pr_head(self):
        publication = self.start()
        check = self.check(publication)
        self.assertEqual(HEAD, check["head_sha"])
        self.assertEqual("in_progress", check["status"])
        self.assertEqual(CHECK_NAME, check["name"])
        self.assertEqual(owner(1, BASE, "run", 100, 1, ""), check_owner(check))
        self.assertEqual(BASE, publication["controller_sha"])

    def test_current_base_snapshot_replaces_stale_pr_base_without_mutating_api(self):
        self.api.pulls[1]["base"]["sha"] = "d" * 40
        result = self.host.start(1)
        self.assertTrue(result["eligible"])
        self.assertEqual(BASE, result["pr"]["base"]["sha"])
        self.assertEqual("d" * 40, result["pr"]["base"]["reported_sha"])
        self.assertEqual("d" * 40, self.api.pulls[1]["base"]["sha"])
        snapshot = self.host.snapshot(1)
        self.assertEqual(result["pr"], snapshot)

    def test_new_controller_assesses_old_pr_base_at_current_branch_tip(self):
        self.api.tip = "c" * 40
        self.assertEqual(BASE, self.api.pulls[1]["base"]["sha"])
        host = self.new_host(101, head=self.api.tip)
        result = host.start(1)
        self.assertTrue(result["eligible"])
        self.assertEqual(self.api.tip, result["publication"]["base_sha"])
        self.assertEqual(self.api.tip, result["pr"]["base"]["sha"])
        self.assertEqual(BASE, result["pr"]["base"]["reported_sha"])

    def test_snapshot_rejects_changed_controller_revision(self):
        self.api.tip = "c" * 40
        with self.assertRaisesRegex(ValueError, "policy advanced"):
            self.host.snapshot(1)
        self.assertEqual([], self.api.mutations)

    def test_stale_expected_head_or_base_does_not_acquire_or_modify_check(self):
        for expected_head, expected_base in (("c" * 40, BASE), (HEAD, "d" * 40)):
            with self.subTest(head=expected_head, base=expected_base):
                result = self.host.start(1, expected_head, expected_base)
                self.assertFalse(result["eligible"])
                self.assertEqual([], self.api.mutations)

    def test_changed_controller_cannot_acquire_current_candidate(self):
        self.api.tip = "c" * 40
        self.api.pulls[1]["base"]["sha"] = self.api.tip
        self.assertFalse(self.host.start(1)["eligible"])
        self.assertEqual([], self.api.mutations)

    def test_fork_closed_or_nondefault_pr_is_not_assessed(self):
        for variant in ("fork", "closed", "other-base"):
            with self.subTest(variant=variant):
                self.api.pulls[1] = FakeGitHub.pull()
                if variant == "fork":
                    self.api.pulls[1]["head"]["repo"]["full_name"] = "outside/project"
                elif variant == "closed":
                    self.api.pulls[1]["state"] = "closed"
                else:
                    self.api.pulls[1]["base"]["ref"] = "release"
                with self.assertRaisesRegex(ValueError, "same-repository PRs"):
                    self.host.start(1)
                self.assertEqual([], self.api.mutations)

    def test_invalid_expected_identity_and_untrusted_context_never_write(self):
        for arguments in ((HEAD, "", ""), (HEAD, BASE, "$(untrusted)"), ("not-a-sha", BASE, "")):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    self.host.start(1, *arguments)
        for key, value in (("ref", "refs/heads/candidate"), ("event_name", "pull_request"),
                           ("workflow_sha", "not-a-sha")):
            with self.subTest(context=key):
                with self.assertRaises(ValueError):
                    Host(self.api, {**self.context, key: value}).start(1)
        self.assertEqual([], self.api.mutations)

    def test_new_attempt_resets_previous_success_before_work_runs(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        retry = self.new_host(100, attempt=2)
        next_publication = self.start(retry)
        self.assertEqual(publication["check_id"], next_publication["check_id"])
        self.assertEqual("in_progress", self.check(publication)["status"])
        self.assertEqual(2, check_owner(self.check(publication))["a"])

    def test_old_run_cannot_acquire_or_finish_a_newer_runs_check(self):
        original = self.start()
        newer = self.new_host(101)
        current = self.start(newer)
        writes = len(self.api.mutations)
        self.assertFalse(self.host.start(1)["eligible"])
        self.assertFalse(self.host.publish(original, "/absent", "success")["published"])
        self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual(101, check_owner(self.check(current))["i"])

    def test_old_attempt_cannot_publish_after_rerun_owns_check(self):
        old = self.start()
        newer = self.new_host(100, attempt=2)
        current = self.start(newer)
        writes = len(self.api.mutations)
        with self.assertRaisesRegex(ValueError, "current run attempt"):
            self.host.publish(old, "/absent", "success")
        self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual(2, check_owner(self.check(current))["a"])

    def test_missing_result_and_failed_gate_close_owned_check_with_failure(self):
        for gate_result in ("success", "failure", "skipped", "cancelled"):
            with self.subTest(gate_result=gate_result):
                api = FakeGitHub()
                host = Host(api, self.context)
                publication = host.start(1)["publication"]
                result = host.publish(publication, "/no-such-sfstack-artifact", gate_result)
                self.assertTrue(result["published"])
                self.assertEqual("failure", result["conclusion"])
                self.assertEqual("completed", api.checks[publication["check_id"]]["status"])

    def test_missing_publication_can_only_fail_its_owned_pending_check(self):
        publication = self.start()
        result = self.host.publish(None, "/absent", "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertEqual("failure", self.check(publication)["conclusion"])

    def test_check_identity_must_match_app_name_head_and_owner_before_writing(self):
        for key, value in (("app", {"slug": "different-app"}), ("name", "different-check"),
                           ("head_sha", "f" * 40), ("external_id", owner_text(owner(2, BASE, "run", 100, 1, "")))):
            with self.subTest(key=key):
                api = FakeGitHub()
                host = Host(api, self.context)
                publication = host.start(1)["publication"]
                api.checks[publication["check_id"]][key] = value
                writes = len(api.mutations)
                self.assertFalse(host.publish(publication, "/absent", "success")["published"])
                self.assertEqual(writes, len(api.mutations))

    def test_duplicate_owned_checks_are_ambiguous_and_cannot_be_reused(self):
        publication = self.start()
        self.api.checks[999] = {**deepcopy(self.check(publication)), "id": 999}
        writes = len(self.api.mutations)
        with self.assertRaisesRegex(ValueError, "Multiple owned checks"):
            self.host.start(1)
        self.assertEqual(writes, len(self.api.mutations))

    def signal(self):
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        signal = self.api.add_run(90, SIGNAL, "pull_request", status="completed", head=HEAD)
        signal["head_branch"] = "candidate"
        signal["pull_requests"] = [{"number": 1}]
        event = {"action": "completed", "workflow_run": deepcopy(signal)}
        return coordinator, signal, event

    def test_signal_dispatches_default_branch_controller_with_pinned_metadata(self):
        coordinator, _, event = self.signal()
        self.assertEqual([1], coordinator.dispatch(event)["dispatched"])
        method, path, request = self.api.mutations[-1]
        self.assertEqual("POST", method)
        self.assertTrue(path.endswith("/" + QUALITY + "/dispatches"))
        self.assertEqual({"ref": "main", "inputs": {"pr-number": "1", "expected-head": HEAD,
                         "expected-base": BASE, "request-id": "200-1"}}, request)
        check = next(iter(self.api.checks.values()))
        self.assertEqual("queued", check["status"])
        self.assertEqual("request", check_owner(check)["k"])
        self.assertFalse(any("artifacts" in call[1] for call in self.api.calls))

    def test_empty_signal_pr_association_resolves_exact_current_branch_and_head(self):
        coordinator, signal, event = self.signal()
        signal["pull_requests"] = []
        self.assertEqual([1], coordinator.dispatch(event)["dispatched"])
        self.assertEqual("queued", next(iter(self.api.checks.values()))["status"])

    def test_empty_signal_association_never_guesses_ambiguous_or_stale_prs(self):
        for variant in ("ambiguous", "branch", "head"):
            with self.subTest(variant=variant):
                self.api = FakeGitHub()
                coordinator, signal, event = self.signal()
                signal["pull_requests"] = []
                if variant == "ambiguous":
                    self.api.pulls[2] = FakeGitHub.pull(2)
                elif variant == "branch":
                    signal["head_branch"] = "unrelated"
                else:
                    signal["head_sha"] = "f" * 40
                self.assertEqual([], coordinator.dispatch(event)["dispatched"])
                self.assertEqual([], self.api.mutations)

    def test_signal_provenance_cannot_be_spoofed_by_name_or_artifact(self):
        for key, value in (("workflow_id", 999), ("path", ".github/workflows/spoof.yml"),
                           ("event", "workflow_dispatch"), ("repository", {"full_name": "other/repo"}),
                           ("head_repository", {"full_name": "outside/fork"})):
            with self.subTest(key=key):
                self.api = FakeGitHub()
                coordinator, signal, event = self.signal()
                signal[key] = value
                with self.assertRaisesRegex(ValueError, "provenance"):
                    coordinator.dispatch(event)
                self.assertEqual([], self.api.mutations)

    def test_stale_signal_head_or_attempt_does_not_dispatch(self):
        for variant in ("head", "attempt", "ambiguous"):
            with self.subTest(variant=variant):
                self.api = FakeGitHub()
                coordinator, signal, event = self.signal()
                if variant == "head":
                    self.api.pulls[1]["head"]["sha"] = "c" * 40
                elif variant == "attempt":
                    signal["run_attempt"] = 2
                else:
                    signal["pull_requests"].append({"number": 2})
                self.assertEqual([], coordinator.dispatch(event)["dispatched"])
                self.assertEqual([], self.api.mutations)

    def test_dispatch_failure_leaves_a_failed_check(self):
        coordinator, _, event = self.signal()
        self.api.fail_dispatch = True
        with self.assertRaisesRegex(ValueError, "Dispatch unavailable"):
            coordinator.dispatch(event)
        check = next(iter(self.api.checks.values()))
        self.assertEqual("completed", check["status"])
        self.assertEqual("failure", check["conclusion"])

    def test_superseded_automatic_request_cannot_steal_the_check(self):
        coordinator, _, event = self.signal()
        coordinator.dispatch(event)
        delayed = self.new_host(201, title="sfstack quality / PR #1 / request 199-1")
        writes = len(self.api.mutations)
        self.assertFalse(delayed.start(1, HEAD, BASE, "199-1")["eligible"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_duplicate_signal_delivery_does_not_dispatch_again(self):
        coordinator, _, event = self.signal()
        coordinator.dispatch(event)
        writes = len(self.api.mutations)
        self.assertEqual([], coordinator.dispatch(event)["dispatched"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_base_push_requeues_current_same_repository_prs(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.tip = "c" * 40
        # GitHub can keep reporting the previous base SHA after main advances.
        self.api.pulls[2] = FakeGitHub.pull(2, head_repository="outside/fork", base=self.api.tip)
        coordinator = self.new_host(200, EVENTS, "push", head=self.api.tip)
        result = coordinator.dispatch({"ref": "refs/heads/main", "after": self.api.tip, "deleted": False})
        self.assertEqual([1], result["dispatched"])
        self.assertEqual("queued", self.check(publication)["status"])
        self.assertEqual(self.api.tip, check_owner(self.check(publication))["b"])
        writes = len(self.api.mutations)
        self.assertFalse(self.host.publish(publication, "/absent", "success")["published"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_cancelled_controller_reconciliation_only_fails_its_owned_check(self):
        publication = self.start()
        self.api.runs[100].update({"status": "completed", "conclusion": "cancelled"})
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        event = {"action": "completed", "workflow_run": deepcopy(self.api.runs[100])}
        result = coordinator.reconcile(event)
        self.assertEqual("failure", result["conclusion"])
        self.assertEqual("failure", self.check(publication)["conclusion"])
        self.assertIn("cancelled", self.check(publication)["output"]["summary"])

    def test_late_cancellation_cannot_close_newer_owner(self):
        publication = self.start()
        self.start(self.new_host(101))
        self.api.runs[100].update({"status": "completed", "conclusion": "cancelled"})
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        writes = len(self.api.mutations)
        event = {"action": "completed", "workflow_run": deepcopy(self.api.runs[100])}
        self.assertFalse(coordinator.reconcile(event)["published"])
        self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual(101, check_owner(self.check(publication))["i"])

    def test_rerun_lifecycle_invalidates_an_earlier_attempt_pass(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.runs[100]["run_attempt"] = 2
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        event = {"action": "in_progress", "workflow_run": deepcopy(self.api.runs[100])}
        result = coordinator.reconcile(event)
        self.assertEqual("pending", result["conclusion"])
        self.assertEqual("in_progress", self.check(publication)["status"])
        self.assertEqual(2, check_owner(self.check(publication))["a"])

    def test_old_completion_event_cannot_close_a_new_run_attempt(self):
        publication = self.start()
        old_event = {"action": "completed", "workflow_run": deepcopy(self.api.runs[100])}
        self.start(self.new_host(100, attempt=2))
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        writes = len(self.api.mutations)
        self.assertFalse(coordinator.reconcile(old_event)["published"])
        self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual(2, check_owner(self.check(publication))["a"])


class GitHubPublicationEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.summary = run_regression(self.directory / "regression")
        fixed = self.summary["cases"]["fixed"]
        self.result = self.directory / "regression/fixed/result"
        self.api = FakeGitHub()
        self.api.tip = fixed["base_sha"]
        self.api.pulls[1] = FakeGitHub.pull(head=fixed["head_sha"], base=fixed["base_sha"])
        self.api.add_run(9002, head=fixed["base_sha"])
        self.context = {"repository": REPOSITORY, "run_id": "9002", "run_attempt": "1",
                        "workflow_sha": fixed["base_sha"], "ref": "refs/heads/main", "event_name": "workflow_dispatch"}
        self.host = Host(self.api, self.context)
        self.publication = self.host.start(1)["publication"]
        self.api.artifacts = [{"id": 8001, "name": "sfstack-quality-1", "expired": False,
                               "workflow_run": {"id": 9002, "head_sha": fixed["base_sha"]}}]

    def mutate_json(self, relative, transform):
        path = self.result / relative
        value = json.loads(path.read_text())
        transform(value)
        path.write_text(json.dumps(value))

    def test_real_bridge_evidence_publishes_success_with_direct_artifact_link(self):
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("success", result["conclusion"])
        check = self.api.checks[self.publication["check_id"]]
        self.assertEqual("completed", check["status"])
        self.assertEqual("success", check["conclusion"])
        self.assertIn("actions/runs/9002/artifacts/8001", check["output"]["summary"])
        self.assertIn(self.publication["head_sha"], check["output"]["summary"])
        writes = len(self.api.mutations)
        self.assertFalse(self.host.publish(self.publication, self.result, "failure")["published"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_historical_pr_base_sha_does_not_invalidate_current_assessment(self):
        self.api.pulls[1]["base"]["sha"] = "d" * 40
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("success", result["conclusion"])
        self.assertEqual("success", self.api.checks[self.publication["check_id"]]["conclusion"])

    def test_failure_evidence_cannot_be_moved_to_a_passing_candidate(self):
        negative = self.directory / "regression/defective/result"
        result = self.host.publish(self.publication, negative, "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("another PR", result["reason"])

    def test_passing_artifact_cannot_override_a_failed_gate_job(self):
        result = self.host.publish(self.publication, self.result, "failure")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("trusted quality gate did not succeed", result["reason"])
        check = self.api.checks[self.publication["check_id"]]
        self.assertEqual("completed", check["status"])
        self.assertEqual("failure", check["conclusion"])
        self.assertIn("actions/runs/9002/artifacts/8001", check["output"]["summary"])

    def test_fresh_assessment_cannot_renew_expired_verification_evidence(self):
        assessment_path = self.result / "assessment/quality-assessment.json"
        original_assessment = assessment_path.read_bytes()
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        self.mutate_json("verification/verification-report.json", lambda value: value.update({"created_at": old}))
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("stale or future-dated", result["reason"])
        self.assertIn("verification/verification-report.json", result["reason"])
        self.assertEqual(original_assessment, assessment_path.read_bytes())

    def test_future_or_timezone_free_evidence_dates_cannot_pass_publication(self):
        for created in ((datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()):
            with self.subTest(created_at=created):
                self.mutate_json("verification/verification-report.json",
                                 lambda value: value.update({"created_at": created}))
                with self.assertRaisesRegex(ValueError, "stale or future-dated.*verification/verification-report.json"):
                    self.host.validate_result(self.publication, self.result)

    def test_run_attempt_from_another_result_is_rejected_before_success(self):
        self.mutate_json("target.json", lambda value: value.update({"run_attempt": "2"}))
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("another workflow run or attempt", result["reason"])

    def test_changed_target_bytes_are_rejected(self):
        self.mutate_json("target.json", lambda value: value.update({"scope": "modified after the quality gate"}))
        self.assertEqual("failure", self.host.publish(self.publication, self.result, "success")["conclusion"])

    def test_failed_source_report_cannot_be_hidden_in_a_green_gate(self):
        def fail_report(value):
            next(report for report in value["payload"]["reports"] if report["artifact_type"] == "verification-report")["status"] = "failed"
        self.mutate_json("assessment/quality-assessment.json", fail_report)
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("Both required source reports", result["reason"])

    def test_artifact_from_another_controller_or_expired_artifact_cannot_pass(self):
        original = deepcopy(self.api.artifacts)
        for variant in ("run", "controller", "expired", "duplicate", "missing"):
            with self.subTest(variant=variant):
                self.api.artifacts = deepcopy(original)
                if variant == "run":
                    self.api.artifacts[0]["workflow_run"]["id"] = 9999
                elif variant == "controller":
                    self.api.artifacts[0]["workflow_run"]["head_sha"] = "f" * 40
                elif variant == "expired":
                    self.api.artifacts[0]["expired"] = True
                elif variant == "duplicate":
                    self.api.artifacts.append(deepcopy(self.api.artifacts[0]))
                else:
                    self.api.artifacts = []
                with self.assertRaisesRegex(ValueError, "attributed"):
                    self.host.validate_result(self.publication, self.result)

    def test_base_or_head_movement_before_publication_blocks_current_success(self):
        # The branch ref, rather than the historical PR base.sha, advanced.
        self.api.tip = "f" * 40
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("advanced", result["reason"])

    def test_duplicate_json_keys_and_symlinked_result_are_rejected(self):
        gate = self.result / "quality-gate.json"
        original = gate.read_bytes()
        gate.write_bytes(b'{"status":"passed","status":"failed"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.host.validate_result(self.publication, self.result)
        gate.unlink()
        outside = self.directory / "outside.json"
        outside.write_bytes(original)
        gate.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.host.validate_result(self.publication, self.result)


if __name__ == "__main__":
    unittest.main()
