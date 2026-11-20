"""Fail-closed RED/GREEN evidence for the opt-in GitHub defect-repair path.

All commands are selected by the trusted host, never by the agent or issue.
This Python unittest runner is an integration adapter, not a core skill dependency.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from common import inspect_artifact, load_json, read_regular
from integrations.github import quality

FIELDS = ("symptom", "expected_behavior", "reproduction", "causal_mechanism",
          "repair_direction", "regression_check")
LIST_FIELDS = ("observations", "hypotheses", "experiments")


def configuration(mode, regression_file, selected, files):
    if mode not in {"change", "defect"}:
        raise ValueError("Unknown Software Factory mode.")
    if mode == "change":
        if regression_file:
            raise ValueError("A regression file is only accepted in defect mode.")
        return {"mode": mode, "regression_file": None}
    if (not isinstance(regression_file, str)
            or not re.fullmatch(r"tests/test_[a-z0-9_]+\.py", regression_file)
            or regression_file not in selected
            or files[regression_file]["blob_sha"] is not None):
        raise ValueError("Defect mode needs one selected, NEW tests/test_*.py regression file.")
    if not any(p.startswith("examples/") for p in selected):
        raise ValueError("Defect mode requires an explicitly selected examples/ implementation file.")
    if any(p.startswith("tests/") and p != regression_file for p in selected):
        raise ValueError("Only the new regression file may be selected under tests/ in defect mode.")
    return {"mode": mode, "regression_file": regression_file}


def check(target):
    # The filename is validated at admission and is not interpreted by a shell.
    return {"id": "defect-regression", "kind": "unittest",
            "command": ["python", "-B", "-m", "unittest", "discover", "-s", "tests",
                        "-p", Path(target["regression_file"]).name, "-v"],
            "criterion": "The new test must fail with a real assertion on the base and pass on the repair."}


def validate_response(response, target):
    if target["mode"] != "defect":
        if "diagnosis" in response:
            raise ValueError("Unrequested diagnosis in change mode.")
        return
    # A negative submission reports inability to diagnose or repair and must
    # remain publish-blocked, not be turned into an invalid positive envelope.
    if response["status"] != "passed":
        return
    record = response.get("diagnosis")
    if (not isinstance(record, dict) or set(record) != set(FIELDS + LIST_FIELDS)
            or any(not isinstance(record.get(k), str) or not record[k].strip() for k in FIELDS)
            or any(not isinstance(record.get(k), list) or not record[k]
                   or any(not isinstance(v, str) or not v.strip() for v in record[k])
                   for k in LIST_FIELDS)):
        raise ValueError("Defect repair requires a complete sf-diagnose-defect record.")
    paths = {item["path"] for item in response["edits"]}
    if (target["regression_file"] not in paths
            or not any(path.startswith("examples/") for path in paths)
            or any(path.startswith("tests/") and path != target["regression_file"] for path in paths)):
        raise ValueError("Defect repair must submit the new regression and a scoped implementation fix.")


def passed(result):
    return (result["status"] == "passed" and result["executed"] is True
            and result["returncode"] == 0
            and (result["kind"] != "unittest"
                 or type(result["tests_run"]) is int and result["tests_run"] >= 1
                 and result["tests_skipped"] == 0 and result["expected_failures"] == 0))


def red_assertion(result, log):
    if (result["status"] != "failed" or result["executed"] is not True
            or result["returncode"] in (None, 0) or not isinstance(result["tests_run"], int)
            or result["tests_run"] < 1 or result["tests_skipped"] or result["expected_failures"]):
        return False
    text = read_regular(log).decode("utf-8", "replace")
    summaries = re.findall(r"^FAILED \(([^\r\n)]*)\)$", text, re.MULTILINE)
    if len(summaries) != 1:
        return False
    failures = re.findall(r"\bfailures=(\d+)", summaries[0])
    errors = re.findall(r"\berrors=(\d+)", summaries[0])
    return len(failures) == 1 and int(failures[0]) > 0 and (not errors or int(errors[0]) == 0)


def reproduce(repo, target, response, output):
    """Run baseline suite, install ONLY the new test, and demand genuine RED."""
    from integrations.github import software

    report = {"status": "blocked", "regression_file": target["regression_file"],
              "base_sha": target["base_sha"], "baseline": [], "red": None,
              "red_head_sha": None, "reason": None}
    for selected in target["checks"]:
        log = output / "logs" / ("baseline-" + selected["id"] + ".txt")
        report["baseline"].append(quality.run_check(selected, repo, log))
        quality.check_candidate(repo, target["base_sha"])
    if not all(passed(r) for r in report["baseline"]):
        report["reason"] = "The existing suite must pass on the unmodified base before adding the regression."
        return report
    regression = next(e for e in response["edits"] if e["path"] == target["regression_file"])
    red_candidate, patch = software.candidate_record(repo, target, [regression])
    (output / "red.patch").write_bytes(patch)
    report["red_head_sha"] = red_candidate["head_sha"]
    path = repo / regression["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(regression["content"], encoding="utf-8")
    software.git(repo, "reset", "--mixed", red_candidate["head_sha"])
    quality.check_candidate(repo, red_candidate["head_sha"])
    log = output / "logs/red-regression.txt"
    report["red"] = quality.run_check(check(target), repo, log)
    quality.check_candidate(repo, red_candidate["head_sha"])
    software.git(repo, "reset", "--hard", target["base_sha"])
    quality.check_candidate(repo, target["base_sha"])
    if not red_assertion(report["red"], log):
        report["reason"] = "RED must be an executed assertion failure, not a pass, import error, skip, or empty test."
        report["status"] = "failed"
        return report
    report["status"] = "passed"
    return report


def green(repo, target, candidate, output):
    log = output / "logs/green-regression.txt"
    result = quality.run_check(check(target), repo, log)
    quality.check_candidate(repo, candidate["head_sha"])
    return result


def log_digests(output):
    return {p.name: quality.digest(p) for p in sorted((output / "logs").glob("*.txt"))}


def retain_negative(output, report):
    quality.write_json(output / "defect-evidence.json", {
        **report, "logs": log_digests(output), "quality_requested": False, "merge_authorized": False})
    gate = {"status": report["status"], "passed": False, "mode": "defect",
            "reasons": [report["reason"] or "Defect reproduction was blocked."],
            "merge_authorized": False}
    quality.write_json(output / "gate.json", gate)
    (output / "summary.md").write_text(
        "# sfstack defect repair\n\n**Verdict: " + report["status"] +
        "**\n\n" + gate["reasons"][0] + "\n\nNo draft PR was authorized.\n", encoding="utf-8")
    return gate


def finalize(output, run, target, response, candidate, preflight, after, observed):
    record = {**preflight, "candidate_sha": candidate["head_sha"], "green": after,
              "status": "passed" if passed(after) else "failed", "logs": log_digests(output),
              "quality_requested": False, "merge_authorized": False}
    quality.write_json(output / "defect-evidence.json", record)
    proof = [quality.evidence(output / "red.patch", "red-test-only-diff", "diff"),
             quality.evidence(output / "logs/red-regression.txt", "red-regression", "test",
                              "logs/red-regression.txt"),
             quality.evidence(output / "logs/green-regression.txt", "green-regression", "test",
                              "logs/green-regression.txt")]
    diagnosis = quality.artifact(run, "diagnosis", "sf-diagnose-defect", record["status"],
        {"agent_report": response["diagnosis"], "base_revision": target["base_sha"],
         "regression_only_revision": preflight["red_head_sha"],
         "candidate_revision": candidate["head_sha"], "regression_file": target["regression_file"],
         "qualification": "The host independently observes RED and GREEN. Causal explanation and experiments are agent claims requiring human review."},
        proof, [{"id": "red-regression", "status": "passed", "evidence": ["red-regression"],
                 "detail": "Host observed a genuine failing assertion before the implementation fix."},
                {"id": "green-regression", "status": record["status"], "evidence": ["green-regression"],
                 "detail": "Host reran the same test on the complete proposed candidate."}], observed)
    quality.write_json(output / "diagnosis.json", diagnosis)
    return record


def validate_evidence(repo, target, candidate, response, output, run, at, max_age):
    from integrations.github import software

    record = load_json(output / "defect-evidence.json")
    red_candidate, red_patch = software.candidate_record(repo, target, [
        next(e for e in response["edits"] if e["path"] == target["regression_file"])])
    if (record.get("status") != "passed" or record.get("base_sha") != target["base_sha"]
            or record.get("candidate_sha") != candidate["head_sha"]
            or record.get("regression_file") != target["regression_file"]
            or record.get("red_head_sha") != red_candidate["head_sha"]
            or read_regular(output / "red.patch") != red_patch
            or record.get("reason") is not None
            or record.get("quality_requested") is not False
            or record.get("merge_authorized") is not False):
        raise ValueError("Defect evidence does not describe this immutable candidate.")
    baseline = record.get("baseline", [])
    if (len(baseline) != len(target["checks"])
            or any(r.get("id") != c["id"] or r.get("kind") != c["kind"]
                   or r.get("command") != c["command"] or not passed(r)
                   for r, c in zip(baseline, target["checks"]))):
        raise ValueError("Baseline suite has incomplete or negative evidence.")
    for phase in ("red", "green"):
        actual = record.get(phase)
        selected = check(target)
        if (not isinstance(actual, dict)
                or any(actual.get(k) != selected[k] for k in ("id", "kind", "command"))):
            raise ValueError("Regression command was changed or missing.")
    if (not red_assertion(record["red"], output / "logs/red-regression.txt")
            or not passed(record["green"])):
        raise ValueError("The same regression was not RED then GREEN.")
    expected_logs = {"baseline-" + c["id"] + ".txt" for c in target["checks"]}
    expected_logs.update({"red-regression.txt", "green-regression.txt"})
    # The GREEN candidate's whole-host-suite logs are part of the retained proof,
    # not extras that should invalidate a successful run.
    expected_logs.update({c["id"] + ".txt" for c in target["checks"]})
    if (set(record.get("logs", {})) != expected_logs
            or any(quality.digest(output / "logs" / name) != record["logs"][name]
                   for name in expected_logs)):
        raise ValueError("Defect logs were omitted or changed.")
    diagnosis, problems = inspect_artifact(output / "diagnosis.json", run["subject"], run["run_id"],
                                           at, max_age, "diagnosis")
    if (problems or diagnosis.get("producer") != {"skill": "sf-diagnose-defect", "version": "1.0.0"}
            or diagnosis["payload"].get("agent_report") != response["diagnosis"]
            or diagnosis["payload"].get("candidate_revision") != candidate["head_sha"]):
        raise ValueError("Diagnosis artifact is missing, stale, or inconsistent.")
    return record


def pr_section(target, record):
    check_cmd = " ".join(check(target)["command"])
    return ["## Defect repair (independent RED → GREEN)", "",
            f"- New regression: `{target['regression_file']}`",
            f"- Host-selected command: `{check_cmd}`",
            f"- Test-only revision: `{record['red_head_sha']}` (RED: {record['red']['tests_run']} executed; assertion failure)",
            f"- Repaired revision: `{record['candidate_sha']}` (GREEN: {record['green']['tests_run']} executed; passed)",
            "- Previously existing baseline checks passed before the new test was applied.",
            "- Full host check plan passed on the repaired revision.",
            "- Retained evidence includes baseline, RED, GREEN, full-suite logs, the test-only diff, and an agent-supplied diagnosis.",
            "- The causal explanation is not independently attested; Quality Factory and human review must assess it.", ""]
