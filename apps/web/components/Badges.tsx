export function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      {children}
    </div>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const tone =
    value === "verified" || value === "approved" || value === "active"
      ? "bg-emerald-100 text-emerald-800"
      : value === "rejected" || value === "suspended"
        ? "bg-rose-100 text-rose-800"
        : value === "submitted" || value === "under_review"
          ? "bg-sky-100 text-sky-800"
          : "bg-neutral-100 text-neutral-700";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function SourceLink({
  signature,
  slot,
}: {
  signature?: string | null;
  slot?: number | null;
}) {
  if (!signature) {
    return <span className="text-xs text-neutral-500">No on-chain source yet</span>;
  }
  return (
    <a
      href={`https://explorer.solana.com/tx/${signature}?cluster=devnet`}
      target="_blank"
      rel="noreferrer"
      className="text-xs text-sky-700 underline"
    >
      Solana Devnet transaction {signature.slice(0, 8)}…{signature.slice(-6)}
      {slot ? ` · slot ${slot}` : ""}
    </a>
  );
}

export function DataOrigin({ value }: { value: string }) {
  return (
    <span className="rounded border border-neutral-300 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-neutral-600">
      {value}
    </span>
  );
}
