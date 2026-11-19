#!/usr/bin/env python3
"""Start, inspect, resume, and summarize a local Quality Factory run."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from common import ROOT, load_json, now, validate_schema
from factory import plan
from quality_report import consolidate


# Presets select existing workflows and policy requirements, not another profile
# language. A host can edit the ordinary workflow/policy before starting work.
PROFILES = {
    "baseline": ("quality", ["verification-report", "review-report", "impact-assessment"]),
    "risk": ("quality-risk", ["verification-report", "review-report", "impact-assessment",
                              "security-assessment", "compatibility-report"]),
}


def git(repo, *args):
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise ValueError("Cannot inspect Git candidate: " + result.stderr.strip())
    return result.stdout.strip()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def initialize(repo, output, goal, environment, profile="baseline", base=None, at=None):
    """Record a clean local Git candidate without executing repository code."""
    if profile not in PROFILES:
        raise ValueError("Unknown quality profile.")
    if not goal.strip() or not environment.strip():
        raise ValueError("Goal and environment must be explicit, nonempty values.")
    repo = Path(git(Path(repo).resolve(), "rev-parse", "--show-toplevel")).resolve()
    destination = Path(output).resolve()
    if destination.exists():
        raise ValueError("Run directory already exists; choose a new output directory.")
    if destination.is_relative_to(repo):
        raise ValueError("Keep the run directory outside the candidate checkout.")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Candidate checkout must be clean, including untracked files.")
    if any(line.startswith("160000 ") for line in git(repo, "ls-files", "--stage").splitlines()):
        raise ValueError("Submodules need an explicit host snapshot; this initializer handles one Git tree.")
    revision = git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    tree = git(repo, "rev-parse", "--verify", "HEAD^{tree}")
    base_revision = git(repo, "rev-parse", "--verify", "--end-of-options", base + "^{commit}") if base else None
    workflow_name, required = PROFILES[profile]
    target = {
        "target_kind": "pull-request" if base else "snapshot",
        "repository": str(repo), "candidate_revision": revision, "git_tree": tree,
        "base_revision": base_revision, "objective": goal.strip(),
        "environment": environment.strip(), "profile": profile,
        "required_assessments": list(required),
        "constraints": ["read-only assessment", "no source modification", "no publication"],
    }
    raw_target = (json.dumps(target, indent=2) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw_target).hexdigest()
    subject = {"revision": revision, "input_digest": digest, "environment": environment.strip()}
    run_id = "quality-" + uuid.uuid4().hex[:12]
    observed = (at or now()).isoformat().replace("+00:00", "Z")
    policy = {
        "schema_version": "1.0", "id": "local-quality-" + profile, "grants": [],
        "max_evidence_age_seconds": 3600, "required_artifacts": {},
        "require_independent_review": True, "required_quality_reports": list(required),
    }
    request = {
        "schema_version": "1.0", "artifact_id": run_id + "-request", "artifact_type": "request",
        "producer": {"skill": "manual-input", "version": "1.0.0"},
        "run_id": run_id, "status": "passed", "created_at": observed, "subject": subject,
        "summary": "Assess the pinned candidate: " + goal.strip(),
        "evidence": [{"id": "target", "kind": "input", "uri": "target.json", "sha256": digest,
                      "description": "Host-selected goal, clean Git identity, environment, and required checks."}],
        "checks": [{"id": "candidate-identified", "status": "passed", "evidence": ["target"],
                    "detail": "Recorded a clean local Git candidate; no quality verdict has been produced."}],
        "unresolved": [], "next_action": "Map the pinned candidate and establish assessment criteria.",
        "payload": target,
    }
    run = {
        "schema_version": "1.0", "run_id": run_id, "subject": subject,
        "capabilities": ["workspace.read", "execution.run", "artifact.write"],
        "effect_scopes": {}, "policy": "policy.json", "inputs": {"request": "request.json"},
        "completed": {},
    }
    for value, schema in ((policy, "policy"), (request, "artifact"), (run, "run")):
        validate_schema(value, schema)
    # Detect a normal checkout change during initialization as well as at entry.
    if git(repo, "rev-parse", "HEAD") != revision or git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Candidate changed during initialization; start again from a fixed checkout.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sfstack-init-", dir=destination.parent) as temporary:
        staged = Path(temporary)
        (staged / "target.json").write_bytes(raw_target)
        for name, value in (("request", request), ("policy", policy), ("run", run)):
            write_json(staged / (name + ".json"), value)
        shutil.copyfile(ROOT / "workflows" / (workflow_name + ".json"), staged / "workflow.json")
        plan(staged / "workflow.json", staged / "run.json", at or now())
        os.rename(staged, destination)
    return {"status": "initialized", "run_id": run_id, "checkpoint": str(destination / "run.json"),
            "workflow": str(destination / "workflow.json"), "revision": revision, "profile": profile}


def workflow_for(run, workflow=None):
    selected = Path(workflow) if workflow else Path(run).resolve().parent / "workflow.json"
    if not selected.is_file():
        raise ValueError("Supply --workflow, or use a run directory created by sfstack init.")
    return selected


def display(result):
    """Human-readable output; --json exposes the unchanged machine result."""
    if "assessment" in result:
        report = load_json(result["assessment"])
        payload = report["payload"]
        print("Quality: " + report["status"])
        print("Candidate: " + report["subject"]["revision"])
        print("Evaluated: " + ", ".join(payload["coverage"]["evaluated"]))
        print("Findings: " + str(len(payload["findings"])))
        for finding in payload["findings"]:
            print(f"  {finding['severity']} / {finding['disposition']}: {finding['mechanism']}")
        for item in payload["limitations"]:
            print("  Limit: " + item)
        print("Assessment: " + result["assessment"])
    else:
        print("Status: " + result["status"])
        if "revision" in result:
            print("Candidate: " + result["revision"])
        if "ready" in result:
            print("Ready: " + (", ".join(result["ready"]) or "none"))
        for step, outcomes in result.get("outcomes", {}).items():
            print("  " + step + ": " + ", ".join(f"{kind}={status}" for kind, status in outcomes.items()))
        if not result.get("ready"):
            for step, reasons in result.get("blocked", {}).items():
                print("  " + step + ": " + "; ".join(reasons))
        if result.get("stop_reason"):
            print("Stopped: " + result["stop_reason"])
        if result.get("error"):
            print("Error: " + result["error"])
    if result.get("checkpoint"):
        print("Checkpoint: " + result["checkpoint"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Pin a clean local Git checkout and create a quality run")
    init.add_argument("--repo", required=True)
    init.add_argument("--out", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--environment", required=True, help="Host-owned environment identifier")
    init.add_argument("--profile", choices=PROFILES, default="baseline")
    init.add_argument("--base", help="Exact local base commit for an existing PR checkout")
    status = commands.add_parser("status", help="Show eligible steps and recorded outcomes")
    run = commands.add_parser("run", help="Resume a bounded sequence through a trusted local adapter")
    run.add_argument("--adapter-script", help="Trusted Python adapter; unnecessary for consolidation")
    run.add_argument("--max-steps", type=int, required=True)
    run.add_argument("--timeout", type=int, default=60)
    assess = commands.add_parser("assess", help="Consolidate existing reports into a readable assessment")
    assess.add_argument("--out-dir", default="assessment")
    assess.add_argument("--out-run", default="run-assessed.json")
    for command in (status, run, assess):
        command.add_argument("--run", required=True)
        command.add_argument("--workflow", help="Defaults to workflow.json beside --run")
        command.add_argument("--at", help="Fixed UTC time for fixtures only; live runs use current time")
    for command in (init, status, run, assess):
        command.add_argument("--json", action="store_true", help="Print the machine-readable result")
    args = parser.parse_args(argv)
    try:
        code = 0
        if args.command == "init":
            result = initialize(args.repo, args.out, args.goal, args.environment, args.profile, args.base)
        else:
            workflow = workflow_for(args.run, args.workflow)
            at = now(args.at) if args.at else None
            if args.command == "status":
                result = plan(workflow, args.run, at or now())
                code = 2 if result["status"] == "blocked" else 0
            elif args.command == "run":
                from local_run import run_local
                result = run_local(workflow, args.run, args.adapter_script, at, args.max_steps, args.timeout)
                code = 1 if result["status"] == "error" else 0 if result["status"] == "complete" else 2
                if any(outcome.get("quality-assessment", "passed") != "passed"
                       for outcome in result.get("outcomes", {}).values()):
                    code = 2
            else:
                result = consolidate(workflow, args.run, args.out_dir, at or now(), args.out_run)
                code = 0 if result["status"] == "passed" else 2
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            display(result)
        return code
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"sfstack: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
