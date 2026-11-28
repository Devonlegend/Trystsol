import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

export interface IndexerConfig {
  rpcUrl: string;
  programId: string;
  apiUrl: string;
  sharedSecret: string;
  cursorName: string;
  pollIntervalMs: number;
  batchSize: number;
}

function required(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (!value) throw new Error(`Missing required environment variable ${name}`);
  return value;
}

export function loadConfig(): IndexerConfig {
  // `here` is kept for future IDL/event work; the indexer reads account state only.
  void here;
  return {
    rpcUrl: required("SERVER_RPC_URL", required("SOLANA_RPC_URL", "https://api.devnet.solana.com")),
    programId: required("PROGRAM_ID"),
    apiUrl: required("API_URL", "http://127.0.0.1:8000"),
    sharedSecret: required("INDEXER_SHARED_SECRET"),
    cursorName: process.env.INDEXER_CURSOR_NAME ?? "main",
    pollIntervalMs: Number(process.env.INDEXER_POLL_INTERVAL_MS ?? 15000),
    batchSize: Number(process.env.INDEXER_BATCH_SIZE ?? 25),
  };
}
