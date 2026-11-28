import assert from "node:assert/strict";
import { test } from "node:test";

import { PublicKey } from "@solana/web3.js";

import { discriminator } from "../src/decode.js";
import { runOnce, type AccountInfoLike, type RpcClient } from "../src/indexer.js";

const PROGRAM_ID = "CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB";
const MILESTONE_PDA = "9xQeWvG816bUx9EPjHmaT23yvVM7vA8c9HhF6k9mV1yZ";
const PROJECT_PDA = "4Nd1mBQtrMJVYVfKf2PJy9NZUZdTAsp7D4xWLs4gDB4T";

function u8(value: number): Buffer {
  return Buffer.from([value]);
}

function u16(value: number): Buffer {
  const buffer = Buffer.alloc(2);
  buffer.writeUInt16LE(value);
  return buffer;
}

function u32(value: number): Buffer {
  const buffer = Buffer.alloc(4);
  buffer.writeUInt32LE(value);
  return buffer;
}

function i64(value: bigint): Buffer {
  const buffer = Buffer.alloc(8);
  buffer.writeBigInt64LE(value);
  return buffer;
}

function text(value: string): Buffer {
  const body = Buffer.from(value, "utf8");
  return Buffer.concat([u32(body.length), body]);
}

function pubkey(value: string): Buffer {
  return Buffer.from(new PublicKey(value).toBuffer());
}

const STATUS = { pending: 0, submitted: 1, underReview: 2, verified: 3, rejected: 4 };

function encodeMilestone(options: {
  status: keyof typeof STATUS;
  round?: number;
  approvals?: number;
  rejections?: number;
  reviewers?: string[];
}): Buffer {
  const reviewers = options.reviewers ?? [];
  return Buffer.concat([
    Buffer.from(discriminator("Milestone")),
    pubkey(PROJECT_PDA),
    Buffer.alloc(16, 1),
    u16(options.round ?? 1),
    Buffer.alloc(32, 9),
    text("https://example.test/evidence/1"),
    Buffer.alloc(32, 5),
    text("https://example.test/criteria/1"),
    Buffer.alloc(16, 4), // criteria_template_id
    u16(1), // criteria_version
    u32(reviewers.length),
    ...reviewers.map((reviewer) => pubkey(reviewer)),
    u8(1), // required_approvals
    u8(options.approvals ?? 1),
    u8(options.rejections ?? 0),
    u8(STATUS[options.status]),
    i64(1_700_000_000n),
    i64(1_700_000_100n),
    u8(255),
    Buffer.alloc(200), // trailing account padding, as allocated on-chain
  ]);
}

function encodeProject(): Buffer {
  return Buffer.concat([
    Buffer.from(discriminator("Project")),
    pubkey(MILESTONE_PDA),
    u8(0), // no pending authority
    Buffer.alloc(32, 7),
    text("https://example.test/project/1"),
    u8(0), // active
    i64(1_700_000_000n),
    u8(254),
    Buffer.alloc(300),
  ]);
}

function fakeRpc(options: {
  signatures: { signature: string; slot: number; err?: unknown }[];
  accountData: Uint8Array;
  accountKey: string;
  transactionErr?: unknown;
}): RpcClient {
  return {
    async getSignatures() {
      return options.signatures.map((entry) => ({
        signature: entry.signature,
        slot: entry.slot,
        blockTime: 1_700_000_000,
        err: entry.err ?? null,
      }));
    },
    async getTransaction() {
      return {
        meta: { err: options.transactionErr ?? null },
        transaction: {
          message: { accountKeys: [options.accountKey, PROGRAM_ID] },
        },
      };
    },
    async getMultipleAccounts(keys: string[]): Promise<(AccountInfoLike | null)[]> {
      return keys.map((key) =>
        key === options.accountKey
          ? { owner: PROGRAM_ID, data: options.accountData }
          : null,
      );
    },
  };
}

function fakeApi(cursor = "") {
  const ingested: any[] = [];
  return {
    ingested,
    api: {
      async getCursor() {
        return { last_signature: cursor, last_slot: cursor ? 1 : null };
      },
      async ingest(payload: Record<string, unknown>) {
        ingested.push(payload);
        return { status: "ok" };
      },
    },
  };
}

const options = {
  programId: PROGRAM_ID,
  cursorName: "main",
  batchSize: 10,
};

test("indexes a verified milestone snapshot", async () => {
  const { api, ingested } = fakeApi();
  const rpc = fakeRpc({
    signatures: [{ signature: "sig1", slot: 10 }],
    accountData: encodeMilestone({ status: "verified" }),
    accountKey: MILESTONE_PDA,
  });

  const result = await runOnce({ rpc, api }, options);
  assert.equal(result.processed, 1);
  assert.equal(result.cursor, "sig1");
  assert.equal(ingested.length, 1);
  assert.deepEqual(ingested[0].milestones, [
    {
      pda: MILESTONE_PDA,
      status: "verified",
      round: 1,
      approvals: 1,
      rejections: 0,
    },
  ]);
});

test("indexes a project lifecycle snapshot", async () => {
  const { api, ingested } = fakeApi();
  const rpc = fakeRpc({
    signatures: [{ signature: "sig2", slot: 11 }],
    accountData: encodeProject(),
    accountKey: PROJECT_PDA,
  });

  await runOnce({ rpc, api }, options);
  assert.deepEqual(ingested[0].projects, [
    { pda: PROJECT_PDA, lifecycle_status: "active" },
  ]);
});

test("stops at the persisted cursor", async () => {
  const { api, ingested } = fakeApi("sig1");
  const rpc = fakeRpc({
    signatures: [
      { signature: "sig2", slot: 11 },
      { signature: "sig1", slot: 10 },
    ],
    accountData: encodeMilestone({ status: "submitted" }),
    accountKey: MILESTONE_PDA,
  });

  const result = await runOnce({ rpc, api }, options);
  assert.equal(result.processed, 1);
  assert.equal(ingested.length, 1);
  assert.equal(ingested[0].signature, "sig2");
});

test("skips failed transactions", async () => {
  const { api, ingested } = fakeApi();
  const rpc = fakeRpc({
    signatures: [{ signature: "sig3", slot: 12, err: { InstructionError: [0, "Custom"] } }],
    accountData: encodeMilestone({ status: "rejected" }),
    accountKey: MILESTONE_PDA,
  });

  const result = await runOnce({ rpc, api }, options);
  assert.equal(result.processed, 0);
  assert.equal(result.skipped, 1);
  assert.equal(ingested.length, 0);
});

test("processes multiple transactions oldest first", async () => {
  const { api, ingested } = fakeApi();
  const rpc = fakeRpc({
    signatures: [
      { signature: "sig3", slot: 13 },
      { signature: "sig2", slot: 12 },
      { signature: "sig1", slot: 11 },
    ],
    accountData: encodeMilestone({ status: "verified" }),
    accountKey: MILESTONE_PDA,
  });

  await runOnce({ rpc, api }, options);
  assert.deepEqual(
    ingested.map((entry) => entry.signature),
    ["sig1", "sig2", "sig3"],
  );
});
