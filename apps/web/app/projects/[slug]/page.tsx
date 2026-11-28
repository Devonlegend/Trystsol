"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DataOrigin, Notice, SourceLink, StatusBadge } from "@/components/Badges";
import { AutomatedFacts, type FactSection } from "@/components/AutomatedFacts";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PublicProject {
  id: string;
  name: string;
  slug: string;
  description: string;
  website: string;
  category: string | null;
  application_status: string;
  lifecycle_status: string;
  data_origin: string;
  token_mint: string;
  founder: { id: string; display_name: string };
  chain: { pda: string; signature: string; slot: number | null; lifecycle_status: string };
  progress: { verified: number; total: number; percentage: number; basis: string };
  roadmaps: { id: string; title: string; description: string; order: number }[];
  milestones: {
    id: string;
    title: string;
    description: string;
    deadline: string;
    status: string;
    is_overdue: boolean;
    current_round: number;
    required_approvals: number;
    roadmap: { id: string; title: string; order: number } | null;
    criteria: { template_id: string | null; version: number; uri: string; hash: string };
    chain: { pda: string; signature: string; slot: number | null; status: string };
    submissions: {
      round: number;
      evidence_uri: string;
      evidence_hash: string;
      criteria_uri: string;
      criteria_hash: string;
      evidence: {
        kind: string;
        uri: string;
        sha256: string;
        content_type: string;
        size_bytes: number;
        data_origin: string;
      }[];
      submitted_at: string;
      data_origin: string;
      chain: { signature: string; slot: number | null };
    }[];
    reviews: {
      id: string;
      round: number;
      decision: string;
      comment: string;
      reviewer_wallet: string;
      criteria_hash: string;
      created_at: string;
      data_origin: string;
      chain: { signature: string; slot: number | null };
      disputes: {
        id: string;
        status: string;
        reason: string;
        resolution: string;
        created_at: string;
        resolved_at: string | null;
      }[];
    }[];
  }[];
  notices: string[];
}

export default function PublicProjectPage() {
  const params = useParams<{ slug: string }>();
  const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
  const { session } = useAuth();
  const [project, setProject] = useState<PublicProject | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [disputeReasons, setDisputeReasons] = useState<Record<string, string>>({});
  const [disputeMessage, setDisputeMessage] = useState<string | null>(null);
  const [automatedSections, setAutomatedSections] = useState<FactSection[]>([]);
  const [treasury, setTreasury] = useState<any>(null);

  const load = useCallback(() => {
    if (!slug) return;
    apiFetch<PublicProject>(`/api/projects/${slug}/`)
      .then(setProject)
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Project not found."),
      );
    apiFetch<{ automated_sections: FactSection[] }>(`/api/decision/projects/${slug}/`)
      .then((data) => setAutomatedSections(data.automated_sections))
      .catch(() => setAutomatedSections([]));
    apiFetch<any>(`/api/treasury/${slug}/`)
      .then(setTreasury)
      .catch(() => setTreasury(null));
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Project not available</h1>
        <Notice>{error}</Notice>
      </div>
    );
  }
  if (!project) return <p className="text-neutral-600">Loading…</p>;

  const verifiedCount = project.milestones.filter((item) => item.status === "verified").length;

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="text-sm uppercase tracking-widest text-neutral-500">Project</p>
        <h1 className="text-3xl font-semibold tracking-tight">{project.name}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <StatusBadge value={project.application_status} />
          <StatusBadge value={project.lifecycle_status} />
          <DataOrigin value={project.data_origin} />
          {project.chain.pda ? (
            <span className="text-emerald-700">Registered on Solana Devnet</span>
          ) : (
            <span className="text-amber-700">Off-chain record only</span>
          )}
        </div>
        <p className="max-w-3xl text-neutral-700">{project.description}</p>
        {project.founder ? (
          <Link href={`/builders/${project.founder.id}`} className="text-sm underline">
            Builder Passport: {project.founder.display_name || "view builder"}
          </Link>
        ) : null}
        {project.website ? (
          <a href={project.website} className="text-sm text-sky-700 underline" target="_blank" rel="noreferrer">
            {project.website}
          </a>
        ) : null}
        <div className="text-sm">
          <SourceLink signature={project.chain.signature} slot={project.chain.slot} />
        </div>
      </header>

      <section className="rounded-lg border border-neutral-200 bg-white p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold">Delivery progress</h2>
          <span className="text-sm text-neutral-600">
            {project.progress.verified} of {project.progress.total} published milestones verified
          </span>
        </div>
        <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-neutral-100">
          <div
            className="h-full rounded-full bg-emerald-600"
            style={{ width: `${project.progress.percentage}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-neutral-500">{project.progress.basis}</p>
        {project.roadmaps.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-neutral-600">
            {project.roadmaps.map((roadmap) => (
              <span key={roadmap.id} className="rounded-full bg-neutral-100 px-2 py-1">
                {roadmap.title}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      {treasury ? (
        <section className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="text-lg font-semibold">Declared treasury wallet</h2>
          {treasury.linked ? (
            <div className="mt-2 space-y-2 text-sm">
              <p className="break-all font-mono text-xs">{treasury.wallet}</p>
              <p>
                Balance:{" "}
                <span className="font-medium">
                  {typeof treasury.balance_sol === "number"
                    ? `${treasury.balance_sol.toFixed(4)} SOL`
                    : "unavailable"}
                </span>{" "}
                on {treasury.chain}
              </p>
              {treasury.error ? (
                <p className="text-rose-700">{treasury.error}</p>
              ) : (
                <div>
                  <p className="font-medium">Recent transactions</p>
                  <ul className="space-y-1 text-xs">
                    {(treasury.recent_transactions ?? []).map((tx: any) => (
                      <li key={tx.signature}>
                        <a
                          href={`https://explorer.solana.com/tx/${tx.signature}${treasury.chain === "devnet" ? "?cluster=devnet" : ""}`}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          {tx.signature.slice(0, 10)}…
                        </a>{" "}
                        slot {tx.slot} {tx.err ? "(failed)" : ""}
                      </li>
                    ))}
                    {(treasury.recent_transactions ?? []).length === 0 ? (
                      <li>No recent transactions returned.</li>
                    ) : null}
                  </ul>
                </div>
              )}
              <p className="text-xs text-neutral-500">
                Source: {treasury.source}
                {treasury.fetched_at
                  ? ` · fetched ${new Date(treasury.fetched_at).toLocaleString()}`
                  : ""}
              </p>
              {(treasury.caveats ?? []).map((caveat: string) => (
                <p key={caveat} className="text-xs text-neutral-600">
                  {caveat}
                </p>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-sm text-neutral-600">{treasury.notice}</p>
          )}
        </section>
      ) : null}

      <section className="space-y-3">
        <div>
          <h2 className="text-xl font-semibold">Automated facts</h2>
          <p className="text-sm text-neutral-600">
            Read-only data with no human review. Each fact shows its source, fetch
            time and what it does not tell you.
          </p>
        </div>
        <AutomatedFacts sections={automatedSections} />
      </section>

      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold">Reviewed claims</h2>
          <p className="text-xs text-neutral-500">
            Completion is shown as verified milestones only. There is no composite score.
          </p>
        </div>

        {project.milestones.length === 0 ? (
          <p className="text-sm text-neutral-600">No milestones have been published yet.</p>
        ) : null}

        {project.milestones.map((milestone) => {
          return (
            <article key={milestone.id} className="rounded-lg border border-neutral-200 bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="text-lg font-semibold">{milestone.title}</h3>
                  <p className="mt-1 text-sm text-neutral-600">{milestone.description}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge value={milestone.status} />
                  {milestone.is_overdue ? (
                    <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-800">
                      overdue
                    </span>
                  ) : null}
                </div>
              </div>

              <p className="mt-2 text-xs text-neutral-500">
                Deadline {milestone.deadline} · round {milestone.current_round} ·{" "}
                {milestone.required_approvals} required approval(s) · {verifiedCount} verified of{" "}
                {project.milestones.length}
              </p>
              <div className="mt-2">
                <SourceLink signature={milestone.chain.signature} slot={milestone.chain.slot} />
              </div>
              <div className="mt-2 text-xs text-neutral-600">
                Criteria v{milestone.criteria.version}:{" "}
                <a href={milestone.criteria.uri} className="underline" target="_blank" rel="noreferrer">
                  {milestone.criteria.uri}
                </a>{" "}
                · hash {milestone.criteria.hash.slice(0, 16)}…
              </div>

              {milestone.submissions.map((submission) => (
                <div key={submission.round} className="mt-3 rounded border border-neutral-200 p-3 text-sm">
                  <p className="font-medium">Evidence · round {submission.round}</p>
                  <a
                    href={submission.evidence_uri}
                    target="_blank"
                    rel="noreferrer"
                    className="break-all text-sky-700 underline"
                  >
                    {submission.evidence_uri}
                  </a>
                  <p className="mt-1 break-all font-mono text-xs text-neutral-500">
                    sha256 {submission.evidence_hash}
                  </p>
                  <p className="mt-1 text-xs text-neutral-600">
                    Criteria:{" "}
                    <a href={submission.criteria_uri} target="_blank" rel="noreferrer" className="underline">
                      {submission.criteria_uri}
                    </a>{" "}
                    · hash {submission.criteria_hash.slice(0, 16)}…
                  </p>
                  <ul className="mt-2 space-y-1 text-xs">
                    {submission.evidence.map((item) => (
                      <li key={`${item.kind}:${item.uri}`}>
                        <span className="uppercase text-neutral-500">{item.kind}</span>{" "}
                        <a href={item.uri} className="underline" target="_blank" rel="noreferrer">
                          {item.uri}
                        </a>{" "}
                        <span className="text-neutral-500">sha256 {item.sha256.slice(0, 12)}…</span>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <DataOrigin value={submission.data_origin} />
                    <SourceLink signature={submission.chain.signature} slot={submission.chain.slot} />
                  </div>
                </div>
              ))}

              {milestone.reviews.map((review) => (
                <div
                  key={`${review.round}:${review.reviewer_wallet}`}
                  className="mt-3 rounded border border-neutral-200 p-3 text-sm"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge value={review.decision === "verify" ? "verified" : "rejected"} />
                    <span className="text-xs text-neutral-600">
                      round {review.round} · reviewer {review.reviewer_wallet.slice(0, 6)}…
                      {review.reviewer_wallet.slice(-4)}
                    </span>
                  </div>
                  {review.comment ? <p className="mt-1">{review.comment}</p> : null}
                  <p className="mt-1 break-all font-mono text-xs text-neutral-500">
                    criteria hash {review.criteria_hash}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <DataOrigin value={review.data_origin} />
                    <SourceLink signature={review.chain.signature} slot={review.chain.slot} />
                  </div>

                  {review.disputes.length > 0 ? (
                    <div className="mt-2 space-y-1 border-t border-neutral-200 pt-2">
                      <p className="text-xs font-medium">Disputes</p>
                      {review.disputes.map((dispute) => (
                        <div key={dispute.id} className="text-xs text-neutral-600">
                          <StatusBadge value={dispute.status} />{" "}
                          <span>{dispute.reason}</span>
                          {dispute.resolution ? (
                            <p className="mt-1">Resolution: {dispute.resolution}</p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {session ? (
                    <form
                      className="mt-2 flex flex-wrap gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const reason = disputeReasons[review.id] ?? "";
                        apiFetch(`/api/reviews/${review.id}/disputes/`, {
                          method: "POST",
                          body: JSON.stringify({ reason }),
                        })
                          .then(() => {
                            setDisputeMessage("Dispute filed.");
                            setDisputeReasons((current) => ({ ...current, [review.id]: "" }));
                            load();
                          })
                          .catch((caught) =>
                            setDisputeMessage(
                              caught instanceof Error ? caught.message : "Could not file dispute.",
                            ),
                          );
                      }}
                    >
                      <input
                        value={disputeReasons[review.id] ?? ""}
                        onChange={(event) =>
                          setDisputeReasons((current) => ({
                            ...current,
                            [review.id]: event.target.value,
                          }))
                        }
                        placeholder="Dispute this verdict (min 20 characters)"
                        className="min-w-64 flex-1 rounded border border-neutral-300 px-2 py-1 text-xs"
                      />
                      <button className="rounded border border-neutral-300 px-2 py-1 text-xs" type="submit">
                        File dispute
                      </button>
                    </form>
                  ) : null}
                </div>
              ))}
            </article>
          );
        })}
      </section>

      <section className="space-y-2">
        {disputeMessage ? <Notice>{disputeMessage}</Notice> : null}
        {project.notices.map((notice) => (
          <Notice key={notice}>{notice}</Notice>
        ))}
        <p className="text-sm text-neutral-600">
          Every review outcome links to its on-chain record. Rejections are published the
          same way as approvals. To dispute a verdict, open an issue in the project’s
          public tracker; the dispute path will be formalised in Phase 3.
        </p>
      </section>
    </div>
  );
}
