#!/usr/bin/env python3
"""Versioned, read-only sfstack contract and evidence interface for external hosts.

All decisions delegate to the canonical sfstack validators and planner. This
entrypoint neither runs candidate code nor supplies permissions or evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from common import ROOT, contained_path, contracts, inspect_artifact, load_json, now, read_regular, validate_schema
from factory import evaluate_gate, plan

INTERFACE_VERSION = "1.0"
DISTRIBUTION_VERSION = "1.0.0"
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

    planner = commands.add_parser("plan", help="Bind a versioned recipe and find eligible steps")
    group = planner.add_mutually_exclusive_group(required=True)
    group.add_argument("--workflow", type=Path)
    group.add_argument("--recipe", help="Name of a bundled workflow")
    planner.add_argument("--run", required=True, type=Path)

    for command in (gate, artifact, planner):
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
    if operation == "recipe":
        name = command.name
        recipe = load_json(named_file("workflows", name, ".json"))
        validate_schema(recipe, "workflow")
        return envelope(operation, "passed", {"name": name, "workflow": recipe}), PASSED

    at = now(command.at)
    if operation == "plan":
        workflow = (command.workflow if command.workflow is not None
                    else named_file("workflows", command.recipe, ".json"))
        result = plan(workflow, command.run, at, root=ROOT)
        status = "blocked" if result["status"] == "blocked" else "passed"
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
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        operation = selected.command if "selected" in locals() else "unknown"
        response, exit_code = envelope(operation, "invalid", errors=[str(exc)]), INVALID
    print(json.dumps(response, sort_keys=True, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
