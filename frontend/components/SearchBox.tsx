"use client";

import { useEffect, useId, useState } from "react";
import { cleanQ, Q_MAX, Q_MIN } from "@/lib/api";

const DEBOUNCE_MS = 300;

/**
 * Keyword search for the card list. Typing is debounced; Enter searches at once.
 * `value` is the committed term from the URL; local text follows it when the URL
 * changes from outside (back/forward, a shared link).
 */
export default function SearchBox({ value, onSearch }: { value: string; onSearch: (q: string | undefined) => void }) {
  const id = useId();
  const hintId = `${id}-hint`;
  const [text, setText] = useState(value);
  const [synced, setSynced] = useState(value);
  if (value !== synced) {
    // The URL changed underneath us: adopt it (adjust-state-during-render pattern).
    setSynced(value);
    if (cleanQ(text) !== (value || undefined)) setText(value);
  }

  const pending = cleanQ(text);
  useEffect(() => {
    if (pending === (value || undefined)) return;
    const t = setTimeout(() => onSearch(pending), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [pending, value, onSearch]);

  const tooShort = text.trim().length > 0 && text.trim().length < Q_MIN;

  return (
    <form
      role="search"
      className="flex flex-col gap-1"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(pending);
      }}
    >
      <label htmlFor={id} className="text-sm font-medium">
        Search opportunities
      </label>
      <div className="flex gap-2">
        <input
          id={id}
          type="search"
          value={text}
          maxLength={Q_MAX}
          placeholder="e.g. invoice, webhook, CSV export"
          aria-describedby={hintId}
          onChange={(e) => setText(e.target.value)}
          className="min-h-11 w-full min-w-0 rounded border border-border bg-surface px-3 text-base text-foreground placeholder:text-muted sm:max-w-md"
        />
        {text && (
          <button
            type="button"
            onClick={() => {
              setText("");
              onSearch(undefined);
            }}
            className="min-h-11 shrink-0 rounded border border-border px-4 text-sm font-medium"
          >
            Clear<span className="sr-only"> search</span>
          </button>
        )}
      </div>
      <p id={hintId} className="text-xs text-muted">
        {tooShort
          ? `Type at least ${Q_MIN} characters to search.`
          : "Matches card titles, problem statements and duct-tape solutions."}
      </p>
    </form>
  );
}
