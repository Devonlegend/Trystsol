import Link from "next/link";

import { Notice } from "@/components/Badges";

export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">
          Proof of build on Solana
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Projects should prove they are delivering.
        </h1>
        <p className="max-w-3xl text-lg text-neutral-700">
          TrystSol records development milestones, checks evidence with independent
          reviewers, and publishes each outcome with its on-chain source and timestamp.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/login"
            className="rounded-md bg-neutral-900 px-4 py-2 text-white hover:bg-neutral-700"
          >
            Sign in with a wallet
          </Link>
          <Link
            href="/dashboard"
            className="rounded-md border border-neutral-300 px-4 py-2 hover:bg-neutral-100"
          >
            Open dashboard
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="text-lg font-semibold">Automated facts</h2>
          <p className="mt-2 text-sm text-neutral-600">
            Data available for a project or token without human review: on-chain reads,
            token data and repository activity. Every fact carries its source and fetch
            time. Phase 4 adds these to decision pages.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="text-lg font-semibold">Reviewed claims</h2>
          <p className="mt-2 text-sm text-neutral-600">
            A founder submits evidence and published criteria. An admin-appointed
            reviewer verifies or rejects it. The verdict, the evidence hash and the
            reviewer wallet are recorded on Devnet and shown here.
          </p>
        </div>
      </section>

      <Notice>
        Information only. TrystSol does not provide investment advice, buy or avoid
        signals, safety ratings or rankings. Verification means the published criteria
        were met, not that a project is safe.
      </Notice>

      <section className="space-y-2 text-sm text-neutral-600">
        <h2 className="text-base font-semibold text-neutral-900">Phase 0 slice</h2>
        <p>
          Wallet sign-in, project approval, on-chain project and milestone records,
          evidence review, indexing and a public progress page run on Solana Devnet.
          Test records are labelled with their <code>data_origin</code>.
        </p>
      </section>
    </div>
  );
}
