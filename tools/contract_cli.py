#!/usr/bin/env python3
"""Versioned sfstack contract and evidence interface for external hosts.

All decisions delegate to the canonical sfstack validators and planner. This
entrypoint neither runs candidate code nor supplies permissions or evidence.
Only consolidation writes files, under explicit host-selected output paths.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from common import ROOT, contained_path, contracts, inspect_artifact, load_json, now, read_regular, validate_schema
from factory import evaluate_gate, plan
from jsonschema import Draft202012Validator, FormatChecker
from quality_report import consolidate
from render_invocation import render

INTERFACE_VERSION = "1.1"
DISTRIBUTION_VERSION = "1.1.0"
PASSED, BLOCKED, INVALID = 0, 2, 64
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class InvalidInvocation(ValueError):
    """A CLI argument or a host-supplied control document is invalid."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidInvocation(message)


def envelope(operation, status, result=None, errors=()):
    """Every non-help invocation emits exactly one JSON object on stdout."""
    return {
        "interface_version": INTERFACE_VERSION,
        "distribution_version": DISTRIBUTION_VERSION,
        "operation": operation,
        "status": status,
        "result": result,
        "errors": list(errors),
    }


def parser():
    root = JsonArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="Report the CLI API and distribution versions")

    resolve = commands.add_parser("resolve", help="Read a selected, versioned skill contract")
    resolve.add_argument("--skill", required=True)

    schema = commands.add_parser("schema", help="Read a canonical JSON Schema")
    schema.add_argument("--name", required=True)

    validate = commands.add_parser("validate", help="Validate JSON against a canonical schema")
    validate.add_argument("--name", required=True)
    validate.add_argument("--path", required=True, type=Path)

    invocation = commands.add_parser("render", help="Render a skill and host-supplied task context")
    invocation.add_argument("--skill", required=True)
    invocation.add_argument("--context", required=True, type=Path)

    recipe = commands.add_parser("recipe", help="Read a canonical workflow recipe")
    recipe.add_argument("--name", required=True)

    gate = commands.add_parser("gate", help="Evaluate an exact-scoped authorization and evidence gate")
    gate.add_argument("--request", required=True, type=Path)
    gate.add_argument("--policy", required=True, type=Path)

    artifact = commands.add_parser("artifact", help="Validate an artifact against a pinned subject and policy")
    artifact.add_argument("--path", required=True, type=Path)
    artifact.add_argument("--request", required=True, type=Path,
                          help="Pinned gate-request containing subject and run ID")
    artifact.add_argument("--policy", required=True, type=Path)
    artifact.add_argument("--type", help="Required artifact type")

    inspection = commands.add_parser("inspect", help="Inspect evidence without an authorization request")
    inspection.add_argument("--path", required=True, type=Path)
    inspection.add_argument("--context", required=True, type=Path,
                            help="Pinned subject, run_id and max_evidence_age_seconds")
    inspection.add_argument("--type", help="Required artifact type")
    inspection.add_argument("--allow-nonpassing", action="store_true",
                            help="Inspect retained negative reports; does not authorize any effect")

    planner = commands.add_parser("plan", help="Bind a versioned recipe and find eligible steps")
    group = planner.add_mutually_exclusive_group(required=True)
    group.add_argument("--workflow", type=Path)
    group.add_argument("--recipe", help="Name of a bundled workflow")
    planner.add_argument("--run", required=True, type=Path)

    summary = commands.add_parser("consolidate", help="Retain a quality assessment from existing evidence")
    group = summary.add_mutually_exclusive_group(required=True)
    group.add_argument("--workflow", type=Path)
    group.add_argument("--recipe", help="Name of a bundled workflow")
    summary.add_argument("--run", required=True, type=Path)
    summary.add_argument("--out-dir", required=True,
                         help="New output directory relative to the run manifest")
    summary.add_argument("--out-run", help="New manifest filename beside the input run")

    for command in (gate, artifact, inspection, planner, summary):
        command.add_argument("--at", help="UTC observation time; omit for the current clock")
    return root


def named_file(folder, name, suffix):
    if not NAME.fullmatch(name):
        raise InvalidInvocation("Expected a canonical resource name.")
    path = ROOT / folder / (name + suffix)
    if not path.is_file():
        raise InvalidInvocation("Unknown sfstack resource: " + name)
    return path


def controls(request_path, policy_path):
    # A malformed request or trusted policy is an invalid invocation. Invalid
    # proof referenced by a valid request blocks the gate instead.
    request, policy = load_json(request_path), load_json(policy_path)
    validate_schema(request, "gate-request")
    validate_schema(policy, "policy")
    return request, policy


def inspection_context(path):
    """Reuse canonical field schemas; inspection is not an authorization grant."""
    request = load_json(ROOT / "schemas/gate-request.schema.json")["properties"]
    policy = load_json(ROOT / "schemas/policy.schema.json")["properties"]
    properties = {"subject": request["subject"], "run_id": request["run_id"],
                  "max_evidence_age_seconds": policy["max_evidence_age_seconds"]}
    schema = {"type": "object", "properties": properties,
              "required": list(properties), "additionalProperties": False}
    context = load_json(path)
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(context))
    if errors:
        raise InvalidInvocation("Invalid inspection context: " + errors[0].message)
    return context


def decision(command):
    operation = command.command
    if operation == "version":
        return envelope(operation, "passed", {
            "interface_version": INTERFACE_VERSION,
            "distribution_version": DISTRIBUTION_VERSION,
        }), PASSED
    if operation == "resolve":
        catalog = contracts()
        if command.skill not in catalog:
            raise InvalidInvocation("Unknown skill: " + command.skill)
        skill = catalog[command.skill]
        directory = ROOT / "skills" / command.skill
        return envelope(operation, "passed", {
            "id": skill["id"],
            "version": skill["version"],
            "contract": skill,
            "skill_markdown": read_regular(directory / "SKILL.md").decode("utf-8"),
            "protocol_markdown": read_regular(directory / "references/protocol.md").decode("utf-8"),
        }), PASSED
    if operation == "schema":
        name = command.name
        return envelope(operation, "passed", {
            "name": name, "schema": load_json(named_file("schemas", name, ".schema.json")),
        }), PASSED
    if operation == "validate":
        # Resource selection is a trusted control. The document being checked
        # is evidence and remains a negative result if absent or malformed.
        named_file("schemas", command.name, ".schema.json")
        try:
            validate_schema(load_json(command.path), command.name)
            result = {"valid": True, "reasons": []}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            result = {"valid": False, "reasons": [str(exc)]}
        status = "passed" if result["valid"] else "blocked"
        return envelope(operation, status, result), PASSED if result["valid"] else BLOCKED
    if operation == "render":
        context = load_json(command.context)
        return envelope(operation, "passed", {
            "skill": command.skill, "invocation_markdown": render(command.skill, context),
        }), PASSED
    if operation == "recipe":
        name = command.name
        recipe = load_json(named_file("workflows", name, ".json"))
        validate_schema(recipe, "workflow")
        return envelope(operation, "passed", {"name": name, "workflow": recipe}), PASSED

    at = now(command.at)
    if operation in {"plan", "consolidate"}:
        workflow = (command.workflow if command.workflow is not None
                    else named_file("workflows", command.recipe, ".json"))
        if operation == "consolidate":
            result = consolidate(workflow, command.run, command.out_dir, at,
                                 out_run=command.out_run, root=ROOT)
            status = "passed" if result["status"] == "passed" else "blocked"
            return envelope(operation, status, result), PASSED if status == "passed" else BLOCKED
        result = plan(workflow, command.run, at, root=ROOT)
        status = "blocked" if result["status"] == "blocked" else "passed"
        return envelope(operation, status, result), BLOCKED if status == "blocked" else PASSED

    if operation == "inspect":
        context = inspection_context(command.context)
        try:
            record, reasons = inspect_artifact(
                command.path, context["subject"], context["run_id"], at,
                context["max_evidence_age_seconds"], expected_type=command.type,
                allow_nonpassing=command.allow_nonpassing,
            )
            result = {"artifact": record, "reasons": reasons}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            result = {"artifact": None, "reasons": ["Invalid or unavailable artifact: " + str(exc)]}
        status = "blocked" if result["reasons"] else "passed"
        return envelope(operation, status, result), BLOCKED if status == "blocked" else PASSED

    request, policy = controls(command.request, command.policy)
    if operation == "gate":
        try:
            result = evaluate_gate(command.request, command.policy, at)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            # A complete, schema-valid host request may still reference broken
            # or unavailable evidence. Fail closed, never as a passing gate.
            result = {"decision": "blocked", "effect": request["effect"],
                      "scope": request["scope"], "reasons": ["Invalid or unavailable evidence: " + str(exc)]}
        status = "passed" if result["decision"] == "allowed" else "blocked"
        return envelope(operation, status, result), PASSED if status == "passed" else BLOCKED

    if operation == "artifact":
        try:
            record, reasons = inspect_artifact(
                command.path, request["subject"], request["run_id"], at,
                policy["max_evidence_age_seconds"], expected_type=command.type,
            )
            result = {"artifact_id": record["artifact_id"],
                      "artifact_type": record["artifact_type"], "reasons": reasons}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            result = {"artifact_id": None, "artifact_type": None,
                      "reasons": ["Invalid or unavailable artifact: " + str(exc)]}
        status = "blocked" if result["reasons"] else "passed"
        return envelope(operation, status, result), BLOCKED if status == "blocked" else PASSED

    raise InvalidInvocation("Unknown command.")


def main(argv=None):
    args = parser()
    try:
        selected = args.parse_args(argv)
        response, exit_code = decision(selected)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration) as exc:
        operation = selected.command if "selected" in locals() else "unknown"
        response, exit_code = envelope(operation, "invalid", errors=[str(exc)]), INVALID
    print(json.dumps(response, sort_keys=True, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
