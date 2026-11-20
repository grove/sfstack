#!/usr/bin/env python3
"""Stage the compiler-redacted, declared proposal artifact for trusted verification.

The safe-output job has no candidate-execution or repository-write authority.
Never read an agent-specified path: gh-aw v1.2.2 downloads custom-job declared
artifacts relative to the fixed agent_output.json download root. The agent job
runs mandatory secret redaction *before* that artifact is uploaded.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys

MAX_SUBMISSION = 120_000


def read_bounded_regular(path):
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Agent artifact must be a single regular non-linked file.")
        if info.st_size > MAX_SUBMISSION:
            raise ValueError("Agent artifact exceeds the bounded submission size.")
        data = source.read(MAX_SUBMISSION + 1)
        if len(data) > MAX_SUBMISSION:
            raise ValueError("Agent artifact exceeds the bounded submission size.")
    return data


def stage(agent_output, destination):
    agent_output = Path(agent_output)
    if not agent_output.is_absolute():
        raise ValueError("Expected a fixed absolute gh-aw agent output path.")
    # gh-aw v1.2.2 preserves declared /tmp/gh-aw/agent/... paths under the
    # downloaded artifact root, next to agent_output.json.
    source_root = agent_output.parent
    if agent_output.name != "agent_output.json":
        raise ValueError("Expected the compiler-owned agent_output.json.")
    proposal = source_root / "agent" / "sfstack-software" / "proposal.json"
    destination = Path(destination)
    if destination.exists() or destination.resolve().is_relative_to(source_root.resolve()):
        raise ValueError("Destination must be new and outside the downloaded agent artifact.")
    # Read both fixed source files before writing anything to the handoff.
    receipt = read_bounded_regular(agent_output)
    payload = read_bounded_regular(proposal)
    destination.mkdir(parents=True)
    for name, content in (("submission.json", receipt), ("proposal.json", payload)):
        with (destination / name).open("xb") as stream:
            stream.write(content)
    return len(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-output", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        length = stage(args.agent_output, args.out)
    except (OSError, ValueError, TypeError) as exc:
        # No source bytes, filenames, or token-bearing paths in diagnostics.
        print("sfstack artifact staging blocked: " + type(exc).__name__, file=sys.stderr)
        return 1
    print(f"sfstack: staged declared, secret-redacted proposal ({length} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
