"""Shared offline validation. No network, subprocesses, or live adapter execution."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
EFFECT_CAPABILITY = {
    "workspace.modify": "workspace.write",
    "tracker.modify": "tracker.write",
    "review.publish": "review.write",
    "integration.modify": "vcs.write",
    "release.publish": "release.publish",
    "deployment.modify": "deployment.write",
    "data.modify": "execution.run",
    "external.communicate": "communication.send",
}


MAX_FILE_BYTES = 16 * 1024 * 1024


def read_regular(path, maximum=MAX_FILE_BYTES):
    """Bound input size and avoid blocking on FIFOs/devices, including a swapped path."""
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"Expected a regular file: {Path(path).name}")
        if info.st_size > maximum:
            raise ValueError(f"File exceeds {maximum} bytes: {Path(path).name}")
        data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError(f"File exceeds {maximum} bytes: {Path(path).name}")
        return data


def load_json(path):

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(read_regular(path).decode('utf-8'), object_pairs_hook=unique_object)


def validate_schema(data, name, root=ROOT):
    schema = load_json(root / "schemas" / f"{name}.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda e: str(list(e.path)))
    if errors:
        first = errors[0]
        location = ".".join(str(p) for p in first.path) or "<root>"
        raise ValueError(f"{name} {location}: {first.message}")


def contained_path(base, relative):
    """Reject absolute paths, URI schemes and escapes, including through symlinks."""
    if not relative or Path(relative).is_absolute() or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", relative):
        raise ValueError(f"Expected a relative local path: {relative}")
    base = Path(base).resolve()
    result = (base / relative).resolve()
    if not result.is_relative_to(base):
        raise ValueError(f"Path escapes its manifest directory: {relative}")
    return result


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError("Timestamps must include UTC (Z or +00:00).")
    return result


def now(value=None):
    return timestamp(value) if value else datetime.now(timezone.utc)


def contracts(root=ROOT):
    result = {}
    for path in sorted((root / "skills").glob("sf-*/contract.json")):
        contract = load_json(path)
        validate_schema(contract, "skill-contract", root)
        if contract["id"] != path.parent.name or contract["id"] in result:
            raise ValueError(f"Duplicate or mismatched skill id: {path}")
        result[contract["id"]] = contract
    return result


def workflow_errors(workflow, catalog):
    """Check graph closure, cycles, and typed input/output bindings."""
    errors = []
    steps = {step["id"]: step for step in workflow["steps"]}
    if len(steps) != len(workflow["steps"]):
        errors.append("Duplicate step id.")
    if not set(workflow["completion"]).issubset(steps):
        errors.append("Completion names an unknown step.")
    visiting, visited, ancestors = set(), set(), {}

    def walk(identifier):
        if identifier in visiting:
            raise ValueError(f"Workflow cycle at {identifier}.")
        if identifier in visited:
            return ancestors[identifier]
        if identifier not in steps:
            raise ValueError(f"Unknown dependency {identifier}.")
        visiting.add(identifier)
        parents = set()
        for parent in steps[identifier]["needs"]:
            parents.add(parent)
            parents.update(walk(parent))
        visiting.remove(identifier)
        visited.add(identifier)
        ancestors[identifier] = parents
        return parents

    try:
        for identifier in steps:
            walk(identifier)
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    covered = set(workflow["completion"])
    for identifier in workflow["completion"]:
        covered.update(ancestors.get(identifier, set()))
    if set(steps) - covered:
        errors.append("Completion omits terminal work: " + ", ".join(sorted(set(steps) - covered)))
    quality_mode = workflow.get("mode", "software") == "quality"
    if quality_mode:
        # A quality recipe is observational. A declared mutation cannot become
        # authorized just because a policy happens to contain a write grant.
        for identifier, step in steps.items():
            contract = catalog.get(step["skill"], {})
            forbidden = set(contract.get("capabilities", [])) & {
                "workspace.write", "vcs.write", "tracker.write", "review.write",
                "release.publish", "deployment.write", "communication.send",
            }
            if contract.get("effects") or contract.get("conditional_effects") or forbidden:
                errors.append(f"{identifier}: quality workflows cannot declare mutations.")
        if not any(
            "quality-assessment" in catalog.get(steps[identifier]["skill"], {}).get("outputs", [])
            for identifier in workflow["completion"] if identifier in steps
        ):
            errors.append("Quality workflow must complete with a quality-assessment artifact.")
    elif any("accept_statuses" in step for step in steps.values()):
        errors.append("accept_statuses is only permitted in quality workflows.")
    for identifier, step in steps.items():
        if set(step.get("accept_statuses", {})) - set(step["needs"]):
            errors.append(f"{identifier}: accept_statuses names a non-dependency.")
        contract = catalog.get(step["skill"])
        if contract is None:
            errors.append(f"{identifier}: unknown skill {step['skill']}.")
            continue
        expected = {item["name"] for item in contract["inputs"]}
        required = {item["name"] for item in contract["inputs"] if item["required"]}
        supplied = set(step["bindings"])
        if 'max_work_items' in step and 'work-plan' not in supplied:
            errors.append(f"{identifier}: max_work_items requires a work-plan binding.")
        if required - supplied:
            errors.append(f"{identifier}: missing required bindings {sorted(required - supplied)}.")
        if supplied - expected:
            errors.append(f"{identifier}: unknown inputs {sorted(supplied - expected)}.")
        for name, binding in step["bindings"].items():
            parts = binding.split(":")
            if parts[0] == "input":
                if parts[1] not in workflow["inputs"] or parts[1] != name:
                    errors.append(f"{identifier}: invalid or mistyped input binding {binding}.")
            else:
                _, source, output = parts
                if source not in ancestors[identifier]:
                    errors.append(f"{identifier}: {source} is not a dependency ancestor.")
                    continue
                upstream = catalog.get(steps[source]["skill"], {})
                if output not in upstream.get("outputs", []) or output != name:
                    errors.append(f"{identifier}: missing or mistyped output {binding}.")
    return errors


def inspect_artifact(path, subject, run_id, at, max_age, expected_type=None,
                     allow_nonpassing=False):
    """Check a supplied record and the retained local evidence bytes it cites."""
    path = Path(path)
    artifact = load_json(path)
    validate_schema(artifact, "artifact")
    problems = []
    # Validate claim-bearing fields as well as the generic artifact envelope.
    # Keep malformed payloads as gate-blocking evidence problems, not exceptions.
    payload_schema = {
        "verification-report": "payload-verification-report",
        "review-report": "payload-review-report",
        "quality-assessment": "payload-quality-assessment",
    }.get(artifact["artifact_type"])
    if payload_schema:
        try:
            validate_schema(artifact["payload"], payload_schema)
        except ValueError as exc:
            problems.append(f"{artifact['artifact_id']}: invalid {payload_schema}: {exc}")
    prefix = artifact["artifact_id"]
    if artifact["subject"] != subject:
        problems.append(f"{prefix}: stale subject (revision, inputs, or environment changed).")
    if artifact["run_id"] != run_id:
        problems.append(f"{prefix}: wrong run_id.")
    if expected_type and artifact["artifact_type"] != expected_type:
        problems.append(f"{prefix}: expected {expected_type}, got {artifact['artifact_type']}.")
    age = (at - timestamp(artifact["created_at"])).total_seconds()
    if age < 0:
        problems.append(f"{prefix}: observation is in the future.")
    elif age > max_age:
        problems.append(f"{prefix}: evidence age exceeds policy.")
    if artifact["status"] != "passed" and not allow_nonpassing:
        problems.append(f"{prefix}: status is {artifact['status']}.")
    if artifact["status"] == "passed" and not artifact["checks"]:
        problems.append(f"{prefix}: no completion checks recorded.")
    evidence = {item["id"]: item for item in artifact["evidence"]}
    if len(evidence) != len(artifact["evidence"]):
        problems.append(f"{prefix}: duplicate evidence IDs.")
    if len({item['id'] for item in artifact['checks']}) != len(artifact['checks']):
        problems.append(f"{prefix}: duplicate check IDs.")
    for item in artifact["evidence"]:
        try:
            retained = contained_path(path.parent, item["uri"])
            actual = hashlib.sha256(read_regular(retained)).hexdigest()
            if actual != item["sha256"]:
                problems.append(f"{prefix}: evidence digest mismatch for {item['id']}.")
        except (ValueError, OSError) as exc:
            problems.append(f"{prefix}: evidence {item['id']} unavailable: {exc}")
    for check in artifact["checks"]:
        if check["status"] != "passed" and (artifact["status"] == "passed" or not allow_nonpassing):
            problems.append(f"{prefix}: check {check['id']} is {check['status']}.")
        if (not set(check["evidence"]).issubset(evidence)
                or (check["status"] in {"passed", "failed"} and not check["evidence"])):
            problems.append(f"{prefix}: check {check['id']} lacks valid evidence references.")
    if artifact["artifact_type"] == "verification-report":
        payload = artifact["payload"]
        passing_claim = artifact["status"] == "passed" or not allow_nonpassing
        count = payload.get("executed_count")
        if passing_claim and (type(count) is not int or count < 1):
            problems.append(f"{prefix}: verification recorded no executed checks.")
        required = payload.get('required_count')
        if type(required) is not int or required < 1 or type(count) is not int or (passing_claim and count < required):
            problems.append(f"{prefix}: required check count is missing, invalid, or not met.")
        failures = payload.get("failed_count")
        if type(failures) is not int or (passing_claim and failures != 0):
            problems.append(f"{prefix}: verification failure count is nonzero or unknown.")
        if type(count) is int and type(failures) is int and failures > count:
            problems.append(f"{prefix}: verification failure count exceeds executed checks.")
        if passing_claim and payload.get("skipped_required") != []:
            problems.append(f"{prefix}: required checks were skipped or not accounted for.")
        cited = {ref for check in artifact['checks'] for ref in check['evidence']}
        if passing_claim and not any(item['kind'] in {'test', 'observation'} and item['id'] in cited for item in artifact['evidence']):
            problems.append(f"{prefix}: verification has no cited execution evidence.")
    if artifact["artifact_type"] == "quality-assessment":
        payload = artifact["payload"]
        # Malformed payloads were already reported by the schema check above.
        # Avoid interpreting their fields or raising an uncaught type error.
        try:
            validate_schema(payload, "payload-quality-assessment")
        except ValueError:
            pass
        else:
            covered = set(payload["coverage"]["evaluated"])
            required = set(payload["coverage"]["required"])
            reports = {item["artifact_type"]: item for item in payload["reports"]}
            if len(reports) != len(payload["reports"]):
                problems.append(f"{prefix}: duplicate quality report type.")
            if any(item["evidence_id"] not in evidence for item in reports.values()):
                problems.append(f"{prefix}: quality report lacks retained evidence.")
            if artifact["status"] == "passed":
                if not {"verification-report", "review-report"}.issubset(covered):
                    problems.append(f"{prefix}: passing quality requires verification and review.")
                if required - covered:
                    problems.append(f"{prefix}: required quality coverage is missing.")
                if any(kind not in reports or reports[kind]["status"] != "passed" for kind in required):
                    problems.append(f"{prefix}: a required quality report is not passing.")
                if any(item["blocking"] and item["disposition"] not in {"resolved", "rejected", "accepted-risk"}
                       for item in payload["findings"]):
                    problems.append(f"{prefix}: unresolved blocking quality finding.")
    if artifact['artifact_type'] == 'review-report':
        findings = artifact['payload'].get('findings')
        if not isinstance(findings, list):
            problems.append(f"{prefix}: review findings must be an explicit array.")
        else:
            for finding in findings:
                if not isinstance(finding, dict) or type(finding.get('blocking')) is not bool:
                    problems.append(f"{prefix}: review finding lacks a boolean blocking decision.")
                    continue
                disposition = finding.get('disposition')
                if not isinstance(disposition, str) or disposition not in {'open', 'resolved', 'rejected', 'accepted-risk'}:
                    problems.append(f"{prefix}: review finding has an unknown disposition.")
                if finding['blocking'] and disposition not in ('resolved', 'rejected'):
                    waiver = finding.get('waiver', {})
                    waiver_id = waiver.get('evidence') if isinstance(waiver, dict) else None
                    waiver_evidence = evidence.get(waiver_id) if isinstance(waiver_id, str) else None
                    valid_waiver = (disposition == 'accepted-risk' and isinstance(waiver, dict)
                        and all(isinstance(waiver.get(k), str) and waiver[k].strip() for k in ('actor', 'decision', 'evidence'))
                        and waiver_evidence and waiver_evidence['kind'] == 'approval')
                    if not valid_waiver and (artifact["status"] == "passed" or not allow_nonpassing):
                        problems.append(f"{prefix}: unresolved blocking review finding.")
    return artifact, problems
