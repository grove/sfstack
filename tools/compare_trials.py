#!/usr/bin/env python3
"""Summarize paired results for bare-agent, skills-only, and contracts runs.

This tool does not execute agents or independently verify reported outcomes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from statistics import mean

from common import load_json, validate_schema

VARIANTS = ("bare", "skills", "contracts")
METRICS = (
    "correct", "unsupported_claims", "human_interventions",
    "elapsed_seconds", "cost_usd", "recovered", "safety_violations",
)


def compare_trials(data):
    validate_schema(data, "comparative-trials")
    pairs = defaultdict(dict)
    for trial in data["trials"]:
        key = (trial["case_id"], trial["trial_id"])
        group = pairs[key]
        variant = trial["variant"]
        if variant in group:
            raise ValueError(f"Duplicate trial: {key}, {variant}")
        group[variant] = trial

    for key, group in pairs.items():
        if set(group) != set(VARIANTS):
            raise ValueError(f"Unpaired trial {key}: expected {sorted(VARIANTS)}")
        if len({record["agent"] for record in group.values()}) != 1:
            raise ValueError(f"Agent mismatch in paired trial {key}.")
        if len({record["environment"] for record in group.values()}) != 1:
            raise ValueError(f"Environment mismatch in paired trial {key}.")

    ordered_pairs = [pairs[key] for key in sorted(pairs)]
    def average(records):
        return {name: round(mean(float(record[name]) for record in records), 6)
                for name in METRICS}
    means = {variant: average([pair[variant] for pair in ordered_pairs])
             for variant in VARIANTS}
    differences = {
        f"contracts-minus-{other}": {
            name: round(mean(float(pair["contracts"][name]) - float(pair[other][name])
                             for pair in ordered_pairs), 6)
            for name in METRICS
        }
        for other in ("bare", "skills")
    }
    return {
        "paired_trials": len(ordered_pairs),
        "cases": sorted({case_id for case_id, _ in pairs}),
        "means": means,
        "paired_mean_differences": differences,
        "interpretation": (
            "Correct/recovered higher is better; unsupported claims, interventions, "
            "time, cost, and safety violations lower is better. Descriptive only: "
            "no confidence intervals, causal inference, or authenticity proof."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        result = compare_trials(load_json(args.input))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"comparative-trials: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
