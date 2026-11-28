import type { Metadata } from "next";

import { Providers } from "./providers";
import { Header } from "@/components/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "TrystSol — proof of build",
  description:
    "Sourced evidence and independent review for projects launching on Solana. Information only, not investment advice.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900">
            Devnet test data. Information only — not investment advice. Search engines
            are excluded while the project is in staging.
          </div>
          <Header />
          <main className="mx-auto w-full max-w-5xl px-4 py-10">{children}</main>
          <footer className="mx-auto w-full max-w-5xl px-4 pb-10 pt-4 text-sm text-neutral-500">
            <p>
              TrystSol shows sourced facts and review outcomes. It does not provide
              investment advice, rankings or safety ratings.
            </p>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
