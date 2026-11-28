"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DataOrigin, Notice } from "@/components/Badges";
import { apiFetch } from "@/lib/api";

interface Passport {
  builder: { id: string; display_name: string };
  verified_milestones: number;
  projects_with_verified_milestones: number;
  entries: {
    project: { id: string; name: string; slug: string };
    milestone: {
      id: string;
      title: string;
      round: number;
      verified_at: string;
      chain: { pda: string; signature: string; slot: number | null };
    };
    reviews: {
      decision: string;
      reviewer_wallet: string;
      created_at: string;
      chain_signature: string;
    }[];
  }[];
  generated_at: string;
  notice: string;
}

export default function BuilderPassportPage() {
  const params = useParams<{ id: string }>();
  const userId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [passport, setPassport] = useState<Passport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!userId) return;
    apiFetch<Passport>(`/api/passport/${userId}/`)
      .then(setPassport)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Builder not found."),
      );
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Builder Passport</h1>
        <Notice>{error}</Notice>
      </div>
    );
  }
  if (!passport) return <p className="text-neutral-600">Loading…</p>;

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-widest text-neutral-500">
          Builder Passport
        </p>
        <h1 className="text-3xl font-semibold">{passport.builder.display_name}</h1>
        <p className="text-neutral-700">
          {passport.verified_milestones} verified milestone(s) across{" "}
          {passport.projects_with_verified_milestones} project(s).
        </p>
        <DataOrigin value="devnet" />
      </header>

      <Notice>{passport.notice}</Notice>

      {passport.entries.length === 0 ? (
        <p className="text-sm text-neutral-600">No verified milestones yet.</p>
      ) : null}

      {passport.entries.map((entry) => (
        <article key={entry.milestone.id} className="rounded-lg border border-neutral-200 bg-white p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <Link href={`/projects/${entry.project.slug}`} className="font-semibold underline">
                {entry.project.name}
              </Link>
              <p className="text-sm text-neutral-700">{entry.milestone.title}</p>
            </div>
            <span className="text-xs text-neutral-500">
              round {entry.milestone.round} · verified{" "}
              {new Date(entry.milestone.verified_at).toLocaleDateString()}
            </span>
          </div>
          <ul className="mt-2 space-y-1 text-xs text-neutral-600">
            {entry.reviews.map((review) => (
              <li key={`${review.created_at}:${review.reviewer_wallet}`}>
                {review.decision} · reviewer {review.reviewer_wallet.slice(0, 6)}…
                {review.reviewer_wallet.slice(-4)} ·{" "}
                {review.chain_signature ? (
                  <a
                    href={`https://explorer.solana.com/tx/${review.chain_signature}?cluster=devnet`}
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    source
                  </a>
                ) : (
                  "no source"
                )}
              </li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
