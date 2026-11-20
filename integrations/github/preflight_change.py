#!/usr/bin/env python3
"""Unprivileged builder preflight for one *raw* sf-build-change JSON response.

Run on the exact bytes that will be supplied as submit_change.change_json.
This diagnostic does NOT grant publication authority and never replaces the
trusted host's separate strict parsing, scope checks, or verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

import automation


def check(proposal, schema, template):
    # Use the SAME strict parser as the host, including for nested objects.
    # An ordinary json.loads + json.dumps round trip silently discards
    # duplicate properties and must never be used to "repair" invalid input.
    response, raw = automation.read_json(proposal)
    expected, _ = automation.read_json(template)
    contract, _ = automation.read_json(schema)
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
                        help="File containing EXACT raw change_json bytes, not the safe-output envelope")
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        checksum = check(args.proposal, args.schema, args.template)
    except (OSError, ValueError, TypeError, KeyError, SchemaError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(1, "sfstack submission preflight: " + str(exc).splitlines()[0][:400] + "\n")
    print("sfstack submission preflight: OK (unique JSON keys, closed schema, pinned identity).")
    print("Checked change_json SHA-256: " + checksum)
    print("Advisory only: the trusted host must independently validate, reproduce RED/GREEN, and review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
