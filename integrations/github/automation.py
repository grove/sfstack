#!/usr/bin/env python3
"""Trusted GitHub event routing and PR-head check publication.

Run only from the default-branch controller in a fresh job, with all check
writers sharing the workflow's queue:max concurrency group. Candidate code and
agent output never execute here. This host uses only the Python standard library.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

CHECK_NAME = "sfstack quality"
QUALITY = "sfstack-quality.yml"
SIGNAL = "sfstack-pr-signal.yml"
EVENTS = "sfstack-quality-events.yml"
SHA = re.compile(r"[a-f0-9]{40}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
REQUEST_ID = re.compile(r"[1-9][0-9]*-[1-9][0-9]*\Z")
RUN_TITLE = re.compile(r"sfstack quality / PR #([1-9][0-9]*) / request (manual|[1-9][0-9]*-[1-9][0-9]*)\Z")
MAX_JSON = 2 * 1024 * 1024


def positive(value):
    return type(value) is int and value > 0


def strict_json(raw):
    if len(raw) > MAX_JSON:
        raise ValueError("JSON exceeds the host's size limit.")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key.")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique)


def read_json(path, root=None):
    path = Path(path)
    if root is not None and not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("Result file escapes its artifact directory.")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JSON:
        raise ValueError("Expected a bounded regular JSON file.")
    raw = path.read_bytes()
    return strict_json(raw), raw


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The JSON API does not require redirects. Never forward a job token to
        # a URL supplied by an API response, artifact, or candidate.
        return None


class GitHubAPI:
    def __init__(self, token):
        if not token:
            raise ValueError("A job-scoped GitHub token is required.")
        self.token = token
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, body=None):
        if not path.startswith("repos/") or "://" in path or ".." in path.split("/"):
            raise ValueError("Only repository-relative GitHub API paths are allowed.")
        request = Request("https://api.github.com/" + path, method=method,
                          data=None if body is None else json.dumps(body).encode(),
                          headers={"Authorization": "Bearer " + self.token,
                                   "Accept": "application/vnd.github+json",
                                   "Content-Type": "application/json",
                                   "X-GitHub-Api-Version": "2022-11-28",
                                   "User-Agent": "sfstack-quality-host"})
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(MAX_JSON + 1)
        except HTTPError as exc:
            # Do not echo request headers or remote response bodies into logs.
            raise ValueError(f"GitHub API {method} failed with HTTP {exc.code}.") from exc
        return strict_json(raw) if raw else None

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body):
        return self.request("POST", path, body)

    def patch(self, path, body):
        return self.request("PATCH", path, body)


def owner(pr, base, kind, identifier, attempt, request_id, generation=1):
    return {"v": 3, "g": generation, "p": pr, "b": base, "k": kind, "i": identifier,
            "a": attempt, "q": request_id or "manual"}


def owner_text(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def check_owner(check):
    if check.get("name") != CHECK_NAME or check.get("app", {}).get("slug") != "github-actions":
        return None
    try:
        value = strict_json(check.get("external_id", ""))
        fields = {"v", "p", "b", "k", "i", "a", "q"}
        if (not isinstance(value, dict) or not ((value.get("v") == 2 and set(value) == fields)
                 or (value.get("v") == 3 and set(value) == fields | {"g"} and positive(value["g"])))
                or not all(positive(value[key]) for key in ("p", "i", "a"))
                or value["k"] not in {"request", "run", "stale"} or not SHA.fullmatch(value["b"])
                or not (value["q"] == "manual" or REQUEST_ID.fullmatch(value["q"]))):
            return None
        return value
    except (ValueError, TypeError, KeyError):
        return None


class Host:
    """API-injected host; callers serialize mutations with the shared job lock."""

    def __init__(self, api, context):
        self.api, self.context = api, context
        self.repository = context["repository"]
        if not REPOSITORY.fullmatch(self.repository):
            raise ValueError("Invalid repository context.")
        self.prefix = "repos/" + self.repository
        self.run_id, self.attempt = int(context["run_id"]), int(context["run_attempt"])
        if not positive(self.run_id) or not positive(self.attempt):
            raise ValueError("Invalid Actions run identity.")

    def path(self, suffix):
        return self.prefix + "/" + suffix

    def pages(self, suffix, key=None):
        result = []
        separator = "&" if "?" in suffix else "?"
        for page in range(1, 101):
            response = self.api.get(self.path(f"{suffix}{separator}per_page=100&page={page}"))
            items = response[key] if key else response
            if not isinstance(items, list):
                raise ValueError("Invalid paginated GitHub response.")
            result.extend(items)
            if len(items) < 100:
                return result
        raise ValueError("GitHub pagination limit reached; refusing a partial result.")

    def repo(self):
        repository = self.api.get(self.prefix)
        if repository.get("full_name", "").lower() != self.repository.lower():
            raise ValueError("GitHub repository identity changed.")
        return repository

    def validate_run(self, run, workflow, events, default_branch=None):
        expected = self.api.get(self.path("actions/workflows/" + workflow))
        if (run.get("workflow_id") != expected.get("id")
                or expected.get("path") != ".github/workflows/" + workflow
                or run.get("path") != expected["path"]
                or run.get("event") not in events
                or run.get("repository", {}).get("full_name", "").lower() != self.repository.lower()
                or run.get("head_repository", {}).get("full_name", "").lower() != self.repository.lower()
                or (default_branch and run.get("head_branch") != default_branch)):
            raise ValueError("Workflow provenance does not match the trusted integration.")
        return run

    def trusted_context(self, workflow, events):
        repository = self.repo()
        branch = repository["default_branch"]
        if (self.context.get("ref") != "refs/heads/" + branch
                or self.context.get("event_name") not in events
                or not SHA.fullmatch(self.context.get("workflow_sha", ""))):
            raise ValueError("Run the host from the trusted default branch.")
        run = self.api.get(self.path(f"actions/runs/{self.run_id}"))
        self.validate_run(run, workflow, events, branch)
        if (run.get("id") != self.run_id or run.get("run_attempt") != self.attempt
                or run.get("head_sha") != self.context["workflow_sha"]):
            raise ValueError("Actions context does not match the current run attempt.")
        return repository, run

    def default_sha(self, branch):
        value = self.api.get(self.path("git/ref/heads/" + quote(branch, safe="")))
        sha = value["object"]["sha"]
        if not SHA.fullmatch(sha):
            raise ValueError("Invalid default-branch revision.")
        return sha

    def pr(self, number, default_branch):
        if not positive(number):
            raise ValueError("Expected a positive PR number.")
        pr = self.api.get(self.path(f"pulls/{number}"))
        if (pr.get("number") != number or pr.get("state") != "open"
                or pr.get("base", {}).get("ref") != default_branch
                or pr.get("base", {}).get("repo", {}).get("full_name", "").lower() != self.repository.lower()
                or pr.get("head", {}).get("repo", {}).get("full_name", "").lower() != self.repository.lower()
                or not SHA.fullmatch(pr.get("head", {}).get("sha", ""))
                or not SHA.fullmatch(pr.get("base", {}).get("sha", ""))):
            raise ValueError("Only open same-repository PRs targeting the default branch are eligible.")
        return pr

    @staticmethod
    def with_current_base(pr, branch_tip):
        """Pin the live default-branch ref, not GitHub's historical PR base.sha."""
        selected = deepcopy(pr)
        selected["base"]["reported_sha"] = pr["base"]["sha"]
        selected["base"]["sha"] = branch_tip
        return selected

    def find_check(self, pr):
        checks = self.pages("commits/" + pr["head"]["sha"] + "/check-runs?"
                            + urlencode({"check_name": CHECK_NAME, "filter": "all"}), "check_runs")
        matches = [check for check in checks
                   if (check_owner(check) or {}).get("p") == pr["number"]
                   and check.get("head_sha") == pr["head"]["sha"]]
        if not matches:
            return None
        # GitHub's `latest` filter uses completed_at, not our assessment order.
        # Keep historical checks and select the explicit host-owned generation.
        # Existing v2 checks precede the first v3 generation.
        generations = [check_owner(check).get("g", 0) for check in matches]
        if len(generations) != len(set(generations)):
            raise ValueError("Multiple owned checks claim one generation; refusing an ambiguous update.")
        return max(matches, key=lambda check: check_owner(check).get("g", 0))

    def update_check(self, pr, check, identity, status, title, summary, conclusion=None, details_url=None):
        body = {"name": CHECK_NAME, "external_id": owner_text(identity), "status": status,
                "details_url": details_url or f"https://github.com/{self.repository}/actions/runs/{self.run_id}",
                "output": {"title": title, "summary": summary}}
        if conclusion:
            body["conclusion"] = conclusion
            body["completed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if check is None:
            body["head_sha"] = pr["head"]["sha"]
            updated = self.api.post(self.path("check-runs"), body)
        else:
            updated = self.api.patch(self.path(f"check-runs/{check['id']}"), body)
        if (updated.get("status") != status or check_owner(updated) != identity
                or (conclusion and updated.get("conclusion") != conclusion)):
            raise ValueError("GitHub did not accept the requested check state.")
        return updated

    def replace_check(self, pr, previous, identity, status, title, summary, conclusion=None, details_url=None):
        """Invalidate old clearance before creating a fresh assessment check.

        PATCHing a completed check to in_progress can retain its conclusion and
        completed status. A new generation must use POST instead. Retire the old
        result first so even an interrupted creation cannot leave stale success
        available to GitHub's latest-completion selection. Old publishers are
        fenced by generation and never update this historical completion again.
        """
        if previous is not None:
            self.update_check(pr, previous, check_owner(previous), "completed", "Quality assessment superseded",
                              "A newer assessment requires fresh evidence. This result no longer grants quality clearance.\n\n"
                              + previous.get("output", {}).get("summary", "")[:60000], "failure",
                              previous.get("details_url"))
        return self.update_check(pr, None, identity, status, title, summary, conclusion, details_url)

    def invalidate(self, event):
        """Revoke old-base clearance on a push, without any Actions dispatch.

        This code only runs with read/checks permissions. No candidate runs or
        agent review can start here. Missing or already-negative quality checks
        cannot grant clearance; GitHub must separately require sfstack quality.
        """
        repository, _ = self.trusted_context(EVENTS, {"push"})
        branch = repository["default_branch"]
        tip = self.default_sha(branch)
        if tip != self.context["workflow_sha"]:
            return {"invalidated": [], "reason": "A newer controller policy owns the current base."}
        if (event.get("ref") != "refs/heads/" + branch or event.get("deleted")
                or event.get("after") != tip):
            return {"invalidated": [], "reason": "Stale or nondefault branch push."}
        candidates = self.pages("pulls?" + urlencode({"state": "open", "base": branch}))
        invalidated = []
        for candidate in candidates:
            # The trusted integration does not assess fork PRs.
            if candidate.get("head", {}).get("repo", {}).get("full_name", "").lower() != self.repository.lower():
                continue
            pr = self.pr(candidate["number"], branch)
            check = self.find_check(pr)
            if check is None:
                # No owned clearance to revoke. The required check must block.
                continue
            previous = check_owner(check)
            if previous["b"] == tip:
                continue
            if check.get("status") == "completed" and check.get("conclusion") != "success":
                # Already negative: repeated base pushes need no check writes.
                continue
            identity = owner(pr["number"], tip, "stale", self.run_id, self.attempt,
                             "manual", previous.get("g", 0) + 1)
            self.replace_check(
                pr, check, identity, "completed", "Base changed - quality revalidation required",
                f"PR #{pr['number']} head {pr['head']['sha']} was previously assessed "
                f"against base {previous['b']}. Current base is {tip}.\n\n"
                "The previous quality result no longer grants clearance. "
                "No AI review or candidate code was run on this base push.\n\n"
                "Before merging, explicitly dispatch sfstack GitHub quality "
                "from the default branch for this PR, and require the new "
                "quality check, ordinary CI, and independent human approval.",
                "failure",
            )
            invalidated.append(pr["number"])
        return {"invalidated": invalidated, "dispatched": []}

    def dispatch(self, event):
        repository, _ = self.trusted_context(EVENTS, {"workflow_run"})
        branch = repository["default_branch"]
        tip = self.default_sha(branch)
        if tip != self.context["workflow_sha"]:
            return {"dispatched": [], "reason": "Controller policy advanced; a newer event owns reassessment."}
        trigger = event.get("workflow_run", {})

        if event.get("action") != "completed" or not positive(trigger.get("id")):
            return {"dispatched": [], "reason": "Not a completed PR signal."}
        source = self.api.get(self.path(f"actions/runs/{trigger['id']}"))
        self.validate_run(source, SIGNAL, {"pull_request"})
        if (source.get("status") != "completed" or source.get("run_attempt") != trigger.get("run_attempt")
                or source.get("head_sha") != trigger.get("head_sha")):
            return {"dispatched": [], "reason": "Stale signal attempt."}
        associated = source.get("pull_requests", [])
        if not isinstance(associated, list):
            return {"dispatched": [], "reason": "Malformed PR signal associations."}
        if len(associated) == 1:
            numbers = [associated[0].get("number")]
        elif not associated:
            # GitHub can return an empty pull_requests array for an actual
            # pull_request workflow run. Reconcile against current API PRs;
            # the authenticated signal's exact head and branch must match
            # one and only one eligible same-repository PR.
            candidates = self.pages("pulls?" + urlencode({"state": "open", "base": branch}))
            numbers = [candidate["number"] for candidate in candidates
                       if candidate.get("head", {}).get("sha") == source.get("head_sha")
                       and candidate.get("head", {}).get("ref") == source.get("head_branch")
                       and candidate.get("head", {}).get("repo", {}).get("full_name", "").lower() == self.repository.lower()]
        else:
            return {"dispatched": [], "reason": "Ambiguous PR signal associations."}
        if len(numbers) != 1 or not positive(numbers[0]):
            return {"dispatched": [], "reason": "PR signal cannot identify one current PR."}
        pr = self.pr(numbers[0], branch)
        if (pr["head"]["sha"] != source.get("head_sha")
                or pr["head"].get("ref") != source.get("head_branch")):
            return {"dispatched": [], "reason": "PR advanced after the signal."}
        numbers = [pr["number"]]
        dispatched = []
        request_id = f"{self.run_id}-{self.attempt}"
        for number in numbers:
            pr = self.pr(number, branch)
            # A PR's base.sha may remain at the commit when it was opened.
            # The live default-branch ref is the authoritative assessment base.
            check = self.find_check(pr)
            previous = check_owner(check) if check else None
            if previous and previous["b"] == tip and (previous["i"], previous["a"]) >= (self.run_id, self.attempt):
                continue
            identity = owner(number, tip, "request", self.run_id, self.attempt, request_id,
                             (previous or {}).get("g", 0) + 1)
            check = self.replace_check(pr, check, identity, "queued", "Quality assessment queued",
                                      f"PR #{number} at `{pr['head']['sha']}` will be assessed against base `{tip}`.\n\n"
                                      "The previous result cannot approve this request.")
            try:
                self.api.post(self.path("actions/workflows/" + QUALITY + "/dispatches"), {
                    "ref": branch, "inputs": {"pr-number": str(number), "expected-head": pr["head"]["sha"],
                                               "expected-base": tip, "request-id": request_id}})
            except (OSError, ValueError):
                self.update_check(pr, check, identity, "completed", "Quality dispatch failed",
                                  "A fresh assessment could not be started. Dispatch sfstack GitHub quality from the default branch.",
                                  "failure")
                raise
            dispatched.append(number)
        return {"dispatched": dispatched}

    def start(self, pr_number, expected_head="", expected_base="", request_id=""):
        repository, run = self.trusted_context(QUALITY, {"workflow_dispatch"})
        branch = repository["default_branch"]
        if request_id and not REQUEST_ID.fullmatch(request_id):
            raise ValueError("Invalid dispatch request identity.")
        if bool(expected_head) != bool(expected_base) or any(value and not SHA.fullmatch(value)
                                                           for value in (expected_head, expected_base)):
            raise ValueError("Expected head and base must be a pair of full commit SHAs.")
        pr = self.pr(int(pr_number), branch)
        title = RUN_TITLE.fullmatch(run.get("display_title", ""))
        if not title or int(title[1]) != pr["number"] or title[2] != (request_id or "manual"):
            raise ValueError("Run title does not match its dispatch identity.")
        tip = self.default_sha(branch)
        if (tip != self.context["workflow_sha"]
                or (expected_head and (pr["head"]["sha"] != expected_head or tip != expected_base))):
            return {"eligible": False, "reason": "Head, base, or controller policy advanced; dispatch a fresh assessment."}
        check = self.find_check(pr)
        previous = check_owner(check) if check else None
        if request_id and (not previous or previous["q"] != request_id or previous["b"] != tip):
            return {"eligible": False, "reason": "This dispatch no longer owns the queued request."}
        if previous and (previous["i"], previous["a"]) > (self.run_id, self.attempt):
            return {"eligible": False, "reason": "A newer assessment owns the check."}
        same_attempt = (previous and previous["k"] == "run" and previous["i"] == self.run_id
                        and previous["a"] == self.attempt)
        if same_attempt and check.get("status") == "completed":
            return {"eligible": False, "reason": "This attempt is completed; re-run all jobs or dispatch a fresh assessment."}
        handoff = previous and previous["k"] == "request" and previous["q"] == request_id
        reuse = (same_attempt or handoff) and check.get("status") in {"queued", "in_progress"} and previous.get("v") == 3
        generation = (previous or {}).get("g", 0) + (0 if reuse else 1)
        identity = owner(pr["number"], tip, "run", self.run_id, self.attempt, request_id, generation)
        writer = self.update_check if reuse else self.replace_check
        check = writer(pr, check, identity, "in_progress", "Assessing the pinned PR head",
                                  f"Candidate `{pr['head']['sha']}`; base `{tip}`; attempt {self.attempt}.\n\n"
                                  "Verification, agent review, and the deterministic quality gate must all complete.")
        publication = {"version": 2, "repository": self.repository, "pull_request": pr["number"],
                       "head_sha": pr["head"]["sha"], "base_sha": tip,
                       "head_repository": self.repository, "controller_sha": self.context["workflow_sha"],
                       "run_id": self.run_id, "run_attempt": self.attempt, "check_id": check["id"],
                       "owner": identity}
        return {"eligible": True, "publication": publication,
                "pr": self.with_current_base(pr, tip),
                "head_sha": publication["head_sha"], "base_sha": tip,
                "pr_number": pr["number"], "check_id": check["id"]}

    def snapshot(self, pr_number):
        """Refresh identity for sfstack finalization using the live default ref."""
        repository, _ = self.trusted_context(QUALITY, {"workflow_dispatch"})
        branch = repository["default_branch"]
        pr = self.pr(pr_number, branch)
        tip = self.default_sha(branch)
        if tip != self.context["workflow_sha"]:
            raise ValueError("Controller policy advanced during this assessment.")
        return self.with_current_base(pr, tip)

    def validate_result(self, publication, result_dir):
        result_dir = Path(result_dir)
        target, target_raw = read_json(result_dir / "target.json", result_dir)
        gate, _ = read_json(result_dir / "quality-gate.json", result_dir)
        assessment, _ = read_json(result_dir / "assessment/quality-assessment.json", result_dir)
        for key in ("repository", "pull_request", "head_sha", "base_sha", "head_repository"):
            if target.get(key) != publication[key]:
                raise ValueError("Evidence belongs to another PR, repository, head, or base.")
        if target.get("run_id") != str(self.run_id) or target.get("run_attempt") != str(self.attempt):
            raise ValueError("Evidence belongs to another workflow run or attempt.")
        subject = {"revision": publication["head_sha"], "input_digest": hashlib.sha256(target_raw).hexdigest(),
                   "environment": target.get("environment")}
        run_id = f"github-{self.run_id}-{self.attempt}"
        if (gate.get("subject") != subject or gate.get("run_id") != run_id
                or gate.get("mutation_authorized") is not False or gate.get("reasons") != []
                or gate.get("status") != "passed" or gate.get("success") is not True
                or gate.get("assessment") != "assessment/quality-assessment.json"
                or assessment.get("artifact_type") != "quality-assessment"
                or assessment.get("subject") != subject or assessment.get("run_id") != run_id
                or assessment.get("status") != "passed"):
            raise ValueError("The retained sfstack assessment does not establish a passing quality gate.")
        reports = assessment.get("payload", {}).get("reports", [])
        for kind in ("verification-report", "review-report"):
            selected = [report for report in reports if report.get("artifact_type") == kind]
            if len(selected) != 1 or selected[0].get("status") != "passed":
                raise ValueError("Both required source reports must pass.")
        # The gate already validated contracts and all evidence hashes before
        # uploading this immutable artifact. A publication queue can outlive its
        # evidence window, so recheck ages of the original inputs and reports,
        # not just the more recently created consolidated assessment.
        policy, _ = read_json(Path(__file__).with_name("policy.json"))
        max_age = policy["max_evidence_age_seconds"]
        if type(max_age) is not int or max_age <= 0:
            raise ValueError("Invalid trusted evidence-age policy.")
        observed_at = datetime.now(timezone.utc)
        for relative in ("request.json", "change-set.json", "specification.json", "test-plan.json",
                         "verification/verification-report.json", "review/review-report.json",
                         "assessment/quality-assessment.json"):
            record, _ = read_json(result_dir / relative, result_dir)
            created = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
            if created.tzinfo is None or not 0 <= (observed_at - created).total_seconds() <= max_age:
                raise ValueError("Evidence is stale or future-dated at publication: " + relative)
        return self.result_artifact()

    def result_artifact(self):
        artifacts = self.pages(f"actions/runs/{self.run_id}/artifacts", "artifacts")
        matches = [item for item in artifacts if item.get("name") == f"sfstack-quality-{self.attempt}"]
        if (len(matches) != 1 or matches[0].get("expired") is not False
                or matches[0].get("workflow_run", {}).get("id") != self.run_id
                or matches[0].get("workflow_run", {}).get("head_sha") != self.context["workflow_sha"]):
            raise ValueError("The retained quality artifact cannot be attributed to this controller run.")
        return matches[0]

    def publish(self, publication, result_dir, gate_result):
        repository, run = self.trusted_context(QUALITY, {"workflow_dispatch"})
        if not isinstance(publication, dict) or publication.get("eligible") is False:
            return self.close_pending(run, repository, "The current attempt has no publication record.")
        if (publication.get("version") != 2 or publication.get("repository") != self.repository
                or publication.get("run_id") != self.run_id or publication.get("run_attempt") != self.attempt
                or publication.get("controller_sha") != self.context["workflow_sha"]):
            return self.close_pending(run, repository, "The publication record does not match this attempt.")
        check = self.api.get(self.path(f"check-runs/{publication['check_id']}"))
        identity = check_owner(check)
        expected = publication.get("owner")
        if (identity != expected or not identity or identity["k"] != "run" or identity["i"] != self.run_id
                or identity["a"] != self.attempt or identity["p"] != publication["pull_request"]
                or identity["b"] != publication["base_sha"] or check.get("head_sha") != publication["head_sha"]):
            return {"published": False, "reason": "A newer request or attempt owns the check."}
        stub = {"number": publication["pull_request"], "head": {"sha": publication["head_sha"]}}
        current = self.find_check(stub)
        if current is None or current["id"] != check["id"]:
            return {"published": False, "reason": "A newer assessment generation owns publication."}
        # Repeated delivery cannot change a completed result for the same attempt.
        if check.get("status") == "completed":
            return {"published": False, "conclusion": check.get("conclusion"),
                    "reason": "This attempt has already published its result."}
        conclusion, reason, artifact = "failure", "The trusted quality gate did not succeed.", None
        try:
            if gate_result != "success":
                raise ValueError("The trusted quality gate did not succeed: " + str(gate_result))
            pr = self.pr(publication["pull_request"], repository["default_branch"])
            if (pr["head"]["sha"] != publication["head_sha"]
                    or self.default_sha(repository["default_branch"]) != publication["controller_sha"]
                    or publication["base_sha"] != publication["controller_sha"]):
                raise ValueError("The PR head, base, or controller policy advanced before publication.")
            target, _ = read_json(Path(result_dir) / "target.json", Path(result_dir))
            if ("pull_request_context" in target and target["pull_request_context"] != {
                    "title": pr.get("title") or "", "body": pr.get("body") or ""}):
                raise ValueError("PR title or acceptance description changed before publication.")
            artifact = self.validate_result(publication, result_dir)
            conclusion, reason = "success", "Both required reports passed and the trusted sfstack quality gate accepted their evidence."
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reason = str(exc)
        if artifact is None:
            # A negative or incomplete result still deserves a direct evidence
            # link when the controller retained one. The link never grants pass.
            try:
                artifact = self.result_artifact()
            except (OSError, ValueError, KeyError, TypeError):
                pass
        run_url = f"https://github.com/{self.repository}/actions/runs/{self.run_id}"
        summary = (f"**{'Passed' if conclusion == 'success' else 'Blocked'}** — {reason}\n\n"
                   f"PR #{publication['pull_request']}; candidate `{publication['head_sha']}`; base `{publication['base_sha']}`.\n\n"
                   f"[Workflow and job summaries]({run_url}) · attempt {self.attempt}.")
        if artifact:
            summary += f"\n\n[Download the complete evidence bundle]({run_url}/artifacts/{artifact['id']})."
        summary += "\n\nAutomated quality evidence does not grant mutation permission or independent human approval."
        self.update_check(stub, check, identity, "completed", "Quality passed" if conclusion == "success" else "Quality blocked",
                          summary, conclusion, run_url)
        return {"published": True, "conclusion": conclusion, "reason": reason, "check_id": check["id"]}

    def close_pending(self, run, repository, reason, in_progress=False):
        title = RUN_TITLE.fullmatch(run.get("display_title", ""))
        if not title:
            raise ValueError("Controller run has no recognized dispatch identity.")
        try:
            pr = self.pr(int(title[1]), repository["default_branch"])
        except ValueError:
            return {"published": False, "reason": "PR is closed or no longer eligible."}
        check = self.find_check(pr)
        identity = check_owner(check) if check else None
        if not identity:
            return {"published": False, "reason": "No owned check to recover."}
        same_run = identity["k"] == "run" and identity["i"] == run["id"] and identity["a"] <= run["run_attempt"]
        queued_request = (identity["k"] == "request" and title[2] != "manual" and identity["q"] == title[2])
        if not (same_run or queued_request):
            return {"published": False, "reason": "A different request or run owns the check."}
        if same_run and identity["a"] == run["run_attempt"] and check.get("status") == "completed":
            return {"published": False, "reason": "The current attempt already published its result."}
        reuse = ((queued_request or (same_run and identity["a"] == run["run_attempt"]))
                 and check.get("status") in {"queued", "in_progress"} and identity.get("v") == 3)
        updated = owner(pr["number"], identity["b"], "run", run["id"], run["run_attempt"], title[2],
                        identity.get("g", 0) + (0 if reuse else 1))
        writer = self.update_check if reuse else self.replace_check
        url = f"https://github.com/{self.repository}/actions/runs/{run['id']}"
        if in_progress:
            if same_run and identity["a"] == run["run_attempt"]:
                return {"published": False, "reason": "The current attempt already owns a pending check."}
            check = writer(pr, check, updated, "in_progress", "Quality assessment running",
                              "This run attempt must produce fresh evidence before quality can pass.", details_url=url)
        else:
            check = writer(pr, check, updated, "completed", "Quality assessment incomplete",
                              reason + "\n\nRe-run all jobs or dispatch a fresh assessment from the default branch.",
                              "failure", url)
        return {"published": True, "conclusion": "pending" if in_progress else "failure", "check_id": check["id"]}

    def reconcile(self, event):
        repository, _ = self.trusted_context(EVENTS, {"workflow_run"})
        trigger = event.get("workflow_run", {})
        if not positive(trigger.get("id")) or event.get("action") not in {"in_progress", "completed"}:
            raise ValueError("Expected a controller run lifecycle event.")
        run = self.api.get(self.path(f"actions/runs/{trigger['id']}"))
        self.validate_run(run, QUALITY, {"workflow_dispatch"}, repository["default_branch"])
        if run.get("run_attempt") != trigger.get("run_attempt"):
            return {"published": False, "reason": "A later controller attempt superseded this lifecycle event."}
        if event["action"] == "in_progress":
            if run.get("status") == "completed":
                return {"published": False, "reason": "Run already completed; its completion event owns recovery."}
            return self.close_pending(run, repository, "", in_progress=True)
        if run.get("status") != "completed":
            return {"published": False, "reason": "Controller attempt is not completed."}
        return self.close_pending(run, repository, "The controller finished without publishing a valid result: "
                                  + str(run.get("conclusion")) + ".")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("dispatch", "invalidate", "reconcile"):
        command = commands.add_parser(name)
        command.add_argument("--event", required=True)
    start = commands.add_parser("start")
    start.add_argument("--pr-number", required=True, type=int)
    for name in ("expected-head", "expected-base", "request-id"):
        start.add_argument("--" + name, default="")
    start.add_argument("--out", required=True)
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--pr-number", required=True, type=int)
    snapshot.add_argument("--out", required=True)
    publish = commands.add_parser("publish")
    for name in ("publication", "result", "gate-result", "out"):
        publish.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        context = {key: os.environ[env] for key, env in {
            "repository": "GITHUB_REPOSITORY", "run_id": "GITHUB_RUN_ID", "run_attempt": "GITHUB_RUN_ATTEMPT",
            "workflow_sha": "GITHUB_WORKFLOW_SHA", "ref": "GITHUB_REF", "event_name": "GITHUB_EVENT_NAME"}.items()}
        host = Host(GitHubAPI(os.environ.get("GH_TOKEN")), context)
        if args.command == "start":
            result = host.start(args.pr_number, args.expected_head, args.expected_base, args.request_id)
            write_json(args.out, result.get("publication", result))
            if result["eligible"]:
                write_json(Path(args.out).with_name("pr.json"), result["pr"])
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write("eligible=" + str(result["eligible"]).lower() + "\n")
                    for key in ("head_sha", "base_sha", "pr_number", "check_id"):
                        if key in result:
                            output.write(f"{key}={result[key]}\n")
            result = {key: value for key, value in result.items() if key not in {"publication", "pr"}}
        elif args.command == "snapshot":
            current = host.snapshot(args.pr_number)
            write_json(args.out, current)
            result = {"pull_request": current["number"],
                      "head_sha": current["head"]["sha"],
                      "base_sha": current["base"]["sha"]}
        elif args.command == "publish":
            try:
                publication, _ = read_json(args.publication)
            except (OSError, ValueError):
                publication = None
            result = host.publish(publication, args.result, args.gate_result)
            write_json(args.out, result)
        else:
            event, _ = read_json(args.event)
            result = getattr(host, args.command)(event)
        print(json.dumps(result, indent=2))
        return 2 if args.command == "publish" and result.get("conclusion") == "failure" else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("sfstack-github-host: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
