#!/usr/bin/env python3
"""Retain actual subprocess RED/GREEN evidence from a bounded defect repair.

The issue, diagnosis and implementation proposal are declared fixtures. Python
unittest commands, Git object construction, log retention and gates are real.
No model, GitHub API, approval, or merge occurs in this local evaluation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from common import load_json
from test_github_defect import DefectRepairTests, REGRESSION_TEST


def one_case(directory, variant):
    fixture = DefectRepairTests("test_real_defect_is_red_then_green_before_draft_and_quality_dispatch")
    fixture.setUp()
    started = perf_counter()
    try:
        fixture.prepare_defect()
        if variant == "unfixed":
            fixture.propose(source="# Not a repair.\n" + fixture.source)
        elif variant == "unreproduced":
            fixture.propose(regression=REGRESSION_TEST.replace(
                "self.assertEqual(0, reserve(5, 5))", "self.assertEqual(3, reserve(5, 2))"))
        elif variant == "repaired":
            fixture.propose()
        else:
            raise ValueError("Unknown evaluation variant")
        gate = fixture.verify()
        proof = load_json(fixture.result / "defect-evidence.json")
        if (gate["passed"] != (variant == "repaired")
                or (variant == "repaired" and not (
                    proof["red"]["status"] == "failed" and proof["green"]["status"] == "passed"))
                or (variant == "unreproduced" and proof["status"] != "failed")
                or (variant == "unfixed" and proof["green"]["status"] != "failed")):
            raise ValueError(f"Unexpected evaluated {variant} verdict: {gate}")
        directory.mkdir()
        shutil.copytree(fixture.bundle, directory / "inputs")
        shutil.copytree(fixture.result, directory / "result")
        shutil.copyfile(fixture.submission, directory / "submission.json")
        return {
            "status": gate["status"], "passed": gate["passed"],
            "base_sha": proof["base_sha"], "red_head_sha": proof["red_head_sha"],
            "candidate_sha": proof.get("candidate_sha"),
            "baseline": [{"id": r["id"], "status": r["status"], "tests": r["tests_run"]}
                         for r in proof["baseline"]],
            "red": ({"status": proof["red"]["status"], "tests": proof["red"]["tests_run"]}
                    if proof["red"] else None),
            "green": ({"status": proof["green"]["status"], "tests": proof["green"]["tests_run"]}
                      if proof.get("green") else None),
            "host_log_paths": sorted("result/logs/" + k for k in proof["logs"]),
            "evidence": "result/defect-evidence.json",
            "duration_seconds": round(perf_counter() - started, 3),
        }
    finally:
        fixture.doCleanups()


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    cases = {variant: one_case(output / variant, variant)
             for variant in ("repaired", "unfixed", "unreproduced")}
    base = {item["base_sha"] for item in cases.values()}
    if len(base) != 1:
        # Test fixtures include environment-dependent timestamped commit
        # identities; invariant is per-run baseline vs RED ancestry instead.
        raise ValueError("Expected common initial fixture revision.")
    summary = {
        "kind": "executed-software-defect-repair-regression",
        "cases": cases,
        "total_duration_seconds": round(perf_counter() - started, 3),
        "limits": [
            "All behavior checks and Git candidate reconstructions really execute.",
            "Diagnosis and implementation submissions are explicit fixture data, not results from a model.",
            "Mock GitHub publishing is covered by unit tests; this evaluation performs no remote API calls.",
            "Normal CI subprocesses are not an adversarial-code sandbox.",
            "Model tokens, billed cost, live GitHub latency and human reviewer time are not measured."
        ]
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New directory to retain evidence")
    args = parser.parse_args()
    try:
        result = run(args.output)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.exit(1, f"defect-regression: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
