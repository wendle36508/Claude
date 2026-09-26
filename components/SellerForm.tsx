"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function SellerForm() {
  const router = useRouter();
  const [handle, setHandle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [contactLink, setContactLink] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const res = await fetch("/api/sellers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ handle, displayName, bio, contactLink }),
    });

    setSubmitting(false);

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      setError(body?.error ?? "Couldn't claim that handle. Try again.");
      return;
    }

    router.push(`/market/${handle.toLowerCase().trim()}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-lg border bg-white p-4">
      <div>
        <label className="mb-1 block text-xs text-gray-500">Handle (your storefront link)</label>
        <div className="flex items-center gap-1 text-sm text-gray-500">
          <span>/market/</span>
          <input
            type="text"
            placeholder="sarahs-finds"
            value={handle}
            onChange={(e) => setHandle(e.target.value.toLowerCase())}
            maxLength={30}
            className="flex-1 rounded border px-3 py-2 text-sm text-gray-900"
          />
        </div>
        <p className="mt-1 text-xs text-gray-400">
          3-30 characters: lowercase letters, numbers, hyphens.
        </p>
      </div>

      <input
        type="text"
        placeholder="Display name (e.g. Sarah's Finds)"
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        maxLength={80}
        className="rounded border px-3 py-2 text-sm"
      />

      <input
        type="text"
        placeholder="Short bio (optional)"
        value={bio}
        onChange={(e) => setBio(e.target.value)}
        maxLength={300}
        className="rounded border px-3 py-2 text-sm"
      />

      <input
        type="text"
        placeholder="Where buyers reach you — Venmo, Poshmark, Instagram, etc. (optional)"
        value={contactLink}
        onChange={(e) => setContactLink(e.target.value)}
        maxLength={300}
        className="rounded border px-3 py-2 text-sm"
      />

      {error && <p className="text-sm text-empty">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Claiming…" : "Claim handle"}
      </button>
    </form>
  );
}
