import type { ApiClient } from "./indexer.js";

export function createHttpApi(baseUrl: string, sharedSecret: string): ApiClient {
  const root = baseUrl.replace(/\/$/, "");

  async function request(path: string, init: RequestInit): Promise<any> {
    const response = await fetch(`${root}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        "x-indexer-secret": sharedSecret,
        ...(init.headers ?? {}),
      },
      signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`API ${response.status}: ${text.slice(0, 300)}`);
    }
    return response.json();
  }

  return {
    async getCursor(name: string) {
      return request(`/api/chain/indexer/state?name=${encodeURIComponent(name)}`, {
        method: "GET",
      });
    },
    async ingest(payload: Record<string, unknown>) {
      return request("/api/chain/indexer/ingest/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  };
}
