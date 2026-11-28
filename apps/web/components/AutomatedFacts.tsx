export interface Fact {
  key: string;
  label: string;
  value: unknown;
  source: string;
  source_url: string;
  fetched_at: string;
  caveat: string;
}

export interface FactSection {
  id: string;
  tier: string;
  title: string;
  facts: Fact[];
}

function renderValue(value: unknown) {
  if (value === null || value === undefined) {
    return <span className="text-neutral-500">Not available</span>;
  }
  if (typeof value === "object") {
    return (
      <pre className="mt-1 overflow-x-auto rounded bg-neutral-50 p-2 text-xs text-neutral-700">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  if (typeof value === "boolean") {
    return <span>{value ? "Yes" : "No"}</span>;
  }
  return <span>{String(value)}</span>;
}

export function AutomatedFacts({ sections }: { sections: FactSection[] }) {
  if (sections.length === 0) {
    return (
      <p className="text-sm text-neutral-600">
        No automated facts are attached to this project or token yet.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {sections.map((section) => (
        <div key={section.id} className="rounded-lg border border-neutral-200 bg-white p-5">
          <h3 className="text-lg font-semibold">{section.title}</h3>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Automated facts · no human review by TrystSol
          </p>
          <div className="mt-3 space-y-3">
            {section.facts.map((fact) => (
              <div key={fact.key} className="border-t border-neutral-100 pt-3 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium">{fact.label}</span>
                  <span className="text-xs text-neutral-500">
                    {new Date(fact.fetched_at).toLocaleString()}
                  </span>
                </div>
                <div className="mt-1">{renderValue(fact.value)}</div>
                <p className="mt-1 text-xs text-neutral-600">{fact.caveat}</p>
                <a
                  href={fact.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-sky-700 underline"
                >
                  Source: {fact.source}
                </a>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
