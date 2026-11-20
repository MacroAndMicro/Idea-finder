"use client";

import { useEffect, useState } from "react";
import { errorMessage, fetchRuns, RUNS_PAGE_SIZE } from "@/lib/api";
import { SOURCE_LABELS, type IngestionRun, type PageResponse, type SourcePlatform } from "@/lib/types";
import { absFmt, relative } from "@/lib/time";
import { SourceBadge } from "./CardMeta";

/** Phase 1 sources, in the same order as everywhere else. */
const SOURCES: SourcePlatform[] = ["reddit", "github", "hackernews", "stackexchange"];
const STATUSES = ["Success", "Partial", "Failed"] as const;

const selectCls = "min-h-11 min-w-44 rounded border border-border bg-surface px-2 text-sm text-foreground";
const num = new Intl.NumberFormat("en");
/** "2 min 5 s" between two ISO times, or null when either is missing/invalid. */
function duration(start: string, end: string | null): string | null {
  if (!end) return null;
  const ms = Date.parse(end) - Date.parse(start);
  if (!Number.isFinite(ms) || ms < 0) return null;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${s % 60} s`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

/** Relative time as the visible text, exact UTC time in the tooltip and dateTime. */
function Time({ iso, now }: { iso: string | null; now: number }) {
  const ms = iso ? Date.parse(iso) : NaN;
  if (!iso || Number.isNaN(ms)) return <span className="text-muted">—</span>;
  const abs = `${absFmt.format(ms)} UTC`;
  return (
    <span className="flex flex-col">
      <time dateTime={iso} title={abs}>
        {relative(ms, now)}
      </time>
      <span className="text-xs text-muted">{abs}</span>
    </span>
  );
}

const STATUS_STYLE: Record<string, { cls: string; icon: string }> = {
  Success: { cls: "bg-good-bg text-good", icon: "✓" },
  Partial: { cls: "bg-warn-bg text-warn", icon: "!" },
  Failed: { cls: "bg-danger-bg text-danger", icon: "✕" },
};

/** Status as icon + word (never colour alone). */
function StatusBadge({ status }: { status: string }) {
  const st = STATUS_STYLE[status] ?? { cls: "bg-neutral-bg text-muted", icon: "•" };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${st.cls}`}>
      <span aria-hidden="true">{st.icon}</span>
      {status}
    </span>
  );
}

function Counts({ run }: { run: IngestionRun }) {
  return (
    <span className="tabular-nums">
      <span className="font-semibold">{num.format(run.fetched_count)}</span> fetched ·{" "}
      <span className="font-semibold">{num.format(run.inserted_count)}</span> new ·{" "}
      <span className="font-semibold">{num.format(run.skipped_count)}</span> skipped
    </span>
  );
}

function ErrorText({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <p className="text-xs break-words text-muted">
      <span className="font-semibold text-danger">Error:</span> {text}
    </p>
  );
}

type Load<T> = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; data: T; now: number };

/** Latest run per source: the "is our data fresh?" answer at a glance. */
function LatestPerSource() {
  const [state, setState] = useState<Load<(IngestionRun | null)[]>>({ kind: "loading" });
  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all(SOURCES.map((s) => fetchRuns({ source: s, size: 1 }, ctrl.signal).then((p) => p.items[0] ?? null)))
      .then((data) => setState({ kind: "ok", data, now: Date.now() }))
      .catch((e: Error) => {
        if (e.name !== "AbortError") setState({ kind: "error", message: errorMessage(e) });
      });
    return () => ctrl.abort();
  }, []);

  // Purely informational: on error the full list below shows the error and retry.
  if (state.kind === "error") return null;
  return (
    <section aria-labelledby="latest-heading" className="mt-4">
      <h2 id="latest-heading" className="text-sm font-semibold">
        Latest run per source
      </h2>
      {state.kind === "loading" ? (
        <div className="mt-2 min-h-24" aria-hidden="true" />
      ) : (
        <ul className="mt-2 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {SOURCES.map((src, i) => {
            const run = state.data[i];
            return (
              <li key={src} className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{SOURCE_LABELS[src]}</span>
                  {run && <StatusBadge status={run.status} />}
                </div>
                {run ? (
                  <>
                    <Time iso={run.finished_at ?? run.started_at} now={state.now} />
                    <span className="text-xs text-muted">
                      <Counts run={run} />
                    </span>
                  </>
                ) : (
                  <span className="text-muted">No runs yet</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default function RunsList() {
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const key = `${source}|${status}|${page}|${attempt}`;
  const [result, setResult] = useState<{ key: string; state: Load<PageResponse<IngestionRun>> } | null>(null);
  const state: Load<PageResponse<IngestionRun>> = result?.key === key ? result.state : { kind: "loading" };

  useEffect(() => {
    const ctrl = new AbortController();
    fetchRuns({ source, status, page }, ctrl.signal)
      .then((data) => setResult({ key, state: { kind: "ok", data, now: Date.now() } }))
      .catch((e: Error) => {
        if (e.name !== "AbortError") setResult({ key, state: { kind: "error", message: errorMessage(e) } });
      });
    return () => ctrl.abort();
  }, [source, status, page, key]);

  const filtered = Boolean(source || status);

  return (
    <div className="mt-4 flex flex-col gap-6">
      <LatestPerSource />

      <section aria-labelledby="history-heading" className="flex flex-col gap-4">
        <h2 id="history-heading" className="text-lg font-semibold">
          Run history
        </h2>
        <form className="flex flex-wrap items-end gap-4" aria-label="Filter runs" onSubmit={(e) => e.preventDefault()}>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Source
            <select
              className={selectCls}
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setPage(0);
              }}
            >
              <option value="">All sources</option>
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {SOURCE_LABELS[s]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Status
            <select
              className={selectCls}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(0);
              }}
            >
              <option value="">Any status</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </form>

        <div aria-live="polite">
          {state.kind === "loading" && <p className="text-muted">Loading runs…</p>}
          {state.kind === "error" && (
            <div role="alert" className="rounded-lg border border-danger p-4">
              <p className="font-medium text-danger">Couldn’t load ingestion runs</p>
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
          {state.kind === "ok" && state.data.items.length === 0 && (
            <div className="rounded-lg border border-dashed border-border p-8 text-center">
              <p className="font-medium">{filtered ? "No runs match these filters" : "No ingestion runs yet"}</p>
              <p className="mt-1 text-sm text-muted">
                {filtered
                  ? "Try another source or status."
                  : "Runs appear here after the ingestion pipeline runs for the first time."}
              </p>
            </div>
          )}
        </div>

        {state.kind === "ok" && state.data.items.length > 0 && (
          <>
            {/* Small screens: one card per run. */}
            <ul className="flex flex-col gap-3 md:hidden">
              {state.data.items.map((r) => (
                <li key={r.id} className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <SourceBadge source={r.source_platform} />
                    <StatusBadge status={r.status} />
                  </div>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
                    <div>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Started</dt>
                      <dd>
                        <Time iso={r.started_at} now={state.now} />
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Finished</dt>
                      <dd>
                        <Time iso={r.finished_at} now={state.now} />
                      </dd>
                    </div>
                  </dl>
                  <p className="text-xs text-muted">
                    <Counts run={r} />
                    {duration(r.started_at, r.finished_at) && <> · took {duration(r.started_at, r.finished_at)}</>}
                  </p>
                  <ErrorText text={r.error_summary} />
                </li>
              ))}
            </ul>

            {/* md and up: a real table. */}
            <div className="hidden overflow-hidden rounded-lg border border-border bg-surface md:block">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Ingestion runs, newest first</caption>
                <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-semibold">Source</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Status</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Started</th>
                    <th scope="col" className="px-3 py-2 font-semibold">Finished</th>
                    <th scope="col" className="px-3 py-2 text-right font-semibold">Fetched</th>
                    <th scope="col" className="px-3 py-2 text-right font-semibold">New</th>
                    <th scope="col" className="px-3 py-2 text-right font-semibold">Skipped</th>
                  </tr>
                </thead>
                {state.data.items.map((r) => (
                  <tbody key={r.id} className="border-b border-border last:border-b-0">
                    <tr className="align-top">
                      <td className="px-3 pt-3 pb-2">
                        <SourceBadge source={r.source_platform} />
                      </td>
                      <td className="px-3 pt-3 pb-2">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-3 pt-3 pb-2">
                        <Time iso={r.started_at} now={state.now} />
                      </td>
                      <td className="px-3 pt-3 pb-2">
                        <Time iso={r.finished_at} now={state.now} />
                        {duration(r.started_at, r.finished_at) && (
                          <span className="text-xs text-muted">took {duration(r.started_at, r.finished_at)}</span>
                        )}
                      </td>
                      <td className="px-3 pt-3 pb-2 text-right tabular-nums">{num.format(r.fetched_count)}</td>
                      <td className="px-3 pt-3 pb-2 text-right tabular-nums">{num.format(r.inserted_count)}</td>
                      <td className="px-3 pt-3 pb-2 text-right tabular-nums">{num.format(r.skipped_count)}</td>
                    </tr>
                    {r.error_summary && (
                      <tr>
                        <td colSpan={7} className="px-3 pb-3">
                          <ErrorText text={r.error_summary} />
                        </td>
                      </tr>
                    )}
                  </tbody>
                ))}
              </table>
            </div>

            <nav aria-label="Pagination" className="flex items-center justify-between gap-4">
              <button
                type="button"
                disabled={state.data.page <= 0}
                onClick={() => setPage((p) => p - 1)}
                className="min-h-11 rounded border border-border px-4 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-muted">
                Page {state.data.page + 1} of {Math.max(1, state.data.total_pages)} ·{" "}
                {num.format(state.data.total_elements)} {state.data.total_elements === 1 ? "run" : "runs"}
              </span>
              <button
                type="button"
                disabled={state.data.page + 1 >= state.data.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="min-h-11 rounded border border-border px-4 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </nav>
          </>
        )}
      </section>
      <p className="text-xs text-muted">Showing up to {RUNS_PAGE_SIZE} runs per page. Times are shown in UTC.</p>
    </div>
  );
}
