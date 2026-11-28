"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import Link from "next/link";

import { useAuth } from "@/lib/auth";

export function Header() {
  const { session, user, signOut } = useAuth();

  return (
    <header className="border-b border-neutral-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          TrystSol
        </Link>
        <nav className="flex flex-wrap items-center gap-3 text-sm">
          <Link href="/dashboard" className="hover:underline">
            Dashboard
          </Link>
          {user ? (
            <>
              <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs uppercase tracking-wide text-neutral-600">
                {user.role}
              </span>
              <button
                type="button"
                onClick={() => void signOut()}
                className="rounded-md border border-neutral-300 px-3 py-1.5 hover:bg-neutral-100"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded-md bg-neutral-900 px-3 py-1.5 text-white hover:bg-neutral-700"
            >
              Sign in
            </Link>
          )}
          <WalletMultiButton />
        </nav>
      </div>
      {session ? (
        <div className="mx-auto w-full max-w-5xl px-4 pb-2 text-xs text-neutral-500">
          Signed in as {session.wallet.address.slice(0, 4)}…
          {session.wallet.address.slice(-4)}
        </div>
      ) : null}
    </header>
  );
}
