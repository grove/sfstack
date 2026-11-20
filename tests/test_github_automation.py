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
                                            Host, check_owner, owner, owner_text,
                                            pr_intent_digest)
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
        self.fail_check_creation = False
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
            if self.fail_check_creation:
                raise ValueError("Check creation unavailable")
            identifier = max(self.checks, default=500) + 1
            check = {"id": identifier, "app": {"slug": "github-actions"},
                     "conclusion": None, "completed_at": None, **deepcopy(body)}
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
        # Match the live API behavior that exposed the retry bug: an existing
        # conclusion keeps the check completed. PATCH status=in_progress alone
        # does not reopen it or clear its completion.
        if check.get("conclusion") is not None:
            check["status"] = "completed"
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
        self.assertEqual(owner(1, BASE, "run", 100, 1, "",
                               intent=pr_intent_digest(self.api.pulls[1])), check_owner(check))
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
        self.assertNotEqual(publication["check_id"], next_publication["check_id"])
        self.assertEqual("failure", self.check(publication)["conclusion"])
        self.assertEqual("in_progress", self.check(next_publication)["status"])
        self.assertIsNone(self.check(next_publication)["conclusion"])
        self.assertIsNone(self.check(next_publication)["completed_at"])
        self.assertEqual(2, check_owner(self.check(next_publication))["a"])
        self.assertEqual(2, check_owner(self.check(next_publication))["g"])

    def test_completed_attempt_cannot_restart_itself_or_clear_its_result(self):
        publication = self.start()
        self.host.publish(publication, "/absent", "failure")
        writes = len(self.api.mutations)
        self.assertFalse(self.host.start(1)["eligible"])
        self.assertEqual("failure", self.host.publish(publication, "/absent", "success")["conclusion"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_failed_fresh_check_creation_cannot_leave_an_old_success(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.fail_check_creation = True
        newer = self.new_host(101)
        with self.assertRaisesRegex(ValueError, "creation unavailable"):
            self.start(newer)
        self.assertEqual("completed", self.check(publication)["status"])
        self.assertEqual("failure", self.check(publication)["conclusion"])
        self.assertFalse(self.host.start(1)["eligible"])

    def test_legacy_v2_check_migrates_to_a_new_generation(self):
        publication = self.start()
        legacy = check_owner(self.check(publication))
        legacy["v"] = 2
        legacy.pop("g")
        legacy.pop("t", None)
        self.check(publication).update({"external_id": owner_text(legacy),
                                        "status": "completed", "conclusion": "success"})
        current = self.start(self.new_host(101))
        self.assertEqual(1, check_owner(self.check(current))["g"])
        self.assertEqual("failure", self.check(publication)["conclusion"])
        self.assertEqual(current["check_id"], self.host.find_check(self.api.pulls[1])["id"])

    def test_completed_at_and_response_order_cannot_choose_an_old_generation(self):
        old = self.start()
        current = self.start(self.new_host(101))
        self.check(old)["completed_at"] = "2099-01-01T00:00:00Z"
        self.api.checks = dict(reversed(list(self.api.checks.items())))
        self.assertEqual(current["check_id"], self.host.find_check(self.api.pulls[1])["id"])
        writes = len(self.api.mutations)
        self.assertFalse(self.host.publish(old, "/absent", "success")["published"])
        self.assertEqual(writes, len(self.api.mutations))

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

    def test_queued_request_hands_its_pending_generation_to_the_correct_run(self):
        coordinator, _, event = self.signal()
        coordinator.dispatch(event)
        queued = coordinator.find_check(self.api.pulls[1])
        controller = self.new_host(201, title="sfstack quality / PR #1 / request 200-1")
        started = controller.start(1, HEAD, BASE, "200-1")
        self.assertTrue(started["eligible"])
        self.assertEqual(queued["id"], started["check_id"])
        self.assertEqual(1, check_owner(self.check(started["publication"]))["g"])
        self.assertEqual("in_progress", self.check(started["publication"])["status"])

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

    def test_lifecycle_workflow_routes_by_path_instead_of_custom_run_name(self):
        workflow = (ROOT / ".github/workflows/sfstack-quality-events.yml").read_text()
        self.assertNotIn("github.event.workflow_run.name", workflow)
        for path in (QUALITY, SIGNAL):
            self.assertIn("github.event.workflow_run.path == '.github/workflows/" + path + "'", workflow)
        publication = self.start()
        self.api.runs[100].update({"name": "sfstack quality / PR #1 / request manual",
                                  "status": "completed", "conclusion": "cancelled"})
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        result = coordinator.reconcile({"action": "completed", "workflow_run": deepcopy(self.api.runs[100])})
        self.assertEqual("failure", result["conclusion"])
        self.assertEqual("failure", self.check(publication)["conclusion"])

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

    def passing_auto_check(self):
        """Exercise coordinator -> controller handoff before reporting success."""
        coordinator, signal, event = self.signal()
        self.assertEqual([1], coordinator.dispatch(event)["dispatched"])
        controller = self.new_host(201, title="sfstack quality / PR #1 / request 200-1")
        prepared = controller.start(1, HEAD, BASE, "200-1")
        self.assertTrue(prepared["eligible"])
        current = self.check(prepared["publication"])
        self.assertEqual(pr_intent_digest(self.api.pulls[1]), check_owner(current)["t"])
        current.update({"status": "completed", "conclusion": "success"})
        return current, event

    def test_ready_for_review_does_not_repeat_completed_identical_pass(self):
        """PR #21 regression: one more signal must not invalidate green CI."""
        current, event = self.passing_auto_check()
        next_coordinator = self.new_host(202, EVENTS, "workflow_run")
        changes = len(self.api.mutations)
        self.assertEqual([], next_coordinator.dispatch(event)["dispatched"])
        self.assertEqual(changes, len(self.api.mutations))
        self.assertEqual("success", current["conclusion"])
        self.assertEqual(current["id"], next_coordinator.find_check(self.api.pulls[1])["id"])
        self.assertFalse(any(path.endswith("/dispatches")
                             for _, path, _ in self.api.mutations[changes:]))

    def test_changed_title_or_body_forces_reassessment_on_unchanged_sha(self):
        for field in ("title", "body"):
            with self.subTest(field=field):
                self.api = FakeGitHub()
                previous, event = self.passing_auto_check()
                old_id = previous["id"]
                self.api.pulls[1][field] = "Updated acceptance intent" if field == "body" else "Updated review title"
                coordinator = self.new_host(202, EVENTS, "workflow_run")
                self.assertEqual([1], coordinator.dispatch(event)["dispatched"])
                current = coordinator.find_check(self.api.pulls[1])
                self.assertNotEqual(old_id, current["id"])
                self.assertEqual("failure", previous["conclusion"])
                self.assertEqual("queued", current["status"])
                self.assertEqual(pr_intent_digest(self.api.pulls[1]), check_owner(current)["t"])

    def test_no_dedupe_for_missing_digest_failed_or_unfinished_check(self):
        for variant in ("legacy", "failed", "in_progress"):
            with self.subTest(variant=variant):
                self.api = FakeGitHub()
                previous, event = self.passing_auto_check()
                if variant == "legacy":
                    older = check_owner(previous)
                    older.pop("t")
                    previous["external_id"] = owner_text(older)
                else:
                    previous["status"] = "completed" if variant == "failed" else "in_progress"
                    previous["conclusion"] = "failure" if variant == "failed" else None
                coordinator = self.new_host(202, EVENTS, "workflow_run")
                self.assertEqual([1], coordinator.dispatch(event)["dispatched"])
                current = coordinator.find_check(self.api.pulls[1])
                self.assertEqual("queued", current["status"])
                self.assertEqual("failure", previous["conclusion"])

    def test_new_head_or_base_cannot_reuse_success(self):
        for field in ("head", "base"):
            with self.subTest(field=field):
                self.api = FakeGitHub()
                old, event = self.passing_auto_check()
                coordinator = self.new_host(202, EVENTS, "workflow_run")
                if field == "head":
                    updated = "c" * 40
                    self.api.pulls[1]["head"]["sha"] = updated
                    run = self.api.add_run(92, SIGNAL, "pull_request", status="completed", head=updated)
                    run["head_branch"] = "candidate"
                    run["pull_requests"] = [{"number": 1}]
                    event = {"action": "completed", "workflow_run": deepcopy(run)}
                else:
                    self.api.tip = "d" * 40
                    coordinator = self.new_host(202, EVENTS, "workflow_run", head=self.api.tip)
                self.assertEqual([1] if field == "head" else [1],
                                 coordinator.dispatch(event)["dispatched"])
                newest = coordinator.find_check(self.api.pulls[1])
                self.assertNotEqual(old["id"], newest["id"])
                self.assertEqual("queued", newest["status"])

    def test_manual_reassessment_of_unchanged_pass_is_still_allowed(self):
        publication = self.start()
        original = self.check(publication)
        original.update({"status": "completed", "conclusion": "success"})
        manual = self.new_host(101)
        next_publication = manual.start(1)["publication"]
        self.assertNotEqual(original["id"], next_publication["check_id"])
        self.assertEqual("failure", original["conclusion"])
        self.assertEqual("in_progress", self.check(next_publication)["status"])

    def test_malformed_intent_fingerprint_cannot_be_trusted_for_deduplication(self):
        for bad in ("1" * 63, "bad", None, {"untrusted": True}):
            with self.subTest(fingerprint=bad):
                self.api = FakeGitHub()
                previous, event = self.passing_auto_check()
                value = check_owner(previous)
                if bad is None:
                    value.pop("t")
                else:
                    value["t"] = bad
                previous["external_id"] = owner_text(value)
                if bad is not None:
                    self.assertIsNone(check_owner(previous))
                    # A malformed check cannot be treated as a successful pass;
                    # ignore it without editing or invalidating its result.
                    coordinator = self.new_host(202, EVENTS, "workflow_run")
                    writes = len(self.api.mutations)
                    self.assertEqual([1], coordinator.dispatch(event)["dispatched"])
                    self.assertEqual("success", previous["conclusion"])
                    self.assertEqual("queued", coordinator.find_check(self.api.pulls[1])["status"])
                    self.assertGreater(len(self.api.mutations), writes)
                else:
                    self.assertNotIn("t", check_owner(previous))
                    coordinator = self.new_host(202, EVENTS, "workflow_run")
                    self.assertEqual([1], coordinator.dispatch(event)["dispatched"])

    def test_base_push_invalidates_success_without_dispatching_expensive_review(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.tip = "c" * 40
        # GitHub may keep returning the original PR base SHA after main moves.
        self.api.pulls[2] = FakeGitHub.pull(2, head_repository="outside/fork", base=self.api.tip)
        coordinator = self.new_host(200, EVENTS, "push", head=self.api.tip)
        result = coordinator.invalidate({"ref": "refs/heads/main", "after": self.api.tip, "deleted": False})
        self.assertEqual({"dispatched": [], "invalidated": [1]}, result)
        current = coordinator.find_check(self.api.pulls[1])
        self.assertNotEqual(publication["check_id"], current["id"])
        self.assertEqual("failure", self.check(publication)["conclusion"])
        self.assertEqual("completed", current["status"])
        self.assertEqual("failure", current["conclusion"])
        self.assertIn("revalidation required", current["output"]["title"])
        self.assertIn("No AI review", current["output"]["summary"])
        self.assertEqual("stale", check_owner(current)["k"])
        self.assertEqual(self.api.tip, check_owner(current)["b"])
        self.assertFalse(any(path.endswith("/dispatches") for _, path, _ in self.api.mutations))
        writes = len(self.api.mutations)
        self.assertFalse(self.host.publish(publication, "/absent", "success")["published"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_push_without_previous_owned_check_cannot_start_review(self):
        self.api.tip = "c" * 40
        coordinator = self.new_host(200, EVENTS, "push", head=self.api.tip)
        result = coordinator.invalidate({"ref": "refs/heads/main", "after": self.api.tip})
        self.assertEqual([], result["dispatched"])
        self.assertEqual([], result["invalidated"])
        self.assertEqual([], self.api.mutations)

    def test_repeated_base_pushes_do_not_write_checks_or_start_reviews_when_already_negative(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.tip = "c" * 40
        first = self.new_host(200, EVENTS, "push", head=self.api.tip)
        self.assertEqual([1], first.invalidate({"ref": "refs/heads/main", "after": self.api.tip})["invalidated"])
        last = first.find_check(self.api.pulls[1])
        self.api.tip = "d" * 40
        repeated = self.new_host(201, EVENTS, "push", head=self.api.tip)
        writes = len(self.api.mutations)
        result = repeated.invalidate({"ref": "refs/heads/main", "after": self.api.tip})
        self.assertEqual([], result["invalidated"])
        self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual(last["id"], repeated.find_check(self.api.pulls[1])["id"])
        self.assertEqual("failure", last["conclusion"])

    def test_failed_previous_check_stays_failed_without_unnecessary_push_writes(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "failure"})
        self.api.tip = "c" * 40
        coordinator = self.new_host(200, EVENTS, "push", head=self.api.tip)
        writes = len(self.api.mutations)
        self.assertEqual([], coordinator.invalidate({"ref": "refs/heads/main", "after": self.api.tip})["invalidated"])
        self.assertEqual(writes, len(self.api.mutations))
        # A selected manual assessment can still start for the new base.
        manual = self.new_host(201, head=self.api.tip)
        current = manual.start(1)["publication"]
        self.assertEqual(self.api.tip, current["base_sha"])
        self.assertEqual("in_progress", self.check(current)["status"])

    def test_inflight_old_base_review_is_invalidated_and_cannot_publish(self):
        publication = self.start()
        self.api.tip = "c" * 40
        coordinator = self.new_host(200, EVENTS, "push", head=self.api.tip)
        self.assertEqual([1], coordinator.invalidate({"ref": "refs/heads/main", "after": self.api.tip})["invalidated"])
        self.assertEqual("failure", self.check(publication)["conclusion"])
        latest = coordinator.find_check(self.api.pulls[1])
        self.assertEqual("stale", check_owner(latest)["k"])
        writes = len(self.api.mutations)
        self.assertFalse(self.host.publish(publication, "/absent", "success")["published"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_stale_or_deleted_push_and_old_controller_cannot_invalidate_checks(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.tip = "c" * 40
        old = self.new_host(200, EVENTS, "push", head=BASE)
        current = self.new_host(201, EVENTS, "push", head=self.api.tip)
        cases = [
            (old, {"ref": "refs/heads/main", "after": self.api.tip}),
            (current, {"ref": "refs/heads/release", "after": self.api.tip}),
            (current, {"ref": "refs/heads/main", "after": BASE}),
            (current, {"ref": "refs/heads/main", "after": self.api.tip, "deleted": True}),
        ]
        for host, event in cases:
            with self.subTest(event=event):
                writes = len(self.api.mutations)
                self.assertEqual([], host.invalidate(event)["invalidated"])
                self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual("success", self.check(publication)["conclusion"])

    def test_push_cannot_invoke_action_dispatch_path(self):
        self.api.tip = "c" * 40
        coordinator = self.new_host(200, EVENTS, "push", head=self.api.tip)
        with self.assertRaises(ValueError):
            coordinator.dispatch({"ref": "refs/heads/main", "after": self.api.tip})
        self.assertEqual([], self.api.mutations)

    def test_many_open_prs_are_invalidated_once_not_n_squared_ai_reviews(self):
        self.api.pulls = {}
        for number in range(1, 6):
            head = format(number + 9, "x") * 40
            self.api.pulls[number] = FakeGitHub.pull(number, head=head)
            self.api.checks[500 + number] = {
                "id": 500 + number, "app": {"slug": "github-actions"},
                "name": CHECK_NAME, "head_sha": head, "external_id": owner_text(
                    owner(number, BASE, "run", 100, 1, "")),
                "status": "completed", "conclusion": "success",
                "output": {"title": "Earlier quality approval", "summary": "Passed on previous base"},
            }
        self.api.tip = "c" * 40
        host = self.new_host(200, EVENTS, "push", head=self.api.tip)
        result = host.invalidate({"ref": "refs/heads/main", "after": self.api.tip})
        self.assertEqual([1, 2, 3, 4, 5], result["invalidated"])
        self.assertEqual([], result["dispatched"])
        self.assertEqual(5, sum(method == "POST" for method, _, _ in self.api.mutations))
        self.assertFalse(any(path.endswith("/dispatches") for _, path, _ in self.api.mutations))
        self.assertTrue(all(host.find_check(self.api.pulls[n])["conclusion"] == "failure"
                            for n in range(1, 6)))
        self.api.tip = "d" * 40
        next_host = self.new_host(201, EVENTS, "push", head=self.api.tip)
        writes = len(self.api.mutations)
        result = next_host.invalidate({"ref": "refs/heads/main", "after": self.api.tip})
        self.assertEqual([], result["invalidated"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_pr_signal_still_dispatches_after_stale_base_invalidation(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.tip = "c" * 40
        invalidator = self.new_host(200, EVENTS, "push", head=self.api.tip)
        invalidator.invalidate({"ref": "refs/heads/main", "after": self.api.tip})
        coordinator = self.new_host(201, EVENTS, "workflow_run", head=self.api.tip)
        signal = self.api.add_run(90, SIGNAL, "pull_request", status="completed", head=HEAD)
        signal["head_branch"] = "candidate"
        signal["pull_requests"] = [{"number": 1}]
        self.assertEqual([1], coordinator.dispatch({
            "action": "completed", "workflow_run": deepcopy(signal)})["dispatched"])
        check = coordinator.find_check(self.api.pulls[1])
        self.assertEqual("queued", check["status"])
        self.assertEqual("request", check_owner(check)["k"])
        self.assertEqual(self.api.tip, check_owner(check)["b"])

    def test_base_push_and_pr_signal_are_isolated_by_actions_permission(self):
        workflow = (ROOT / ".github/workflows/sfstack-quality-events.yml").read_text()
        push = workflow[workflow.index("  invalidate:"):workflow.index("  reconcile:")]
        signal = workflow[workflow.index("  dispatch:"):workflow.index("  invalidate:")]
        self.assertIn("github.event_name == 'push'", push)
        self.assertIn("automation.py invalidate", push)
        self.assertIn("actions: read", push)
        self.assertNotIn("actions: write", push)
        self.assertIn("github.event_name == 'workflow_run'", signal)
        self.assertIn("automation.py dispatch", signal)
        self.assertIn("actions: write", signal)

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
        current = self.start(self.new_host(101))
        self.api.runs[100].update({"status": "completed", "conclusion": "cancelled"})
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        writes = len(self.api.mutations)
        event = {"action": "completed", "workflow_run": deepcopy(self.api.runs[100])}
        self.assertFalse(coordinator.reconcile(event)["published"])
        self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual(101, check_owner(self.check(current))["i"])
        self.assertEqual(100, check_owner(self.check(publication))["i"])

    def test_rerun_lifecycle_invalidates_an_earlier_attempt_pass(self):
        publication = self.start()
        self.check(publication).update({"status": "completed", "conclusion": "success"})
        self.api.runs[100]["run_attempt"] = 2
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        event = {"action": "in_progress", "workflow_run": deepcopy(self.api.runs[100])}
        result = coordinator.reconcile(event)
        self.assertEqual("pending", result["conclusion"])
        current = self.api.checks[result["check_id"]]
        self.assertNotEqual(publication["check_id"], current["id"])
        self.assertEqual("failure", self.check(publication)["conclusion"])
        self.assertEqual("in_progress", current["status"])
        self.assertEqual(2, check_owner(current)["a"])

    def test_old_completion_event_cannot_close_a_new_run_attempt(self):
        publication = self.start()
        old_event = {"action": "completed", "workflow_run": deepcopy(self.api.runs[100])}
        current = self.start(self.new_host(100, attempt=2))
        coordinator = self.new_host(200, EVENTS, "workflow_run")
        writes = len(self.api.mutations)
        self.assertFalse(coordinator.reconcile(old_event)["published"])
        self.assertEqual(writes, len(self.api.mutations))
        self.assertEqual(2, check_owner(self.check(current))["a"])


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
        assessed_pr = json.loads((self.directory / "regression/fixed/pr.json").read_text())
        self.api.pulls[1].update({key: assessed_pr[key] for key in ("title", "body")})
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

    def test_fresh_run_publishes_pass_after_an_earlier_completed_failure(self):
        # Reproduce the live defect: same PR head, an old completed failure,
        # then a new all-green controller with retained real bridge evidence.
        self.api.checks.clear()
        self.api.add_run(9001, head=self.api.tip)
        earlier = Host(self.api, {**self.context, "run_id": "9001"})
        old = earlier.start(1)["publication"]
        self.assertEqual("failure", earlier.publish(old, "/absent", "failure")["conclusion"])
        current = self.host.start(1)["publication"]
        self.assertNotEqual(old["check_id"], current["check_id"])
        self.assertEqual("in_progress", self.api.checks[current["check_id"]]["status"])
        self.assertIsNone(self.api.checks[current["check_id"]]["conclusion"])
        self.assertEqual("success", self.host.publish(current, self.result, "success")["conclusion"])
        self.assertEqual("success", self.api.checks[current["check_id"]]["conclusion"])
        writes = len(self.api.mutations)
        self.assertFalse(earlier.publish(old, self.result, "success")["published"])
        self.assertEqual(writes, len(self.api.mutations))

    def test_historical_pr_base_sha_does_not_invalidate_current_assessment(self):
        self.api.pulls[1]["base"]["sha"] = "d" * 40
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("success", result["conclusion"])
        self.assertEqual("success", self.api.checks[self.publication["check_id"]]["conclusion"])

    def test_changed_pr_title_during_publication_queue_blocks_otherwise_passing_evidence(self):
        self.api.pulls[1]["title"] = "Implement different behavior after review"
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("title or acceptance description changed", result["reason"])

    def test_changed_acceptance_description_during_publication_queue_blocks_old_review(self):
        self.api.pulls[1]["body"] += "\nNew required behavior was added after the quality gate completed."
        result = self.host.publish(self.publication, self.result, "success")
        self.assertEqual("failure", result["conclusion"])
        self.assertIn("title or acceptance description changed", result["reason"])

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
