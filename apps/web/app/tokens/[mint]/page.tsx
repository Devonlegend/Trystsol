"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AutomatedFacts, type FactSection } from "@/components/AutomatedFacts";
import { Notice } from "@/components/Badges";
import { apiFetch } from "@/lib/api";

interface TokenDecision {
  mint: string;
  generated_at: string;
  automated_sections: FactSection[];
  notices: string[];
}

export default function TokenDecisionPage() {
  const params = useParams<{ mint: string }>();
  const mint = Array.isArray(params.mint) ? params.mint[0] : params.mint;
  const [decision, setDecision] = useState<TokenDecision | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!mint) return;
    apiFetch<TokenDecision>(`/api/decision/tokens/${mint}/`)
      .then(setDecision)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Token not found."),
      );
  }, [mint]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Token decision page</h1>
        <Notice>{error}</Notice>
      </div>
    );
  }
  if (!decision) return <p className="text-neutral-600">Loading…</p>;

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-widest text-neutral-500">
          Token decision page · automated facts only
        </p>
        <h1 className="break-all text-2xl font-semibold">{decision.mint}</h1>
        <a
          href={`https://explorer.solana.com/address/${decision.mint}`}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-sky-700 underline"
        >
          View the mint on Solana Explorer
        </a>
        <p className="text-xs text-neutral-500">
          Generated {new Date(decision.generated_at).toLocaleString()}
        </p>
      </header>

      {decision.notices.map((notice) => (
        <Notice key={notice}>{notice}</Notice>
      ))}

      <AutomatedFacts sections={decision.automated_sections} />
    </div>
  );
}
