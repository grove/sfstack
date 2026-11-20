#!/usr/bin/env python3
"""Trusted local unittest adapter; execute only code isolated by the host.

The test-plan's python_unittest object pins two directories and required test
IDs. This adapter is deliberately specific to Python's standard unittest runner.
It supplies no sandbox, dependency installation, or reviewer authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

WORKER_ENV_NAMES = frozenset({
    "PATH", "HOME", "USERPROFILE", "LANG", "LANGUAGE", "TZ", "TMPDIR", "TEMP", "TMP",
    "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "VIRTUAL_ENV", "LD_LIBRARY_PATH",
})
WORKER_ENV_PREFIXES = ("LC_", "PYTHON")


def worker_environment():
    """Pass candidate tests only non-credential process basics, never the host's secrets."""
    env = {name: value for name, value in os.environ.items()
           if name in WORKER_ENV_NAMES or name.startswith(WORKER_ENV_PREFIXES)}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from common import contained_path, load_json, read_regular


def snapshot_digest(directory):
    """Hash source filenames/bytes, excluding only top-level .git metadata."""
    directory = Path(directory)
    entries = []
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Snapshot must be a real directory.")
    for path in sorted(directory.rglob("*")):
        if path.relative_to(directory).parts[0] == ".git":
            continue
        if path.is_symlink():
            raise ValueError("Snapshot must not contain symlinks.")
        if path.is_dir():
            continue
        entries.append([path.relative_to(directory).as_posix(),
                        hashlib.sha256(read_regular(path)).hexdigest()])
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def check_revision(candidate, revision, digest):
    """Bind either a content snapshot or a clean Git root to the run subject."""
    if revision == "sha256:" + digest:
        return
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ValueError("Subject revision must identify the snapshot digest or exact Git commit.")

    def git(*arguments):
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", *arguments],
            cwd=candidate, capture_output=True, text=True, timeout=10, check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        if result.returncode:
            raise ValueError("Candidate Git identity could not be established.")
        return result.stdout.strip()

    if Path(git("rev-parse", "--show-toplevel")).resolve() != candidate.resolve():
        raise ValueError("Candidate must be the Git checkout root.")
    if git("rev-parse", "HEAD") != revision:
        raise ValueError("Candidate HEAD differs from the subject revision.")
    if git("status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"):
        raise ValueError("Candidate Git checkout must be clean.")


def worker(candidate, tests, output):
    """Child process owns imports/execution; JSON counts accompany the raw log."""
    # discover() prepends its top-level directory only when it is absent.
    # Register it first so test helpers cannot shadow the pinned candidate.
    sys.path.insert(0, str(tests))
    sys.path.insert(0, str(candidate))
    os.environ["SFSTACK_CANDIDATE_DIR"] = str(candidate)
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests))

    class Result(unittest.TextTestResult):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.executed = []
            self.failed_ids = set()
            self.suite_errors = []

        def startTest(self, test):
            # unittest represents import/discovery errors as synthetic tests.
            # Their error is real, but no candidate test actually executed.
            if not isinstance(test, unittest.loader._FailedTest):
                self.executed.append(test.id())
            super().startTest(test)

        def addFailure(self, test, err):
            self.failed_ids.add(test.id())
            super().addFailure(test, err)

        def addError(self, test, err):
            if test.id() in self.executed:
                self.failed_ids.add(test.id())
            else:
                self.suite_errors.append({"location": test.id(), "detail": str(err[1])})
            super().addError(test, err)

        def addUnexpectedSuccess(self, test):
            self.failed_ids.add(test.id())
            super().addUnexpectedSuccess(test)

        def addSubTest(self, test, subtest, err):
            if err is not None:
                self.failed_ids.add(test.id())
            super().addSubTest(test, subtest, err)

    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    Path(output).write_text(json.dumps({
        "executed": result.executed,
        "failed": sorted(result.failed_ids),
        "skipped": [test.id() for test, _ in result.skipped],
        "expected_failures": [test.id() for test, _ in result.expectedFailures],
        "discovery_errors": loader.errors,
        "suite_errors": result.suite_errors,
    }, indent=2) + "\n", encoding="utf-8")


def verify(invocation_path, output_path):
    invocation, output = load_json(invocation_path), Path(output_path)
    if invocation["skill"] != "sf-verify-change" or invocation["output_type"] != "verification-report":
        raise ValueError("This adapter only executes sf-verify-change.")
    plan_path = Path(invocation["bindings"]["test-plan"])
    config = load_json(plan_path)["payload"]["python_unittest"]
    candidate = contained_path(plan_path.parent, config["candidate_dir"])
    tests = contained_path(plan_path.parent, config["tests_dir"])
    required = config["required_tests"]
    if (not isinstance(required, list) or not required
            or any(not isinstance(item, str) or not item.strip() for item in required)
            or len(set(required)) != len(required)):
        raise ValueError("required_tests must contain unique explicit unittest IDs.")
    timeout = config.get("timeout_seconds", 30)
    if type(timeout) is not int or not 1 <= timeout <= 240:
        raise ValueError("timeout_seconds must be between 1 and 240.")
    before = [snapshot_digest(candidate), snapshot_digest(tests)]
    if before != [config["candidate_sha256"], config["tests_sha256"]]:
        raise ValueError("Candidate or test snapshot digest differs from the pinned test plan.")
    check_revision(candidate, invocation["subject"]["revision"], before[0])

    logs = output.parent / "evidence"
    logs.mkdir()
    counts = logs / "counts.json"
    timed_out = False
    with (logs / "stdout.txt").open("wb") as stdout, (logs / "stderr.txt").open("wb") as stderr:
        try:
            completed = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).resolve()), "--worker",
                 str(candidate), str(tests), str(counts)],
                cwd=candidate, stdout=stdout, stderr=stderr,
                timeout=timeout, check=False,
                env=worker_environment(),
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            completed = None
    missing_runner = timed_out or completed.returncode != 0 or not counts.is_file()
    data = (load_json(counts) if not missing_runner else
            {"executed": [], "failed": [], "skipped": [], "expected_failures": [],
             "discovery_errors": ["Runner timed out or exited without complete results."],
             "suite_errors": []})
    missing = sorted(set(required) - set(data["executed"]))
    skipped = sorted(set(data["skipped"] + data["expected_failures"] + missing))
    changed = before != [snapshot_digest(candidate), snapshot_digest(tests)]
    try:
        check_revision(candidate, invocation["subject"]["revision"], before[0])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        changed = True
    incomplete = bool(skipped or data["discovery_errors"] or data["suite_errors"] or changed or missing_runner)
    status = "failed" if data["failed"] else "inconclusive" if incomplete else "passed"
    limitations = []
    if incomplete:
        limitations.append("Required tests were missing, skipped, incomplete, or the pinned inputs changed.")
    if data["failed"]:
        limitations.append("Observed failing tests: " + ", ".join(data["failed"]))
    if data["suite_errors"] or data["discovery_errors"]:
        limitations.append("Test discovery or suite setup/teardown failed; inspect retained runner errors.")
    # Always retain the complete runner result, including failed/empty discovery.
    counts.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    evidence = [{
        "id": name, "kind": "test", "uri": f"evidence/{filename}",
        "sha256": hashlib.sha256(read_regular(logs / filename)).hexdigest(),
        "description": f"Actual unittest subprocess {name}; no agent judgment is implied.",
    } for name, filename in (("counts", "counts.json"), ("stdout", "stdout.txt"), ("stderr", "stderr.txt"))]
    findings = [{
        "id": f"test-failure-{index}", "blocking": True, "disposition": "open",
        "severity": "unspecified", "location": test,
        "mechanism": "The executed behavioral assertion failed.",
        "impact": "The pinned candidate does not satisfy this test's expected behavior.",
        "evidence": ["counts", "stderr"],
    } for index, test in enumerate(data["failed"], start=1)]
    report = {
        "schema_version": "1.0", "artifact_id": f"unittest-{invocation['run_id']}",
        "artifact_type": "verification-report",
        "producer": {"skill": invocation["skill"], "version": invocation["contract"]["version"]},
        "run_id": invocation["run_id"], "subject": invocation["subject"],
        "created_at": invocation["observed_at"], "status": status,
        "summary": f"Unittest {status}: {len(data['executed'])} run, {len(data['failed'])} failed.",
        "evidence": evidence,
        "checks": [{"id": "required-tests", "status": status,
                    "evidence": ["counts", "stdout", "stderr"],
                    "detail": "All required test IDs must execute without failures or skips on unchanged inputs."}],
        "unresolved": limitations,
        "next_action": "none" if status == "passed" else "Inspect retained test results; remediation requires separate authorization.",
        "payload": {"required_count": len(required), "executed_count": len(data["executed"]),
                    "failed_count": len(data["failed"]), "skipped_required": skipped,
                    "suite_errors": data["suite_errors"], "discovery_errors": data["discovery_errors"],
                    "findings": findings, "runner": "python-unittest",
                    "candidate_sha256": before[0], "tests_sha256": before[1]},
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--invocation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        verify(args.invocation, args.output)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"python-unittest: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
