"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";

import { DataOrigin, Notice, SourceLink, StatusBadge } from "@/components/Badges";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sendIntent, type Intent } from "@/lib/chain";

interface EvidenceItem {
  kind: string;
  uri: string;
  sha256: string;
  content_type: string;
  size_bytes: number;
  data_origin: string;
}

interface Submission {
  round: number;
  evidence_uri: string;
  evidence_hash: string;
  evidence: EvidenceItem[];
  criteria_uri: string;
  criteria_hash: string;
  submitted_at: string;
  data_origin: string;
  chain: { signature: string; slot: number | null };
}

interface Review {
  round: number;
  decision: string;
  comment: string;
  reviewer_wallet: string;
  criteria_hash: string;
  created_at: string;
  data_origin: string;
  chain: { signature: string; slot: number | null };
}

interface Milestone {
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
  submissions: Submission[];
  reviews: Review[];
}

interface ManagedProject {
  id: string;
  name: string;
  slug: string;
  description: string;
  application_status: string;
  lifecycle_status: string;
  data_origin: string;
  chain: { pda: string; signature: string; slot: number | null; lifecycle_status: string };
  token_mint: string;
  treasury_wallet: string;
  treasury_chain: "devnet" | "mainnet";
  progress: { verified: number; total: number; percentage: number; basis: string };
  roadmaps: { id: string; title: string; description: string; order: number }[];
  milestones: Milestone[];
}

interface CriteriaRow {
  id: string;
  version: number;
  criteria_uri: string;
  criteria_hash: string;
  onchain_pda: string;
}

interface ReviewerRow {
  id: string;
  wallet_address: string;
  active: boolean;
  display_name: string;
  onchain_pda: string;
}

export default function ManageProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = Array.isArray(params.id) ? params.id[0] : params.id;
  const { connection } = useConnection();
  const { wallet, signMessage } = useWallet();
  const { session, user } = useAuth();

  const [project, setProject] = useState<ManagedProject | null>(null);
  const [pending, setPending] = useState<Intent[]>([]);
  const [reviewers, setReviewers] = useState<ReviewerRow[]>([]);
  const [criteria, setCriteria] = useState<CriteriaRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [milestoneDescription, setMilestoneDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [requiredApprovals, setRequiredApprovals] = useState(2);
  const [criteriaId, setCriteriaId] = useState("");
  const [roadmapId, setRoadmapId] = useState("");
  const [roadmapTitle, setRoadmapTitle] = useState("");
  const [roadmapDescription, setRoadmapDescription] = useState("");
  const [roadmapOrder, setRoadmapOrder] = useState(1);
  const [tokenMint, setTokenMint] = useState("");
  const [treasuryWallet, setTreasuryWallet] = useState("");
  const [treasuryChain, setTreasuryChain] = useState<"devnet" | "mainnet">("devnet");
  const [githubStatus, setGithubStatus] = useState<any>(null);
  const [githubRepo, setGithubRepo] = useState("");
  const [githubChallenge, setGithubChallenge] = useState<any>(null);
  const [proofJson, setProofJson] = useState("");
  const [githubMessage, setGithubMessage] = useState<string | null>(null);

  const [selectedReviewers, setSelectedReviewers] = useState<Record<string, boolean>>({});
  const [submitForms, setSubmitForms] = useState<Record<string, Record<string, string>>>({});

  const isAdmin = Boolean(user?.is_admin || user?.role === "admin");

  const load = useCallback(async () => {
    if (!projectId) return;
    setError(null);
    try {
      const loaded = await apiFetch<ManagedProject>(`/api/projects/${projectId}/manage/`);
      setProject(loaded);
      setTokenMint(loaded.token_mint ?? "");
      setTreasuryWallet(loaded.treasury_wallet ?? "");
      setTreasuryChain(loaded.treasury_chain ?? "devnet");
      apiFetch<any>(`/api/integrations/github/${projectId}/`)
        .then(setGithubStatus)
        .catch(() => setGithubStatus(null));
      if (isAdmin) {
        const registry = await apiFetch<{ results: ReviewerRow[] }>("/api/admin/reviewers/");
        setReviewers(registry.results);
      }
      const criteriaRows = await apiFetch<{ results: CriteriaRow[] }>("/api/criteria/");
      setCriteria(criteriaRows.results);
      if (!criteriaId && criteriaRows.results.length > 0) {
        setCriteriaId(criteriaRows.results[0].id);
      }
      const intents = await apiFetch<{ results: Intent[] }>("/api/chain/intents/pending/");
      const milestoneIds = new Set(loaded.milestones.map((milestone) => milestone.id));
      setPending(
        intents.results.filter(
          (intent) =>
            (intent.object_type === "project" && intent.object_id === loaded.id) ||
            (intent.object_type === "milestone" && milestoneIds.has(intent.object_id)),
        ),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load project.");
    }
  }, [projectId, isAdmin]);

  useEffect(() => {
    void load();
  }, [load]);

  async function signAndConfirm(intent?: Intent | null) {
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

  if (!session) {
    return <Notice>Sign in to manage this project.</Notice>;
  }
  if (!project) {
    return (
      <div className="space-y-3">
        {error ? <Notice>{error}</Notice> : <p className="text-neutral-600">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm text-neutral-500">Manage project</p>
        <h1 className="text-3xl font-semibold tracking-tight">{project.name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          <StatusBadge value={project.application_status} />
          <StatusBadge value={project.lifecycle_status} />
          <DataOrigin value={project.data_origin} />
          {project.chain.pda ? (
            <span className="text-emerald-700">Registered on Devnet</span>
          ) : (
            <span className="text-amber-700">Not registered on-chain</span>
          )}
        </div>
        <p className="mt-3 max-w-3xl text-neutral-700">{project.description}</p>
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

      {pending.length > 0 ? (
        <section className="space-y-3 rounded-lg border border-amber-300 bg-amber-50 p-5">
          <h2 className="font-semibold text-amber-900">Pending wallet signatures</h2>
          <p className="text-sm text-amber-900">
            These transactions were prepared but not confirmed. Sign them with the wallet
            shown, or they expire after 15 minutes.
          </p>
          {pending.map((intent) => (
            <div key={intent.id} className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm">
                <span className="font-medium">{intent.payload.instruction}</span>
                <span className="ml-2 font-mono text-xs text-amber-900">
                  signer {intent.payload.signer.slice(0, 6)}…{intent.payload.signer.slice(-4)}
                </span>
              </div>
              <button
                type="button"
                onClick={() =>
                  void run(async () => {
                    await signAndConfirm(intent);
                    setMessage("Transaction confirmed and recorded.");
                  })
                }
                className="rounded bg-amber-800 px-3 py-1.5 text-sm text-white"
              >
                Sign & submit
              </button>
            </div>
          ))}
        </section>
      ) : null}

      {isAdmin && project.application_status === "submitted" ? (
        <section className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="font-semibold">Approve and register</h2>
          <p className="mt-1 text-sm text-neutral-600">
            Approval registers the project on Devnet. The project must then be registered
            before milestones can be created.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() =>
                void run(async () => {
                  const response = await apiFetch<any>(`/api/projects/${project.id}/decision/`, {
                    method: "POST",
                    body: JSON.stringify({ decision: "approve", notes: "" }),
                  });
                  await signAndConfirm(response.intent);
                  setMessage("Approved and registered on Devnet.");
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
                  setMessage("Project rejected.");
                })
              }
              className="rounded border border-neutral-300 px-3 py-1.5 text-sm"
            >
              Reject
            </button>
          </div>
        </section>
      ) : null}

      <section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-5">
        <h2 className="font-semibold">Token and GitHub integrations</h2>
        <p className="text-sm text-neutral-600">
          The token mint must be a Mainnet mint. Jupiter facts are Mainnet data.
        </p>
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              await apiFetch(`/api/projects/${project.id}/token/`, {
                method: "PATCH",
                body: JSON.stringify({ token_mint: tokenMint }),
              });
              setMessage("Mainnet token mint saved for the decision page.");
            });
          }}
        >
          <input
            value={tokenMint}
            onChange={(event) => setTokenMint(event.target.value)}
            placeholder="Mainnet token mint (optional)"
            className="min-w-72 flex-1 rounded border border-neutral-300 px-3 py-2 font-mono text-sm"
          />
          <button className="rounded bg-neutral-900 px-3 py-2 text-sm text-white" type="submit">
            Save mint
          </button>
        </form>

        <div className="border-t border-neutral-200 pt-4">
          <h3 className="font-medium">Declared treasury wallet</h3>
          <p className="mt-1 text-sm text-neutral-600">
            Read-only. This does not prove ownership or move funds.
          </p>
          <form
            className="mt-2 flex flex-wrap gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await apiFetch(`/api/projects/${project.id}/treasury/`, {
                  method: "PATCH",
                  body: JSON.stringify({
                    treasury_wallet: treasuryWallet,
                    treasury_chain: treasuryChain,
                  }),
                });
                setMessage("Declared treasury wallet saved.");
              });
            }}
          >
            <input
              value={treasuryWallet}
              onChange={(event) => setTreasuryWallet(event.target.value)}
              placeholder="Treasury wallet (optional)"
              className="min-w-72 flex-1 rounded border border-neutral-300 px-3 py-2 font-mono text-sm"
            />
            <select
              value={treasuryChain}
              onChange={(event) => setTreasuryChain(event.target.value as "devnet" | "mainnet")}
              className="rounded border border-neutral-300 px-2 py-2 text-sm"
            >
              <option value="devnet">Devnet</option>
              <option value="mainnet">Mainnet</option>
            </select>
            <button className="rounded bg-neutral-900 px-3 py-2 text-sm text-white" type="submit">
              Save treasury
            </button>
          </form>
        </div>

        <div className="border-t border-neutral-200 pt-4">
          <h3 className="font-medium">GitHub repository proof</h3>
          {githubStatus?.linked ? (
            <p className="mt-1 text-sm text-emerald-800">
              Linked:{" "}
              <a href={githubStatus.repo_url} className="underline" target="_blank" rel="noreferrer">
                {githubStatus.repo_url}
              </a>{" "}
              (signed-file proof, {new Date(githubStatus.verified_at).toLocaleString()})
            </p>
          ) : (
            <p className="mt-1 text-sm text-neutral-600">
              Prove commit control with a signed file. A repository URL alone proves nothing.
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <input
              value={githubRepo}
              onChange={(event) => setGithubRepo(event.target.value)}
              placeholder="https://github.com/owner/repo"
              className="min-w-72 flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() =>
                void run(async () => {
                  const challenge = await apiFetch<any>("/api/integrations/github/challenge/", {
                    method: "POST",
                    body: JSON.stringify({ project_id: project.id, repo_url: githubRepo }),
                  });
                  setGithubChallenge(challenge);
                  setProofJson("");
                  setGithubMessage(null);
                })
              }
              className="rounded border border-neutral-300 px-3 py-2 text-sm"
            >
              Create challenge
            </button>
          </div>
          {githubChallenge ? (
            <div className="mt-3 space-y-2 rounded border border-neutral-200 p-3">
              <p className="text-sm font-medium">1. Sign this message with the connected wallet</p>
              <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-neutral-50 p-2 text-xs">
                {githubChallenge.message}
              </pre>
              <button
                type="button"
                onClick={() =>
                  void run(async () => {
                    if (!signMessage || !wallet?.adapter?.publicKey) {
                      throw new Error("Connect a wallet that can sign messages.");
                    }
                    const signature = await signMessage(
                      new TextEncoder().encode(githubChallenge.message),
                    );
                    const binary = Array.from(new Uint8Array(signature))
                      .map((byte) => String.fromCharCode(byte))
                      .join("");
                    const payload = {
                      address: wallet.adapter.publicKey.toBase58(),
                      message: githubChallenge.message,
                      signature: window.btoa(binary),
                    };
                    setProofJson(JSON.stringify(payload, null, 2));
                    setGithubMessage(`Commit this as ${githubChallenge.file_path} on the default branch.`);
                  })
                }
                className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white"
              >
                Sign proof message
              </button>
              {proofJson ? (
                <>
                  <p className="text-sm font-medium">
                    2. Commit this as {githubChallenge.file_path}
                  </p>
                  <textarea
                    value={proofJson}
                    readOnly
                    rows={7}
                    className="w-full rounded border border-neutral-300 p-2 font-mono text-xs"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      void run(async () => {
                        await apiFetch("/api/integrations/github/verify/", {
                          method: "POST",
                          body: JSON.stringify({ challenge_id: githubChallenge.challenge_id }),
                        });
                        setGithubMessage("Repository control verified.");
                        setGithubChallenge(null);
                        setProofJson("");
                      })
                    }
                    className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white"
                  >
                    I committed it — verify proof
                  </button>
                </>
              ) : null}
              {githubMessage ? <p className="text-xs text-neutral-600">{githubMessage}</p> : null}
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-lg border border-neutral-200 bg-white p-5">
        <h2 className="font-semibold">Roadmaps</h2>
        <p className="mt-1 text-sm text-neutral-600">
          Group milestones into public delivery tracks. Roadmaps are off-chain and
          do not affect the on-chain verdict.
        </p>
        <ul className="mt-3 space-y-1 text-sm">
          {project.roadmaps.map((roadmap) => (
            <li key={roadmap.id}>
              <span className="font-medium">{roadmap.title}</span>
              <span className="ml-2 text-neutral-500">order {roadmap.order}</span>
              {roadmap.description ? (
                <span className="ml-2 text-neutral-600">{roadmap.description}</span>
              ) : null}
            </li>
          ))}
        </ul>
        <form
          className="mt-3 grid gap-2 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              await apiFetch(`/api/projects/${project.id}/roadmaps/`, {
                method: "POST",
                body: JSON.stringify({
                  title: roadmapTitle,
                  description: roadmapDescription,
                  order: roadmapOrder,
                }),
              });
              setRoadmapTitle("");
              setRoadmapDescription("");
              setRoadmapOrder((value) => value + 1);
              setMessage("Roadmap created.");
            });
          }}
        >
          <input
            value={roadmapTitle}
            onChange={(event) => setRoadmapTitle(event.target.value)}
            placeholder="Roadmap title"
            required
            className="rounded border border-neutral-300 px-2 py-1 text-sm"
          />
          <input
            value={roadmapDescription}
            onChange={(event) => setRoadmapDescription(event.target.value)}
            placeholder="Short description (optional)"
            className="rounded border border-neutral-300 px-2 py-1 text-sm"
          />
          <label className="text-sm">
            Order
            <input
              type="number"
              min={1}
              value={roadmapOrder}
              onChange={(event) => setRoadmapOrder(Number(event.target.value))}
              className="ml-2 w-16 rounded border border-neutral-300 px-2 py-1"
            />
          </label>
          <button className="rounded bg-neutral-900 px-3 py-2 text-sm text-white" type="submit">
            Create roadmap
          </button>
        </form>
      </section>

      {project.chain.pda ? (
        <section className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="font-semibold">Create a milestone</h2>
          <form
            className="mt-3 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                const response = await apiFetch<any>(
                  `/api/projects/${project.id}/milestones/`,
                  {
                    method: "POST",
                    body: JSON.stringify({
                      title,
                      description: milestoneDescription,
                      deadline,
                      required_approvals: requiredApprovals,
                      criteria_id: criteriaId,
                      roadmap_id: roadmapId || null,
                    }),
                  },
                );
                await signAndConfirm(response.intent);
                setTitle("");
                setMilestoneDescription("");
                setDeadline("");
                setMessage("Milestone created on Devnet.");
              });
            }}
          >
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Milestone title"
              required
              className="w-full rounded border border-neutral-300 px-3 py-2"
            />
            <textarea
              value={milestoneDescription}
              onChange={(event) => setMilestoneDescription(event.target.value)}
              placeholder="What will be delivered? (at least 20 characters)"
              required
              rows={3}
              className="w-full rounded border border-neutral-300 px-3 py-2"
            />
            <label className="block text-sm">
              Roadmap
              <select
                value={roadmapId}
                onChange={(event) => setRoadmapId(event.target.value)}
                className="ml-2 rounded border border-neutral-300 px-2 py-1"
              >
                <option value="">No roadmap</option>
                {project.roadmaps.map((roadmap) => (
                  <option key={roadmap.id} value={roadmap.id}>
                    {roadmap.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Criteria template
              <select
                value={criteriaId}
                onChange={(event) => setCriteriaId(event.target.value)}
                required
                className="ml-2 rounded border border-neutral-300 px-2 py-1"
              >
                <option value="">Select an admin-published template</option>
                {criteria
                  .filter((row) => row.onchain_pda)
                  .map((row) => (
                    <option key={row.id} value={row.id}>
                      v{row.version} · {row.criteria_uri}
                    </option>
                  ))}
              </select>
            </label>
            <div className="flex flex-wrap gap-3">
              <label className="text-sm">
                Deadline
                <input
                  type="date"
                  value={deadline}
                  onChange={(event) => setDeadline(event.target.value)}
                  required
                  className="ml-2 rounded border border-neutral-300 px-2 py-1"
                />
              </label>
              <label className="text-sm">
                Required approvals
                <input
                  type="number"
                  min={2}
                  max={5}
                  value={requiredApprovals}
                  onChange={(event) => setRequiredApprovals(Number(event.target.value))}
                  className="ml-2 w-16 rounded border border-neutral-300 px-2 py-1"
                />
              </label>
            </div>
            <button className="rounded bg-neutral-900 px-4 py-2 text-white" type="submit">
              Create milestone
            </button>
          </form>
        </section>
      ) : null}

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Milestones</h2>
        {project.milestones.length === 0 ? (
          <p className="text-sm text-neutral-600">No milestones yet.</p>
        ) : null}
        {project.milestones.map((milestone) => {
          const form = submitForms[milestone.id] ?? {
            kind: "repo",
            uri: "",
            sha256: "",
            size_bytes: "",
          };
          return (
            <article key={milestone.id} className="rounded-lg border border-neutral-200 bg-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{milestone.title}</h3>
                  <p className="text-sm text-neutral-600">{milestone.description}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge value={milestone.status} />
                  {milestone.is_overdue ? (
                    <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-800">
                      overdue
                    </span>
                  ) : null}
                  <span className="text-xs text-neutral-500">
                    round {milestone.current_round} · {milestone.required_approvals} approval(s)
                  </span>
                  {milestone.roadmap ? (
                    <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700">
                      {milestone.roadmap.title}
                    </span>
                  ) : null}
                </div>
              </div>

              <div className="mt-2 text-xs text-neutral-600">
                Deadline {milestone.deadline} · on-chain{" "}
                {milestone.chain.pda ? "registered" : "not registered"}
              </div>
              <div className="mt-1 text-xs text-neutral-600">
                Criteria v{milestone.criteria.version}:{" "}
                <a href={milestone.criteria.uri} className="underline" target="_blank" rel="noreferrer">
                  {milestone.criteria.uri}
                </a>{" "}
                · hash {milestone.criteria.hash.slice(0, 16)}…
              </div>

              {isAdmin &&
              milestone.chain.pda &&
              (milestone.status === "submitted" || milestone.status === "under_review") ? (
                <div className="mt-3 rounded border border-amber-300 bg-amber-50 p-3">
                  <p className="text-sm text-amber-900">
                    If this round is stuck (for example a deactivated reviewer), expire it.
                    The founder can then submit a new round and you can assign fresh reviewers.
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      void run(async () => {
                        const response = await apiFetch<any>(
                          `/api/milestones/${milestone.id}/expire/`,
                          { method: "POST" },
                        );
                        await signAndConfirm(response.intent);
                        setMessage("Round expired. Assign reviewers for the next round.");
                      })
                    }
                    className="mt-2 rounded bg-amber-800 px-3 py-1.5 text-sm text-white"
                  >
                    Expire stuck round
                  </button>
                </div>
              ) : null}

              {isAdmin && milestone.chain.pda && (milestone.status === "draft" || milestone.status === "rejected") ? (
                <div className="mt-4 rounded border border-neutral-200 p-3">
                  <p className="text-sm font-medium">Assign reviewers</p>
                  <div className="mt-2 space-y-1">
                    {reviewers
                      .filter((reviewer) => reviewer.onchain_pda)
                      .map((reviewer) => (
                        <label key={reviewer.id} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={Boolean(selectedReviewers[`${milestone.id}:${reviewer.id}`])}
                            onChange={(event) =>
                              setSelectedReviewers((current) => ({
                                ...current,
                                [`${milestone.id}:${reviewer.id}`]: event.target.checked,
                              }))
                            }
                          />
                          <code className="text-xs">{reviewer.wallet_address}</code>
                        </label>
                      ))}
                  </div>
                  <div className="mt-2 flex flex-wrap items-end gap-3">
                    <label className="text-sm">
                      Required approvals
                      <input
                        type="number"
                        min={1}
                        max={5}
                        value={requiredApprovals}
                        onChange={(event) => setRequiredApprovals(Number(event.target.value))}
                        className="ml-2 w-16 rounded border border-neutral-300 px-2 py-1"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        void run(async () => {
                          const ids = reviewers
                            .filter((reviewer) => selectedReviewers[`${milestone.id}:${reviewer.id}`])
                            .map((reviewer) => reviewer.id);
                          const response = await apiFetch<any>(
                            `/api/milestones/${milestone.id}/assign/`,
                            {
                              method: "POST",
                              body: JSON.stringify({
                                reviewer_ids: ids,
                                required_approvals: requiredApprovals,
                              }),
                            },
                          );
                          await signAndConfirm(response.intent);
                          setMessage("Reviewers assigned on Devnet.");
                        })
                      }
                      className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white"
                    >
                      Assign on-chain
                    </button>
                  </div>
                </div>
              ) : null}

              {milestone.chain.pda && (milestone.status === "draft" || milestone.status === "rejected") ? (
                <div className="mt-4 rounded border border-neutral-200 p-3">
                  <p className="text-sm font-medium">Submit evidence</p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <label className="text-sm">
                      Kind
                      <select
                        value={form.kind}
                        onChange={(event) =>
                          setSubmitForms((current) => ({
                            ...current,
                            [milestone.id]: { ...form, kind: event.target.value },
                          }))
                        }
                        className="ml-2 rounded border border-neutral-300 px-2 py-1"
                      >
                        <option value="repo">Repository</option>
                        <option value="document">Document</option>
                        <option value="url">URL</option>
                        <option value="file">File</option>
                      </select>
                    </label>
                    <input
                      value={form.uri}
                      onChange={(event) =>
                        setSubmitForms((current) => ({
                          ...current,
                          [milestone.id]: { ...form, uri: event.target.value },
                        }))
                      }
                      placeholder="Evidence URI (primary max 128)"
                      className="rounded border border-neutral-300 px-2 py-1 text-sm"
                    />
                    <input
                      value={form.sha256}
                      onChange={(event) =>
                        setSubmitForms((current) => ({
                          ...current,
                          [milestone.id]: { ...form, sha256: event.target.value },
                        }))
                      }
                      placeholder="Evidence SHA-256 (64 hex)"
                      className="rounded border border-neutral-300 px-2 py-1 text-sm"
                    />
                    <input
                      value={form.size_bytes}
                      onChange={(event) =>
                        setSubmitForms((current) => ({
                          ...current,
                          [milestone.id]: { ...form, size_bytes: event.target.value },
                        }))
                      }
                      placeholder="Size in bytes (optional)"
                      className="rounded border border-neutral-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      void run(async () => {
                        const response = await apiFetch<any>(
                          `/api/milestones/${milestone.id}/submit/`,
                          {
                            method: "POST",
                            body: JSON.stringify({
                              evidence: [
                                {
                                  kind: form.kind,
                                  uri: form.uri,
                                  sha256: form.sha256,
                                  size_bytes: Number(form.size_bytes || 0),
                                },
                              ],
                            }),
                          },
                        );
                        await signAndConfirm(response.intent);
                        setMessage("Submission opened a new review round on Devnet.");
                      })
                    }
                    className="mt-2 rounded bg-neutral-900 px-3 py-1.5 text-sm text-white"
                  >
                    Submit round {milestone.current_round + 1}
                  </button>
                </div>
              ) : null}

              {milestone.submissions.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className="text-sm font-medium">Submissions</p>
                  {milestone.submissions.map((submission) => (
                    <div key={submission.round} className="rounded border border-neutral-200 p-3 text-sm">
                      <p>
                        Round {submission.round} ·{" "}
                        <a href={submission.evidence_uri} className="underline" target="_blank" rel="noreferrer">
                          evidence
                        </a>{" "}
                        ·{" "}
                        <a href={submission.criteria_uri} className="underline" target="_blank" rel="noreferrer">
                          criteria
                        </a>
                      </p>
                      <p className="mt-1 break-all font-mono text-xs text-neutral-500">
                        sha256 {submission.evidence_hash}
                      </p>
                      <ul className="mt-1 space-y-1 text-xs">
                        {submission.evidence.map((item) => (
                          <li key={`${item.kind}:${item.uri}`}>
                            <span className="uppercase text-neutral-500">{item.kind}</span>{" "}
                            <a href={item.uri} className="underline" target="_blank" rel="noreferrer">
                              {item.uri}
                            </a>
                          </li>
                        ))}
                      </ul>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <DataOrigin value={submission.data_origin} />
                        <SourceLink {...submission.chain} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}

              {milestone.reviews.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className="text-sm font-medium">Review outcomes</p>
                  {milestone.reviews.map((review) => (
                    <div
                      key={`${review.round}:${review.reviewer_wallet}`}
                      className="rounded border border-neutral-200 p-3 text-sm"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge value={review.decision === "verify" ? "verified" : "rejected"} />
                        <span className="text-xs text-neutral-600">
                          round {review.round} · reviewer {review.reviewer_wallet.slice(0, 6)}…
                          {review.reviewer_wallet.slice(-4)}
                        </span>
                      </div>
                      {review.comment ? <p className="mt-1">{review.comment}</p> : null}
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <DataOrigin value={review.data_origin} />
                        <SourceLink {...review.chain} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
    </div>
  );
}
