#!/usr/bin/env python3
"""Export independent skill folders. Does not install into any agent or contact services."""
import argparse
from pathlib import Path
import shutil

from common import ROOT, contracts
from sync_protocol import sync
from validate import frontmatter


def export(output, selected=None):
    catalog = contracts()
    selected = selected or sorted(catalog)
    if len(selected) != len(set(selected)):
        raise ValueError('A skill may be selected only once.')
    unknown = set(selected) - catalog.keys()
    if unknown:
        raise ValueError('Unknown skills: ' + ', '.join(sorted(unknown)))
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Export destination must be absent or an empty directory.')
    if sync(check=True):
        raise ValueError('Shared references are stale; synchronize them before export.')
    # Complete all source checks before creating an output directory.
    sources = []
    for name in selected:
        source = ROOT / 'skills' / name
        frontmatter((source / 'SKILL.md').read_text())
        for relative in ('SKILL.md', 'contract.json', 'references/protocol.md', 'references/artifact.schema.json'):
            path = source / relative
            if path.is_symlink() or not path.is_file():
                raise ValueError(f'Invalid package resource: {path}')
        sources.append((name, source))
    output.mkdir(parents=True, exist_ok=True)
    for name, source in sources:
        target = output / name
        (target / 'references').mkdir(parents=True)
        for relative in ('SKILL.md', 'contract.json', 'references/protocol.md', 'references/artifact.schema.json'):
            shutil.copyfile(source / relative, target / relative)
        shutil.copyfile(ROOT / 'LICENSE', target / 'LICENSE')
    return len(sources)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--skill', action='append', help='Export only this skill; repeat to select more')
    args = parser.parse_args()
    try:
        count = export(args.output, args.skill)
        print(f'Exported {count} independent skill packages to {args.output}.')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
