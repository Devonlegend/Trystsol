#!/usr/bin/env bash
# Build, deploy and publish the project_registry IDL.
# Devnet is the default. The wallet must be funded for program upgrade rent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROGRAM_DIR="$ROOT/programs/project_registry"
CLUSTER="${ANCHOR_CLUSTER:-devnet}"
RPC_URL="${ANCHOR_RPC_URL:-https://api.devnet.solana.com}"
KEYPAIR="$PROGRAM_DIR/target/deploy/project_registry-keypair.json"
IDL_CHECK="$(mktemp)"

export PATH="$HOME/.cargo/bin:$HOME/.avm/bin:$HOME/.local/share/solana/install/active_release/bin:$PATH"

cd "$PROGRAM_DIR"

echo "Anchor: $(anchor --version)"
echo "Solana: $(solana --version | head -1)"
echo "Cluster: $CLUSTER ($RPC_URL)"
echo "Program ID: $(solana-keygen pubkey "$KEYPAIR")"
echo "Wallet: $(solana address)"
echo "Wallet balance: $(solana balance --url "$RPC_URL")"

anchor build

SO_BYTES="$(stat -c%s target/deploy/project_registry.so)"
REQUIRED_LAMPORTS=$(( SO_BYTES * 6960 + 50000000 ))
BALANCE_LAMPORTS="$(solana balance --lamports --url "$RPC_URL" | awk '{print $1}')"
echo "Program size: $SO_BYTES bytes; estimated required lamports: $REQUIRED_LAMPORTS"
if (( BALANCE_LAMPORTS < REQUIRED_LAMPORTS )); then
  echo "Insufficient balance for program rent: have $BALANCE_LAMPORTS, need about $REQUIRED_LAMPORTS." >&2
  echo "Fund the wallet or use ANCHOR_CLUSTER=localnet for a local deployment." >&2
  exit 1
fi

anchor program deploy \
  --provider.cluster "$CLUSTER" \
  --provider.wallet "$HOME/.config/solana/id.json"

PROGRAM_ID="$(solana-keygen pubkey "$KEYPAIR")"
if [[ "$CLUSTER" == "localnet" || "$CLUSTER" == "localhost" ]]; then
  # Anchor deliberately skips on-chain IDL publishing on localnet.
  cp target/idl/project_registry.json "$IDL_CHECK"
  echo "Localnet: verifying the generated IDL artifact (on-chain publishing skipped)."
else
  anchor idl fetch "$PROGRAM_ID" --provider.cluster "$CLUSTER" > "$IDL_CHECK"
fi

python3 - "$IDL_CHECK" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    idl = json.load(handle)

required = {
    "initialize_registry",
    "propose_registry_admin",
    "accept_registry_admin",
    "add_reviewer",
    "deactivate_reviewer",
    "publish_criteria_template",
    "register_project",
    "update_project_metadata",
    "propose_authority_transfer",
    "accept_authority_transfer",
    "update_project_status",
    "create_milestone",
    "assign_reviewers",
    "submit_milestone",
    "verify_milestone",
    "reject_milestone",
    "expire_round",
}
found = {instruction["name"] for instruction in idl.get("instructions", [])}
missing = sorted(required - found)
if missing:
    raise SystemExit(f"Published IDL is missing instructions: {missing}")
print(f"Published IDL verified: {len(found)} instructions")
PY

"$ROOT/scripts/sync-idl.sh"
solana program show "$PROGRAM_ID" --url "$RPC_URL"
rm -f "$IDL_CHECK"
echo "Deployment complete: $PROGRAM_ID"
