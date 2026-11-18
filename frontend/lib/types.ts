/** Mirrors the backend CardResponse / PageResponse DTOs (GET /api/cards). */
export type EconomicIntent = "High" | "Medium" | "Low" | "Unspecified";

export type SourcePlatform =
  | "reddit"
  | "github"
  | "hackernews"
  | "stackexchange"
  | "g2"
  | "capterra"
  | "other";

export interface OpportunityCard {
  id: number;
  title: string;
  problem_statement: string | null;
  trigger_context: string | null;
  market_size: string | null;
  duct_tape_solutions: string | null;
  economic_intent: EconomicIntent | null;
  mvp_wedge: string | null;
  confidence_score: number | null;
  source_platform: SourcePlatform;
  source_url: string | null;
  raw_content_snippet: string | null;
  /** Number of source signals clustered into this card (null for legacy cards). */
  signal_count: number | null;
  /** Number of distinct source platforms among those signals. */
  platform_count: number | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  created_at: string;
}

export interface PageResponse<T> {
  items: T[];
  page: number;
  size: number;
  total_elements: number;
  total_pages: number;
}

export const SOURCE_LABELS: Record<SourcePlatform, string> = {
  reddit: "Reddit",
  github: "GitHub",
  hackernews: "Hacker News",
  stackexchange: "Stack Exchange",
  g2: "G2",
  capterra: "Capterra",
  other: "Other",
};

/** Mirrors the backend SignalResponse (GET /api/cards/{id}/signals): one piece of evidence. */
export interface Signal {
  id: number;
  source_platform: SourcePlatform;
  url: string | null;
  title: string | null;
  body_snippet: string | null;
  score: number | null;
  comment_count: number | null;
  source_created_at: string | null;
}

/** Subset of the backend StatsResponse (GET /api/stats) used by the stats strip. */
export interface Stats {
  total_cards: number;
  cards_by_source: Partial<Record<SourcePlatform, number>>;
  total_signals: number;
  signals_by_source: Partial<Record<SourcePlatform, number>>;
}

/** Mirrors the backend FacetsResponse (GET /api/cards/facets). Each map ignores its own filter. */
export interface Facets {
  total: number;
  source_platform: Partial<Record<SourcePlatform, number>>;
  economic_intent: Partial<Record<EconomicIntent, number>>;
  is_b2b_filtered: { true?: number; false?: number };
}
