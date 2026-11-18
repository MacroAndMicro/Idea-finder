import type { Metadata } from "next";
import { Suspense } from "react";
import CardDetail from "@/components/CardDetail";

export const metadata: Metadata = { title: "Opportunity" };

async function CardDetailForParams({ params }: { params: PageProps<"/cards/[id]">["params"] }) {
  const { id } = await params;
  return <CardDetail id={id} />;
}

export default function CardPage({ params }: PageProps<"/cards/[id]">) {
  // Params are request-time data, so they're read inside Suspense (Cache Components).
  return (
    <Suspense fallback={<p className="text-muted">Loading opportunity…</p>}>
      <CardDetailForParams params={params} />
    </Suspense>
  );
}
