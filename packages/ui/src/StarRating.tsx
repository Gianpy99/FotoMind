export interface StarRatingProps {
  value: number;
  onChange(value: number): void;
  disabled?: boolean;
}

/** Five toggle buttons; choosing the current rating again clears it. */
export function StarRating({ value, onChange, disabled }: StarRatingProps) {
  return (
    <span className="fm-stars" role="group" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={n <= value ? "fm-star fm-star-on" : "fm-star"}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          aria-pressed={n === value}
          disabled={disabled}
          onClick={() => onChange(n === value ? 0 : n)}
        >
          ★
        </button>
      ))}
    </span>
  );
}
