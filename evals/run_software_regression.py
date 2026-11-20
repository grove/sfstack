#!/usr/bin/env python3
"""Retain a failing-then-fixed execution through the GitHub software factory.

Issue metadata and builder submissions are explicit fixtures. The selected skill
invocation, exact-file application, Git candidates, host behavioral execution,
and verification evidence are real. No GitHub API or model is called here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from common import load_json, now
from integrations.github import software


def git(repo, *arguments):
    return subprocess.run([
        "git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
        "-c", "user.name=sfstack fixture", "-c", "user.email=fixture@example.invalid",
        *arguments,
    ], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def exercise(directory, repo, issue, checks, run_id, source, at):
    directory.mkdir()
    bundle, context, result_path = directory / "inputs", directory / "context", directory / "result"
    software.prepare(
        repo, issue, "fixture/inventory", str(run_id), "1", ["examples/inventory.py"],
        ["Exact-quantity reservations succeed and leave zero units.",
         "Partial, excessive, empty-stock, zero, and negative requests retain their documented behavior."],
        bundle, at=at, checks=checks,
    )
    software.render(bundle, repo, context, at=at)
    response = load_json(context / "change-template.json")
    response.update({
        "status": "passed", "summary": "Explicit optimistic builder fixture, not an agent's result.",
        "criteria_addressed": [c["id"] for c in load_json(bundle / "target.json")["criteria"]],
        "behavior_changes": ["Candidate claims to permit exact-quantity reservations."],
        "checks_run": [{
            "command": "Declared fixture; no agent command was run.",
            "observed": "Synthetic positive claim intentionally cannot override fresh host observations.",
        }],
        "remaining_work": [],
        "edits": [{"path": "examples/inventory.py", "content": source}],
    })
    submission = directory / "submission.json"
    raw = json.dumps(response)
    write_json(submission, {"items": [{"type": "submit_change",
                                     "change_json": raw,
                                     "change_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}]})
    result = software.verify(repo, bundle, submission, "success", result_path, at=at)
    candidate = load_json(result_path / "candidate.json")
    report = load_json(result_path / "verification-report.json")
    observed = report["payload"]["check_results"][0]
    return {
        "base_sha": candidate["base_sha"], "candidate_sha": candidate["head_sha"],
        "verification": report["status"], "gate": result["status"], "passed": result["passed"],
        "tests_run": observed["tests_run"], "tests_skipped": observed["tests_skipped"],
        "returncode": observed["returncode"],
        "verification_report": str((result_path / "verification-report.json").relative_to(directory.parent)),
        "verification_log": str((result_path / "logs/inventory-contract.txt").relative_to(directory.parent)),
        "candidate_manifest": str((result_path / "candidate.json").relative_to(directory.parent)),
    }


def run_regression(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    repo = output / "candidate"
    (repo / "examples").mkdir(parents=True)
    git(repo, "init", "--quiet")
    seed = ROOT / "evals/cases/inventory-boundary"
    defective = (seed / "seed/inventory.py").read_text(encoding="utf-8")
    (repo / "examples/inventory.py").write_text(defective, encoding="utf-8")
    git(repo, "add", "examples/inventory.py")
    git(repo, "commit", "--quiet", "-m", "Pin the reported inventory defect")
    base = git(repo, "rev-parse", "HEAD")
    grader = (seed / "grading/test_inventory.py").read_text(encoding="utf-8")
    grader = grader.replace("Path(os.environ['SFSTACK_CANDIDATE_DIR']).resolve()", "(Path.cwd() / 'examples')")
    checks = [{
        "id": "inventory-contract", "kind": "unittest",
        "command": [sys.executable, "-B", "-c", grader],
        "criterion": "Six independently supplied reservation behaviors execute without skips.",
    }]
    issue = {
        "number": 1, "state": "open", "title": "Allow reservations equal to the available stock",
        "body": "reserve(5, 5) should return zero; the current candidate rejects it.",
        "updated_at": "2026-11-19T12:00:00Z",
        "html_url": "https://github.com/fixture/inventory/issues/1",
    }
    results, at = {}, now()
    for index, variant in enumerate(("unfixed", "fixed"), start=1):
        git(repo, "checkout", "--quiet", "--detach", base)
        # A changed comment alone is an intentionally insufficient proposal;
        # avoid a no-op so both candidates reach the actual execution gate.
        source = "# Reservation behavior proposed for review.\n" + defective
        if variant == "fixed":
            source = source.replace("requested >= available", "requested > available")
        results[variant] = exercise(output / variant, repo, issue, checks, 9200 + index, source, at)
    for variant, expected in (("unfixed", "failed"), ("fixed", "passed")):
        observed = results[variant]
        if (observed["gate"] != expected or observed["verification"] != expected
                or observed["passed"] != (expected == "passed")
                or observed["tests_run"] != 6 or observed["tests_skipped"] != 0
                or observed["base_sha"] != base):
            raise ValueError(f"Unexpected {variant} software result: {observed}")
    if results["unfixed"]["candidate_sha"] == results["fixed"]["candidate_sha"]:
        raise ValueError("The repaired candidate must have a different immutable identity.")
    summary = {
        "kind": "executed-github-software-regression", "cases": results,
        "limits": [
            "Issue metadata and optimistic builder submissions are fixtures; no Copilot agent ran.",
            "The same retained behavioral checks execute against distinct real unfixed and fixed Git candidates.",
            "This validates deterministic application and failure propagation, not model implementation ability.",
            "No remote branch, pull request, GitHub quality check, approval, or merge was created.",
            "Ordinary subprocess execution is not a hostile-code sandbox; these are known local fixtures.",
        ],
    }
    write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New directory for retained evidence")
    args = parser.parse_args()
    try:
        result = run_regression(args.output)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"software-regression: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
