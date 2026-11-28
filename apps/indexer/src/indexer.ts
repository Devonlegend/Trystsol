import {
  decodeMilestone,
  decodeProject,
  discriminator,
} from "./decode.js";

export interface SignatureInfo {
  signature: string;
  slot: number;
  blockTime: number | null;
  err: unknown | null;
}

export interface AccountInfoLike {
  owner: string;
  data: Uint8Array;
}

export interface RpcClient {
  getSignatures(limit: number, before?: string): Promise<SignatureInfo[]>;
  getTransaction(signature: string): Promise<any | null>;
  getMultipleAccounts(keys: string[]): Promise<(AccountInfoLike | null)[]>;
}

export interface ApiClient {
  getCursor(name: string): Promise<{ last_signature: string; last_slot: number | null }>;
  ingest(payload: Record<string, unknown>): Promise<{ status: string }>;
}

export interface RunResult {
  processed: number;
  skipped: number;
  cursor: string;
}

export interface IndexerOptions {
  programId: string;
  cursorName: string;
  batchSize: number;
}

function accountKeys(transaction: any): string[] {
  const message = transaction?.transaction?.message;
  if (!message) return [];
  if (Array.isArray(message.accountKeys)) return message.accountKeys.map(String);
  if (Array.isArray(message.staticAccountKeys)) return message.staticAccountKeys.map(String);
  return [];
}

export function decodeSnapshots(
  keys: string[],
  accounts: (AccountInfoLike | null)[],
  programId: string,
): { projects: any[]; milestones: any[] } {
  const projects: any[] = [];
  const milestones: any[] = [];

  const milestoneDiscriminator = discriminator("Milestone");
  const projectDiscriminator = discriminator("Project");

  accounts.forEach((account, index) => {
    if (!account || account.owner !== programId) return;
    const data = account.data;
    if (data.length < 8) return;

    const prefix = data.subarray(0, 8);
    const isMilestone = prefix.every((byte, offset) => byte === milestoneDiscriminator[offset]);
    const isProject = prefix.every((byte, offset) => byte === projectDiscriminator[offset]);

    try {
      if (isMilestone) {
        const decoded = decodeMilestone(data);
        milestones.push({
          pda: keys[index],
          status: decoded.status,
          round: decoded.round,
          approvals: decoded.approvals,
          rejections: decoded.rejections,
        });
      } else if (isProject) {
        const decoded = decodeProject(data);
        projects.push({
          pda: keys[index],
          lifecycle_status: decoded.lifecycleStatus,
        });
      }
    } catch (error) {
      console.warn(
        JSON.stringify({
          level: "warn",
          message: "account_decode_failed",
          account: keys[index],
          error: error instanceof Error ? error.message : String(error),
        }),
      );
    }
  });

  return { projects, milestones };
}

export async function runOnce(
  deps: { rpc: RpcClient; api: ApiClient },
  options: IndexerOptions,
): Promise<RunResult> {
  const { rpc, api } = deps;
  const cursor = await api.getCursor(options.cursorName);
  const signatures = await rpc.getSignatures(options.batchSize);

  const fresh: SignatureInfo[] = [];
  for (const entry of signatures) {
    if (entry.signature === cursor.last_signature) break;
    fresh.push(entry);
  }
  fresh.reverse(); // oldest first

  let processed = 0;
  let skipped = 0;
  let lastSignature = cursor.last_signature;

  for (const entry of fresh) {
    if (entry.err) {
      skipped += 1;
      lastSignature = entry.signature;
      continue;
    }
    const transaction = await rpc.getTransaction(entry.signature);
    if (!transaction || transaction.meta?.err) {
      skipped += 1;
      lastSignature = entry.signature;
      continue;
    }

    const keys = accountKeys(transaction);
    if (keys.length === 0) {
      skipped += 1;
      lastSignature = entry.signature;
      continue;
    }
    const accounts = await rpc.getMultipleAccounts(keys);
    const { projects, milestones } = decodeSnapshots(keys, accounts, options.programId);

    if (projects.length === 0 && milestones.length === 0) {
      skipped += 1;
      lastSignature = entry.signature;
      continue;
    }

    await api.ingest({
      cursor_name: options.cursorName,
      signature: entry.signature,
      slot: entry.slot,
      block_time: entry.blockTime,
      projects,
      milestones,
    });
    processed += 1;
    lastSignature = entry.signature;
  }

  return { processed, skipped, cursor: lastSignature };
}
