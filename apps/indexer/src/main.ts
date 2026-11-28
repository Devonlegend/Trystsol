import { loadConfig } from "./config.js";
import { createHttpApi } from "./httpApi.js";
import { runOnce } from "./indexer.js";
import { createWeb3Rpc } from "./web3Rpc.js";

function log(level: string, message: string, fields: Record<string, unknown> = {}) {
  console.log(
    JSON.stringify({ ts: new Date().toISOString(), level, message, ...fields }),
  );
}

async function main() {
  const config = loadConfig();
  const rpc = createWeb3Rpc(config.rpcUrl, config.programId);
  const api = createHttpApi(config.apiUrl, config.sharedSecret);

  log("info", "indexer_started", {
    program_id: config.programId,
    cursor: config.cursorName,
    poll_interval_ms: config.pollIntervalMs,
  });

  let stopping = false;
  process.on("SIGINT", () => {
    stopping = true;
  });
  process.on("SIGTERM", () => {
    stopping = true;
  });

  while (!stopping) {
    try {
      const result = await runOnce(
        { rpc, api },
        {
          programId: config.programId,
          cursorName: config.cursorName,
          batchSize: config.batchSize,
        },
      );
      log("info", "indexer_poll", { ...result });
    } catch (error) {
      log("error", "indexer_poll_failed", {
        error: error instanceof Error ? error.message : String(error),
      });
    }
    await new Promise((resolve) => setTimeout(resolve, config.pollIntervalMs));
  }

  log("info", "indexer_stopped");
}

main().catch((error) => {
  log("error", "indexer_fatal", {
    error: error instanceof Error ? error.message : String(error),
  });
  process.exitCode = 1;
});
