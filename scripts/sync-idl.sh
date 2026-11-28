#!/usr/bin/env bash
# Copy generated IDL/types from the Anchor build into the web app.
# Do not edit the copied files by hand.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$root/programs/project_registry/target/idl/project_registry.json"
dst="$root/apps/web/lib/idl/project_registry.json"
if [ ! -f "$src" ]; then
  echo "Missing $src. Run 'anchor build' in programs/project_registry first." >&2
  exit 1
fi
mkdir -p "$(dirname "$dst")"
cp "$src" "$dst"
echo "Copied IDL to $dst"
