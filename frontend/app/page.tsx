import CardList from "@/components/CardList";

export default function Home() {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Opportunities</h1>
      <p className="mb-6 mt-1 max-w-2xl text-sm text-muted">
        Evidence-backed software opportunities mined from real developer and business feedback.
      </p>
      <CardList />
    </>
  );
}
