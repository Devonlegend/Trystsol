"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";

import { DataOrigin, Notice, StatusBadge } from "@/components/Badges";
import { apiFetch, refreshCurrentUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sendIntent, type Intent } from "@/lib/chain";

interface ProjectMilestone {
  id: string;
  title: string;
  status: string;
  deadline: string;
  current_round: number;
  required_approvals: number;
  chain_pda: string;
}

interface ProjectSummary {
  id: string;
  name: string;
  slug: string;
  description: string;
  application_status: string;
  lifecycle_status: string;
  data_origin: string;
  chain: { pda: string; signature: string; slot: number | null };
  milestones?: ProjectMilestone[];
}

interface ReviewerRow {
  id: string;
  wallet_address: string;
  active: boolean;
  display_name: string;
  onchain_pda: string;
}

interface CriteriaRow {
  id: string;
  version: number;
  criteria_uri: string;
  criteria_hash: string;
  onchain_pda: string;
}

interface DisputeRow {
  id: string;
  status: string;
  reason: string;
  resolution: string;
  created_at: string;
  filed_by: string;
  project: { id: string; name: string; slug: string };
  milestone: { id: string; title: string };
  review_id: string;
}

interface AssignmentRow {
  milestone_id: string;
  title: string;
  status: string;
  round: number;
  required_approvals: number;
  deadline: string;
  project: { id: string; name: string; slug: string };
}

export default function DashboardPage() {
  const { connection } = useConnection();
  const { wallet, publicKey } = useWallet();
  const { session, user, signOut } = useAuth();

  const [founderProjects, setFounderProjects] = useState<ProjectSummary[]>([]);
  const [adminProjects, setAdminProjects] = useState<ProjectSummary[]>([]);
  const [reviewers, setReviewers] = useState<ReviewerRow[]>([]);
  const [assignments, setAssignments] = useState<AssignmentRow[]>([]);
  const [criteria, setCriteria] = useState<CriteriaRow[]>([]);
  const [adminDisputes, setAdminDisputes] = useState<DisputeRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [website, setWebsite] = useState("");
  const [reviewerWallet, setReviewerWallet] = useState("");
  const [criteriaVersion, setCriteriaVersion] = useState(1);
  const [criteriaHash, setCriteriaHash] = useState("");
  const [criteriaUri, setCriteriaUri] = useState("");
  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});
  const [disputeResolutions, setDisputeResolutions] = useState<Record<string, string>>({});

  const canSign = Boolean(publicKey && wallet?.adapter);

  const load = useCallback(async () => {
    if (!user) return;
    setError(null);
    setLoading(true);
    try {
      const founder = await apiFetch<{ results: ProjectSummary[] }>("/api/founders/projects/");
      setFounderProjects(founder.results);
      if (user.is_admin || user.role === "admin") {
        const admin = await apiFetch<{ results: ProjectSummary[] }>(
          "/api/admin/projects/?status=submitted",
        );
        setAdminProjects(admin.results);
        const registry = await apiFetch<{ results: ReviewerRow[] }>("/api/admin/reviewers/");
        setReviewers(registry.results);
      } else {
        setAdminProjects([]);
        setReviewers([]);
      }
      const reviewerRows = await apiFetch<{ results: AssignmentRow[] }>(
        "/api/reviewer/assignments/",
      );
      setAssignments(reviewerRows.results);
      const criteriaRows = await apiFetch<{ results: CriteriaRow[] }>("/api/criteria/");
      setCriteria(criteriaRows.results);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load dashboard.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  async function signAndConfirm(intent: Intent | null | undefined) {
    if (!intent) return;
    if (!wallet?.adapter) throw new Error("Connect a wallet before signing.");
    await sendIntent(intent, wallet.adapter as any, connection);
  }

  async function run(action: () => Promise<void>) {
    setError(null);
    setMessage(null);
    try {
      await action();
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Action failed.");
    }
  }

  async function createProject(event: React.FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiFetch("/api/projects/", {
        method: "POST",
        body: JSON.stringify({ name, description, website }),
      });
      setName("");
      setDescription("");
      setWebsite("");
      setMessage("Project created as a draft. Submit it for admin review next.");
    });
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <h1 className="text-3xl font-semibold">Dashboard</h1>
        <Notice>Sign in with a wallet to continue.</Notice>
        <Link href="/login" className="inline-block underline">
          Go to sign-in
        </Link>
      </div>
    );
  }

  const isAdmin = Boolean(user?.is_admin || user?.role === "admin");

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-neutral-600">
            Role: {user?.role} · Wallet {publicKey?.toBase58().slice(0, 6) ?? "not connected"}
            {publicKey ? "…" : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void run(refreshCurrentUser)}
            className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100"
          >
            Refresh role
          </button>
          {loading ? <span className="text-sm text-neutral-500">Loading…</span> : null}
        </div>
      </div>

      {error ? (
        <div className="rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}
      {!canSign ? (
        <Notice>Connect the wallet that owns this role before signing any transaction.</Notice>
      ) : null}

      {(user?.role === "founder" || isAdmin) ? (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Founder</h2>
          <form onSubmit={createProject} className="space-y-3 rounded-lg border border-neutral-200 bg-white p-5">
            <h3 className="font-medium">Register a project</h3>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Project name"
              required
              className="w-full rounded border border-neutral-300 px-3 py-2"
            />
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What the project is building (at least 20 characters)"
              required
              rows={3}
              className="w-full rounded border border-neutral-300 px-3 py-2"
            />
            <input
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
              placeholder="https://… (optional)"
              className="w-full rounded border border-neutral-300 px-3 py-2"
            />
            <button className="rounded-md bg-neutral-900 px-4 py-2 text-white" type="submit">
              Create draft
            </button>
          </form>

          <div className="space-y-3">
            {founderProjects.length === 0 ? (
              <p className="text-sm text-neutral-600">No projects yet.</p>
            ) : null}
            {founderProjects.map((project) => (
              <div key={project.id} className="rounded-lg border border-neutral-200 bg-white p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <Link href={`/projects/${project.slug}`} className="font-medium underline">
                      {project.name}
                    </Link>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-600">
                      <StatusBadge value={project.application_status} />
                      <DataOrigin value={project.data_origin} />
                      {project.chain.pda ? (
                        <span className="text-emerald-700">Registered on Devnet</span>
                      ) : (
                        <span className="text-amber-700">Not registered on-chain yet</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {project.application_status === "draft" ||
                    project.application_status === "rejected" ? (
                      <button
                        type="button"
                        onClick={() =>
                          void run(async () => {
                            await apiFetch(`/api/projects/${project.id}/submit/`, { method: "POST" });
                            setMessage("Application submitted for admin review.");
                          })
                        }
                        className="rounded border border-neutral-300 px-3 py-1.5 text-sm"
                      >
                        Submit application
                      </button>
                    ) : null}
                    <Link
                      href={`/dashboard/projects/${project.id}`}
                      className="rounded border border-neutral-300 px-3 py-1.5 text-sm"
                    >
                      Manage
                    </Link>
                  </div>
                </div>
                {project.milestones?.length ? (
                  <ul className="mt-3 space-y-1 text-sm text-neutral-700">
                    {project.milestones.map((milestone) => (
                      <li key={milestone.id} className="flex flex-wrap items-center gap-2">
                        <span>{milestone.title}</span>
                        <StatusBadge value={milestone.status} />
                        <span className="text-xs text-neutral-500">
                          round {milestone.current_round} · {milestone.required_approvals} approval(s)
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {isAdmin ? (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Admin</h2>
          <div className="space-y-3">
            {adminProjects.length === 0 ? (
              <p className="text-sm text-neutral-600">No applications awaiting a decision.</p>
            ) : null}
            {adminProjects.map((project) => (
              <div key={project.id} className="rounded-lg border border-neutral-200 bg-white p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">{project.name}</p>
                    <p className="mt-1 max-w-2xl text-sm text-neutral-600">{project.description}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        void run(async () => {
                          const response = await apiFetch<any>(
                            `/api/projects/${project.id}/decision/`,
                            {
                              method: "POST",
                              body: JSON.stringify({ decision: "approve", notes: "" }),
                            },
                          );
                          await signAndConfirm(response.intent);
                          setMessage("Project approved and registered on Devnet.");
                        })
                      }
                      className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white"
                    >
                      Approve + register
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        void run(async () => {
                          await apiFetch(`/api/projects/${project.id}/decision/`, {
                            method: "POST",
                            body: JSON.stringify({ decision: "reject", notes: "" }),
                          });
                          setMessage("Project rejected. Rejections are published like approvals.");
                        })
                      }
                      className="rounded border border-neutral-300 px-3 py-1.5 text-sm"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-neutral-200 bg-white p-5">
            <h3 className="font-medium">Criteria templates</h3>
            <p className="mt-1 text-sm text-neutral-600">
              Published by the admin, versioned and immutable on-chain. Founders choose a
              version when creating a milestone; they cannot edit its content.
            </p>
            <form
              className="mt-3 grid gap-2 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                void run(async () => {
                  const response = await apiFetch<any>("/api/admin/criteria/", {
                    method: "POST",
                    body: JSON.stringify({
                      version: criteriaVersion,
                      criteria_hash: criteriaHash,
                      criteria_uri: criteriaUri,
                    }),
                  });
                  await signAndConfirm(response.intent);
                  setCriteriaHash("");
                  setCriteriaUri("");
                  setCriteriaVersion((value) => value + 1);
                  setMessage("Criteria template published on Devnet.");
                });
              }}
            >
              <label className="text-sm">
                Version
                <input
                  type="number"
                  min={1}
                  value={criteriaVersion}
                  onChange={(event) => setCriteriaVersion(Number(event.target.value))}
                  className="ml-2 w-16 rounded border border-neutral-300 px-2 py-1"
                />
              </label>
              <input
                value={criteriaUri}
                onChange={(event) => setCriteriaUri(event.target.value)}
                placeholder="Criteria URI (max 128)"
                className="rounded border border-neutral-300 px-2 py-1 text-sm"
                required
              />
              <input
                value={criteriaHash}
                onChange={(event) => setCriteriaHash(event.target.value)}
                placeholder="Criteria SHA-256 (64 hex)"
                className="rounded border border-neutral-300 px-2 py-1 text-sm sm:col-span-2"
                required
              />
              <button className="rounded bg-neutral-900 px-3 py-2 text-sm text-white sm:col-span-2" type="submit">
                Publish criteria
              </button>
            </form>
            <ul className="mt-3 space-y-1 text-sm">
              {criteria.map((row) => (
                <li key={row.id} className="flex flex-wrap items-center gap-2">
                  <span>v{row.version}</span>
                  <a href={row.criteria_uri} className="underline" target="_blank" rel="noreferrer">
                    {row.criteria_uri}
                  </a>
                  <StatusBadge value={row.onchain_pda ? "verified" : "pending"} />
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-lg border border-neutral-200 bg-white p-5">
            <h3 className="font-medium">Disputes</h3>
            <p className="mt-1 text-sm text-neutral-600">
              Verdicts are immutable; resolutions are published next to them.
            </p>
            {adminDisputes.length === 0 ? (
              <p className="mt-2 text-sm text-neutral-600">No disputes filed.</p>
            ) : null}
            <ul className="mt-3 space-y-3 text-sm">
              {adminDisputes.map((dispute) => (
                <li key={dispute.id} className="rounded border border-neutral-200 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge value={dispute.status} />
                    <span className="font-medium">
                      {dispute.project.name} · {dispute.milestone.title}
                    </span>
                    <span className="text-xs text-neutral-500">
                      filed by {dispute.filed_by}
                    </span>
                  </div>
                  <p className="mt-1">{dispute.reason}</p>
                  {dispute.resolution ? (
                    <p className="mt-1 text-xs text-neutral-600">
                      Resolution: {dispute.resolution}
                    </p>
                  ) : (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <input
                        value={disputeResolutions[dispute.id] ?? ""}
                        onChange={(event) =>
                          setDisputeResolutions((current) => ({
                            ...current,
                            [dispute.id]: event.target.value,
                          }))
                        }
                        placeholder="Resolution (min 5 characters)"
                        className="min-w-64 flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
                      />
                      {(["upheld", "rejected"] as const).map((status) => (
                        <button
                          key={status}
                          type="button"
                          onClick={() =>
                            void run(async () => {
                              await apiFetch(`/api/disputes/${dispute.id}/resolve/`, {
                                method: "POST",
                                body: JSON.stringify({
                                  status,
                                  resolution: disputeResolutions[dispute.id] ?? "",
                                }),
                              });
                              setMessage(`Dispute ${status}.`);
                            })
                          }
                          className="rounded border border-neutral-300 px-2 py-1 text-xs"
                        >
                          {status}
                        </button>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-lg border border-neutral-200 bg-white p-5">
            <h3 className="font-medium">Reviewer registry</h3>
            <p className="mt-1 text-sm text-neutral-600">
              The reviewer must sign in once before they can be appointed.
            </p>
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                void run(async () => {
                  const response = await apiFetch<any>("/api/admin/reviewers/", {
                    method: "POST",
                    body: JSON.stringify({ wallet_address: reviewerWallet }),
                  });
                  await signAndConfirm(response.intent);
                  setReviewerWallet("");
                  setMessage("Reviewer appointed and recorded on Devnet.");
                });
              }}
            >
              <input
                value={reviewerWallet}
                onChange={(event) => setReviewerWallet(event.target.value)}
                placeholder="Reviewer wallet address"
                className="min-w-72 flex-1 rounded border border-neutral-300 px-3 py-2 font-mono text-sm"
                required
              />
              <button className="rounded bg-neutral-900 px-3 py-2 text-sm text-white" type="submit">
                Appoint reviewer
              </button>
            </form>
            <ul className="mt-3 space-y-1 text-sm">
              {reviewers.map((reviewer) => (
                <li key={reviewer.id} className="flex flex-wrap items-center gap-2">
                  <code className="text-xs">{reviewer.wallet_address}</code>
                  <StatusBadge value={reviewer.onchain_pda ? "verified" : "pending"} />
                  <span className="text-xs text-neutral-500">
                    {reviewer.onchain_pda ? "on-chain" : "not on-chain"}
                  </span>
                  {reviewer.onchain_pda ? (
                    <button
                      type="button"
                      onClick={() =>
                        void run(async () => {
                          const response = await apiFetch<any>(
                            `/api/admin/reviewers/${reviewer.id}/deactivate/`,
                            { method: "POST" },
                          );
                          await signAndConfirm(response.intent);
                          setMessage("Reviewer deactivated on Devnet.");
                        })
                      }
                      className="rounded border border-rose-300 px-2 py-1 text-xs text-rose-700"
                    >
                      Deactivate
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {user?.role === "reviewer" ? (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Reviewer</h2>
          {assignments.length === 0 ? (
            <p className="text-sm text-neutral-600">No assigned milestones.</p>
          ) : null}
          {assignments.map((assignment) => (
            <div
              key={assignment.milestone_id}
              className="rounded-lg border border-neutral-200 bg-white p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">{assignment.title}</p>
                  <p className="text-sm text-neutral-600">
                    {assignment.project.name} · round {assignment.round} · deadline{" "}
                    {assignment.deadline}
                  </p>
                </div>
                <StatusBadge value={assignment.status} />
              </div>
              {assignment.status === "submitted" || assignment.status === "under_review" ? (
                <div className="mt-3 space-y-2">
                  <textarea
                    value={reviewComments[assignment.milestone_id] ?? ""}
                    onChange={(event) =>
                      setReviewComments((current) => ({
                        ...current,
                        [assignment.milestone_id]: event.target.value,
                      }))
                    }
                    placeholder="Review comment (published with the verdict)"
                    rows={2}
                    className="w-full rounded border border-neutral-300 px-2 py-1 text-sm"
                  />
                  <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      void run(async () => {
                        const response = await apiFetch<any>(
                          `/api/milestones/${assignment.milestone_id}/review/`,
                          {
                            method: "POST",
                            body: JSON.stringify({
                              decision: "verify",
                              comment: reviewComments[assignment.milestone_id] ?? "",
                            }),
                          },
                        );
                        await signAndConfirm(response.intent);
                        setMessage("Verification recorded on Devnet.");
                      })
                    }
                    className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white"
                  >
                    Verify
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void run(async () => {
                        const response = await apiFetch<any>(
                          `/api/milestones/${assignment.milestone_id}/review/`,
                          {
                            method: "POST",
                            body: JSON.stringify({
                              decision: "reject",
                              comment: reviewComments[assignment.milestone_id] ?? "",
                            }),
                          },
                        );
                        await signAndConfirm(response.intent);
                        setMessage("Rejection recorded on Devnet. Rejections are published.");
                      })
                    }
                    className="rounded border border-rose-300 px-3 py-1.5 text-sm text-rose-700"
                  >
                    Reject
                  </button>
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </section>
      ) : null}

      <button type="button" onClick={() => void signOut()} className="text-sm underline">
        Sign out
      </button>
    </div>
  );
}
