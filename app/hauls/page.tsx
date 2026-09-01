import { prisma } from "@/lib/db";
import { HaulCard } from "@/components/HaulCard";
import { HaulForm } from "@/components/HaulForm";

export const dynamic = "force-dynamic";

export default async function HaulsPage({
  searchParams,
}: {
  searchParams: { location?: string };
}) {
  const [hauls, locations] = await Promise.all([
    prisma.haul.findMany({
      include: { location: { select: { id: true, name: true, city: true, state: true } } },
      orderBy: { createdAt: "desc" },
      take: 50,
    }),
    prisma.location.findMany({
      select: { id: true, name: true, city: true, state: true },
      orderBy: { city: "asc" },
    }),
  ]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Hauls</h1>
        <p className="text-sm text-gray-500">What people are finding, and where.</p>
      </div>

      <HaulForm locations={locations} defaultLocationId={searchParams.location} />

      {hauls.length === 0 ? (
        <p className="text-sm text-gray-500">No hauls posted yet — be the first.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {hauls.map((haul) => (
            <HaulCard key={haul.id} haul={haul} />
          ))}
        </div>
      )}
    </div>
  );
}
