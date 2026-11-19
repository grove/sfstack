#!/usr/bin/env python3
"""Bound one maintainer-selected issue to a verified candidate and a draft PR.

The builder has local execution, never a repository write credential. A fresh
host reconstructs its bounded submission and measures the candidate. A separate
publisher performs only Git data/API operations, then requests Quality Factory.
This is ordinary Actions isolation, not an attestation against hostile code
running as the runner user. No automatic merge or independent approval is given.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from common import contained_path, inspect_artifact, load_json, now, read_regular, timestamp, validate_schema
from factory import plan
from jsonschema import Draft202012Validator
from quality_report import report_status
from render_invocation import render as render_skill
from integrations.github import automation, quality

HERE = Path(__file__).resolve().parent
WORKFLOW = "sfstack-software.yml"
MAX_FILE = 32_768
MAX_CONTENT = 65_536
MAX_SUBMISSION = 120_000
MAX_AGE = 7200
AUTHOR = {"name": "sfstack software factory", "email": "41898282+github-actions[bot]@users.noreply.github.com"}
write_json = quality.write_json
digest = quality.digest


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def allowed_files(paths):
    if not isinstance(paths, list) or not 1 <= len(paths) <= 8 or any(not isinstance(p, str) for p in paths):
        raise ValueError("Select one to eight exact file paths as a JSON array.")
    if len(set(p.casefold() for p in paths)) != len(paths):
        raise ValueError("Duplicate or case-ambiguous allowed paths.")
    for path in paths:
        parts = PurePosixPath(path).parts
        if (len(path) > 240 or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*", path)
                or str(PurePosixPath(path)) != path or any(p.startswith(".") for p in parts)
                or not (path == "README.md" or len(parts) > 1 and parts[0] in {"docs", "examples", "tests"})):
            raise ValueError("Pilot paths must be explicit files within docs/, examples/, tests/, or README.md.")
        if any(other != path and other.startswith(path + "/") for other in paths):
            raise ValueError("An allowed file cannot also be a parent directory.")
    return sorted(paths)


def criteria(values):
    if (not isinstance(values, list) or not 1 <= len(values) <= 8
            or any(not isinstance(v, str) or not v.strip() or len(v) > 2000 or "\0" in v for v in values)
            or len(set(values)) != len(values)):
        raise ValueError("Supply one to eight distinct acceptance criteria as a JSON array of strings.")
    return [{"id": f"acceptance-{i}", "description": value} for i, value in enumerate(values, 1)]


def issue_snapshot(issue, repository):
    if (not isinstance(issue, dict) or not automation.positive(issue.get("number"))
            or issue.get("state") != "open" or "pull_request" in issue
            or not isinstance(issue.get("title"), str) or not issue["title"].strip()
            or len(issue["title"]) > 1000 or not isinstance(issue.get("body") or "", str)
            or len((issue.get("body") or "").encode()) > 20_000):
        raise ValueError("Select an open issue (not a pull request) with a bounded text description.")
    timestamp(issue["updated_at"])
    return {"number": issue["number"], "state": "open", "title": issue["title"],
            "body": issue.get("body") or "", "updated_at": issue["updated_at"],
            "url": f"https://github.com/{repository}/issues/{issue['number']}"}


def git(repo, *args, data=None, extra_env=None):
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(extra_env or {})
    result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                             "-c", "commit.gpgsign=false", "-C", str(repo), *args], input=data,
                            capture_output=True, timeout=60, check=False, env=environment)
    if result.returncode:
        raise ValueError("Cannot materialize candidate: " + result.stderr.decode("utf-8", "replace")[:1500])
    return result.stdout


def file_snapshot(repo, path):
    # Check ancestors before opening/writing: a normalized string alone does not
    # prevent a symlink already present in the trusted base tree.
    cursor = Path(repo)
    for part in PurePosixPath(path).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("Allowed paths cannot traverse symlinks.")
    if cursor.exists() and not cursor.is_file():
        raise ValueError("Allowed paths must identify regular text files.")
    for ancestor in cursor.parents:
        if ancestor == Path(repo):
            break
        if ancestor.exists() and not ancestor.is_dir():
            raise ValueError("Allowed path has a non-directory ancestor.")
    entry = git(repo, "ls-tree", "-z", "HEAD", "--", path)
    if not entry:
        return {"blob_sha": None, "sha256": None, "mode": "100644"}, None
    mode, kind, identity = entry.split(b"\t", 1)[0].decode().split()
    if mode != "100644" or kind != "blob":
        raise ValueError("The pilot edits only ordinary non-executable text files.")
    raw = read_regular(cursor)
    if len(raw) > MAX_FILE or b"\0" in raw:
        raise ValueError("Allowed file is binary or exceeds 32 KiB.")
    raw.decode("utf-8")
    if blob_sha(raw) != identity:
        raise ValueError("Worktree bytes do not match the base Git blob.")
    return {"blob_sha": identity, "sha256": sha256(raw), "mode": mode}, raw


def prepare(repo, issue, repository, run_id, run_attempt, allowed_paths, acceptance_criteria,
            output, at=None, checks=None, actor="maintainer", base_branch="main"):
    at = (at or now()).replace(microsecond=0)
    repo, output = Path(repo).resolve(), Path(output).resolve()
    if (not quality.REPOSITORY.fullmatch(repository)
            or not re.fullmatch(r"[1-9][0-9]*", str(run_id))
            or not re.fullmatch(r"[1-9][0-9]*", str(run_attempt))):
        raise ValueError("Invalid repository or workflow run identity.")
    base = git(repo, "rev-parse", "HEAD").decode().strip()
    quality.check_candidate(repo, base)
    if output.exists() or output.is_relative_to(repo):
        raise ValueError("Input directory must be new and outside the repository.")
    selected, acceptance = allowed_files(allowed_paths), criteria(acceptance_criteria)
    snapshot = issue_snapshot(issue, repository)
    checks = deepcopy(checks if checks is not None else load_json(HERE / "checks.json"))
    quality.check_plan(checks)
    files, originals = {}, {}
    for index, path in enumerate(selected):
        info, raw = file_snapshot(repo, path)
        files[path] = {**info, "original": f"original/{index}.txt" if raw is not None else None}
        if raw is not None:
            originals[files[path]["original"]] = raw
    target = {"repository": repository, "issue": snapshot, "base_sha": base,
              "base_tree_sha": git(repo, "rev-parse", "HEAD^{tree}").decode().strip(),
              "base_branch": base_branch, "actor": actor, "run_id": str(run_id),
              "run_attempt": str(run_attempt), "allowed_files": files, "criteria": acceptance,
              "checks": checks, "created_at": at.isoformat().replace("+00:00", "Z"),
              "environment": f"github-actions-python-{sys.version_info.major}.{sys.version_info.minor}"}
    output.mkdir(parents=True)
    for path, raw in originals.items():
        destination = output / path
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(raw)
    write_json(output / "target.json", target)
    run = {"schema_version": "1.0", "run_id": f"software-{run_id}-{run_attempt}",
           "subject": {"revision": base, "input_digest": digest(output / "target.json"), "environment": target["environment"]},
           "capabilities": ["workspace.read", "workspace.write", "execution.run", "artifact.write"],
           "effect_scopes": {"workspace.modify": f"github:{repository}:issue:{snapshot['number']}:run:{run_id}:{run_attempt}:candidate"},
           "policy": "policy.json", "inputs": {}, "completed": {}}
    policy = {"schema_version": "1.0", "id": "github-software-bounded-workspace", "grants": [{
        "id": "selected-issue-workspace", "actor": actor, "run_id": run["run_id"], "effect": "workspace.modify",
        "scope": run["effect_scopes"]["workspace.modify"], "subject": run["subject"],
        "expires_at": (at + timedelta(seconds=MAX_AGE)).isoformat().replace("+00:00", "Z")}],
        "max_evidence_age_seconds": MAX_AGE, "required_artifacts": {"workspace.modify": ["work-plan", "specification"]},
        "require_independent_review": False}
    payloads = {
        "work-plan": {"items": [{"id": f"issue-{snapshot['number']}", "state": "ready", "dependencies": [],
                                  "owner": actor, "allowed_paths": selected}], "ready_frontier": [f"issue-{snapshot['number']}"]},
        "specification": {"criteria": acceptance, "issue": snapshot,
                          "scope": "One selected issue increment within the maintainer's exact file list."},
        "test-plan": {"checks": checks, "item_level": "Establish discriminating acceptance evidence before implementation; disclose gaps."},
    }
    for kind, payload in payloads.items():
        record = quality.artifact(run, kind, "github-software-host-input", "passed", payload,
            [quality.evidence(output / "target.json", "host-target", "input")],
            [{"id": "selected-issue", "status": "passed", "evidence": ["host-target"],
              "detail": "Maintainer-selected issue, exact base, file scope, and acceptance criteria."}], at)
        write_json(output / (kind + ".json"), record)
        run["inputs"][kind] = kind + ".json"
    write_json(output / "policy.json", policy)
    write_json(output / "run.json", run)
    shutil.copyfile(HERE / "software-workflow.json", output / "workflow.json")
    load_bundle(output, at)
    return {"status": "prepared", "base_sha": base, "issue_number": snapshot["number"]}


def load_bundle(bundle, at):
    bundle = Path(bundle)
    run, target, policy = (load_json(bundle / name) for name in ("run.json", "target.json", "policy.json"))
    validate_schema(run, "run")
    validate_schema(policy, "policy")
    if (run["subject"]["revision"] != target["base_sha"]
            or run["subject"]["input_digest"] != digest(bundle / "target.json")
            or run["run_id"] != f"software-{target['run_id']}-{target['run_attempt']}"
            or not 0 <= (at - timestamp(target["created_at"])).total_seconds() <= MAX_AGE
            or set(run["inputs"]) != {"work-plan", "specification", "test-plan"}
            or load_json(bundle / "workflow.json") != load_json(HERE / "software-workflow.json")):
        raise ValueError("Software inputs changed, expired, or belong to another subject.")
    allowed_files(list(target["allowed_files"]))
    if target["criteria"] != criteria([c["description"] for c in target["criteria"]]):
        raise ValueError("Invalid acceptance criteria identities.")
    quality.check_plan(target["checks"])
    for info in target["allowed_files"].values():
        if info["original"] is not None:
            raw = read_regular(contained_path(bundle, info["original"]))
            if sha256(raw) != info["sha256"] or blob_sha(raw) != info["blob_sha"]:
                raise ValueError("Original file evidence changed.")
    if (load_json(bundle / "specification.json")["payload"]["criteria"] != target["criteria"]
            or load_json(bundle / "test-plan.json")["payload"]["checks"] != target["checks"]):
        raise ValueError("Contract inputs differ from the pinned host target.")
    if plan(bundle / "workflow.json", bundle / "run.json", at)["ready"] != ["build"]:
        raise ValueError("The bounded build is not eligible under its skill contract and authorization.")
    return run, target, policy


def render(bundle, candidate, output, at=None):
    at, output = at or now(), Path(output)
    run, target, policy = load_bundle(bundle, at)
    quality.check_candidate(candidate, target["base_sha"])
    output.mkdir(parents=True, exist_ok=False)
    template = {"run_id": run["run_id"], "subject": run["subject"], "status": "inconclusive",
        "summary": "Replace with the supported build outcome.", "criteria_addressed": [],
        "behavior_changes": [], "checks_run": [], "remaining_work": [], "edits": []}
    write_json(output / "change-template.json", template)
    shutil.copyfile(HERE / "change.schema.json", output / "change.schema.json")
    context = {"run_id": run["run_id"], "subject": run["subject"], "capabilities": run["capabilities"],
        "authorized_effects": policy["grants"], "allowed_paths": list(target["allowed_files"]),
        "inputs": {kind: load_json(Path(bundle) / path) for kind, path in run["inputs"].items()},
        "candidate_directory": str(Path(candidate).resolve()), "response_template": str((output / "change-template.json").resolve()),
        "response_schema": str((output / "change.schema.json").resolve()),
        "transport": "Submit complete UTF-8 contents of only changed allowed files. The host supplies immutable identities and evidence envelopes.",
        "limits": "At most 8 files, 32 KiB per file, 64 KiB total; no deletes, renames, mode changes, or external effects. Two repair cycles."}
    (output / "invocation.md").write_text(render_skill("sf-build-change", context), encoding="utf-8")
    return {"status": "rendered", "skill": "sf-build-change"}


def load_response(path, run, target):
    raw = read_regular(path)
    if len(raw) > MAX_SUBMISSION:
        raise ValueError("Agent submission exceeds the bounded transport size.")
    outer = automation.strict_json(raw)
    items = outer.get("items") if isinstance(outer, dict) else None
    # gh-aw's live safe-output transport adds an output_id alongside the
    # documented type and payload. It identifies the envelope, not a new grant.
    if (not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict)
            or items[0].get("type") != "submit_change"
            or not {"type", "change_json"}.issubset(items[0])
            or not set(items[0]).issubset({"type", "change_json", "output_id"})
            or not isinstance(items[0]["change_json"], str)
            or ("output_id" in items[0]
                and (not isinstance(items[0]["output_id"], str)
                     or not items[0]["output_id"].startswith("so_")
                     or len(items[0]["output_id"]) > 128))):
        raise ValueError("Expected exactly one submit_change safe output.")
    response = automation.strict_json(items[0]["change_json"])
    errors = list(Draft202012Validator(load_json(HERE / "change.schema.json")).iter_errors(response))
    if errors:
        raise ValueError("Agent change response does not match the closed schema: " + errors[0].message[:500])
    if response["run_id"] != run["run_id"] or response["subject"] != run["subject"]:
        raise ValueError("Agent response belongs to another run or subject.")
    expected = {c["id"] for c in target["criteria"]}
    if not set(response["criteria_addressed"]).issubset(expected):
        raise ValueError("Unknown acceptance criterion in the agent response.")
    if response["status"] == "passed" and (set(response["criteria_addressed"]) != expected
            or not response["behavior_changes"] or not response["checks_run"]
            or response["remaining_work"] or not response["edits"]):
        raise ValueError("Passing build lacks complete criteria, behavioral checks, or a complete bounded change.")
    edits = response["edits"]
    if len({e["path"] for e in edits}) != len(edits):
        raise ValueError("Duplicate edited file.")
    total = 0
    for edit in edits:
        if edit["path"] not in target["allowed_files"]:
            raise ValueError("Agent edit exceeds the maintainer-selected file scope.")
        raw_content = edit["content"].encode("utf-8")
        total += len(raw_content)
        if b"\0" in raw_content or len(raw_content) > MAX_FILE or total > MAX_CONTENT:
            raise ValueError("Agent edit is binary or exceeds the content budget.")
        if sha256(raw_content) == target["allowed_files"][edit["path"]]["sha256"]:
            raise ValueError("Agent submitted an unchanged file.")
    return response, raw


def candidate_record(repo, target, edits):
    """Compute immutable objects with a temporary index; never execute a patch."""
    identity = {**AUTHOR, "date": target["created_at"]}
    message = f"Implement issue #{target['issue']['number']} (sfstack run {target['run_id']}/{target['run_attempt']})\n"
    normalized = []
    with tempfile.TemporaryDirectory() as temporary:
        environment = {"GIT_INDEX_FILE": str(Path(temporary) / "index")}
        git(repo, "read-tree", target["base_sha"], extra_env=environment)
        for edit in sorted(edits, key=lambda item: item["path"]):
            raw = edit["content"].encode("utf-8")
            sha = git(repo, "hash-object", "-w", "--stdin", data=raw).decode().strip()
            if sha != blob_sha(raw):
                raise ValueError("Git blob identity mismatch.")
            git(repo, "update-index", "--add", "--cacheinfo", "100644", sha, edit["path"], extra_env=environment)
            normalized.append({**edit, "blob_sha": sha, "sha256": sha256(raw)})
        tree = git(repo, "write-tree", extra_env=environment).decode().strip()
    author_env = {f"GIT_{role}_{field}": identity[key] for role in ("AUTHOR", "COMMITTER")
                  for field, key in (("NAME", "name"), ("EMAIL", "email"), ("DATE", "date"))}
    head = git(repo, "commit-tree", tree, "-p", target["base_sha"], data=message.encode(), extra_env=author_env).decode().strip()
    diff = git(repo, "diff", "--no-ext-diff", "--no-textconv", target["base_sha"], head, "--")
    return {"base_sha": target["base_sha"], "tree_sha": tree, "head_sha": head, "message": message,
            "identity": identity, "edits": normalized, "diff_sha256": sha256(diff)}, diff


def verify(repo, bundle, submission_path, agent_result, output, at=None):
    fixed_time, at = at, at or now()
    repo, bundle, output = Path(repo).resolve(), Path(bundle), Path(output).resolve()
    run, target, _ = load_bundle(bundle, at)
    quality.check_candidate(repo, target["base_sha"])
    if output.exists() or output.is_relative_to(repo):
        raise ValueError("Result directory must be new and outside the candidate.")
    output.mkdir(parents=True)
    (output / "logs").mkdir()
    response, raw = load_response(submission_path, run, target)
    (output / "submission.json").write_bytes(raw)
    if agent_result != "success" or response["status"] != "passed":
        status = response["status"] if agent_result == "success" else "blocked"
        gate = {"status": status, "passed": False, "reasons": ["Builder did not establish a complete change."],
                "agent_result": agent_result, "input_digest": run["subject"]["input_digest"]}
        write_json(output / "gate.json", gate)
        (output / "summary.md").write_text(f"# sfstack software factory\n\n**Verdict: {status}**\n\nNo draft PR was authorized.\n")
        return gate
    for path, expected in target["allowed_files"].items():
        actual, _ = file_snapshot(repo, path)
        if any(actual[key] != expected[key] for key in actual):
            raise ValueError("Candidate no longer matches the pinned base file evidence.")
    candidate, diff = candidate_record(repo, target, response["edits"])
    if candidate["tree_sha"] == target["base_tree_sha"]:
        raise ValueError("Builder produced no change.")
    write_json(output / "candidate.json", candidate)
    (output / "diff.patch").write_bytes(diff)
    for edit in candidate["edits"]:
        path = contained_path(repo, edit["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(edit["content"], encoding="utf-8")
    # Install the previously calculated tree in the index without checkout hooks,
    # filters, or committing any unselected worktree paths.
    git(repo, "reset", "--mixed", candidate["head_sha"])
    quality.check_candidate(repo, candidate["head_sha"])
    results, evidence, checks = [], [], []
    for selected in target["checks"]:
        log = output / "logs" / (selected["id"] + ".txt")
        result = quality.run_check(selected, repo, log)
        results.append(result)
        evidence.append(quality.evidence(log, selected["id"], "test", "logs/" + log.name))
        checks.append({"id": selected["id"], "status": result["status"], "evidence": [selected["id"]],
                       "detail": json.dumps(result, sort_keys=True)})
    quality.check_candidate(repo, candidate["head_sha"])
    observed = fixed_time or now()
    status = report_status({r["status"] for r in results})
    verify_run = {"run_id": run["run_id"] + "-verify", "subject": {"revision": candidate["head_sha"],
                  "input_digest": digest(output / "candidate.json"), "environment": target["environment"]}}
    payload = {"candidate_revision": candidate["head_sha"], "environment": target["environment"],
               "executed_count": sum(r["executed"] for r in results), "required_count": len(results),
               "failed_count": sum(r["status"] == "failed" for r in results),
               "skipped_required": [r["id"] for r in results if r["status"] in {"blocked", "inconclusive"}],
               "check_results": results, "criteria_coverage": [r["id"] for r in results],
               "remaining_risks": ["Issue acceptance is a builder claim until the separate quality review and human review."]}
    verification = quality.artifact(verify_run, "verification-report", "sf-verify-change", status, payload, evidence, checks, observed)
    write_json(output / "verification-report.json", verification)
    proof = [quality.evidence(output / "submission.json", "agent-submission", "analysis"),
             quality.evidence(output / "diff.patch", "candidate-diff", "diff"),
             quality.evidence(output / "candidate.json", "candidate-identity", "input"),
             quality.evidence(output / "verification-report.json", "verification-report", "observation"), *evidence]
    change = quality.artifact(run, "change-set", "sf-build-change", status, {
        "work_item": f"issue-{target['issue']['number']}", "criteria_addressed": response["criteria_addressed"],
        "base_revision": target["base_sha"], "candidate_revision": candidate["head_sha"],
        "changed_paths": [e["path"] for e in candidate["edits"]], "behavior_changes": response["behavior_changes"],
        "checks_run": results, "agent_checks_claimed": response["checks_run"], "compatibility_notes": [],
        "documentation_needs": [], "remaining_work": response["remaining_work"],
        "verification_subject": verify_run["subject"], "acceptance_basis": "Builder claims plus measured host checks; independent quality and human review remain."},
        proof, [{"id": "host-verification", "status": status, "evidence": ["verification-report"],
                 "detail": "Fresh host reconstructed only scoped files and executed the fixed check plan."}], observed)
    change["summary"] = response["summary"]
    write_json(output / "change-set.json", change)
    if status == "passed":
        # Preserve the base subject for build. Verification has its own new,
        # candidate-bound subject: no old evidence is relabelled as current.
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary)
            shutil.copytree(bundle, checkpoint, dirs_exist_ok=True)
            quality.copy_record(output / "change-set.json", checkpoint / "build")
            completed = deepcopy(run)
            completed["completed"] = {"build": ["build/change-set.json"]}
            write_json(checkpoint / "run.json", completed)
            if plan(checkpoint / "workflow.json", checkpoint / "run.json", observed)["status"] != "complete":
                raise ValueError("Completed build does not satisfy its skill handoff.")
    gate = {"status": status, "passed": status == "passed", "candidate_sha": candidate["head_sha"],
            "subject": verify_run["subject"], "input_digest": run["subject"]["input_digest"],
            "digests": {name: digest(output / name) for name in ("candidate.json", "diff.patch", "submission.json", "change-set.json", "verification-report.json")},
            "mutation_authorized": False, "reasons": [] if status == "passed" else ["Required candidate verification did not pass."]}
    write_json(output / "gate.json", gate)
    lines = ["# sfstack software factory", "", f"**Verdict: {status}**", "",
        f"Issue: {target['issue']['url']}", "", f"Candidate: `{candidate['head_sha']}`", "",
        "| Host check | Status |", "| --- | --- |"]
    lines += [f"| {r['id']} | {r['status']} |" for r in results]
    lines += ["", "The build preserves the original issue, acceptance criteria, base, scoped edits, agent claims, and actual host logs.",
              "A passing build may be published as a draft. The separate Quality Factory and human review remain required; no merge is authorized."]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return gate


class SoftwareHost(automation.Host):
    def admitted(self):
        repository, source = self.trusted_context(WORKFLOW, {"workflow_dispatch"})
        actor = source.get("triggering_actor", source.get("actor", {})).get("login", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", actor):
            raise ValueError("A human repository writer must dispatch this workflow.")
        permission = self.api.get(self.path("collaborators/" + quote(actor, safe="") + "/permission"))
        if permission.get("permission") not in {"admin", "maintain", "write"}:
            raise ValueError("The dispatcher must have write, maintain, or admin repository permission.")
        if self.default_sha(repository["default_branch"]) != self.context["workflow_sha"]:
            raise ValueError("Default branch advanced; dispatch a fresh Software Factory run.")
        return repository, source, actor

    def prepare(self, repo, issue_number, paths, acceptance, output, at=None):
        repository, _, actor = self.admitted()
        if not automation.positive(issue_number):
            raise ValueError("Expected a positive issue number.")
        if git(repo, "rev-parse", "HEAD").decode().strip() != self.context["workflow_sha"]:
            raise ValueError("Controller checkout does not match the dispatched default revision.")
        issue = self.api.get(self.path(f"issues/{issue_number}"))
        if issue.get("number") != issue_number:
            raise ValueError("Issue identity mismatch.")
        return prepare(repo, issue, self.repository, self.run_id, self.attempt, paths, acceptance, output,
                       at=at, actor=actor, base_branch=repository["default_branch"])

    def current(self, target):
        repository, _, actor = self.admitted()
        current = issue_snapshot(self.api.get(self.path(f"issues/{target['issue']['number']}")), self.repository)
        if (current != target["issue"] or actor != target["actor"]
                or repository["default_branch"] != target["base_branch"]
                or self.context["workflow_sha"] != target["base_sha"]
                or target["repository"] != self.repository
                or target["run_id"] != str(self.run_id) or target["run_attempt"] != str(self.attempt)):
            raise ValueError("Issue, authorizing actor, base, or workflow attempt changed; dispatch a fresh run.")

    def validate_result(self, bundle, result, repo, at):
        result = Path(result)
        run, target, _ = load_bundle(bundle, at)
        self.current(target)
        gate, candidate = load_json(result / "gate.json"), load_json(result / "candidate.json")
        if (gate.get("passed") is not True or gate.get("status") != "passed" or gate.get("reasons") != []
                or gate.get("mutation_authorized") is not False or gate.get("input_digest") != run["subject"]["input_digest"]
                or gate.get("candidate_sha") != candidate.get("head_sha")
                or set(gate.get("digests", {})) != {"candidate.json", "diff.patch", "submission.json", "change-set.json", "verification-report.json"}
                or any(digest(result / path) != value for path, value in gate["digests"].items())):
            raise ValueError("Build gate is negative, incomplete, or its evidence was modified.")
        response, _ = load_response(result / "submission.json", run, target)
        expected, diff = candidate_record(repo, target, response["edits"])
        if response["status"] != "passed" or candidate != expected or read_regular(result / "diff.patch") != diff:
            raise ValueError("Verified Git objects differ from the bounded submitted content.")
        subject = {"revision": candidate["head_sha"], "input_digest": digest(result / "candidate.json"), "environment": target["environment"]}
        if gate.get("subject") != subject:
            raise ValueError("Candidate subject mismatch.")
        verification, problems = inspect_artifact(result / "verification-report.json", subject, run["run_id"] + "-verify",
                                                   at, MAX_AGE, "verification-report")
        change, change_errors = inspect_artifact(result / "change-set.json", run["subject"], run["run_id"], at, MAX_AGE, "change-set")
        problems += change_errors
        if (verification["producer"] != {"skill": "sf-verify-change", "version": "1.0.0"}
                or change["producer"] != {"skill": "sf-build-change", "version": "1.0.0"}
                or change["payload"].get("candidate_revision") != candidate["head_sha"]):
            problems.append("Skill producer or candidate changed.")
        results = verification["payload"].get("check_results", [])
        if len(results) != len(target["checks"]) or {r.get("id") for r in results} != {c["id"] for c in target["checks"]}:
            problems.append("Verification omitted a required check.")
        else:
            for selected in target["checks"]:
                observed = next(r for r in results if r["id"] == selected["id"])
                if (any(observed.get(k) != selected[k] for k in ("command", "kind"))
                        or observed.get("status") != "passed" or observed.get("executed") is not True
                        or observed.get("returncode") != 0
                        or selected["kind"] == "unittest" and (type(observed.get("tests_run")) is not int
                            or observed["tests_run"] < 1 or observed.get("tests_skipped") != 0 or observed.get("expected_failures") != 0)):
                    problems.append("Verification lacks a substantive passing host check.")
        if problems:
            raise ValueError("Invalid build evidence: " + "; ".join(problems))
        artifacts = self.pages(f"actions/runs/{self.run_id}/artifacts", "artifacts")
        matches = [a for a in artifacts if a.get("name") == f"sfstack-software-result-{self.attempt}" and not a.get("expired")]
        if (len(matches) != 1 or matches[0].get("workflow_run", {}).get("id") != self.run_id
                or matches[0]["workflow_run"].get("head_sha") != target["base_sha"]):
            raise ValueError("Current-attempt build evidence artifact is unavailable.")
        return target, candidate, matches[0]

    def publish(self, bundle, result, repo, at=None):
        target, candidate, artifact = self.validate_result(bundle, result, repo, at or now())
        # Objects are immutable and harmless until referenced. Never execute
        # candidate files in this job, which alone has repository write scopes.
        for edit in candidate["edits"]:
            created = self.api.post(self.path("git/blobs"), {"content": edit["content"], "encoding": "utf-8"})
            if created.get("sha") != edit["blob_sha"]:
                raise ValueError("GitHub stored a different candidate blob.")
        tree = self.api.post(self.path("git/trees"), {"base_tree": target["base_tree_sha"], "tree": [
            {"path": e["path"], "mode": "100644", "type": "blob", "sha": e["blob_sha"]} for e in candidate["edits"]]})
        if tree.get("sha") != candidate["tree_sha"]:
            raise ValueError("GitHub tree differs from the verified candidate.")
        commit = self.api.post(self.path("git/commits"), {"message": candidate["message"], "tree": tree["sha"],
            "parents": [target["base_sha"]], "author": candidate["identity"], "committer": candidate["identity"]})
        if commit.get("sha") != candidate["head_sha"]:
            raise ValueError("GitHub commit differs from the verified candidate.")
        self.current(target)
        branch = f"sfstack/issue-{target['issue']['number']}-{self.run_id}-{self.attempt}"
        self.publication_state = {"published": False, "quality_requested": False, "branch": branch,
                                  "candidate_sha": candidate["head_sha"], "merge_authorized": False}
        refs = self.api.get(self.path("git/matching-refs/heads/" + quote(branch, safe="")))
        exact = [ref for ref in refs if ref.get("ref") == "refs/heads/" + branch]
        if exact:
            if len(exact) != 1 or exact[0].get("object", {}).get("sha") != candidate["head_sha"]:
                raise ValueError("Factory branch exists with different content; it will not be overwritten.")
        else:
            self.api.post(self.path("git/refs"), {"ref": "refs/heads/" + branch, "sha": candidate["head_sha"]})
        self.current(target)
        pulls = self.pages("pulls?" + urlencode({"state": "all", "head": self.repository.split('/')[0] + ":" + branch}))
        evidence_url = f"https://github.com/{self.repository}/actions/runs/{self.run_id}/artifacts/{artifact['id']}"
        title = f"[sfstack] {target['issue']['title']}"[:240]
        body = "\n".join([
            f"Implements the selected increment from #{target['issue']['number']}.", "",
            "## Acceptance criteria", "", *[f"- {c['description']}" for c in target['criteria']], "",
            "## Evidence", "", f"- [Build evidence and retained host logs]({evidence_url})",
            f"- Base: `{target['base_sha']}`", f"- Verified candidate: `{candidate['head_sha']}`", "",
            "Created by sfstack's bounded Software Factory. Local verification passed. A separate Quality Factory assessment is requested for this exact head.",
            "This is a draft for human review. Builder claims are retained separately from measured host checks; no human approval or merge is authorized."])

        def validate_pull(pull):
            if (not automation.positive(pull.get("number")) or pull.get("state") != "open" or pull.get("draft") is not True
                    or pull.get("head", {}).get("sha") != candidate["head_sha"]
                    or pull.get("head", {}).get("ref") != branch
                    or pull.get("head", {}).get("repo", {}).get("full_name", "").lower() != self.repository.lower()
                    or pull.get("base", {}).get("repo", {}).get("full_name", "").lower() != self.repository.lower()
                    or pull.get("base", {}).get("ref") != target["base_branch"]
                    or pull.get("title") != title or pull.get("body") != body):
                raise ValueError("Factory PR content, state, or acceptance criteria changed; human review is required.")

        if pulls:
            if len(pulls) != 1:
                raise ValueError("Multiple PRs refer to the factory branch; human review is required.")
            pull = pulls[0]
            self.publication_state.update({"published": True, "draft": pull.get("draft"), "pull_request": pull["number"],
                "url": f"https://github.com/{self.repository}/pull/{pull['number']}", "evidence_url": evidence_url})
            validate_pull(pull)
        else:
            # If the response is lost, publication may have happened. Report
            # uncertainty rather than telling an operator no PR exists.
            self.publication_state["published"] = None
            pull = self.api.post(self.path("pulls"), {"title": title,
                "head": branch, "base": target["base_branch"], "body": body, "draft": True,
                "maintainer_can_modify": True})
        self.publication_state.update({"published": True, "draft": True, "pull_request": pull["number"],
            "url": f"https://github.com/{self.repository}/pull/{pull['number']}", "evidence_url": evidence_url})
        self.current(target)
        current_pull = self.api.get(self.path(f"pulls/{pull['number']}"))
        if current_pull.get("number") != pull["number"]:
            raise ValueError("Factory PR identity changed before quality dispatch.")
        validate_pull(current_pull)
        self.api.post(self.path("actions/workflows/sfstack-quality.yml/dispatches"), {
            "ref": target["base_branch"], "inputs": {"pr-number": str(pull["number"]),
                "expected-head": candidate["head_sha"], "expected-base": target["base_sha"]}})
        return {"published": True, "draft": True, "pull_request": pull["number"],
                "url": f"https://github.com/{self.repository}/pull/{pull['number']}",
                "candidate_sha": candidate["head_sha"], "quality_requested": True,
                "quality_passed": False, "evidence_url": evidence_url, "merge_authorized": False}


def context():
    return {name: os.environ.get(variable, "") for name, variable in {
        "repository": "GITHUB_REPOSITORY", "run_id": "GITHUB_RUN_ID", "run_attempt": "GITHUB_RUN_ATTEMPT",
        "workflow_sha": "GITHUB_WORKFLOW_SHA", "ref": "GITHUB_REF", "event_name": "GITHUB_EVENT_NAME"}.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    for name in ("repo", "issue-number", "allowed-paths", "acceptance-criteria", "out"):
        prep.add_argument("--" + name, required=True)
    rendering = commands.add_parser("render")
    for name in ("bundle", "candidate", "out"):
        rendering.add_argument("--" + name, required=True)
    verification = commands.add_parser("verify")
    for name in ("repo", "bundle", "submission", "agent-result", "out"):
        verification.add_argument("--" + name, required=True)
    publication = commands.add_parser("publish")
    for name in ("bundle", "result", "out"):
        publication.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in {"prepare", "publish"}:
            host = SoftwareHost(automation.GitHubAPI(os.environ.get("GH_TOKEN", "")), context())
        if args.command != "prepare":
            quality.check_actions_run(args.bundle)
        if args.command == "prepare":
            result = host.prepare(args.repo, int(args.issue_number), automation.strict_json(args.allowed_paths),
                                  automation.strict_json(args.acceptance_criteria), args.out)
        elif args.command == "render":
            result = render(args.bundle, args.candidate, args.out)
        elif args.command == "verify":
            result = verify(args.repo, args.bundle, args.submission, args.agent_result, args.out)
        else:
            result = host.publish(args.bundle, args.result, ROOT)
            write_json(args.out, result)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                for key in ("base_sha", "issue_number", "passed", "candidate_sha"):
                    if key in result:
                        output.write(f"{key}={str(result[key]).lower()}\n")
        print(json.dumps(result, indent=2))
        return 2 if args.command == "verify" and not result["passed"] else 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, subprocess.TimeoutExpired) as exc:
        if args.command == "verify":
            output = Path(args.out)
            output.mkdir(parents=True, exist_ok=True)
            write_json(output / "gate.json", {"status": "blocked", "passed": False, "reasons": [str(exc)]})
            (output / "summary.md").write_text("# sfstack software factory\n\n**Verdict: blocked**\n\n" + str(exc) + "\n")
        elif args.command == "publish":
            state = getattr(locals().get("host"), "publication_state", {"published": False, "quality_requested": False})
            write_json(args.out, {**state, "reason": str(exc),
                                  "recovery": "Inspect this run and any sfstack/issue branch or draft PR before retrying. No merge was authorized."})
        print("sfstack-software: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
