/** Shared Azure cost API response shapes (UTC-normalized by backend). */

export interface AzureUtcRangeMeta {
  fromDate?: string;
  toDate?: string;
  fromDateUtc?: string;
  toDateUtc?: string;
  fetchedAtUtc?: string;
}

export interface AzureCostPoint {
  date: string;
  dateUtc?: string;
  cost: number;
}

export interface AzureDailyRangeResponse extends AzureUtcRangeMeta {
  success: boolean;
  points: AzureCostPoint[];
  count: number;
  error?: string;
}

export interface AzureServiceCostsResponse extends AzureUtcRangeMeta {
  success: boolean;
  services: unknown[][];
  rows: unknown[][];
  error?: string;
}

export interface AzureTopResourcesResponse extends AzureUtcRangeMeta {
  success: boolean;
  top_resources: unknown[][];
  rows: unknown[][];
  error?: string;
}

export interface AzureTotalCostResponse extends AzureUtcRangeMeta {
  success: boolean;
  total_cost: number;
  amount: number;
  error?: string;
}

export interface AzureBudgetsResponse extends AzureUtcRangeMeta {
  success: boolean;
  budgets: Array<{ name?: string; amount?: number; timeGrain?: string }>;
  error?: string;
}
