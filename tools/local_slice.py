#!/usr/bin/env python3
"""Run one effect-free workflow node through an explicitly supplied local adapter.

This is a reference harness, NOT a sandbox or a production factory controller.
Only use an adapter executable already trusted and isolated by the host.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

from common import ROOT, contained_path, contracts, inspect_artifact, load_json, now
from factory import plan


def stderr_tail(stream):
    """Keep diagnostics useful without capturing an unbounded pipe in memory."""
    length = stream.seek(0, os.SEEK_END)
    stream.seek(max(0, length - 4096))
    tail = stream.read(4096).decode("utf-8", errors="replace").strip()
    return f"\nAdapter stderr (last 4096 bytes):\n{tail}" if tail else ""


def run_one(workflow_path, run_path, step_id, adapter_script, out_run, artifact_dir,
            at, timeout=60, root=ROOT):
    workflow_path = Path(workflow_path).resolve()
    run_path = Path(run_path).resolve()
    run_dir = run_path.parent
    if not 1 <= timeout <= 300:
        raise ValueError("Timeout must be between 1 and 300 seconds.")
    output_run = contained_path(run_dir, out_run)
    output_dir = contained_path(run_dir, artifact_dir)
    if output_run.parent != run_dir:
        raise ValueError("Output checkpoint must be beside the input run manifest.")
    if output_run.exists() or output_dir.exists():
        raise ValueError("Output checkpoint or artifact directory already exists.")
    if output_dir == run_dir or output_dir == output_run:
        raise ValueError("Invalid artifact output directory.")

    workflow = load_json(workflow_path)
    run = load_json(run_path)
    readiness = plan(workflow_path, run_path, at, root=root)
    if step_id not in readiness["ready"]:
        raise ValueError(f"Step {step_id} is not ready: {readiness['blocked'].get(step_id)}")
    step = next(item for item in workflow["steps"] if item["id"] == step_id)
    contract = contracts(root)[step["skill"]]
    # This harness has no enforcement boundary for writes. It must not be used
    # for even a nominally authorized effectful skill.
    if (contract["effects"] or run.get("selected_effects", {}).get(step_id)
            or len(contract["outputs"]) != 1):
        raise ValueError("Local slice accepts only one-output, effect-free invocations.")

    bindings = {}
    for name, source in step["bindings"].items():
        parts = source.split(":")
        if parts[0] == "input":
            path = run["inputs"][parts[1]]
        else:
            paths = run["completed"][parts[1]]
            if len(paths) != 1:
                raise ValueError(f"Ambiguous artifact binding {source}.")
            path = paths[0]
        bound = contained_path(run_dir, path)
        if not bound.is_file():
            raise ValueError(f"Missing bound artifact: {name}")
        bindings[name] = str(bound)

    script = Path(adapter_script).resolve()
    if not script.is_file():
        raise ValueError("Adapter script does not exist.")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    reservation = output_dir.with_name(f".{output_dir.name}.attempt.json")
    try:
        attempt = reservation.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ValueError(
            f"Interrupted or concurrent attempt recorded at {reservation}. "
            "Inspect its process and outputs before explicitly retrying."
        ) from exc
    with attempt:
        json.dump({"step": step_id, "input_checkpoint": str(run_path),
                   "output_checkpoint": str(output_run), "artifact_dir": str(output_dir),
                   "started_at": at.isoformat().replace("+00:00", "Z")}, attempt, indent=2)
        attempt.write("\n")
        attempt.flush()
        os.fsync(attempt.fileno())
    publication_started = False
    try:
        with tempfile.TemporaryDirectory(prefix=".sfstack-step-", dir=run_dir) as staging:
            stage = Path(staging)
            result_path = stage / "result.json"
            invocation = {
                "skill": step["skill"],
                "skill_root": str(root / "skills" / step["skill"]),
                "contract": contract,
                "step": step_id,
                "run_id": run["run_id"],
                "subject": run["subject"],
                "bindings": bindings,
                "observed_at": at.isoformat().replace("+00:00", "Z"),
                "output_type": contract["outputs"][0],
            }
            invocation_path = stage / "invocation.json"
            invocation_path.write_text(json.dumps(invocation, indent=2) + "\n", encoding="utf-8")
            # This diagnostic stream is intentionally outside the artifact
            # staging directory; successful bundles contain only adapter output.
            with tempfile.TemporaryFile(dir=run_dir) as diagnostics:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script), "--invocation", str(invocation_path),
                         "--output", str(result_path)],
                        cwd=run_dir, stdout=subprocess.DEVNULL, stderr=diagnostics,
                        timeout=timeout, check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise ValueError("Adapter exceeded the declared time limit."
                                     + stderr_tail(diagnostics)) from exc
                if proc.returncode != 0:
                    raise ValueError(f"Adapter exited with status {proc.returncode}."
                                     + stderr_tail(diagnostics))
            policy = load_json(contained_path(run_dir, run["policy"]))
            artifact, errors = inspect_artifact(
                result_path, run["subject"], run["run_id"], at,
                policy["max_evidence_age_seconds"], expected_type=contract["outputs"][0],
                allow_nonpassing=workflow.get("mode") == "quality",
            )
            if artifact["producer"] != {"skill": step["skill"], "version": contract["version"]}:
                errors.append("Producer identity/version does not match the invoked skill.")
            if errors:
                raise ValueError("Adapter returned invalid evidence: " + "; ".join(errors))
            # The run file is not overwritten. A new checkpoint is written only
            # after the output has passed evidence and producer validation.
            stage.joinpath("invocation.json").unlink()
            publication_started = True
            shutil.copytree(stage, output_dir)
        updated = deepcopy(run)
        updated.setdefault("completed", {})[step_id] = [
            str((output_dir / "result.json").relative_to(run_dir))
        ]
        # Publish the completed manifest atomically without replacing an existing
        # checkpoint. A reader must never observe half of a JSON document.
        temporary_run = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=run_dir,
                                             prefix=".sfstack-checkpoint-", delete=False) as stream:
                temporary_run = Path(stream.name)
                json.dump(updated, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary_run, output_run)
        finally:
            if temporary_run is not None:
                temporary_run.unlink(missing_ok=True)
    except Exception:
        # A known adapter/validation failure has no usable result to preserve.
        # Once publication starts, or on process interruption (BaseException),
        # retain the reservation so an ambiguous attempt is never auto-retried.
        if not publication_started:
            reservation.unlink(missing_ok=True)
        raise
    reservation.unlink()
    next_state = plan(workflow_path, output_run, at, root=root)
    return {
        "completed_step": step_id,
        "artifact": str(output_dir / "result.json"),
        "artifact_status": artifact["status"],
        "checkpoint": str(output_run),
        "next_ready": next_state["ready"],
        "workflow_status": next_state["status"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--adapter-script", required=True)
    parser.add_argument("--out-run", required=True, help="New JSON filename beside --run")
    parser.add_argument("--artifact-dir", required=True, help="New directory under --run parent")
    parser.add_argument("--at", help="UTC observation time; fixture/testing only")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)
    try:
        result = run_one(
            args.workflow, args.run, args.step, args.adapter_script, args.out_run,
            args.artifact_dir, now(args.at), args.timeout,
        )
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"local-slice: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
