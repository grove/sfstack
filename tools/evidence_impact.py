#!/usr/bin/env python3
"""Conservative offline revalidation planning for an explicit evidence dependency graph.

Outputs are advisory only: this tool never promotes evidence across checkpoints,
authenticates a source snapshot, or authorizes an external effect.
"""
from __future__ import annotations

import argparse
import json

from common import load_json, validate_schema


def plan_impact(manifest):
    validate_schema(manifest, "evidence-impact")
    before = manifest["before"]
    after = manifest["after"]
    old_inputs = before["inputs"]
    new_inputs = after["inputs"]
    changed = sorted(
        key for key in old_inputs.keys() | new_inputs.keys()
        if old_inputs.get(key) != new_inputs.get(key)
    )
    claims = {claim["id"]: claim for claim in manifest["claims"]}
    if len(claims) != len(manifest["claims"]):
        raise ValueError("Duplicate claim id.")
    for claim in claims.values():
        unknown = set(claim["needs"]) - claims.keys()
        if unknown:
            raise ValueError(f"{claim['id']}: unknown upstream claim(s): {sorted(unknown)}")
        if claim["id"] in claim["needs"]:
            raise ValueError(f"{claim['id']}: self-dependency")

    # A changed checkpoint digest with no recorded input change suggests incomplete
    # capture. Even a declared complete inventory cannot make that safe to reuse.
    unaccounted_change = (
        before["subject"]["input_digest"] != after["subject"]["input_digest"]
        and not changed
    )
    changed_environment = before["subject"]["environment"] != after["subject"]["environment"]
    inconsistent_digest = bool(
        changed and before["subject"]["input_digest"] == after["subject"]["input_digest"]
    )

    decisions = {}
    visiting = set()

    def assess(claim_id):
        if claim_id in decisions:
            return decisions[claim_id]
        if claim_id in visiting:
            raise ValueError(f"Dependency cycle at {claim_id}.")
        visiting.add(claim_id)
        claim = claims[claim_id]
        reasons = []
        if not manifest["complete_inventory"]:
            reasons.append("Dependency inventory is not declared complete.")
        if unaccounted_change or inconsistent_digest:
            reasons.append("Checkpoint input digest and tracked changes disagree.")
        if changed_environment:
            reasons.append("Execution environment changed.")
        if not claim["depends_on"]:
            reasons.append("No direct dependencies declared; conservative revalidation required.")
        missing = set(claim["depends_on"]) - (old_inputs.keys() & new_inputs.keys())
        if missing:
            reasons.append(f"Dependency inputs missing from a checkpoint: {sorted(missing)}.")
        affected = set(claim["depends_on"]) & set(changed)
        if affected:
            reasons.append(f"Dependency inputs changed: {sorted(affected)}.")
        for upstream in claim["needs"]:
            if assess(upstream)["decision"] == "revalidate":
                reasons.append(f"Upstream claim {upstream} requires revalidation.")
        visiting.remove(claim_id)
        decisions[claim_id] = {
            "id": claim_id,
            "decision": "revalidate" if reasons else "reuse-candidate",
            "reasons": reasons,
        }
        return decisions[claim_id]

    for claim_id in claims:
        assess(claim_id)
    ordered = [decisions[c["id"]] for c in manifest["claims"]]
    return {
        "from_revision": before["subject"]["revision"],
        "to_revision": after["subject"]["revision"],
        "changed_inputs": changed,
        "revalidate": [entry for entry in ordered if entry["decision"] == "revalidate"],
        "reuse_candidates": [entry for entry in ordered if entry["decision"] == "reuse-candidate"],
        "advisory_only": True,
        "note": (
            "Reuse candidates require host-established provenance and an explicit "
            "revalidation decision for the new subject. Existing gates still reject "
            "proof carrying an old subject. No external effect is authorized."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        result = plan_impact(load_json(args.manifest))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"evidence-impact: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
