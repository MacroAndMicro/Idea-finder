import type { Metadata } from "next";
import RunsList from "@/components/RunsList";

export const metadata: Metadata = { title: "Ingestion runs" };

export default function RunsPage() {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Ingestion runs</h1>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        When each source was last ingested and whether it worked. Newest runs first.
      </p>
      <RunsList />
    </>
  );
}
