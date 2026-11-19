#!/usr/bin/env python3
"""Normalize an exported tracker item using an explicit mapping; never writes a tracker."""
import argparse
import json
from pathlib import Path

from common import load_json, validate_schema


def read_field(item, field):
    current = item
    for part in field.split('.'):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f'Missing native field: {field}')
        current = current[part]
    return current


def normalize(item, mapping):
    validate_schema(mapping, 'tracker-mapping')
    result = {name: read_field(item, path) for name, path in mapping['fields'].items()}
    native_state = result['state']
    if not isinstance(native_state, str) or native_state not in mapping['states']:
        raise ValueError(f'Unmapped tracker state: {native_state!r}')
    native_id = result['id']
    if not isinstance(native_id, (str, int)) or isinstance(native_id, bool):
        raise ValueError('Native item identity must be a string or integer.')
    if not isinstance(result['version'], (str, int)) or isinstance(result['version'], bool):
        raise ValueError('Native version must be an explicit string or integer.')
    result.update(schema_version='1.0', id=str(native_id), version=str(result['version']),
                  state=mapping['states'][native_state],
                  source={'adapter': mapping['id'], 'native_id': str(native_id), 'native_state': native_state})
    validate_schema(result, 'work-item')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', required=True, type=Path)
    parser.add_argument('--item', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(normalize(load_json(args.item), load_json(args.mapping)), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
