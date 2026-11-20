"""External host fixture: only stdlib and an installed CLI, never sfstack imports."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys


CLI = Path(sys.argv[1]).resolve()
AT = "2026-11-19T12:00:00Z"
REQUEST = Path("examples/gate-request.json")
POLICY = Path("examples/policy.json")
VERIFICATION = Path("examples/records/verification-report.json")
REVIEW = Path("examples/records/review-report.json")
KEYS = {"interface_version", "distribution_version", "operation", "status", "result", "errors"}


def invoke(operation, arguments=(), expected=0, status="passed"):
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    finished = subprocess.run(
        [str(CLI), operation, *map(str, arguments)], check=False,
        capture_output=True, text=True, timeout=60, env=environment,
    )
    assert finished.returncode == expected, (operation, finished.returncode, finished.stdout, finished.stderr)
    assert finished.stdout.count("\n") == 1, finished.stdout
    reply = json.loads(finished.stdout)
    assert set(reply) == KEYS, reply
    assert reply["interface_version"] == "1.0", reply
    assert reply["distribution_version"] == "1.0.0", reply
    assert reply["operation"] == operation, reply
    assert reply["status"] == status, reply
    assert isinstance(reply["errors"], list), reply
    if status == "invalid":
        assert reply["result"] is None and reply["errors"], reply
    else:
        assert reply["errors"] == [] and isinstance(reply["result"], dict), reply
    return reply["result"]


@contextmanager
def edit_json(path, mutation):
    original = path.read_bytes()
    value = json.loads(original)
    mutation(value)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    try:
        yield
    finally:
        path.write_bytes(original)


def gate(expected=0, status="passed"):
    return invoke("gate", ("--request", REQUEST, "--policy", POLICY, "--at", AT),
                  expected, status)


def rejected(reason):
    reply = gate(2, "blocked")
    assert reply["decision"] == "blocked", reply
    assert reason in " ".join(reply["reasons"]), reply


def main():
    assert CLI.is_file() and "consumer" in str(Path.cwd())
    assert "sfstack" not in str(Path.cwd()), "Must invoke outside the sfstack checkout"

    version = invoke("version")
    assert version == {"interface_version": "1.0", "distribution_version": "1.0.0"}
    skill = invoke("resolve", ("--skill", "sf-verify-change"))
    assert skill["id"] == "sf-verify-change" and skill["version"] == "1.0.0"
    assert skill["contract"]["id"] == skill["id"]
    assert "# " in skill["skill_markdown"] and skill["protocol_markdown"]
    schema = invoke("schema", ("--name", "artifact"))
    assert schema["schema"]["$id"].startswith("urn:sfstack:artifact:")
    workflow = invoke("recipe", ("--name", "feature"))
    assert workflow["workflow"]["id"] == "feature"

    state = invoke("plan", ("--workflow", "workflows/feature.json", "--run",
                            "examples/feature-run.json", "--at", AT))
    assert state["status"] == "ready" and state["ready"] == ["orient"], state
    artifact = invoke("artifact", ("--path", VERIFICATION, "--request", REQUEST,
                                   "--policy", POLICY, "--type", "verification-report", "--at", AT))
    assert artifact["artifact_type"] == "verification-report" and artifact["reasons"] == []
    allowed = gate()
    assert allowed["decision"] == "allowed" and allowed["reasons"] == [], allowed

    with edit_json(VERIFICATION, lambda a: a.update(created_at="2026-10-01T00:00:00Z")):
        rejected("age exceeds policy")
    with edit_json(VERIFICATION, lambda a: a["subject"].update(revision="different-candidate")):
        rejected("stale subject")
    with edit_json(VERIFICATION, lambda a: a.update(checks=[])):
        rejected("no completion checks")
    with edit_json(VERIFICATION, lambda a: a["payload"].update(executed_count=0)):
        rejected("executed check")
    with edit_json(REQUEST, lambda a: a.update(scope="repository:other/change:42")):
        rejected("authorization")
    with edit_json(REQUEST, lambda a: a["artifacts"].remove("records/review-report.json")):
        rejected("Missing required review-report")
    with edit_json(REVIEW, lambda a: a.pop("schema_version")):
        rejected("Invalid or unavailable evidence")

    retained = Path("examples/records/evidence/fixture.txt")
    raw = retained.read_bytes()
    try:
        retained.write_text("modified after host observation", encoding="utf-8")
        rejected("digest mismatch")
    finally:
        retained.write_bytes(raw)

    with edit_json(VERIFICATION, lambda a: a.pop("schema_version")):
        bad = invoke("artifact", ("--path", VERIFICATION, "--request", REQUEST,
                                  "--policy", POLICY, "--at", AT), 2, "blocked")
        assert "Invalid or unavailable artifact" in " ".join(bad["reasons"]), bad

    old_request = REQUEST.read_bytes()
    try:
        REQUEST.write_text("{invalid json", encoding="utf-8")
        invoke("gate", ("--request", REQUEST, "--policy", POLICY, "--at", AT), 64, "invalid")
    finally:
        REQUEST.write_bytes(old_request)

    invoke("schema", ("--name", "../outside"), 64, "invalid")
    invoke("resolve", ("--skill", "nonexistent"), 64, "invalid")
    print("External pinned sfstack-contract wheel: all positive and negative cases passed.")


if __name__ == "__main__":
    main()
