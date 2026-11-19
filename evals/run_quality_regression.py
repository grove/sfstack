#!/usr/bin/env python3
"""Exercise real verification and negative quality handoffs on disposable fixtures.

This is a regression of tooling, not a comparative agent-quality experiment.
Planning and review records are explicit fixture inputs; only tests execute.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "examples" / "adapters"))
from common import contracts, inspect_artifact, load_json, now
from local_slice import run_one
from python_unittest import snapshot_digest
from quality_report import consolidate

REQUIRED_TESTS = [f"test_inventory.InventoryContract.test_{name}"
                  for name in ("partial", "exact", "excess", "empty", "zero", "negative")]
WORKFLOW = ROOT / "workflows" / "quality.json"
ADAPTER = ROOT / "examples" / "adapters" / "python_unittest.py"


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def prepare_case(directory, variant, at):
    """Create a pinned, disposable candidate plus explicit prerequisite fixtures."""
    directory = Path(directory)
    directory.mkdir(parents=True)
    records = directory / "records"
    records.mkdir()
    candidate, tests = records / "candidate", records / "tests"
    candidate.mkdir()
    tests.mkdir()
    seed = ROOT / "evals" / "cases" / "inventory-boundary"
    source = (seed / "seed" / "inventory.py").read_text(encoding="utf-8")
    if variant != "boundary":
        source = source.replace("requested >= available", "requested > available")
    (candidate / "inventory.py").write_text(source, encoding="utf-8")
    if variant != "empty":
        grader = (seed / "grading" / "test_inventory.py").read_text(encoding="utf-8")
        if variant == "skipped":
            grader = grader.replace("    def test_exact(self):",
                                    "    @unittest.skip('seeded missing check')\n    def test_exact(self):")
        (tests / "test_inventory.py").write_text(grader, encoding="utf-8")
    config = {
        "candidate_dir": "candidate", "tests_dir": "tests",
        "candidate_sha256": snapshot_digest(candidate),
        "tests_sha256": snapshot_digest(tests), "required_tests": REQUIRED_TESTS,
        "timeout_seconds": 20,
    }
    subject = {
        "revision": "sha256:" + config["candidate_sha256"],
        "input_digest": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "environment": f"regression-{platform.system()}-{platform.python_implementation()}-{platform.python_version()}",
    }
    run_id = f"quality-regression-{variant}"
    fixture = ("Planning and review are declared test harness inputs, not outputs from a live agent.\n"
               "Verification runs the retained inventory behavior checks on a pinned disposable copy.\n")
    (records / "fixture.txt").write_text(fixture, encoding="utf-8")
    evidence = {"id": "fixture", "kind": "input", "uri": "fixture.txt",
                "sha256": hashlib.sha256(fixture.encode()).hexdigest(),
                "description": "Explicit scope and limits of the regression scaffolding."}
    catalog = contracts()

    def artifact(kind, skill, payload):
        record = {
            "schema_version": "1.0", "artifact_id": f"fixture-{kind}", "artifact_type": kind,
            "producer": {"skill": skill, "version": catalog[skill]["version"] if skill in catalog else "1.0.0"},
            "run_id": run_id, "subject": subject, "status": "passed",
            "created_at": at.isoformat().replace("+00:00", "Z"),
            "summary": f"Declared regression fixture: {kind}; not an independent agent assessment.",
            "evidence": [evidence],
            "checks": [{"id": "fixture-input", "status": "passed", "evidence": ["fixture"],
                        "detail": "Fixture input supplied by the regression harness."}],
            "unresolved": ["Planning and review are fixture inputs; independent review is not authenticated."],
            "next_action": "Inspect real verification separately from fixture scaffolding.", "payload": payload,
        }
        path = records / f"{kind}.json"
        write_json(path, record)
        return str(path.relative_to(directory))

    request = artifact("request", "manual-input", {
        "required_assessments": ["verification-report", "review-report", "impact-assessment"],
        "objective": "Exercise the fixed six inventory behavior criteria without changing the candidate.",
    })
    completed = {}
    for step, kind, skill, payload in (
        ("orient", "project-context", "sf-map-project", {"entry_points": ["inventory.reserve"]}),
        ("clarify", "outcome-brief", "sf-clarify-outcome", {"goal": "Assess the six inventory assertions."}),
        ("specify", "specification", "sf-write-specification", {"requirements": REQUIRED_TESTS}),
        ("scope", "change-set", "sf-scope-candidate", {
            "target_kind": "snapshot", "candidate_revision": subject["revision"],
            "base_revision": None, "source_reference": "sfstack/evals/cases/inventory-boundary",
            "read_only": True,
        }),
        ("tests", "test-plan", "sf-design-tests", {"python_unittest": config}),
        ("impact", "impact-assessment", "sf-assess-impact", {"findings": []}),
        ("review", "review-report", "sf-review-change", {
            "reviewer": "fixture-reviewer", "change_author": "fixture-author",
            "independence_basis": "Declared scaffolding only; identities are not authenticated.",
            "findings": [],
        }),
    ):
        completed[step] = [artifact(kind, skill, payload)]
    # Review is attached after verification, as an explicitly declared fixture.
    review_path = completed.pop("review")[0]
    write_json(directory / "policy.json", {
        "schema_version": "1.0", "id": "regression-read-only", "grants": [],
        "max_evidence_age_seconds": 3600, "required_artifacts": {},
        "require_independent_review": True,
    })
    manifest = {
        "schema_version": "1.0", "run_id": run_id, "subject": subject,
        "capabilities": ["workspace.read", "execution.run", "artifact.write"],
        "effect_scopes": {}, "policy": "policy.json", "inputs": {"request": request},
        "completed": completed,
    }
    write_json(directory / "run.json", manifest)
    return directory / "run.json", review_path


def exercise(directory, variant, at):
    run_path, review_path = prepare_case(directory, variant, at)
    result = run_one(WORKFLOW, run_path, "verify", ADAPTER,
                     "after-verify.json", "verification", at)
    verification = load_json(result["artifact"])
    checkpoint = load_json(result["checkpoint"])
    checkpoint["completed"]["review"] = [review_path]
    write_json(Path(directory) / "after-review.json", checkpoint)
    quality = consolidate(WORKFLOW, Path(directory) / "after-review.json", "quality", at)
    assessment = load_json(quality["assessment"])
    return {
        "verification": verification["status"], "quality": quality["status"],
        "executed_count": verification["payload"]["executed_count"],
        "failed_count": verification["payload"]["failed_count"],
        "skipped_required": verification["payload"]["skipped_required"],
        "findings": len(assessment["payload"]["findings"]),
        "assessment": str(Path(quality["assessment"]).relative_to(Path(directory).parent)),
    }


def run_regression(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    at = now()
    results = {variant: exercise(output / variant, variant, at)
               for variant in ("boundary", "fixed", "skipped", "empty")}
    expected = {"boundary": ("failed", "failed", 6, 1),
                "fixed": ("passed", "inconclusive", 6, 0),
                "skipped": ("inconclusive", "inconclusive", 6, 0),
                "empty": ("inconclusive", "inconclusive", 0, 0)}
    for variant, values in expected.items():
        got = results[variant]
        actual = tuple(got[key] for key in ("verification", "quality", "executed_count", "failed_count"))
        if actual != values:
            raise ValueError(f"{variant}: expected {values}, observed {actual}")
    if results["boundary"]["findings"] != 1:
        raise ValueError("The observed failing test was lost during quality consolidation.")
    report_path = output / "fixed" / "verification" / "result.json"
    record = load_json(report_path)
    stale = {**record["subject"], "revision": "sha256:" + "0" * 64}
    _, stale_errors = inspect_artifact(report_path, stale, record["run_id"], at, 3600)
    tampered = output / "tampered-verification"
    shutil.copytree(report_path.parent, tampered)
    (tampered / "evidence" / "stderr.txt").write_text("changed after verification\n", encoding="utf-8")
    _, tamper_errors = inspect_artifact(tampered / "result.json", record["subject"], record["run_id"], at, 3600)
    if not any("stale subject" in message for message in stale_errors):
        raise ValueError("Stale evidence was accepted.")
    if not any("digest mismatch" in message for message in tamper_errors):
        raise ValueError("Modified evidence was accepted.")
    summary = {
        "kind": "executed-tooling-regression", "cases": results,
        "stale_evidence_rejected": True, "tampered_evidence_rejected": True,
        "limits": ["No live agent or provider was invoked; no comparative effectiveness claim.",
                   "Prerequisite planning and review are declared fixtures.",
                   "The fixed candidate's quality verdict remains inconclusive without authenticated independent review.",
                   "Subprocess execution is not a sandbox; these known fixtures require no external access."],
    }
    write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New directory for retained evidence")
    args = parser.parse_args()
    try:
        summary = run_regression(args.output)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"quality-regression: {exc}\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
