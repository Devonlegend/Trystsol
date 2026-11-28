"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { useWallet } from "@solana/wallet-adapter-react";
import Link from "next/link";

import { Notice } from "@/components/Badges";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { connected } = useWallet();
  const { session, user, signIn, busy, error } = useAuth();

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Wallet sign-in</h1>
      <p className="text-neutral-700">
        Signing proves you control the wallet. It does not create a blockchain
        transaction or cost a fee.
      </p>

      <div className="space-y-4 rounded-lg border border-neutral-200 bg-white p-5">
        <WalletMultiButton />
        <button
          type="button"
          onClick={() => void signIn()}
          disabled={!connected || busy}
          className="rounded-md bg-neutral-900 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-neutral-400"
        >
          {busy ? "Waiting for wallet…" : "Sign in with Solana"}
        </button>
        {error ? <p className="text-sm text-rose-700">{error}</p> : null}
        {session ? (
          <div className="space-y-2 text-sm text-emerald-800">
            <p>Signed in as {user?.role}.</p>
            <Link href="/dashboard" className="underline">
              Go to dashboard
            </Link>
          </div>
        ) : null}
      </div>

      <Notice>
        Wallets without the Sign In With Solana feature fall back to connect +
        signMessage with the same domain, nonce and expiry. Hardware and mobile wallets
        are untested in Phase 0.
      </Notice>
    </div>
  );
}
