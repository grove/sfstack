#!/usr/bin/env python3
"""Advance a bounded local workflow, keeping an immutable checkpoint per step.

Use one controller at a time in a run directory. Supplied adapters must already
be trusted and isolated by the host; this is not a sandbox or a write controller.
No step is retried automatically. Resume by explicitly passing the returned
checkpoint, after inspecting any failed or interrupted attempt.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import ROOT, contracts, load_json, now
from factory import plan
from local_slice import run_one
from quality_report import consolidate


def run_local(workflow_path, run_path, adapter_script=None, at=None,
              max_steps=1, timeout=60, root=ROOT):
    """Run at most max_steps effect-free nodes; return the last saved checkpoint.

    Quality consolidation uses the built-in offline summarizer. Other nodes
    require an explicitly selected adapter. ``at`` is a fixed fixture time;
    leaving it unset rechecks current evidence age before every step.
    """
    if type(max_steps) is not int or not 1 <= max_steps <= 100:
        raise ValueError("max_steps must be an integer between 1 and 100.")
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise ValueError("Timeout must be an integer between 1 and 300 seconds.")
    workflow_path = Path(workflow_path).resolve()
    checkpoint = Path(run_path).resolve()
    workflow = load_json(workflow_path)
    catalog = contracts(root)
    completed_steps = []

    def state_result(state, reason, **extra):
        return {**state, "checkpoint": str(checkpoint),
                "completed_steps": completed_steps, "stop_reason": reason, **extra}

    for _ in range(max_steps):
        observed_at = at if at is not None else now()
        state = plan(workflow_path, checkpoint, observed_at, root)
        if state["status"] != "ready":
            return state_result(state, "complete" if state["status"] == "complete"
                                else "workflow-blocked")
        step_id = state["ready"][0]
        step = next(item for item in workflow["steps"] if item["id"] == step_id)
        contract = catalog[step["skill"]]
        run = load_json(checkpoint)
        if (contract["effects"] or run.get("selected_effects", {}).get(step_id)
                or len(contract["outputs"]) != 1):
            return state_result(state, "host-required", status="blocked", error=(
                f"{step_id} requires an effectful or multiple-output host adapter; "
                "the local runner accepts one-output, effect-free steps only."))
        builtin_summary = (workflow.get("mode") == "quality"
                           and step["skill"] == "sf-consolidate-quality")
        if not builtin_summary and adapter_script is None:
            return state_result(state, "adapter-required", status="blocked", error=(
                f"{step_id} needs an explicitly selected trusted Python adapter. "
                "Pass --adapter-script to execute it."))

        number = len(run["completed"]) + 1
        output_run = f"checkpoint-{number:04d}-{step_id}.json"
        output_dir = f"artifacts/{number:04d}-{step_id}"
        try:
            if builtin_summary:
                summary = consolidate(workflow_path, checkpoint, output_dir,
                                      observed_at, output_run, root)
                result = {"completed_step": step_id, "artifact": summary["assessment"],
                          "artifact_status": summary["status"],
                          "checkpoint": summary["checkpoint"]}
            else:
                result = run_one(workflow_path, checkpoint, step_id, adapter_script,
                                 output_run, output_dir, observed_at, timeout, root)
        except (OSError, ValueError, KeyError) as exc:
            return state_result(state, "step-error", status="error", error=str(exc),
                                failed_step=step_id)
        checkpoint = Path(result["checkpoint"])
        completed_steps.append({"step": step_id, "artifact": result["artifact"],
                                "status": result["artifact_status"]})

    state = plan(workflow_path, checkpoint, at if at is not None else now(), root)
    return state_result(state, "step-limit" if state["status"] == "ready"
                        else "complete" if state["status"] == "complete" else "workflow-blocked")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--adapter-script", help="Trusted Python adapter; required except for consolidation")
    parser.add_argument("--max-steps", required=True, type=int, help="Maximum steps for this invocation (1-100)")
    parser.add_argument("--timeout", type=int, default=60, help="Seconds per adapter (1-300)")
    parser.add_argument("--at", help="Fixed UTC observation time for offline fixtures only")
    args = parser.parse_args(argv)
    try:
        result = run_local(args.workflow, args.run, args.adapter_script,
                           now(args.at) if args.at else None, args.max_steps, args.timeout)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"local-run: {exc}\n")
    print(json.dumps(result, indent=2))
    nonpassing = any(status != "passed" for outputs in result.get("outcomes", {}).values()
                     for kind, status in outputs.items() if kind == "quality-assessment")
    return (1 if result["status"] == "error" else
            0 if result["status"] == "complete" and not nonpassing else 2)


if __name__ == "__main__":
    raise SystemExit(main())
