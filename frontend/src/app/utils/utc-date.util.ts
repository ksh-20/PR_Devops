/**
 * UTC date helpers aligned with backend normalize_utc_date / ISO-8601 Z payloads.
 * All calendar-day values use YYYY-MM-DD in UTC; instants use ...Z suffix.
 */

/** Current UTC calendar day as YYYY-MM-DD. */
export function utcTodayDate(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Yesterday's UTC calendar day as YYYY-MM-DD. */
export function utcYesterdayDate(): string {
  return new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
}

/** UTC calendar day N days before today (N=7 → seven days ago). */
export function utcDateDaysAgo(days: number): string {
  return new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
}

/** First day of the current UTC year as YYYY-MM-DD. */
export function utcYearStartDate(): string {
  return `${new Date().getUTCFullYear()}-01-01`;
}

/**
 * Normalize any date or datetime string to a UTC YYYY-MM-DD calendar day.
 * Mirrors backend costs.normalize_utc_date.
 */
export function normalizeUtcDate(value: string | null | undefined): string {
  if (!value) {
    return '';
  }

  let raw = String(value).trim();
  if (!raw) {
    return '';
  }

  if (raw.includes('T')) {
    raw = raw.split('T')[0];
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return raw;
  }

  if (/^\d{8}$/.test(raw)) {
    return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
  }

  try {
    const dt = new Date(raw.includes('Z') || raw.includes('+') ? raw : `${raw}T00:00:00Z`);
    if (!Number.isNaN(dt.getTime())) {
      return dt.toISOString().slice(0, 10);
    }
  } catch {
    // fall through
  }

  return raw.length >= 10 ? raw.slice(0, 10) : raw;
}

/** Midnight UTC for a calendar day → ISO-8601 Z. */
export function utcDayStartIso(date: string): string {
  const day = normalizeUtcDate(date);
  return day ? `${day}T00:00:00Z` : '';
}

/** End-of-day UTC for a calendar day → ISO-8601 Z. */
export function utcDayEndIso(date: string): string {
  const day = normalizeUtcDate(date);
  return day ? `${day}T23:59:59Z` : '';
}

/** Human-readable UTC range label for UI headers. */
export function formatUtcRangeLabel(fromDate: string, toDate: string): string {
  const from = normalizeUtcDate(fromDate);
  const to = normalizeUtcDate(toDate);
  if (!from || !to) {
    return '';
  }
  return `${utcDayStartIso(from)} – ${utcDayEndIso(to)}`;
}

/** Clamp a from/to pair to valid UTC bounds (from ≤ to ≤ maxDate). */
export function clampUtcDateRange(
  fromDate: string,
  toDate: string,
  maxDate?: string
): { from: string; to: string } {
  const max = normalizeUtcDate(maxDate || utcYesterdayDate());
  let from = normalizeUtcDate(fromDate);
  let to = normalizeUtcDate(toDate);

  if (to > max) {
    to = max;
  }
  if (from > to) {
    from = to;
  }

  return { from, to };
}
