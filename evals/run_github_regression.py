#!/usr/bin/env python3
"""Retain a real defective-then-fixed execution through the GitHub quality bridge.

The GitHub PR metadata and positive review are declared fixtures. Candidate
commits, behavioral execution, evidence validation, and quality gates are real.
No GitHub API, Copilot model, or other provider is called by this regression.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from common import load_json, now
from integrations.github import quality


def git(repo, *arguments):
    return subprocess.run([
        "git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
        "-c", "user.name=sfstack fixture", "-c", "user.email=fixture@example.invalid",
        *arguments,
    ], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def exercise(directory, repo, pr, checks, run_id, at):
    directory.mkdir()
    pr_path = directory / "pr.json"
    write_json(pr_path, pr)
    bundle, verification = directory / "inputs", directory / "verification"
    quality.prepare(repo, pr_path, "fixture/inventory", run_id, "1", bundle, at=at, checks=checks)
    quality.verify(repo, bundle, verification, at=at)
    context = directory / "review-context"
    quality.render(bundle, verification, repo, context, at=at)
    response = load_json(context / "review-template.json")
    response.update({
        "status": "passed",
        "summary": "Explicit positive review fixture; no agent reviewed this candidate.",
        "engineering_quality": "Synthetic review input used to test the deterministic quality gate.",
        "limitations": ["No live Copilot review; this fixture deliberately cannot override real test failure."],
    })
    for criterion in response["criteria"]:
        criterion.update({
            "status": "passed", "detail": "Declared positive review fixture, not a measured review result.",
            "evidence": ["candidate-diff", "verification-report"],
        })
    submission = directory / "review-submission.json"
    write_json(submission, {"items": [{"type": "submit_review", "review_json": json.dumps(response)}]})
    result = quality.finalize(bundle, verification, submission, pr_path, "success", directory / "result", at=at)
    report = load_json(verification / "verification-report.json")
    assessment = load_json(result["assessment"])
    observed = report["payload"]["check_results"][0]
    return {
        "head_sha": pr["head"]["sha"], "base_sha": pr["base"]["sha"],
        "verification": report["status"], "quality": result["status"],
        "tests_run": observed["tests_run"], "tests_skipped": observed["tests_skipped"],
        "returncode": observed["returncode"],
        "failed_reports": sum(r["status"] == "failed" for r in assessment["payload"]["reports"]),
        "mutation_authorized": result["mutation_authorized"],
        "assessment": str(Path(result["assessment"]).relative_to(directory.parent)),
        "verification_log": str((verification / "logs/inventory-contract.txt").relative_to(directory.parent)),
    }


def run_regression(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    repo = output / "candidate"
    repo.mkdir()
    git(repo, "init", "--quiet")
    (repo / "README.md").write_text("Known inventory fixture for GitHub bridge regression.\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "--quiet", "-m", "Create fixture base")
    base = git(repo, "rev-parse", "HEAD")
    seed = ROOT / "evals/cases/inventory-boundary"
    defective = (seed / "seed/inventory.py").read_text(encoding="utf-8")
    grader = (seed / "grading/test_inventory.py").read_text(encoding="utf-8")
    grader = grader.replace("Path(os.environ['SFSTACK_CANDIDATE_DIR']).resolve()", "Path.cwd()")
    checks = [{
        "id": "inventory-contract", "kind": "unittest",
        "command": [sys.executable, "-B", "-c", grader],
        "criterion": "All six inventory behaviors execute, including exact-quantity reservations, without skips.",
    }]
    pr = {
        "number": 1, "state": "open", "title": "Add inventory reservations",
        "body": "Declared regression fixture, not a live GitHub pull request.",
        "user": {"login": "fixture-author"},
        "html_url": "https://github.com/fixture/inventory/pull/1",
        "head": {"sha": "", "repo": {"full_name": "fixture/inventory"}},
        "base": {"sha": base, "repo": {"full_name": "fixture/inventory"}},
    }
    at = now()
    results = {}
    for index, variant in enumerate(("defective", "fixed"), start=1):
        source = defective if variant == "defective" else defective.replace("requested >= available", "requested > available")
        (repo / "inventory.py").write_text(source, encoding="utf-8")
        git(repo, "add", "inventory.py")
        git(repo, "commit", "--quiet", "-m", f"Pin {variant} fixture candidate")
        candidate_pr = deepcopy(pr)
        candidate_pr["head"]["sha"] = git(repo, "rev-parse", "HEAD")
        results[variant] = exercise(output / variant, repo, candidate_pr, checks, str(9000 + index), at)
    for variant, expected in (("defective", "failed"), ("fixed", "passed")):
        observed = results[variant]
        if (observed["verification"] != expected or observed["quality"] != expected
                or observed["tests_run"] != 6 or observed["tests_skipped"] != 0
                or observed["mutation_authorized"]):
            raise ValueError(f"{variant}: unexpected GitHub quality result: {observed}")
    if results["defective"]["failed_reports"] < 1 or results["fixed"]["failed_reports"] != 0:
        raise ValueError("The failed verification report must survive until the fixed commit is verified.")
    if results["defective"]["head_sha"] == results["fixed"]["head_sha"]:
        raise ValueError("The repaired candidate must have a new immutable Git identity.")
    summary = {
        "kind": "executed-github-bridge-regression", "cases": results,
        "limits": [
            "No live GitHub check or Copilot model was invoked; PR metadata and positive review are fixtures.",
            "The same retained behavioral checks run against separate real defective and fixed Git commits.",
            "This measures deterministic failure propagation and recovery, not agent defect-detection effectiveness.",
            "The automated pilot policy does not establish independent human approval or authorize a mutation.",
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
        parser.exit(1, f"github-regression: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
