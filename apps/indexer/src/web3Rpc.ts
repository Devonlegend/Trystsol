import { Connection, PublicKey } from "@solana/web3.js";

import type { AccountInfoLike, RpcClient, SignatureInfo } from "./indexer.js";

export function createWeb3Rpc(rpcUrl: string, programId: string): RpcClient {
  const connection = new Connection(rpcUrl, "confirmed");
  const program = new PublicKey(programId);

  return {
    async getSignatures(limit: number, before?: string): Promise<SignatureInfo[]> {
      const rows = await connection.getSignaturesForAddress(program, {
        limit,
        before,
      });
      return rows.map((row) => ({
        signature: row.signature,
        slot: row.slot,
        blockTime: row.blockTime ?? null,
        err: row.err,
      }));
    },

    async getTransaction(signature: string): Promise<any | null> {
      return connection.getTransaction(signature, {
        commitment: "confirmed",
        maxSupportedTransactionVersion: 0,
      });
    },

    async getMultipleAccounts(keys: string[]): Promise<(AccountInfoLike | null)[]> {
      const infos = await connection.getMultipleAccountsInfo(
        keys.map((key) => new PublicKey(key)),
        "confirmed",
      );
      return infos.map((info) =>
        info
          ? { owner: info.owner.toBase58(), data: new Uint8Array(info.data) }
          : null,
      );
    },
  };
}
