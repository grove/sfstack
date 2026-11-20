#!/usr/bin/env bash
# A release-shaped, version-pinned consumer with no source-tree imports.
set -euo pipefail

source_root="$(cd "$(dirname "$0")/../.." && pwd)"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT

# Wheelhouse contains this exact distribution and its resolved dependencies.
# No source paths are installed into the consumer environment.
python -m pip wheel --disable-pip-version-check --wheel-dir "$temporary/wheels" "$source_root"
python - "$temporary/wheels" "$temporary/requirements.lock" <<'PY'
import hashlib
from email.parser import BytesParser
from pathlib import Path
import sys
import zipfile

entries = []
for wheel in sorted(Path(sys.argv[1]).glob("*.whl")):
    with zipfile.ZipFile(wheel) as archive:
        metadata_path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    entries.append(f"{metadata['Name']}=={metadata['Version']} --hash=sha256:{digest}")
Path(sys.argv[2]).write_text("\n".join(entries) + "\n", encoding="utf-8")
PY
python -m venv "$temporary/venv"
"$temporary/venv/bin/python" -m pip install --disable-pip-version-check \
  --no-index --find-links "$temporary/wheels" --require-hashes -r "$temporary/requirements.lock"

mkdir "$temporary/consumer"
cp -R "$source_root/examples" "$temporary/consumer/examples"
cp -R "$source_root/workflows" "$temporary/consumer/workflows"
cp "$source_root/tests/external_consumer/check.py" "$temporary/consumer/check.py"
cd "$temporary/consumer"
env -u PYTHONPATH -u PYTHONHOME "$temporary/venv/bin/python" \
  check.py "$temporary/venv/bin/sfstack-contract"
