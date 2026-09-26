import { SellerForm } from "@/components/SellerForm";

export default function NewSellerPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Claim your storefront</h1>
        <p className="text-sm text-gray-500">
          One handle, no password — it's just a unique link for your resale finds. Anyone can
          browse it at <span className="text-gray-700">binbuddy/market/your-handle</span>.
        </p>
      </div>
      <SellerForm />
    </div>
  );
}
