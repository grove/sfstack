#!/usr/bin/env python3
"""Read-only reference planner and evidence gate. Never executes live operations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from common import (ROOT, contracts, contained_path, inspect_artifact, load_json,
                    now, timestamp, validate_schema, workflow_errors)

def grant_errors(policy, run_id, effect, scope, subject, at):
    if not scope:
        return [f"No explicit target scope for {effect}."]
    for grant in policy["grants"]:
        if (grant["run_id"] == run_id and grant["effect"] == effect
                and grant["scope"] == scope and grant["subject"] == subject
                and timestamp(grant["expires_at"]) > at):
            return []
    return [f"No current exact-scope authorization for {effect} on {scope}."]


def proof_errors(policy, effect, artifacts):
    errors = []
    by_type = {}
    seen_ids = set()
    for artifact in artifacts:
        kind = artifact["artifact_type"]
        if artifact['artifact_id'] in seen_ids:
            errors.append(f"Duplicate artifact identity {artifact['artifact_id']}.")
        seen_ids.add(artifact['artifact_id'])
        if kind in by_type:
            errors.append(f"Ambiguous multiple artifacts of type {kind}.")
        by_type[kind] = artifact
    if effect not in policy["required_artifacts"]:
        errors.append(f"Policy has no explicit evidence rule for {effect}.")
    # A policy is supplied by the trusted host, never by untrusted task content.
    # Separate recovery policies can require different preconditions; a worker must
    # not rewrite this policy merely to make a blocked decision pass.
    required = set(policy["required_artifacts"].get(effect, []))
    for kind in sorted(required - by_type.keys()):
        errors.append(f"Missing required {kind}.")
    verification = by_type.get("verification-report")
    if verification:
        payload = verification["payload"]
        count = payload.get("executed_count")
        if type(count) is not int or count < 1:
            errors.append("Verification did not record at least one executed check.")
        if type(payload.get("failed_count")) is not int or payload["failed_count"] != 0:
            errors.append("Verification has failures or an unknown failure count.")
        if payload.get("skipped_required") != []:
            errors.append("Verification skipped required checks or omitted that record.")
        cited = {ref for check in verification['checks'] for ref in check['evidence']}
        if not any(e["kind"] in {"test", "observation"} and e['id'] in cited for e in verification["evidence"]):
            errors.append("Verification lacks cited test or runtime observation evidence.")
    review = by_type.get("review-report")
    if review and policy["require_independent_review"]:
        payload = review["payload"]
        reviewer, author = payload.get("reviewer"), payload.get("change_author")
        identity_values = (reviewer, author, payload.get('independence_basis'))
        known = all(isinstance(value, str) and value.strip() and value.strip().lower() not in
                    {'unknown', 'unavailable', 'none', 'n/a'} for value in identity_values)
        if not known or reviewer.strip() == author.strip():
            errors.append("Policy requires an independently identified review.")
    quality = by_type.get("quality-assessment")
    if quality and policy["require_independent_review"]:
        independence = quality["payload"].get("independence")
        if not isinstance(independence, dict) or independence.get("established") is not True:
            errors.append("Quality assessment does not establish required independent review.")
    review_status = by_type.get('review-status')
    if review_status:
        if review_status['payload'].get('readiness') != 'ready':
            errors.append('Review status has not established readiness.')
        if review_status['payload'].get('head') != review_status['subject']['revision']:
            errors.append('Review status head does not match the candidate.')
        checks = review_status['payload'].get('checks')
        if not isinstance(checks, list):
            errors.append('Review status lacks an explicit checks array.')
        else:
            for check in checks:
                if (not isinstance(check, dict) or type(check.get('required', True)) is not bool
                        or (check.get('required', True) and check.get('status') != 'passed')):
                    errors.append('Review status has an unsatisfied required check.')
    return errors


def evaluate_gate(request_path, policy_path, at):
    request_path, policy_path = Path(request_path), Path(policy_path)
    request, policy = load_json(request_path), load_json(policy_path)
    validate_schema(request, "gate-request")
    validate_schema(policy, "policy")
    reasons = grant_errors(policy, request["run_id"], request["effect"], request["scope"], request["subject"], at)
    artifacts = []
    for relative in request["artifacts"]:
        artifact_path = contained_path(request_path.parent, relative)
        artifact, problems = inspect_artifact(artifact_path, request["subject"], request["run_id"], at,
                                              policy["max_evidence_age_seconds"])
        artifacts.append(artifact)
        reasons.extend(problems)
    reasons.extend(proof_errors(policy, request["effect"], artifacts))
    return {"decision": "blocked" if reasons else "allowed", "effect": request["effect"],
            "scope": request["scope"], "reasons": reasons}


def plan(workflow_path, run_path, at, root=ROOT):
    workflow, run = load_json(workflow_path), load_json(run_path)
    validate_schema(workflow, "workflow", root)
    validate_schema(run, "run", root)
    catalog = contracts(root)
    quality_mode = workflow.get("mode", "software") == "quality"
    errors = workflow_errors(workflow, catalog)
    if errors:
        raise ValueError(" ".join(errors))
    run_dir = Path(run_path).parent
    policy = load_json(contained_path(run_dir, run["policy"]))
    validate_schema(policy, "policy", root)
    steps = {step["id"]: step for step in workflow["steps"]}
    if set(run["completed"]) - set(steps):
        raise ValueError("Run names unknown completed steps.")
    if set(run['inputs']) - set(workflow['inputs']):
        raise ValueError("Run names unknown workflow inputs.")
    selections = run.get('selected_effects', {})
    if set(selections) - set(steps):
        raise ValueError('Conditional effect selection names an unknown step.')
    for identifier, selected in selections.items():
        allowed = {item['effect'] for item in catalog[steps[identifier]['skill']].get('conditional_effects', [])}
        if set(selected) - allowed:
            raise ValueError(f'{identifier}: selected effect is not declared conditional.')
    inputs, input_errors = {}, {}
    for kind in workflow["inputs"]:
        if kind not in run["inputs"]:
            input_errors[kind] = [f"Missing workflow input {kind}."]
            continue
        artifact, problems = inspect_artifact(contained_path(run_dir, run["inputs"][kind]),
            run["subject"], run["run_id"], at, policy["max_evidence_age_seconds"], kind)
        inputs[kind], input_errors[kind] = artifact, problems
    completed, blocked, outputs, ready = set(), {}, {}, []
    pending = list(steps)
    while pending:
        progressed = False
        for identifier in pending[:]:
            step = steps[identifier]
            if any(parent in pending for parent in step["needs"]):
                continue
            pending.remove(identifier)
            progressed = True
            contract = catalog[step["skill"]]
            reasons, bound = [], []
            accepted_by_parent = step.get("accept_statuses", {})
            for parent in step["needs"]:
                if parent not in completed:
                    reasons.append(f"Waiting for {parent} to complete with current evidence.")
                elif quality_mode:
                    accepted = accepted_by_parent.get(parent, ["passed"])
                    for (producer, _), artifact in outputs.items():
                        if producer == parent and artifact["status"] not in accepted:
                            reasons.append(f"Upstream {parent} status {artifact['status']} not accepted by {identifier}.")
            for kind, binding in step["bindings"].items():
                parts = binding.split(":")
                if parts[0] == "input":
                    reasons.extend(input_errors.get(parts[1], []))
                    if parts[1] in inputs:
                        bound.append(inputs[parts[1]])
                else:
                    artifact = outputs.get((parts[1], parts[2]))
                    if artifact:
                        bound.append(artifact)
                        if quality_mode and artifact["status"] not in accepted_by_parent.get(parts[1], ["passed"]):
                            reasons.append(f"Input {kind} status {artifact['status']} not accepted by {identifier}.")
                    else:
                        reasons.append(f"Input {kind} is not available from {parts[1]}.")
            if 'max_work_items' in step:
                plans = [artifact for artifact in bound if artifact['artifact_type'] == 'work-plan']
                for work_plan in plans:
                    items = work_plan['payload'].get('items')
                    frontier = work_plan['payload'].get('ready_frontier')
                    if not isinstance(items, list) or not 1 <= len(items) <= step['max_work_items']:
                        reasons.append('Work plan exceeds the selected increment or has no explicit items; split or expand the workflow.')
                    elif not isinstance(frontier, list) or any(not isinstance(item, dict) or not item.get('id') or item['id'] not in frontier for item in items):
                        reasons.append('The selected work items are not explicitly ready.')
            if identifier in run["completed"]:
                found = {}
                for relative in run["completed"][identifier]:
                    artifact, problems = inspect_artifact(contained_path(run_dir, relative), run["subject"],
                        run["run_id"], at, policy["max_evidence_age_seconds"],
                        allow_nonpassing=quality_mode)
                    reasons.extend(problems)
                    kind = artifact["artifact_type"]
                    if kind in found:
                        reasons.append(f"Duplicate output {kind} for {identifier}.")
                    found[kind] = artifact
                    if artifact["producer"] != {"skill": contract["id"], "version": contract["version"]}:
                        reasons.append(f"Output producer mismatch for {identifier}.")
                if set(found) != set(contract["outputs"]):
                    reasons.append(f"Output types do not match {identifier}'s contract.")
                if not reasons:
                    completed.add(identifier)
                    for kind, artifact in found.items():
                        outputs[(identifier, kind)] = artifact
            else:
                missing = set(contract["capabilities"]) - set(run["capabilities"])
                if missing:
                    reasons.append("Missing capabilities: " + ", ".join(sorted(missing)))
                # Only bound artifacts and dependency outputs can support an action.
                ancestors, queue = set(), list(step["needs"])
                while queue:
                    parent = queue.pop()
                    if parent not in ancestors:
                        ancestors.add(parent)
                        queue.extend(steps[parent]["needs"])
                proof = {}
                def add_proof(artifact):
                    existing = proof.get(artifact['artifact_id'])
                    if existing is not None and existing != artifact:
                        reasons.append(f"Conflicting content for artifact identity {artifact['artifact_id']}.")
                    proof[artifact['artifact_id']] = artifact
                for artifact in bound:
                    add_proof(artifact)
                for (parent, _), artifact in outputs.items():
                    if parent in ancestors:
                        add_proof(artifact)
                for effect in contract["effects"] + selections.get(identifier, []):
                    reasons.extend(grant_errors(policy, run["run_id"], effect,
                        run["effect_scopes"].get(effect), run["subject"], at))
                    reasons.extend(proof_errors(policy, effect, list(proof.values())))
                if not reasons:
                    ready.append(identifier)
            if reasons:
                blocked[identifier] = sorted(set(reasons))
        if not progressed:
            raise ValueError("Workflow cannot be ordered.")
    status = "complete" if set(workflow["completion"]).issubset(completed) else "ready" if ready else "blocked"
    result = {"workflow": workflow["id"], "run_id": run["run_id"], "status": status,
              "ready": ready, "completed": sorted(completed), "blocked": blocked}
    if quality_mode:
        # Workflow completion means a report exists, not that its subject passed.
        result["outcomes"] = {
            identifier: {kind: artifact["status"] for (producer, kind), artifact in outputs.items()
                         if producer == identifier}
            for identifier in sorted(completed)
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    planner = sub.add_parser("plan", help="Find eligible steps in a fixed-subject checkpoint")
    planner.add_argument("--workflow", required=True, type=Path)
    planner.add_argument("--run", required=True, type=Path)
    gate = sub.add_parser("gate", help="Check supplied authorization and local evidence")
    gate.add_argument("--request", required=True, type=Path)
    gate.add_argument("--policy", required=True, type=Path)
    for command in (planner, gate):
        command.add_argument("--at", help="UTC evaluation time; defaults to current time")
    args = parser.parse_args(argv)
    try:
        at = now(args.at)
        result = plan(args.workflow, args.run, at) if args.command == "plan" else evaluate_gate(args.request, args.policy, at)
        print(json.dumps(result, indent=2))
        return 2 if result.get("decision") == "blocked" or result.get("status") == "blocked" else 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
