import Link from "next/link";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function MarketPage() {
  const sellers = await prisma.seller.findMany({
    include: { _count: { select: { hauls: { where: { forSale: true } } } } },
    orderBy: { createdAt: "desc" },
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Market</h1>
          <p className="text-sm text-gray-500">Resellers turning their bin finds into a storefront.</p>
        </div>
        <Link
          href="/market/new"
          className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white"
        >
          Claim a handle
        </Link>
      </div>

      {sellers.length === 0 ? (
        <p className="text-sm text-gray-500">No storefronts yet — be the first to claim one.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {sellers.map((seller) => (
            <Link
              key={seller.id}
              href={`/market/${seller.handle}`}
              className="flex items-center justify-between rounded-lg border bg-white p-4 hover:border-gray-400"
            >
              <div>
                <p className="font-medium">{seller.displayName}</p>
                <p className="text-sm text-gray-500">@{seller.handle}</p>
              </div>
              <span className="text-sm text-gray-400">{seller._count.hauls} for sale</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
