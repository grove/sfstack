#!/usr/bin/env python3
"""Unprivileged builder preflight for one *raw* sf-build-change JSON response.

Run on the exact UTF-8 JSON file declared as the gh-aw custom safe-output
job's agent artifact. The safe-output tool receives only its SHA-256 receipt.
This diagnostic does NOT grant publication authority and never replaces the
trusted host's separate strict parsing, scope checks, or verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

# Agent execution may use a different Python environment from its controller
# checkout. Duplicate detection and identity validation require stdlib only;
# full JSON Schema is checked here when jsonschema is available, and ALWAYS
# checked independently by the trusted host on submitted bytes.
try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:
    Draft202012Validator = None
    SchemaError = ValueError

import automation


def check(proposal, schema, template):
    # Use the SAME strict parser as the host, including for nested objects.
    # An ordinary json.loads + json.dumps round trip silently discards
    # duplicate properties and must never be used to "repair" invalid input.
    response, raw = automation.read_json(proposal)
    expected, _ = automation.read_json(template)
    contract, _ = automation.read_json(schema)
    if not isinstance(response, dict):
        raise ValueError("The raw change_json must be one JSON object.")
    if not isinstance(contract, dict) or not isinstance(contract.get("properties"), dict):
        raise ValueError("The trusted change schema is malformed.")
    required = set(contract.get("required", []))
    allowed = set(contract["properties"])
    if set(response) - allowed or required - set(response):
        raise ValueError("Closed schema rejected unexpected or missing top-level fields.")
    if Draft202012Validator is not None:
        Draft202012Validator.check_schema(contract)
        violations = list(Draft202012Validator(contract).iter_errors(response))
        if violations:
            first = sorted(violations, key=lambda v: (str(v.json_path), str(v.validator)))[0]
            # Never echo submitted source text or any credentials into job logs.
            raise ValueError("Closed schema rejected " + first.json_path
                             + " (" + str(first.validator) + ").")
    if response["run_id"] != expected["run_id"] or response["subject"] != expected["subject"]:
        raise ValueError("Proposal run_id or subject differs from the pinned template.")
    if response["status"] == "passed" and (response["remaining_work"]
                                          or not response["criteria_addressed"]
                                          or not response["behavior_changes"]
                                          or not response["checks_run"]
                                          or not response["edits"]):
        raise ValueError("Passing proposal is missing required work or contains remaining_work.")
    return hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True, type=Path,
                        help="Exact raw proposal.json bytes for the declared, redacted agent artifact")
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        checksum = check(args.proposal, args.schema, args.template)
    except (OSError, ValueError, TypeError, KeyError, SchemaError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(1, "sfstack submission preflight: " + str(exc).splitlines()[0][:400] + "\n")
    print("sfstack submission preflight: OK (unique JSON keys, allowed fields, pinned identity).")
    if Draft202012Validator is None:
        print("Full schema validation deferred: jsonschema unavailable to the agent; host validation remains required.")
    else:
        print("JSON Schema preflight: OK (independent trusted host validation remains required).")
    print("Checked change_json SHA-256: " + checksum)
    print("Advisory only: the trusted host must independently validate, reproduce RED/GREEN, and review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
