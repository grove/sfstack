#!/usr/bin/env bash
# A release-shaped, version-pinned consumer with no source-tree imports.
set -euo pipefail

source_root="$(cd "$(dirname "$0")/../.." && pwd)"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT

# Wheelhouse contains this exact distribution and its resolved dependencies.
# No source paths are installed into the consumer environment.
python -m pip wheel --disable-pip-version-check --wheel-dir "$temporary/wheels" "$source_root"
python -m venv "$temporary/venv"
"$temporary/venv/bin/python" -m pip install --disable-pip-version-check \
  --no-index --find-links "$temporary/wheels" 'sfstack-contracts==1.0.0'

mkdir "$temporary/consumer"
cp -R "$source_root/examples" "$temporary/consumer/examples"
cp -R "$source_root/workflows" "$temporary/consumer/workflows"
cp "$source_root/tests/external_consumer/check.py" "$temporary/consumer/check.py"
cd "$temporary/consumer"
env -u PYTHONPATH -u PYTHONHOME "$temporary/venv/bin/python" \
  check.py "$temporary/venv/bin/sfstack-contract"
