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

# Use the checkout while developing and the wheel's immutable bundled snapshot
# when installed in an independent consumer environment.
_SOURCE_ROOT = Path(__file__).resolve().parents[1]
ROOT = (_SOURCE_ROOT if (_SOURCE_ROOT / "schemas/artifact.schema.json").is_file()
        else Path(__file__).resolve().parent / "sfstack_contracts_data")
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


def load_json(path, expected_sha256=None):

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    raw = read_regular(path)
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"Evidence digest mismatch: {Path(path).name}")
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)


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


def finding_cleared(finding, evidence):
    """A risk label alone is not a resolved finding or an evidenced waiver."""
    disposition = finding.get("disposition")
    if not isinstance(disposition, str):
        return False
    if disposition in {"resolved", "rejected"}:
        return True
    waiver = finding.get("waiver")
    if disposition != "accepted-risk" or not isinstance(waiver, dict):
        return False
    if not all(isinstance(waiver.get(k), str) and waiver[k].strip()
               for k in ("actor", "decision", "evidence")):
        return False
    return evidence.get(waiver["evidence"], {}).get("kind") == "approval"


def quality_source_errors(path, artifact, evidence, at, max_age):
    """Check one level of retained reports; summaries cannot attest to summaries."""
    prefix, payload = artifact["artifact_id"], artifact["payload"]
    errors, sources = [], {}
    if payload["target"]["revision"] != artifact["subject"]["revision"]:
        errors.append(f"{prefix}: quality target revision differs from its subject.")
    reported_types = {r["artifact_type"] for r in payload["reports"]
                      if r["artifact_type"].endswith(("-report", "-assessment"))}
    if set(payload["coverage"]["evaluated"]) != reported_types:
        errors.append(f"{prefix}: quality coverage does not match retained reports.")
    if set(payload["coverage"]["evaluated"]) & set(payload["coverage"]["omitted"]):
        errors.append(f"{prefix}: evaluated quality coverage is also marked omitted.")
    severity = {"passed": 0, "inconclusive": 1, "blocked": 2, "failed": 3}
    for report in payload["reports"]:
        retained = evidence.get(report["evidence_id"])
        if retained is None:
            continue  # The caller reports the missing evidence reference.
        if report["artifact_type"] == "quality-assessment":
            errors.append(f"{prefix}: nested quality assessments are not supported.")
            continue
        try:
            source_path = contained_path(path.parent, retained["uri"])
            source, problems = inspect_artifact(
                source_path, artifact["subject"], artifact["run_id"], at, max_age,
                report["artifact_type"], allow_nonpassing=True,
                expected_sha256=retained["sha256"],
            )
            errors.extend(f"{prefix}: retained source: {p}" for p in problems)
        except (ValueError, OSError) as exc:
            errors.append(f"{prefix}: retained source unavailable: {exc}")
            continue
        if any(source[key] != report[key] for key in ("artifact_id", "artifact_type", "status")):
            errors.append(f"{prefix}: source metadata differs from retained {report['artifact_type']}.")
        if source["artifact_type"] == "quality-assessment":
            continue
        if source["artifact_id"] in sources:
            errors.append(f"{prefix}: duplicate quality source artifact id.")
        sources[source["artifact_id"]] = (source, report)
        if timestamp(source["created_at"]) > timestamp(artifact["created_at"]):
            errors.append(f"{prefix}: source report was created after its summary.")
        if severity[source["status"]] > severity[artifact["status"]]:
            errors.append(f"{prefix}: summary weakens a non-passing source verdict.")

    findings = payload["findings"]
    if len({f["id"] for f in findings}) != len(findings):
        errors.append(f"{prefix}: duplicate quality finding id.")
    for finding in findings:
        if finding["source_report"] not in sources:
            errors.append(f"{prefix}: quality finding has no retained source report.")
        if not set(finding["evidence"]).issubset(evidence):
            errors.append(f"{prefix}: quality finding has invalid evidence references.")
        if (artifact["status"] == "passed" and finding["blocking"]
                and not finding_cleared(finding, evidence)):
            errors.append(f"{prefix}: blocking quality finding lacks resolution or an evidenced waiver.")

    for source, report in sources.values():
        original = source["payload"].get("findings", [])
        represented = [f for f in findings if f["source_report"] == source["artifact_id"]]
        if not isinstance(original, list):
            if artifact["status"] == "passed":
                errors.append(f"{prefix}: malformed source findings cannot support passing quality.")
            continue
        valid_findings = [f for f in original if isinstance(f, dict)
                          and type(f.get("blocking")) is bool
                          and isinstance(f.get("disposition"), str)
                          and f["disposition"] in {"open", "resolved", "rejected", "accepted-risk"}]
        if len(valid_findings) != len(original) and artifact["status"] == "passed":
            errors.append(f"{prefix}: malformed source findings cannot support passing quality.")
        original = valid_findings
        if len(original) != len(represented):
            errors.append(f"{prefix}: source findings were omitted or added in the summary.")
        source_evidence = {e["id"]: e for e in source["evidence"]}
        for item in original:
            # IDs may be chosen by a different conforming summarizer. Match the
            # actual finding meaning and consume each match once instead.
            match = next((f for f in represented if all(
                f.get(key) == item[key] for key in
                ("blocking", "disposition", "severity", "mechanism", "impact", "location")
                if key in item)), None)
            if match is None:
                errors.append(f"{prefix}: source finding meaning changed in the summary.")
                continue
            represented.remove(match)
            refs = match.get("source_evidence", [])
            if (not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs)
                    or not set(refs).issubset(source_evidence)
                    or refs != item.get("evidence", [])
                    or report["evidence_id"] not in match["evidence"]):
                errors.append(f"{prefix}: quality finding lacks matching source evidence.")
            source_waiver, waiver = item.get("waiver"), match.get("waiver")
            if source_waiver is not None or waiver is not None:
                source_ref = source_waiver.get("evidence") if isinstance(source_waiver, dict) else None
                summary_ref = waiver.get("evidence") if isinstance(waiver, dict) else None
                original_proof = source_evidence.get(source_ref, {}) if isinstance(source_ref, str) else {}
                summary_proof = evidence.get(summary_ref, {}) if isinstance(summary_ref, str) else {}
                if (not isinstance(source_waiver, dict) or not isinstance(waiver, dict)
                        or any(waiver.get(k) != source_waiver.get(k) for k in ("actor", "decision"))
                        or not original_proof or not summary_proof
                        or any(original_proof.get(k) != summary_proof.get(k) for k in ("kind", "sha256"))):
                    errors.append(f"{prefix}: quality finding waiver differs from retained approval.")
    return errors


def inspect_artifact(path, subject, run_id, at, max_age, expected_type=None,
                     allow_nonpassing=False, expected_sha256=None):
    """Check a supplied record and the retained local evidence bytes it cites."""
    path = Path(path)
    artifact = load_json(path, expected_sha256)
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
        # Source reports may not hide another summary behind a different type.
        # Return before traversing its sources, keeping validation one level deep.
        if artifact["artifact_type"] == "quality-assessment":
            problems.append(f"{prefix}: nested quality assessments are not supported.")
            return artifact, problems
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
            problems.extend(quality_source_errors(path, artifact, evidence, at, max_age))
            covered = set(payload["coverage"]["evaluated"])
            required = set(payload["coverage"]["required"])
            reports = {item["artifact_type"]: item for item in payload["reports"]}
            if len(reports) != len(payload["reports"]):
                problems.append(f"{prefix}: duplicate quality report type.")
            if any(item["evidence_id"] not in evidence for item in reports.values()):
                problems.append(f"{prefix}: quality report lacks retained evidence.")
            if artifact["status"] == "passed":
                core = {"verification-report", "review-report"}
                if not core.issubset(covered):
                    problems.append(f"{prefix}: passing quality requires verification and review.")
                if required - covered:
                    problems.append(f"{prefix}: required quality coverage is missing.")
                if (covered - set(reports)
                        or any(reports[kind]["status"] != "passed" for kind in covered & set(reports))):
                    problems.append(f"{prefix}: a selected quality report is absent or non-passing.")
                if required & set(payload["coverage"]["omitted"]):
                    problems.append(f"{prefix}: required quality coverage is marked omitted.")
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
                if (finding['blocking'] and not finding_cleared(finding, evidence)
                        and (artifact["status"] == "passed" or not allow_nonpassing)):
                    problems.append(f"{prefix}: unresolved blocking review finding.")
    return artifact, problems
