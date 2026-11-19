#!/usr/bin/env python3
"""Validate sfstack packages, schemas, recipe graphs, examples, and local doc links."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from common import ROOT, EFFECT_CAPABILITY, contracts, load_json, validate_schema, workflow_errors
from sync_protocol import sync


def frontmatter(text):
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("Missing YAML frontmatter.")
    raw = text[4:].split("\n---\n", 1)[0]
    result = {}
    for line in raw.splitlines():
        if ": " not in line:
            raise ValueError("Use canonical single-line name and description fields.")
        key, value = line.split(": ", 1)
        if key in result:
            raise ValueError(f"Duplicate frontmatter key {key}.")
        if key == 'description' and not value.startswith('"'):
            raise ValueError('Use a JSON-quoted description scalar (also valid YAML).')
        if value.startswith('"'):
            value = json.loads(value)
        result[key] = value
    if set(result) != {"name", "description"}:
        raise ValueError("Use only name and description in frontmatter.")
    if not isinstance(result['name'], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", result['name']):
        raise ValueError("Invalid skill name.")
    if len(result['name']) > 64:
        raise ValueError("Skill name exceeds 64 characters.")
    if not isinstance(result['description'], str) or not 1 <= len(result['description']) <= 1024:
        raise ValueError("Invalid description length.")
    if '<' in result['description'] or '>' in result['description']:
        raise ValueError("Description includes markup delimiters.")
    return result


def check_links(path, root):
    text = path.read_text(encoding="utf-8")
    # Code examples are not navigational links.
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    errors = []
    for raw in re.findall(r"\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", text):
        target = raw.split("#", 1)[0]
        if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            continue
        destination = (path.parent / unquote(target)).resolve()
        if not destination.is_relative_to(root.resolve()) or not destination.exists():
            errors.append(f"{path.relative_to(root)}: broken or escaping link {raw}")
    return errors


def validate_repository(root=ROOT):
    errors = []
    for path in sorted((root / "schemas").glob("*.json")):
        try:
            Draft202012Validator.check_schema(load_json(path))
        except (ValueError, OSError, SchemaError) as exc:
            errors.append(f"{path.name}: {exc}")
    try:
        catalog = contracts(root)
    except (ValueError, OSError) as exc:
        return [str(exc)], {}
    if not catalog:
        errors.append("No skill contracts found.")
    skill_paths = sorted((root / "skills").glob("*/SKILL.md"))
    if {p.parent.name for p in skill_paths} != set(catalog):
        errors.append("Skill directories and contracts do not match.")
    for path in skill_paths:
        try:
            text = path.read_text(encoding="utf-8")
            meta = frontmatter(text)
            if meta['name'] != path.parent.name:
                errors.append(f"{path}: directory and name disagree.")
            if len(text.splitlines()) >= 500:
                errors.append(f"{path}: skill exceeds the 500-line limit.")
            for link in ('(references/protocol.md)', '(contract.json)', '(references/artifact.schema.json)'):
                if link not in text:
                    errors.append(f"{path}: required self-contained resource link {link} missing.")
            if re.search(r'\b(TODO|TBD|FIXME)\b|\[Insert ', text):
                errors.append(f"{path}: unfinished authoring marker.")
            contract = catalog[path.parent.name]
            names = [item['name'] for item in contract['inputs']]
            if len(names) != len(set(names)):
                errors.append(f"{path}: duplicate contract inputs.")
            conditionals = [item['effect'] for item in contract.get('conditional_effects', [])]
            if len(set(conditionals)) != len(conditionals) or set(conditionals) & set(contract['effects']):
                errors.append(f"{path}: conditional effects repeat or overlap baseline effects.")
            for effect in contract['effects'] + conditionals:
                capability = EFFECT_CAPABILITY[effect]
                if capability not in contract['capabilities']:
                    errors.append(f"{path}: effect {effect} lacks capability {capability}.")
        except (ValueError, KeyError) as exc:
            errors.append(f"{path}: {exc}")
    for path in sorted((root / "workflows").glob("*.json")):
        try:
            workflow = load_json(path)
            validate_schema(workflow, "workflow", root)
            if path.stem != workflow['id']:
                errors.append(f"{path}: filename differs from workflow ID.")
            errors.extend(f"{path.name}: {error}" for error in workflow_errors(workflow, catalog))
        except (ValueError, OSError) as exc:
            errors.append(f"{path.name}: {exc}")
    for path in sorted((root / "adapters").glob("*.json")):
        try:
            manifest = load_json(path)
            validate_schema(manifest, "adapter", root)
            declared = set(manifest['capabilities'])
            for operation in manifest['operations']:
                if operation['capability'] not in declared:
                    errors.append(f"{path.name}: undeclared operation capability.")
        except (ValueError, OSError) as exc:
            errors.append(f"{path.name}: {exc}")
    index_path = root / 'examples/index.json'
    if index_path.exists():
        for example in load_json(index_path):
            try:
                path = root / 'examples' / example['path']
                validate_schema(load_json(path), example['schema'], root)
            except (ValueError, OSError) as exc:
                errors.append(f"{example['path']}: {exc}")
    for path in sorted(root.rglob("*.md")):
        if not any(part in {'.git', '.venv', 'dist'} for part in path.relative_to(root).parts):
            errors.extend(check_links(path, root))
    errors.extend(f"Stale protocol copy: {path}" for path in sync(root, check=True))
    catalog_doc = root / 'docs/reference/catalog.md'
    if catalog_doc.exists():
        text = catalog_doc.read_text()
        for name in catalog:
            if name not in text:
                errors.append(f"Catalog documentation omits {name}.")
    for quadrant in ('tutorials', 'how-to', 'reference', 'explanation'):
        if not list((root / 'docs' / quadrant).glob('*.md')):
            errors.append(f"Missing Diataxis documentation quadrant: {quadrant}.")
    return errors, {"skills": len(catalog), "workflows": len(list((root / 'workflows').glob('*.json'))),
                    "schemas": len(list((root / 'schemas').glob('*.json')))}


if __name__ == '__main__':
    errors, counts = validate_repository()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        raise SystemExit(1)
    print('Validation passed: ' + ', '.join(f'{value} {key}' for key, value in counts.items()) + '.')
