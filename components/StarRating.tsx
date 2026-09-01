const STAR_PATH =
  "M12 2l2.9 6.6 7.1.7-5.4 4.8 1.6 7-6.2-3.7-6.2 3.7 1.6-7L2 9.3l7.1-.7L12 2z";

function Star({ filled, size }: { filled: boolean; size: number }) {
  return filled ? (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="#eab308">
      <path d={STAR_PATH} />
    </svg>
  ) : (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth={1.5}>
      <path d={STAR_PATH} />
    </svg>
  );
}

/**
 * Read-only star display. `value` may be fractional (an average) — it
 * rounds to the nearest whole star for the fill.
 */
export function StarRating({
  value,
  size = 14,
  showValue = false,
}: {
  value: number;
  size?: number;
  showValue?: boolean;
}) {
  const rounded = Math.round(value);
  return (
    <span className="inline-flex items-center gap-1">
      <span className="inline-flex gap-0.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <Star key={n} filled={n <= rounded} size={size} />
        ))}
      </span>
      {showValue && <span className="text-xs text-gray-500">{value.toFixed(1)}</span>}
    </span>
  );
}

/** Interactive 1-5 tap-to-rate picker. `value` of 0 means "not rated yet". */
export function StarRatingInput({
  value,
  onChange,
  size = 24,
}: {
  value: number;
  onChange: (rating: number) => void;
  size?: number;
}) {
  return (
    <span className="inline-flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n === value ? 0 : n)}
          aria-label={`Rate ${n} star${n === 1 ? "" : "s"}`}
          className="p-0.5"
        >
          <Star filled={n <= value} size={size} />
        </button>
      ))}
    </span>
  );
}
