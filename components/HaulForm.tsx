"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export interface LocationOption {
  id: string;
  name: string;
  city: string;
  state: string;
}

export function HaulForm({
  locations,
  defaultLocationId,
}: {
  locations: LocationOption[];
  defaultLocationId?: string;
}) {
  const router = useRouter();
  const [locationId, setLocationId] = useState(defaultLocationId ?? locations[0]?.id ?? "");
  const [caption, setCaption] = useState("");
  const [posterName, setPosterName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [forSale, setForSale] = useState(false);
  const [sellerHandle, setSellerHandle] = useState("");
  const [price, setPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    setPreview(selected ? URL.createObjectURL(selected) : null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !locationId) {
      setError("Add a photo and pick where you found it.");
      return;
    }
    if (forSale && (!sellerHandle.trim() || !price.trim())) {
      setError("Enter your seller handle and a price to list this for sale.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.set("image", file);
    formData.set("locationId", locationId);
    formData.set("caption", caption);
    formData.set("posterName", posterName);
    formData.set("forSale", String(forSale));
    if (forSale) {
      formData.set("sellerHandle", sellerHandle.trim());
      formData.set("price", price);
    }

    const res = await fetch("/api/hauls", { method: "POST", body: formData });
    setSubmitting(false);

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      setError(body?.error ?? "Couldn't post your haul. Try again.");
      return;
    }

    setFile(null);
    setPreview(null);
    setCaption("");
    setForSale(false);
    setSellerHandle("");
    setPrice("");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-lg border bg-white p-4">
      <p className="font-medium">Post a haul</p>

      <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-gray-300 p-4 text-sm text-gray-500 hover:border-gray-400">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="Selected haul preview" className="max-h-48 rounded object-contain" />
        ) : (
          <span>Tap to add a photo of your haul</span>
        )}
        <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
      </label>

      <select
        value={locationId}
        onChange={(e) => setLocationId(e.target.value)}
        className="rounded border px-3 py-2 text-sm"
      >
        {locations.map((loc) => (
          <option key={loc.id} value={loc.id}>
            {loc.name} — {loc.city}, {loc.state}
          </option>
        ))}
      </select>

      <input
        type="text"
        placeholder="Caption (e.g. found this leather jacket for $2/lb!)"
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        maxLength={500}
        className="rounded border px-3 py-2 text-sm"
      />

      <input
        type="text"
        placeholder="Your name (optional)"
        value={posterName}
        onChange={(e) => setPosterName(e.target.value)}
        maxLength={80}
        className="rounded border px-3 py-2 text-sm"
      />

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input type="checkbox" checked={forSale} onChange={(e) => setForSale(e.target.checked)} />
        List this for sale
      </label>

      {forSale && (
        <div className="flex flex-col gap-2 rounded border border-dashed border-gray-300 p-3">
          <input
            type="text"
            placeholder="Your seller handle"
            value={sellerHandle}
            onChange={(e) => setSellerHandle(e.target.value)}
            className="rounded border px-3 py-2 text-sm"
          />
          <input
            type="number"
            min="0.01"
            step="0.01"
            placeholder="Price ($)"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="rounded border px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-500">
            No handle yet?{" "}
            <Link href="/market/new" className="underline">
              Claim one
            </Link>
            .
          </p>
        </div>
      )}

      {error && <p className="text-sm text-empty">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Posting…" : "Post haul"}
      </button>
    </form>
  );
}
