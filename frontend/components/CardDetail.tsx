"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, errorMessage, fetchCard } from "@/lib/api";
import { SOURCE_LABELS, type OpportunityCard } from "@/lib/types";
import { ConfidenceMeter, IntentBadge, SourceBadge, Spread, When } from "./CardMeta";
import EvidenceList from "./EvidenceList";

type State =
  | { kind: "loading" }
  | { kind: "not-found" }
  | { kind: "error"; message: string }
  | { kind: "ok"; card: OpportunityCard };

const VALID_ID = /^[1-9]\d{0,17}$/;

function BackLink() {
  return (
    <Link
      href="/"
      className="inline-flex min-h-11 items-center gap-1 rounded text-sm font-medium text-accent underline-offset-4 hover:underline"
    >
      <span aria-hidden="true">←</span> All opportunities
    </Link>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-1 border-t border-border pt-4 first:border-t-0 first:pt-0">
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-sm leading-relaxed whitespace-pre-line">{value || "Not provided"}</dd>
    </div>
  );
}

export default function CardDetail({ id }: { id: string }) {
  const valid = VALID_ID.test(id);
  const [result, setResult] = useState<{ key: string; state: State } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = `${id}#${attempt}`;
  const state: State = !valid ? { kind: "not-found" } : result?.key === key ? result.state : { kind: "loading" };

  useEffect(() => {
    if (!valid) return;
    const ctrl = new AbortController();
    fetchCard(id, ctrl.signal)
      .then((card) => setResult({ key, state: { kind: "ok", card } }))
      .catch((e: Error) => {
        if (e.name === "AbortError") return;
        const notFound = e instanceof ApiError && (e.status === 404 || e.status === 400);
        setResult({ key, state: notFound ? { kind: "not-found" } : { kind: "error", message: errorMessage(e) } });
      });
    return () => ctrl.abort();
  }, [id, key, valid]);

  return (
    <div className="flex flex-col gap-6">
      <BackLink />
      <div aria-live="polite">
        {state.kind === "loading" && <p className="text-muted">Loading opportunity…</p>}
        {state.kind === "not-found" && (
          <div className="rounded-lg border border-dashed border-border p-8 text-center">
            <h1 className="text-xl font-semibold">Opportunity not found</h1>
            <p className="mt-1 text-sm text-muted">This card doesn’t exist or is no longer available.</p>
          </div>
        )}
        {state.kind === "error" && (
          <div role="alert" className="rounded-lg border border-danger p-4">
            <h1 className="font-medium text-danger">Couldn’t load this opportunity</h1>
            <p className="mt-1 text-sm text-muted">{state.message}</p>
            <button
              type="button"
              onClick={() => setAttempt((a) => a + 1)}
              className="mt-3 min-h-11 rounded bg-accent px-4 text-sm font-medium text-accent-foreground"
            >
              Try again
            </button>
          </div>
        )}
      </div>
      {state.kind === "ok" && <CardBody card={state.card} />}
    </div>
  );
}

function CardBody({ card }: { card: OpportunityCard }) {
  return (
    <>
      <title>{`${card.title} · Idea Finder`}</title>
      <article className="flex flex-col gap-6" aria-labelledby="card-title">
        <header className="flex flex-col gap-3">
          <h1 id="card-title" className="text-2xl font-semibold leading-tight tracking-tight">
            {card.title}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <SourceBadge source={card.source_platform} />
            <IntentBadge intent={card.economic_intent} />
          </div>
          <Spread card={card} />
          <div className="max-w-md">
            <ConfidenceMeter score={card.confidence_score} />
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <section aria-labelledby="fields-heading" className="rounded-lg border border-border bg-surface p-4 sm:p-6">
            <h2 id="fields-heading" className="sr-only">
              Opportunity details
            </h2>
            <dl className="flex flex-col gap-4">
              <Field label="Problem statement" value={card.problem_statement} />
              <Field label="Trigger context & frequency" value={card.trigger_context} />
              <Field label="Market size / segment" value={card.market_size} />
              <Field label="Duct-tape solutions" value={card.duct_tape_solutions} />
              <Field label="Economic intent" value={card.economic_intent ?? "Unspecified"} />
              <Field label="MVP wedge" value={card.mvp_wedge} />
              <Field
                label="Confidence score"
                value={card.confidence_score == null ? null : `${Math.round(card.confidence_score)} / 100`}
              />
            </dl>
          </section>

          <section aria-labelledby="provenance-heading" className="flex flex-col gap-3 self-start rounded-lg border border-border bg-surface p-4 sm:p-6">
            <h2 id="provenance-heading" className="text-base font-semibold">
              Provenance
            </h2>
            <dl className="flex flex-col gap-3 text-sm">
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Primary source</dt>
                <dd className="mt-1">{SOURCE_LABELS[card.source_platform] ?? card.source_platform}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Card created</dt>
                <dd className="mt-1">
                  <When iso={card.created_at} />
                </dd>
              </div>
              {card.raw_content_snippet && (
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Original excerpt</dt>
                  <dd className="mt-1">
                    <blockquote className="border-l-2 border-border pl-3 italic text-muted">
                      {card.raw_content_snippet}
                    </blockquote>
                  </dd>
                </div>
              )}
            </dl>
            {card.source_url && (
              <a
                href={card.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-11 items-center self-start rounded text-sm font-medium text-accent underline-offset-4 hover:underline"
              >
                View original source<span className="sr-only"> (opens in new tab)</span>
              </a>
            )}
          </section>
        </div>

        <EvidenceList cardId={String(card.id)} />
      </article>
    </>
  );
}
