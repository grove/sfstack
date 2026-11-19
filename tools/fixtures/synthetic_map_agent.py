#!/usr/bin/env python3
"""Synthetic read-only adapter for illustrating local_slice's result protocol.

It does not run an LLM, inspect a repository, or establish a real project map.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--invocation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    ctx = json.loads(Path(args.invocation).read_text(encoding="utf-8"))
    if ctx["skill"] != "sf-map-project":
        raise ValueError("This fixture supports sf-map-project only.")
    path = Path(args.output)
    evidence = path.parent / "request-evidence.txt"
    evidence.write_bytes(Path(ctx["bindings"]["request"]).read_bytes())
    artifact = {
        "schema_version": "1.0", "artifact_id": "synthetic-project-context",
        "artifact_type": "project-context",
        "producer": {"skill": ctx["skill"], "version": ctx["contract"]["version"]},
        "run_id": ctx["run_id"], "status": "passed",
        "created_at": ctx["observed_at"], "subject": ctx["subject"],
        "summary": "Synthetic adapter handshake only; no repository mapping was performed.",
        "evidence": [{
            "id": "request-input", "kind": "input", "uri": evidence.name,
            "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            "description": "Unmodified synthetic request artifact used to exercise transport."
        }],
        "checks": [{
            "id": "fixture-transport", "status": "passed", "evidence": ["request-input"],
            "detail": "Confirmed that the adapter received the bound request file."
        }],
        "unresolved": ["Actual repository map requires a real, qualified agent adapter."],
        "next_action": "Replace this fixture with a real adapter before evaluating behavior.",
        "payload": {"entry_points": [], "behavior_boundaries": [], "verification_paths": []}
    }
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
