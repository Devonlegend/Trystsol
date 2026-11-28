"use client";

import { AnchorProvider, Program } from "@anchor-lang/core";
import { Connection, PublicKey, type Transaction, type VersionedTransaction } from "@solana/web3.js";

import { apiFetch } from "./api";
import idl from "./idl/project_registry.json";

export interface IntentPayload {
  instruction: string;
  program_id: string;
  signer: string;
  account: string;
  args: Record<string, any>;
  accounts: Record<string, any>;
}

export interface Intent {
  id: string;
  intent: string;
  object_type: string;
  object_id: string;
  payload: IntentPayload;
  expires_at: string;
}

interface WalletLike {
  publicKey: PublicKey | null;
  signTransaction: <T extends Transaction | VersionedTransaction>(
    transaction: T,
  ) => Promise<T | undefined>;
}

function bytes(hex: string): number[] {
  if (!/^[0-9a-fA-F]+$/.test(hex) || hex.length % 2 !== 0) {
    throw new Error("Invalid hex value.");
  }
  return Array.from({ length: hex.length / 2 }, (_, index) =>
    Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16),
  );
}

export async function sendIntent(
  intent: Intent,
  wallet: WalletLike,
  connection: Connection,
): Promise<string> {
  if (!wallet.publicKey) throw new Error("Wallet is not connected.");
  const provider = new AnchorProvider(connection, wallet as any, {
    commitment: "confirmed",
  });
  const program = new Program(idl as any, provider);
  const methods = program.methods as any;
  const payload = intent.payload;
  const args = payload.args;
  const accounts = payload.accounts;

  let builder: any;
  switch (payload.instruction) {
    case "register_project":
      builder = methods
        .registerProject(
          bytes(args.project_id_hex),
          bytes(args.metadata_hash_hex),
          args.metadata_uri,
          new PublicKey(args.founder),
        )
        .accounts({
          admin: new PublicKey(accounts.admin),
          registry: new PublicKey(accounts.registry),
          project: new PublicKey(accounts.project),
          systemProgram: new PublicKey(accounts.system_program),
        });
      break;
    case "publish_criteria_template":
      builder = methods
        .publishCriteriaTemplate(
          bytes(args.template_id_hex),
          args.version,
          bytes(args.criteria_hash_hex),
          args.criteria_uri,
        )
        .accounts({
          admin: new PublicKey(accounts.admin),
          registry: new PublicKey(accounts.registry),
          criteriaTemplate: new PublicKey(accounts.criteria_template),
          systemProgram: new PublicKey(accounts.system_program),
        });
      break;
    case "accept_authority_transfer":
      builder = methods.acceptAuthorityTransfer().accounts({
        pendingAuthority: new PublicKey(accounts.pending_authority),
        project: new PublicKey(accounts.project),
      });
      break;
    case "deactivate_reviewer":
      builder = methods.deactivateReviewer(new PublicKey(args.wallet)).accounts({
        admin: new PublicKey(accounts.admin),
        registry: new PublicKey(accounts.registry),
        reviewer: new PublicKey(accounts.reviewer),
      });
      break;
    case "add_reviewer":
      builder = methods.addReviewer(new PublicKey(args.wallet)).accounts({
        admin: new PublicKey(accounts.admin),
        registry: new PublicKey(accounts.registry),
        reviewer: new PublicKey(accounts.reviewer),
        systemProgram: new PublicKey(accounts.system_program),
      });
      break;
    case "create_milestone":
      builder = methods
        .createMilestone(bytes(args.milestone_id_hex), bytes(args.criteria_template_id_hex))
        .accounts({
          authority: new PublicKey(accounts.authority),
          project: new PublicKey(accounts.project),
          milestone: new PublicKey(accounts.milestone),
          criteriaTemplate: new PublicKey(accounts.criteria_template),
          systemProgram: new PublicKey(accounts.system_program),
        });
      break;
    case "assign_reviewers":
      builder = methods
        .assignReviewers(
          bytes(args.milestone_id_hex),
          (args.reviewers as string[]).map((walletAddress) => new PublicKey(walletAddress)),
          args.required_approvals,
        )
        .accounts({
          admin: new PublicKey(accounts.admin),
          registry: new PublicKey(accounts.registry),
          project: new PublicKey(accounts.project),
          milestone: new PublicKey(accounts.milestone),
        })
        .remainingAccounts(
          (accounts.reviewer_accounts as string[]).map((address) => ({
            pubkey: new PublicKey(address),
            isSigner: false,
            isWritable: false,
          })),
        );
      break;
    case "submit_milestone":
      builder = methods
        .submitMilestone(
          bytes(args.milestone_id_hex),
          bytes(args.evidence_hash_hex),
          args.evidence_uri,
        )
        .accounts({
          authority: new PublicKey(accounts.authority),
          project: new PublicKey(accounts.project),
          milestone: new PublicKey(accounts.milestone),
        });
      break;
    case "expire_round":
      builder = methods.expireRound(bytes(args.milestone_id_hex)).accounts({
        admin: new PublicKey(accounts.admin),
        registry: new PublicKey(accounts.registry),
        project: new PublicKey(accounts.project),
        milestone: new PublicKey(accounts.milestone),
      });
      break;
    case "verify_milestone":
      builder = methods.verifyMilestone(bytes(args.milestone_id_hex)).accounts({
        reviewerWallet: new PublicKey(accounts.reviewer_wallet),
        registry: new PublicKey(accounts.registry),
        reviewer: new PublicKey(accounts.reviewer),
        project: new PublicKey(accounts.project),
        milestone: new PublicKey(accounts.milestone),
        verification: new PublicKey(accounts.verification),
        systemProgram: new PublicKey(accounts.system_program),
      });
      break;
    case "reject_milestone":
      builder = methods.rejectMilestone(bytes(args.milestone_id_hex)).accounts({
        reviewerWallet: new PublicKey(accounts.reviewer_wallet),
        registry: new PublicKey(accounts.registry),
        reviewer: new PublicKey(accounts.reviewer),
        project: new PublicKey(accounts.project),
        milestone: new PublicKey(accounts.milestone),
        verification: new PublicKey(accounts.verification),
        systemProgram: new PublicKey(accounts.system_program),
      });
      break;
    default:
      throw new Error(`Unsupported instruction ${payload.instruction}.`);
  }

  const transaction = await builder.transaction();
  const latest = await connection.getLatestBlockhash("confirmed");
  transaction.feePayer = wallet.publicKey;
  transaction.recentBlockhash = latest.blockhash;

  const signed = await wallet.signTransaction(transaction);
  if (!signed) throw new Error("Wallet did not sign the transaction.");
  const signature = await connection.sendRawTransaction(signed.serialize(), {
    skipPreflight: false,
    maxRetries: 3,
  });
  await connection.confirmTransaction(
    {
      signature,
      blockhash: latest.blockhash,
      lastValidBlockHeight: latest.lastValidBlockHeight,
    },
    "confirmed",
  );

  await apiFetch(`/api/chain/intents/${intent.id}/confirm/`, {
    method: "POST",
    body: JSON.stringify({ signature }),
  });
  return signature;
}
