import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { HaulCard } from "@/components/HaulCard";

export const dynamic = "force-dynamic";

export default async function SellerStorefrontPage({ params }: { params: { handle: string } }) {
  const seller = await prisma.seller.findUnique({
    where: { handle: params.handle.toLowerCase() },
    include: {
      hauls: {
        where: { forSale: true },
        include: { location: { select: { id: true, name: true, city: true, state: true } } },
        orderBy: { createdAt: "desc" },
      },
    },
  });

  if (!seller) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{seller.displayName}</h1>
        <p className="text-sm text-gray-500">@{seller.handle}</p>
        {seller.bio && <p className="mt-2 text-sm text-gray-700">{seller.bio}</p>}
        {seller.contactLink && (
          <p className="mt-1 text-sm text-gray-500">Contact to buy: {seller.contactLink}</p>
        )}
      </div>

      {seller.hauls.length === 0 ? (
        <p className="text-sm text-gray-500">Nothing listed for sale yet.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {seller.hauls.map((haul) => (
            <HaulCard key={haul.id} haul={haul} />
          ))}
        </div>
      )}
    </div>
  );
}
