import { SOURCE_LABELS, type OpportunityCard, type SourcePlatform } from "@/lib/types";

/** Shared pieces of the Opportunity Card used by the list card and the detail page. */

export const INTENT_STYLE: Record<string, string> = {
  High: "bg-good-bg text-good",
  Medium: "bg-warn-bg text-warn",
  Low: "bg-neutral-bg text-muted",
  Unspecified: "bg-neutral-bg text-muted",
};

const dateFmt = new Intl.DateTimeFormat("en", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export function When({ iso }: { iso: string }) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return <time dateTime={iso}>{dateFmt.format(d)}</time>;
}

export function SourceBadge({ source }: { source: SourcePlatform | string }) {
  return (
    <span className="rounded-full bg-neutral-bg px-2 py-1 text-xs font-medium">
      {SOURCE_LABELS[source as SourcePlatform] ?? source}
    </span>
  );
}

export function IntentBadge({ intent }: { intent: string | null }) {
  const value = intent ?? "Unspecified";
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${INTENT_STYLE[value] ?? INTENT_STYLE.Unspecified}`}>
      Economic intent: {value}
    </span>
  );
}

/** Evidence spread behind the card: how many signals, from how many platforms, over what window. */
export function Spread({ card }: { card: OpportunityCard }) {
  const { signal_count: n, platform_count: p, first_seen_at: first, last_seen_at: last } = card;
  if (n == null && p == null && !first && !last) return null;
  return (
    <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
      {n != null && (
        <span>
          <span className="font-semibold text-foreground tabular-nums">{n}</span> {n === 1 ? "signal" : "signals"}
        </span>
      )}
      {p != null && (
        <span>
          <span className="font-semibold text-foreground tabular-nums">{p}</span> {p === 1 ? "source" : "sources"}
        </span>
      )}
      {first && last && (
        <span>
          Seen <When iso={first} /> – <When iso={last} />
        </span>
      )}
      {!first && last && (
        <span>
          Last seen <When iso={last} />
        </span>
      )}
    </p>
  );
}

export function ConfidenceMeter({ score }: { score: number | null }) {
  if (score == null) return null;
  return (
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
  );
}

/** Only http(s) links from ingested data are rendered as links (blocks javascript:, data: etc.). */
export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}
