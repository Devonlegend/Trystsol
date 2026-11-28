/**
 * Phase 0 Devnet end-to-end.
 *
 * Signs in with three keypairs (SIWS), drives the API, signs every prepared intent
 * with the Anchor client, sends it to Devnet, confirms it through the backend, then
 * clears the read-model and replays the indexer to prove backfill.
 *
 * Run with: npm run e2e:devnet
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { AnchorProvider, Program } from "@anchor-lang/core";
import nacl from "tweetnacl";
import {
  Connection,
  Keypair,
  PublicKey,
  SystemProgram,
  Transaction,
} from "@solana/web3.js";

import { createHttpApi } from "../src/httpApi.js";
import { runOnce } from "../src/indexer.js";
import { createWeb3Rpc } from "../src/web3Rpc.js";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
const RPC_URL =
  process.env.SERVER_RPC_URL ??
  process.env.SOLANA_RPC_URL ??
  "https://api.devnet.solana.com";
const PROGRAM_ID = process.env.PROGRAM_ID ?? "CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB";
const INDEXER_SECRET = process.env.INDEXER_SHARED_SECRET ?? "dev-indexer-secret";
const repoRoot = path.resolve(import.meta.dirname, "../../..");
const programId = new PublicKey(PROGRAM_ID);
const connection = new Connection(RPC_URL, "confirmed");
const idl = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "programs/project_registry/target/idl/project_registry.json"),
    "utf8",
  ),
);

function loadOrCreate(file: string): Keypair {
  if (fs.existsSync(file)) {
    const secret = JSON.parse(fs.readFileSync(file, "utf8"));
    return Keypair.fromSecretKey(Uint8Array.from(secret));
  }
  const keypair = Keypair.generate();
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  fs.writeFileSync(file, JSON.stringify(Array.from(keypair.secretKey)), { mode: 0o600 });
  return keypair;
}

const admin = Keypair.fromSecretKey(
  Uint8Array.from(JSON.parse(fs.readFileSync(path.join(os.homedir(), ".config/solana/id.json"), "utf8"))),
);
const founder = loadOrCreate(path.join(os.homedir(), ".config/solana/trystsol/founder.json"));
const reviewer = loadOrCreate(path.join(os.homedir(), ".config/solana/trystsol/reviewer.json"));
const reviewerTwo = loadOrCreate(
  path.join(os.homedir(), ".config/solana/trystsol/reviewer-two.json"),
);

function providerFor(keypair: Keypair) {
  const wallet = {
    publicKey: keypair.publicKey,
    signTransaction: async (transaction: any) => {
      transaction.sign(keypair);
      return transaction;
    },
    signAllTransactions: async (transactions: any[]) => {
      transactions.forEach((transaction) => transaction.sign(keypair));
      return transactions;
    },
  };
  return new AnchorProvider(connection, wallet as any, { commitment: "confirmed" });
}

function programFor(keypair: Keypair) {
  return new Program(idl as any, providerFor(keypair));
}

async function sendTransaction(transaction: Transaction, keypair: Keypair): Promise<string> {
  const latest = await connection.getLatestBlockhash("confirmed");
  transaction.feePayer = keypair.publicKey;
  transaction.recentBlockhash = latest.blockhash;
  transaction.sign(keypair);
  const signature = await connection.sendRawTransaction(transaction.serialize(), {
    skipPreflight: false,
    maxRetries: 3,
  });
  await connection.confirmTransaction(
    { signature, blockhash: latest.blockhash, lastValidBlockHeight: latest.lastValidBlockHeight },
    "confirmed",
  );
  return signature;
}

async function ensureFunded(keypair: Keypair, minimumSol: number) {
  const balance = await connection.getBalance(keypair.publicKey);
  if (balance >= minimumSol * 1e9) return;
  const lamports = Math.ceil(minimumSol * 1e9) - balance;
  console.log(`Funding ${keypair.publicKey.toBase58()} with ${lamports} lamports`);
  const transaction = new Transaction().add(
    SystemProgram.transfer({
      fromPubkey: admin.publicKey,
      toPubkey: keypair.publicKey,
      lamports,
    }),
  );
  await sendTransaction(transaction, admin);
}

async function http(
  method: string,
  route: string,
  body?: unknown,
  token?: string,
): Promise<any> {
  const response = await fetch(`${API_URL}${route}`, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(`${method} ${route} -> ${response.status}: ${text}`);
  }
  return data;
}

function siwsMessage(challenge: any, address: string): string {
  let message = `${challenge.domain} wants you to sign in with your Solana account:\n${address}`;
  if (challenge.statement) message += `\n\n${challenge.statement}`;
  const fields = [
    `URI: ${challenge.uri}`,
    `Version: ${challenge.version}`,
    `Chain ID: ${challenge.chainId}`,
    `Nonce: ${challenge.nonce}`,
    `Issued At: ${challenge.issuedAt}`,
    `Expiration Time: ${challenge.expirationTime}`,
  ];
  return `${message}\n\n${fields.join("\n")}`;
}

async function login(keypair: Keypair): Promise<string> {
  const challenge = await http("POST", "/api/auth/nonce/", {});
  const message = siwsMessage(challenge, keypair.publicKey.toBase58());
  const signature = nacl.sign.detached(Buffer.from(message, "utf8"), keypair.secretKey);
  const result = await http("POST", "/api/auth/verify/", {
    message,
    signature: Buffer.from(signature).toString("base64"),
  });
  return result.access;
}

function hexBytes(hex: string): number[] {
  return Array.from({ length: hex.length / 2 }, (_, index) =>
    Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16),
  );
}

async function signIntent(intent: any, keypair: Keypair, token: string): Promise<string> {
  const program = programFor(keypair);
  const methods = program.methods as any;
  const payload = intent.payload;
  const args = payload.args;
  const accounts = payload.accounts;
  let builder: any;

  switch (payload.instruction) {
    case "register_project":
      builder = methods
        .registerProject(
          hexBytes(args.project_id_hex),
          hexBytes(args.metadata_hash_hex),
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
          hexBytes(args.template_id_hex),
          args.version,
          hexBytes(args.criteria_hash_hex),
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
        .createMilestone(
          hexBytes(args.milestone_id_hex),
          hexBytes(args.criteria_template_id_hex),
        )
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
          hexBytes(args.milestone_id_hex),
          (args.reviewers as string[]).map((address) => new PublicKey(address)),
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
          hexBytes(args.milestone_id_hex),
          hexBytes(args.evidence_hash_hex),
          args.evidence_uri,
        )
        .accounts({
          authority: new PublicKey(accounts.authority),
          project: new PublicKey(accounts.project),
          milestone: new PublicKey(accounts.milestone),
        });
      break;
    case "verify_milestone":
      builder = methods.verifyMilestone(hexBytes(args.milestone_id_hex)).accounts({
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
      builder = methods.rejectMilestone(hexBytes(args.milestone_id_hex)).accounts({
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
      throw new Error(`Unsupported instruction ${payload.instruction}`);
  }

  const transaction = await builder.transaction();
  const signature = await sendTransaction(transaction, keypair);
  await http(
    "POST",
    `/api/chain/intents/${intent.id}/confirm/`,
    { signature },
    token,
  );
  console.log(`  ${payload.instruction}: ${signature}`);
  return signature;
}

async function main() {
  console.log("Wallets:");
  console.log("  admin   ", admin.publicKey.toBase58());
  console.log("  founder ", founder.publicKey.toBase58());
  console.log("  reviewer", reviewer.publicKey.toBase58());
  console.log("  reviewer2", reviewerTwo.publicKey.toBase58());

  await ensureFunded(founder, 0.08);
  await ensureFunded(reviewer, 0.08);
  await ensureFunded(reviewerTwo, 0.08);

  execFileSync(
    path.join(repoRoot, "apps/api/.venv/bin/python"),
    [
      "manage.py",
      "bootstrap_phase0",
      "--admin",
      admin.publicKey.toBase58(),
      "--founder",
      founder.publicKey.toBase58(),
      "--reviewer",
      reviewer.publicKey.toBase58(),
      "--reviewer2",
      reviewerTwo.publicKey.toBase58(),
    ],
    { cwd: path.join(repoRoot, "apps/api"), stdio: "inherit" },
  );

  const [registry] = PublicKey.findProgramAddressSync([Buffer.from("registry")], programId);
  if (!(await connection.getAccountInfo(registry))) {
    const signature = await programFor(admin)
      .methods.initializeRegistry()
      .accounts({
        admin: admin.publicKey,
        registry,
        systemProgram: SystemProgram.programId,
      })
      .rpc();
    console.log(`initialize_registry: ${signature}`);
  } else {
    console.log("Registry already initialised.");
  }

  const adminToken = await login(admin);
  const founderToken = await login(founder);
  const reviewerToken = await login(reviewer);
  const reviewerTwoToken = await login(reviewerTwo);
  console.log("SIWS sign-in: ok for all three wallets.");

  // Admin publishes an immutable, versioned criteria template.
  const criteriaResponse = await http(
    "POST",
    "/api/admin/criteria/",
    {
      version: 1,
      criteria_hash: "c".repeat(64),
      criteria_uri: "https://example.test/criteria/indexer-v1",
    },
    adminToken,
  );
  const criteriaId = criteriaResponse.criteria.id;
  await signIntent(criteriaResponse.intent, admin, adminToken);

  const project = await http(
    "POST",
    "/api/projects/",
    {
      name: "Orbit Tools (Devnet E2E)",
      description:
        "End-to-end Phase 0 project used to exercise real Devnet transactions and indexing.",
      website: "https://example.test/orbit",
    },
    founderToken,
  );
  await http("POST", `/api/projects/${project.id}/submit/`, undefined, founderToken);
  const decision = await http(
    "POST",
    `/api/projects/${project.id}/decision/`,
    { decision: "approve", notes: "Phase 0 end-to-end run." },
    adminToken,
  );
  await signIntent(decision.intent, admin, adminToken);

  // Two-step authority: the founder must accept from their own wallet.
  const pending = await http(
    "GET",
    `/api/chain/intents/pending/?object_type=project&object_id=${project.id}`,
    undefined,
    founderToken,
  );
  const acceptIntent = pending.results.find(
    (item: any) => item.intent === "project.accept_authority",
  );
  if (!acceptIntent) throw new Error("Founder authority acceptance intent was not created.");
  await signIntent(acceptIntent, founder, founderToken);

  const profile = await http(
    "PUT",
    "/api/founders/me/",
    {
      display_name: "Orbit founder",
      bio: "Building verifiable delivery tooling on Solana.",
    },
    founderToken,
  );
  console.log("Founder profile:", profile.display_name);

  const roadmap = await http(
    "POST",
    `/api/projects/${project.id}/roadmaps/`,
    {
      title: "Indexer delivery",
      description: "The first public delivery track.",
      order: 1,
    },
    founderToken,
  );

  const milestoneResponse = await http(
    "POST",
    `/api/projects/${project.id}/milestones/`,
    {
      title: "Ship the indexer",
      description:
        "Deliver an indexer that re-reads account state, persists a cursor and backfills after an outage.",
      deadline: "2026-12-31",
      required_approvals: 2,
      criteria_id: criteriaId,
      roadmap_id: roadmap.id,
    },
    founderToken,
  );
  const milestoneId = milestoneResponse.milestone.id;
  await signIntent(milestoneResponse.intent, founder, founderToken);

  const ensureReviewer = async (keypair: Keypair): Promise<string> => {
    const registryRows = await http(
      "GET",
      "/api/admin/reviewers/",
      undefined,
      adminToken,
    );
    const existing = registryRows.results.find(
      (row: any) => row.wallet_address === keypair.publicKey.toBase58(),
    );
    if (existing?.onchain_pda) return existing.id;
    const registered = await http(
      "POST",
      "/api/admin/reviewers/",
      { wallet_address: keypair.publicKey.toBase58() },
      adminToken,
    );
    await signIntent(registered.intent, admin, adminToken);
    return registered.reviewer.id;
  };

  const reviewerOneId = await ensureReviewer(reviewer);
  const reviewerTwoId = await ensureReviewer(reviewerTwo);

  const assign = await http(
    "POST",
    `/api/milestones/${milestoneId}/assign/`,
    { reviewer_ids: [reviewerOneId, reviewerTwoId], required_approvals: 2 },
    adminToken,
  );
  await signIntent(assign.intent, admin, adminToken);

  const evidenceHash = "a".repeat(64);
  const submit = await http(
    "POST",
    `/api/milestones/${milestoneId}/submit/`,
    {
      evidence: [
        {
          kind: "repo",
          uri: "https://example.test/orbit/indexer-pr",
          sha256: evidenceHash,
          content_type: "text/html",
          size_bytes: 1234,
        },
      ],
    },
    founderToken,
  );
  await signIntent(submit.intent, founder, founderToken);

  const verdictOne = await http(
    "POST",
    `/api/milestones/${milestoneId}/review/`,
    { decision: "verify", comment: "Reviewer one: Devnet end-to-end verification." },
    reviewerToken,
  );
  await signIntent(verdictOne.intent, reviewer, reviewerToken);

  const verdictTwo = await http(
    "POST",
    `/api/milestones/${milestoneId}/review/`,
    { decision: "verify", comment: "Reviewer two: independent confirmation." },
    reviewerTwoToken,
  );
  const verifySignature = await signIntent(verdictTwo.intent, reviewerTwo, reviewerTwoToken);

  // Simulated outage: blank the indexer-owned fields, then let the worker backfill.
  execFileSync(
    path.join(repoRoot, "apps/api/.venv/bin/python"),
    [
      "manage.py",
      "shell",
      "-c",
      `from apps.milestones.models import Milestone; Milestone.objects.filter(pk="${milestoneId}").update(chain_status="", chain_signature="", chain_slot=None)`,
    ],
    { cwd: path.join(repoRoot, "apps/api"), stdio: "inherit" },
  );

  const indexResult = await runOnce(
    {
      rpc: createWeb3Rpc(RPC_URL, PROGRAM_ID),
      api: createHttpApi(API_URL, INDEXER_SECRET),
    },
    { programId: PROGRAM_ID, cursorName: "e2e-backfill-v2", batchSize: 50 },
  );
  console.log("Indexer:", indexResult);
  assert.ok(indexResult.processed >= 1, "Indexer should have processed at least one transaction.");

  const publicProject = await http("GET", `/api/projects/${project.slug}/`);
  const publicMilestone = publicProject.milestones.find((item: any) => item.id === milestoneId);
  assert.ok(publicMilestone, "Public page must include the milestone.");
  assert.equal(publicMilestone.status, "verified");
  assert.equal(publicMilestone.chain.status, "verified", "Indexer must restore chain_status.");
  assert.ok(publicMilestone.chain.signature, "Indexer must record a chain signature.");
  assert.equal(publicMilestone.reviews.length, 2, "Public page must show both reviews.");
  assert.equal(publicMilestone.criteria.hash, "c".repeat(64));
  assert.equal(publicProject.progress.percentage, 100);
  assert.equal(publicProject.progress.verified, 1);
  assert.equal(publicProject.roadmaps.length, 1);
  assert.equal(publicProject.roadmaps[0].title, "Indexer delivery");
  assert.equal(publicMilestone.roadmap.title, "Indexer delivery");
  assert.equal(publicMilestone.submissions[0].evidence[0].kind, "repo");

  const cursor = await fetch(
    `${API_URL}/api/chain/indexer/state/?name=e2e-backfill-v2`,
    { headers: { "x-indexer-secret": INDEXER_SECRET } },
  )
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => null);

  console.log("\nPhase 3 Devnet E2E passed.");
  console.log(
    JSON.stringify(
      {
        project: project.slug,
        milestone_id: milestoneId,
        verify_signature: verifySignature,
        public_url: `${process.env.WEB_URL ?? "http://localhost:3000"}/projects/${project.slug}`,
        indexer_processed: indexResult.processed,
        indexer_cursor: cursor,
      },
      null,
      2,
    ),
  );
}

main()
  .then(() => {
    // Some clients keep sockets open; the CLI is done once main resolves.
    setTimeout(() => process.exit(0), 100);
  })
  .catch((error) => {
    console.error("\nE2E failed:");
    console.error(error);
    setTimeout(() => process.exit(1), 100);
  });
