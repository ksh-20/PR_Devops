import {
  clampUtcDateRange,
  formatUtcRangeLabel,
  normalizeUtcDate,
  utcDateDaysAgo,
  utcDayEndIso,
  utcDayStartIso,
  utcTodayDate,
  utcYesterdayDate,
  utcYearStartDate,
} from './utc-date.util';

describe('utc-date.util', () => {
  it('normalizes ISO datetime to UTC calendar day', () => {
    expect(normalizeUtcDate('2026-06-01T15:30:00Z')).toBe('2026-06-01');
  });

  it('normalizes YYYYMMDD to YYYY-MM-DD', () => {
    expect(normalizeUtcDate('20260601')).toBe('2026-06-01');
  });

  it('builds UTC day boundary instants with Z suffix', () => {
    expect(utcDayStartIso('2026-06-01')).toBe('2026-06-01T00:00:00Z');
    expect(utcDayEndIso('2026-06-01')).toBe('2026-06-01T23:59:59Z');
  });

  it('clamps to-date to max and preserves order', () => {
    const result = clampUtcDateRange('2026-06-10', '2099-01-01', '2026-06-14');
    expect(result.from).toBe('2026-06-10');
    expect(result.to).toBe('2026-06-14');
  });

  it('formats a UTC range label', () => {
    expect(formatUtcRangeLabel('2026-06-01', '2026-06-07')).toBe(
      '2026-06-01T00:00:00Z – 2026-06-07T23:59:59Z'
    );
  });

  it('returns UTC today/yesterday helpers', () => {
    expect(utcTodayDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(utcYesterdayDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(utcDateDaysAgo(7)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(utcYearStartDate()).toMatch(/^\d{4}-01-01$/);
  });
});
