"use client";

import Link from "next/link";
import { useId, useState } from "react";
import type { OpportunityCard } from "@/lib/types";
import { ConfidenceMeter, IntentBadge, safeHref, SourceBadge, Spread } from "./CardMeta";

/**
 * One card field. Collapsed list cards are a summary on small screens: only the
 * Problem Statement shows below md (`primary`); the rest appear on "Show full card".
 */
function Field({ label, value, open, primary = false }: { label: string; value: string | null; open: boolean; primary?: boolean }) {
  return (
    <div className={open || primary ? "" : "hidden md:block"}>
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`mt-1 text-sm ${open ? "" : "line-clamp-3"}`}>{value || "Not provided"}</dd>
    </div>
  );
}

export default function OpportunityCardView({ card }: { card: OpportunityCard }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const sourceHref = safeHref(card.source_url);
  return (
    <article className="relative flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 md:gap-4" aria-labelledby={id}>
      <header className="flex flex-col gap-2">
        <h2 id={id} className="text-base font-semibold leading-snug">
          <Link href={`/cards/${card.id}`} className="stretched-link rounded-lg underline-offset-4 hover:text-accent hover:underline">
            {card.title}
          </Link>
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source={card.source_platform} />
          <IntentBadge intent={card.economic_intent} />
        </div>
        <Spread card={card} />
        <ConfidenceMeter score={card.confidence_score} />
      </header>
      <dl className="flex flex-col gap-3">
        <Field label="Problem statement" value={card.problem_statement} open={open} primary />
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
          className="relative z-10 min-h-11 rounded px-3 text-sm font-medium text-accent hover:underline"
        >
          {open ? "Show less" : "Show full card"}
        </button>
        {sourceHref && (
          <a
            href={sourceHref}
            target="_blank"
            rel="noopener noreferrer"
            className="relative z-10 inline-flex min-h-11 items-center rounded px-3 text-sm font-medium text-accent hover:underline"
          >
            View source<span className="sr-only"> (opens in new tab)</span>
          </a>
        )}
      </footer>
    </article>
  );
}
