"use client";

import { useId, useState } from "react";
import { SOURCE_LABELS, type OpportunityCard } from "@/lib/types";

const INTENT_STYLE: Record<string, string> = {
  High: "bg-good-bg text-good",
  Medium: "bg-warn-bg text-warn",
  Low: "bg-neutral-bg text-muted",
  Unspecified: "bg-neutral-bg text-muted",
};

function Field({ label, value, open }: { label: string; value: string | null; open: boolean }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`mt-1 text-sm ${open ? "" : "line-clamp-3"}`}>{value || "Not provided"}</dd>
    </div>
  );
}

export default function OpportunityCardView({ card }: { card: OpportunityCard }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const score = card.confidence_score;
  const intent = card.economic_intent ?? "Unspecified";
  return (
    <article className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4" aria-labelledby={id}>
      <header className="flex flex-col gap-2">
        <h2 id={id} className="text-base font-semibold leading-snug">
          {card.title}
        </h2>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-neutral-bg px-2 py-1 font-medium">
            {SOURCE_LABELS[card.source_platform] ?? card.source_platform}
          </span>
          <span className={`rounded-full px-2 py-1 font-medium ${INTENT_STYLE[intent]}`}>
            Economic intent: {intent}
          </span>
        </div>
        {score != null && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted">Confidence</span>
            <div
              role="meter"
              aria-label="Confidence score"
              aria-valuemin={1}
              aria-valuemax={100}
              aria-valuenow={Math.round(score)}
              className="h-2 flex-1 overflow-hidden rounded-full bg-neutral-bg"
            >
              <div className="h-full bg-accent" style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
            </div>
            <span className="w-8 text-right font-semibold tabular-nums">{Math.round(score)}</span>
          </div>
        )}
      </header>
      <dl className="flex flex-col gap-3">
        <Field label="Problem statement" value={card.problem_statement} open={open} />
        <Field label="Trigger context & frequency" value={card.trigger_context} open={open} />
        <Field label="Market size / segment" value={card.market_size} open={open} />
        <Field label="Duct-tape solutions" value={card.duct_tape_solutions} open={open} />
        <Field label="MVP wedge" value={card.mvp_wedge} open={open} />
      </dl>
      <footer className="mt-auto flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className="min-h-11 rounded px-3 text-sm font-medium text-accent hover:underline"
        >
          {open ? "Show less" : "Show full card"}
        </button>
        {card.source_url && (
          <a
            href={card.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center rounded px-3 text-sm font-medium text-accent hover:underline"
          >
            View source<span className="sr-only"> (opens in new tab)</span>
          </a>
        )}
      </footer>
    </article>
  );
}
