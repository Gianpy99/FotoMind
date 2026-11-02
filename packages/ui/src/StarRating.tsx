import { Star } from "lucide-react";

export interface StarRatingProps {
  value: number;
  onChange(value: number): void;
  disabled?: boolean;
  /** Group label, e.g. "Rating" or "Minimum rating". */
  label?: string;
  /** Accessible name of each star button. */
  itemLabel?(n: number): string;
  size?: "sm" | "md";
}

const defaultItemLabel = (n: number) => `${n} star${n > 1 ? "s" : ""}`;

/** Five toggle buttons; choosing the current rating again clears it. */
export function StarRating({
  value,
  onChange,
  disabled,
  label = "Rating",
  itemLabel = defaultItemLabel,
  size = "md",
}: StarRatingProps) {
  return (
    <span className={`fm-stars fm-stars-${size}`} role="group" aria-label={label}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={n <= value ? "fm-star fm-star-on" : "fm-star"}
          aria-label={itemLabel(n)}
          aria-pressed={n === value}
          disabled={disabled}
          onClick={() => onChange(n === value ? 0 : n)}
        >
          <Star aria-hidden="true" />
        </button>
      ))}
    </span>
  );
}

/** Read-only stars under a thumbnail. */
export function StarDisplay({ value }: { value: number }) {
  return (
    <span className="fm-stars fm-stars-sm fm-stars-static" role="img" aria-label={`${value} stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} aria-hidden="true" className={n <= value ? "fm-star-on" : undefined} />
      ))}
    </span>
  );
}
