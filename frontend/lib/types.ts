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

/** Subset of the backend StatsResponse (GET /api/stats) used by the stats strip and empty state. */
export interface Stats {
  total_cards: number;
  cards_by_source: Partial<Record<SourcePlatform, number>>;
  total_signals: number;
  signals_by_source: Partial<Record<SourcePlatform, number>>;
  /** When the newest raw signal was fetched; null before any ingestion. */
  last_signal_fetched_at?: string | null;
  /** Latest ingestion run per source (IF-23); both fields null when a source never ran. */
  last_runs?: Partial<Record<SourcePlatform, { last_run_at: string | null; last_run_status: string | null }>>;
  /** How far raw signals got through the pipeline (IF-45). */
  pipeline?: {
    embedded_signals: number;
    extracted_signals: number;
    pain_points: number;
    b2b_pain_points: number;
    failed_extractions: number;
  };
}

/** Mirrors the backend FacetsResponse (GET /api/cards/facets). Each map ignores its own filter. */
export interface Facets {
  total: number;
  source_platform: Partial<Record<SourcePlatform, number>>;
  economic_intent: Partial<Record<EconomicIntent, number>>;
  is_b2b_filtered: { true?: number; false?: number };
}

/** Mirrors the ingestion_runs_status_chk constraint. */
export type RunStatus = "Success" | "Partial" | "Failed";

/** Mirrors the backend IngestionRunResponse (GET /api/ingestion-runs): one ingestion run. */
export interface IngestionRun {
  id: number;
  source_platform: SourcePlatform;
  started_at: string;
  /** Null while a run has not finished (or if it never recorded an end time). */
  finished_at: string | null;
  status: RunStatus | string;
  fetched_count: number;
  inserted_count: number;
  skipped_count: number;
  /** Short error text (the API caps it at 500 characters); null on clean runs. */
  error_summary: string | null;
}
