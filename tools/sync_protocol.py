#!/usr/bin/env python3
"""Keep standalone protocol and artifact schema references in sync."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(root=ROOT, check=False):
    sources = {
        'protocol.md': (root / "protocol/execution.md").read_bytes(),
        'artifact.schema.json': (root / 'schemas/artifact.schema.json').read_bytes(),
    }
    stale = []
    for skill in sorted((root / "skills").glob("sf-*/SKILL.md")):
        for name, source in sources.items():
            target = skill.parent / "references" / name
            if not target.exists() or target.read_bytes() != source:
                stale.append(str(target.relative_to(root)))
                if not check:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source)
    return stale


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = sync(check=args.check)
    if args.check and stale:
        print("Shared reference copies differ:\n" + "\n".join(stale))
        raise SystemExit(1)
    print(f"Shared reference copies {'checked' if args.check else 'synchronized'}.")
