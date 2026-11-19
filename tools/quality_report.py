#!/usr/bin/env python3
"""Package a read-only Quality Factory assessment from already recorded reports.

No agent is launched, and no code, tracker, PR, or deployment is modified.
This offline utility cannot authenticate reviewer identity or evidence producers.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from common import (ROOT, contained_path, contracts, inspect_artifact, load_json,
                    now, read_regular, validate_schema)
from factory import plan


STATUS_ORDER = ("failed", "blocked", "inconclusive", "passed")
RISK_REPORTS = (
    "security-assessment", "compatibility-report", "privacy-assessment",
    "accessibility-report", "dependency-report", "performance-report",
    "exploration-report",
)


def report_status(statuses):
    return next(item for item in STATUS_ORDER if item in statuses)


def consolidate(workflow_path, run_path, output_dir, at, out_run=None, root=ROOT):
    workflow_path, run_path = Path(workflow_path).resolve(), Path(run_path).resolve()
    run_dir = run_path.parent
    workflow, run = load_json(workflow_path), load_json(run_path)
    validate_schema(workflow, "workflow", root)
    validate_schema(run, "run", root)
    if workflow.get("mode") != "quality":
        raise ValueError("Quality consolidation only accepts a quality workflow.")
    result_step = next((step for step in workflow["steps"]
                        if step["id"] in workflow["completion"] and
                        step["skill"] == "sf-consolidate-quality"), None)
    if not result_step or len(workflow["completion"]) != 1:
        raise ValueError("Expected exactly one sf-consolidate-quality completion node.")
    if result_step["id"] not in plan(workflow_path, run_path, at, root)["ready"]:
        raise ValueError("Quality consolidation is not ready; inspect workflow blockers.")
    destination = contained_path(run_dir, output_dir)
    if destination == run_dir or destination.exists():
        raise ValueError("Output directory must be new and below the run directory.")
    output_manifest = None
    if out_run is not None:
        output_manifest = contained_path(run_dir, out_run)
        if output_manifest.parent != run_dir or output_manifest.exists():
            raise ValueError("Output run manifest must be a new file beside the input.")
    policy = load_json(contained_path(run_dir, run["policy"]))
    catalog = contracts(root)

    sources = {}
    for kind, binding in result_step["bindings"].items():
        parts = binding.split(":")
        if parts[0] == "input":
            path = contained_path(run_dir, run["inputs"][parts[1]])
            artifact, problems = inspect_artifact(
                path, run["subject"], run["run_id"], at,
                policy["max_evidence_age_seconds"], expected_type=kind,
            )
        else:
            step_id = parts[1]
            records = run["completed"][step_id]
            if len(records) != 1:
                raise ValueError(f"Expected one artifact for {step_id}.")
            path = contained_path(run_dir, records[0])
            artifact, problems = inspect_artifact(
                path, run["subject"], run["run_id"], at,
                policy["max_evidence_age_seconds"], expected_type=kind,
                allow_nonpassing=True,
            )
            expected = {"skill": catalog[next(s for s in workflow["steps"] if s["id"] == step_id)["skill"]]["id"],
                        "version": catalog[next(s for s in workflow["steps"] if s["id"] == step_id)["skill"]]["version"]}
            if artifact["producer"] != expected:
                problems.append(f"{step_id}: producer mismatch.")
        if problems:
            raise ValueError(f"Invalid {kind} source: {'; '.join(problems)}")
        sources[kind] = (artifact, path)
    scope = sources["change-set"][0]
    if scope["status"] != "passed":
        raise ValueError("Candidate scope did not establish a fixed, inspectable subject.")
    target_kind = scope["payload"].get("target_kind")
    if target_kind not in {"snapshot", "pull-request", "external-change"}:
        raise ValueError("Candidate must identify snapshot, pull-request, or external-change.")
    if scope["payload"].get("candidate_revision") != run["subject"]["revision"]:
        raise ValueError("Candidate identity differs from the checkpoint.")

    request = sources["request"][0]
    specified = request["payload"].get("required_assessments", [])
    if not isinstance(specified, list) or any(not isinstance(x, str) for x in specified):
        raise ValueError("required_assessments must be a list of artifact types.")
    selected = sorted(k for k in sources if k.endswith("-report") or k.endswith("-assessment"))
    required = sorted(set(selected) | set(specified))
    missing = sorted(set(required) - set(selected))
    statuses = {kind: sources[kind][0]["status"] for kind in selected}
    problems = []
    if missing:
        problems.append("Requested quality dimensions have no selected workflow node: " + ", ".join(missing))
    if not selected:
        raise ValueError("No quality reports were selected.")
    review = sources["review-report"][0]
    identities = review["payload"]
    reviewer, author, basis = (identities.get(k) for k in ("reviewer", "change_author", "independence_basis"))
    identified = all(isinstance(s, str) and s.strip() and s.strip().lower()
                     not in {"unknown", "none", "n/a", "unavailable"}
                     for s in (reviewer, author, basis))
    identified = identified and reviewer.strip() != author.strip() if identified else False
    # Names and descriptions in an artifact are not host authentication.
    if policy["require_independent_review"]:
        problems.append("Independent review is required but cannot be authenticated by the offline summarizer.")

    findings, recommendations = [], []
    for kind in selected:
        source = sources[kind][0]
        for item in source["payload"].get("findings", []):
            if not isinstance(item, dict) or not isinstance(item.get("blocking"), bool) or item.get("disposition") not in {
                "open", "resolved", "rejected", "accepted-risk"
            }:
                problems.append(f"{kind} contains findings that cannot be normalized safely.")
                continue
            findings.append({
                "id": f"{kind}-{item.get('id', len(findings) + 1)}",
                "source_report": source["artifact_id"],
                "blocking": item["blocking"],
                "disposition": item["disposition"],
                "severity": str(item.get("severity", "unspecified")),
                "mechanism": str(item.get("mechanism", "See retained source report")),
                "impact": str(item.get("impact", "See retained source report")),
                "evidence": [f"report-{kind}"],
                "source_evidence": item.get("evidence", []),
            })
        recommendations.extend(source["unresolved"])
        if source["next_action"] != "none":
            recommendations.append(source["next_action"])
    if any(f["blocking"] and f["disposition"] == "open" for f in findings):
        statuses["blocking-finding"] = "failed"
    if missing:
        statuses["missing-report"] = "blocked"
    if problems:
        statuses["uncertainty"] = "inconclusive"
    overall = report_status(set(statuses.values()))
    limitations = list(dict.fromkeys(problems + [
        item for kind in selected for item in sources[kind][0]["unresolved"]
    ]))
    omitted = sorted(set(RISK_REPORTS) - set(selected))
    limitations.extend(f"{kind} not selected; no clearance claimed." for kind in omitted)
    payload = {
        "target": {
            "kind": target_kind,
            "revision": run["subject"]["revision"],
            "base_revision": scope["payload"].get("base_revision"),
            "source_reference": scope["payload"].get("source_reference", "Unspecified"),
        },
        "reports": [],
        "coverage": {"required": required, "evaluated": selected, "omitted": omitted},
        "findings": findings,
        "limitations": limitations,
        "independence": {
            "established": False,
            "basis": ("Distinct reviewer/author identifiers reported; the host must authenticate them."
                      if identified else "Review independence is not established from supplied metadata."),
            "reviewer": reviewer if isinstance(reviewer, str) else "unknown",
            "change_author": author if isinstance(author, str) else "unknown",
        },
        "recommendations": list(dict.fromkeys(recommendations)),
        "remediation_authorized": False,
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sfstack-quality-", dir=run_dir) as temp:
        staged = Path(temp)
        evidence, checks = [], []
        for kind, (source, path) in sources.items():
            if kind == "request":
                continue
            rel = Path("support") / kind
            folder = staged / rel
            folder.mkdir(parents=True, exist_ok=True)
            raw = read_regular(path)
            (folder / "report.json").write_bytes(raw)
            # Retain source evidence under the same relative paths as the
            # original record, so nested checks remain inspectable.
            for item in source["evidence"]:
                src = contained_path(path.parent, item["uri"])
                dst = contained_path(folder, item["uri"])
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                evidence.append({
                    "id": f"support-{kind}-{item['id']}",
                    "kind": item["kind"],
                    "uri": str(rel / item["uri"]),
                    "sha256": item["sha256"],
                    "description": f"Retained source evidence from {kind}: {item['id']}.",
                })
            eid = f"report-{kind}"
            evidence.append({
                "id": eid, "kind": "review" if kind == "review-report" else "analysis",
                "uri": str(rel / "report.json"),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "description": f"Retained {kind} artifact with its cited evidence."
            })
            payload["reports"].append({
                "artifact_id": source["artifact_id"], "artifact_type": kind,
                "status": source["status"], "evidence_id": eid,
            })
            if kind in selected:
                checks.append({
                    "id": f"quality-{kind}", "status": source["status"],
                    "evidence": [eid], "detail": f"{kind} verdict: {source['status']}; check source evidence and limits.",
                })
        for kind in missing:
            checks.append({
                "id": f"missing-{kind}", "status": "blocked",
                "evidence": [], "detail": "Required quality dimension not selected in workflow.",
            })
        if problems and not missing:
            # An independence/normalization gap is a real assessment limitation.
            checks.append({
                "id": "assessment-limits", "status": "inconclusive", "evidence": [],
                "detail": "; ".join(problems),
            })
        summary = {
            "schema_version": "1.0", "artifact_id": f"quality-{run['run_id']}",
            "artifact_type": "quality-assessment",
            "producer": {"skill": "sf-consolidate-quality", "version": "1.0.0"},
            "run_id": run["run_id"], "status": overall,
            "created_at": at.isoformat().replace("+00:00", "Z"),
            "subject": run["subject"],
            "summary": f"Quality assessment {overall} for {target_kind} at the fixed candidate.",
            "evidence": evidence, "checks": checks,
            "unresolved": limitations, "next_action": (
                "Resolve findings and obtain separate remediation authorization." if overall != "passed" else "none"
            ),
            "payload": payload,
        }
        validate_schema(summary, "artifact", root)
        validate_schema(payload, "payload-quality-assessment", root)
        (staged / "quality-assessment.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        # Check references before handing the record to the host.
        _, errors = inspect_artifact(
            staged / "quality-assessment.json", run["subject"], run["run_id"],
            at, policy["max_evidence_age_seconds"], "quality-assessment",
            allow_nonpassing=True,
        )
        if errors:
            raise ValueError("Consolidated report is invalid: " + "; ".join(errors))
        os.rename(staged, destination)
    if output_manifest:
        next_run = deepcopy(run)
        next_run.setdefault("completed", {})[result_step["id"]] = [
            str((destination / "quality-assessment.json").relative_to(run_dir))
        ]
        with output_manifest.open("x", encoding="utf-8") as file:
            json.dump(next_run, file, indent=2)
            file.write("\n")
    return {
        "assessment": str(destination / "quality-assessment.json"),
        "status": overall, "findings": len(findings), "selected_reports": selected,
        "checkpoint": str(output_manifest) if output_manifest else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--out-run", help="New manifest filename beside the input run")
    parser.add_argument("--at", help="UTC time for reproducible offline fixtures")
    args = parser.parse_args(argv)
    try:
        result = consolidate(args.workflow, args.run, args.out_dir, now(args.at), args.out_run)
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.exit(1, f"quality-report: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
