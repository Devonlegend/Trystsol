import { createHash } from "node:crypto";

import { PublicKey } from "@solana/web3.js";

/**
 * Explicit Borsh reader for the two account types the indexer needs.
 *
 * We do not use @anchor-lang/core's account coder here: in 1.2.2 it produced
 * inconsistent encode/decode sizes for these accounts (the enum field made the
 * layout stop early), which is unsafe for on-chain data. The layout below is the
 * exact field order in programs/project_registry/src/state.rs, and is covered by
 * tests that encode a known snapshot.
 */

const MILESTONE_STATUS = [
  "pending",
  "submitted",
  "under_review",
  "verified",
  "rejected",
] as const;

const LIFECYCLE_STATUS = ["active", "completed", "suspended"] as const;

export function discriminator(name: string): Uint8Array {
  return createHash("sha256").update(`account:${name}`).digest().subarray(0, 8);
}

class Reader {
  private offset: number;
  private view: DataView;

  constructor(private data: Uint8Array, skip = 0) {
    this.view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    this.offset = skip;
  }

  private need(count: number) {
    if (this.offset + count > this.data.length) {
      throw new Error("Account data is shorter than the declared layout.");
    }
  }

  u8(): number {
    this.need(1);
    return this.data[this.offset++];
  }

  u16(): number {
    this.need(2);
    const value = this.view.getUint16(this.offset, true);
    this.offset += 2;
    return value;
  }

  u32(): number {
    this.need(4);
    const value = this.view.getUint32(this.offset, true);
    this.offset += 4;
    return value;
  }

  i64(): bigint {
    this.need(8);
    const value = this.view.getBigInt64(this.offset, true);
    this.offset += 8;
    return value;
  }

  bytes(count: number): Uint8Array {
    this.need(count);
    const value = this.data.subarray(this.offset, this.offset + count);
    this.offset += count;
    return value;
  }

  string(): string {
    const length = this.u32();
    return new TextDecoder().decode(this.bytes(length));
  }

  pubkey(): PublicKey {
    return new PublicKey(this.bytes(32));
  }

  vecPubkeys(): PublicKey[] {
    const length = this.u32();
    if (length > 64) throw new Error("Unreasonable vector length.");
    return Array.from({ length }, () => this.pubkey());
  }
}

function matches(data: Uint8Array, name: string): boolean {
  const expected = discriminator(name);
  if (data.length < 8) return false;
  for (let index = 0; index < 8; index += 1) {
    if (data[index] !== expected[index]) return false;
  }
  return true;
}

export interface MilestoneSnapshotData {
  project: string;
  round: number;
  approvals: number;
  rejections: number;
  status: string;
}

export interface ProjectSnapshotData {
  authority: string;
  lifecycleStatus: string;
}

export function decodeMilestone(data: Uint8Array): MilestoneSnapshotData {
  const reader = new Reader(data, 8);
  const project = reader.pubkey();
  reader.bytes(16); // milestone_id
  const round = reader.u16();
  reader.bytes(32); // evidence_hash
  reader.string(); // evidence_uri
  reader.bytes(32); // criteria_hash
  reader.string(); // criteria_uri
  reader.bytes(16); // criteria_template_id
  reader.u16(); // criteria_version
  reader.vecPubkeys(); // assigned_reviewers
  const requiredApprovals = reader.u8();
  const approvals = reader.u8();
  const rejections = reader.u8();
  const statusIndex = reader.u8();
  // requiredApprovals is 0 until reviewers are assigned; that is a valid state.
  void requiredApprovals;
  if (statusIndex >= MILESTONE_STATUS.length) {
    throw new Error("Milestone account has an invalid status.");
  }
  return {
    project: project.toBase58(),
    round,
    approvals,
    rejections,
    status: MILESTONE_STATUS[statusIndex],
  };
}

export function decodeProject(data: Uint8Array): ProjectSnapshotData {
  const reader = new Reader(data, 8);
  const authority = reader.pubkey();
  const hasPending = reader.u8();
  if (hasPending) reader.bytes(32);
  reader.bytes(32); // metadata_hash
  reader.string(); // metadata_uri
  const lifecycleIndex = reader.u8();
  if (lifecycleIndex >= LIFECYCLE_STATUS.length) {
    throw new Error("Project account has an invalid lifecycle status.");
  }
  return {
    authority: authority.toBase58(),
    lifecycleStatus: LIFECYCLE_STATUS[lifecycleIndex],
  };
}
