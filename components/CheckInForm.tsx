"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { CheckInStatus } from "@/lib/types";
import { StarRatingInput } from "@/components/StarRating";

const OPTIONS: { value: CheckInStatus; label: string }[] = [
  { value: "FRESH", label: "Fresh bins" },
  { value: "PICKED_OVER", label: "Picked over" },
  { value: "EMPTY", label: "Empty" },
];

export function CheckInForm({ locationId }: { locationId: string }) {
  const router = useRouter();
  const [status, setStatus] = useState<CheckInStatus>("FRESH");
  const [rating, setRating] = useState(0);
  const [note, setNote] = useState("");
  const [reporterName, setReporterName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const res = await fetch("/api/checkins", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locationId, status, rating: rating || null, note, reporterName }),
    });

    setSubmitting(false);

    if (!res.ok) {
      setError("Couldn't submit your report. Try again.");
      return;
    }

    setRating(0);
    setNote("");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-lg border bg-white p-4">
      <p className="font-medium">Report what you saw</p>

      <div className="flex gap-2">
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setStatus(opt.value)}
            className={`rounded-full border px-3 py-1 text-sm ${
              status === opt.value ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div>
        <p className="mb-1 text-xs text-gray-500">Haul quality (optional)</p>
        <StarRatingInput value={rating} onChange={setRating} />
      </div>

      <input
        type="text"
        placeholder="Optional note (e.g. lots of shoes, long line)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={500}
        className="rounded border px-3 py-2 text-sm"
      />

      <input
        type="text"
        placeholder="Your name (optional)"
        value={reporterName}
        onChange={(e) => setReporterName(e.target.value)}
        maxLength={80}
        className="rounded border px-3 py-2 text-sm"
      />

      {error && <p className="text-sm text-empty">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Submitting…" : "Submit report"}
      </button>
    </form>
  );
}
