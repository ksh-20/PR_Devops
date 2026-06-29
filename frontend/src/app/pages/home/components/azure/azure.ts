import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { combineLatest, of } from 'rxjs';
import { finalize, catchError } from 'rxjs/operators';
import { DashboardService } from '../../../../services/dashboard.service';
import { AzureApiService } from '../../../../services/api/azure-api.service';
import {
  clampUtcDateRange,
  formatUtcRangeLabel,
  utcDateDaysAgo,
  utcYesterdayDate,
  utcYearStartDate,
} from '../../../../utils/utc-date.util';
import { AzureCostPoint } from '../../../../models/azure-cost.models';

@Component({
  selector: 'app-azure',
  imports: [CommonModule, FormsModule],
  templateUrl: './azure.html',
  styleUrl: '../../home.css'
})
export class AzureComponent implements OnInit {

  azureProjects: string[] = [];
  selectedAzureProject = '';
  selectedSubscriptionId = '';
  subscriptions: any[] = [];
  totalCost = 0;
  budgets: any[] = [];
  topResources: any[] = [];
  serviceCosts: any[] = [];

  projectSearch = '';
  subSearch = '';

  get filteredAzureProjects(): string[] {
    if (!this.projectSearch) return this.azureProjects;
    const q = this.projectSearch.toLowerCase();
    return this.azureProjects.filter(p => p.toLowerCase().includes(q));
  }

  get filteredSubscriptions(): any[] {
    if (!this.subSearch) return this.subscriptions;
    const q = this.subSearch.toLowerCase();
    return this.subscriptions.filter(s =>
      (s.displayName || '').toLowerCase().includes(q) ||
      (s.subscriptionId || '').toLowerCase().includes(q)
    );
  }

  // Global overview states
  isLoadingOverview = false;
  overviewData: any[] = [];
  overviewError: string | null = null;
  hoveredOverviewBar: any = null;

  resourcesCurrentPage = 1;
  servicesCurrentPage = 1;
  pageSize = 10;
  get Math() { return Math; }

  get paginatedTopResources(): any[] {
    const start = (this.resourcesCurrentPage - 1) * this.pageSize;
    return this.topResourcesPieSlices.slice(start, start + this.pageSize);
  }
  get resourcesTotalPages(): number {
    return Math.ceil(this.topResourcesPieSlices.length / this.pageSize);
  }

  get paginatedServiceCosts(): any[] {
    const start = (this.servicesCurrentPage - 1) * this.pageSize;
    return this.serviceCostsPieSlices.slice(start, start + this.pageSize);
  }
  get servicesTotalPages(): number {
    return Math.ceil(this.serviceCostsPieSlices.length / this.pageSize);
  }

  // Filter / loader states
  isLoadingAzure = false;
  isLoadingAzureRange = false;
  isLoadingCostTrend = false;
  isSubmittingDateFilter = false;
  private azureRangeLoadSeq = 0;

  // Cost Trend page date bounds & selected dates
  costTrendFromDate = '';
  costTrendToDate = '';
  costTrendMinDate = '';
  costTrendRangeLabelUtc = '';
  costTrendPoints: AzureCostPoint[] = [];

  // Pending date selection
  pendingFromDate = '';
  pendingToDate = '';

  // Error States
  subscriptionsError: string | null = null;
  azureError: string | null = null;
  costTrendError: string | null = null;
  topResourcesError: string | null = null;
  serviceCostsError: string | null = null;

  // Hovers
  hoveredTopResource: any = null;
  hoveredServiceCost: any = null;

  readonly PIE_COLORS = [
    '#2563eb', '#7c3aed', '#db2777', '#16a34a', '#ea580c',
    '#d97706', '#0891b2', '#9333ea', '#dc2626', '#65a30d',
    '#0284c7', '#c026d3', '#f59e0b', '#4f46e5', '#e11d48',
  ];

  constructor(
    public dashboardService: DashboardService,
    private azureApi: AzureApiService,
    private cdr: ChangeDetectorRef
  ) { }

  ngOnInit() {
    this.initCostTrendDates();
    this.loadAzureProjects();
    this.loadGlobalOverview();
  }

  private initCostTrendDates(): void {
    if (this.costTrendFromDate && this.costTrendToDate) {
      return;
    }
    this.costTrendToDate = utcYesterdayDate();
    this.costTrendFromDate = utcDateDaysAgo(7);
    this.costTrendMinDate = utcYearStartDate();
    // Keep pending in sync with defaults
    this.pendingFromDate = this.costTrendFromDate;
    this.pendingToDate = this.costTrendToDate;
    this.syncCostTrendRangeLabel();
  }

  private syncCostTrendRangeLabel(fromUtc?: string, toUtc?: string): void {
    if (fromUtc && toUtc) {
      this.costTrendRangeLabelUtc = `${fromUtc} – ${toUtc}`;
      return;
    }
    this.costTrendRangeLabelUtc = formatUtcRangeLabel(
      this.costTrendFromDate,
      this.costTrendToDate
    );
  }

  private applyUtcRangeMeta(res: { fromDateUtc?: string; toDateUtc?: string } | null | undefined): void {
    if (res?.fromDateUtc && res?.toDateUtc) {
      this.syncCostTrendRangeLabel(res.fromDateUtc, res.toDateUtc);
    } else {
      this.syncCostTrendRangeLabel();
    }
  }

  loadAzureProjects() {
    this.azureApi.getAzureProjects().subscribe({
      next: (res: any) => {
        let list = [];
        if (res && res.projects && res.projects.length > 0) {
          list = res.projects;
        } else if (res && Array.isArray(res) && res.length > 0) {
          list = res;
        }
        this.azureProjects = list || [];
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Could not fetch Azure projects', err);
        this.azureProjects = [];
        this.cdr.detectChanges();
      }
    });
  }

  loadSubscriptions() {
    this.subscriptionsError = null;
    this.azureApi.getSubscriptions(this.selectedAzureProject).subscribe({
      next: (res: any) => {
        let subs = [];
        if (res && res.subscriptions && res.subscriptions.length > 0) {
          subs = res.subscriptions;
        } else if (res && Array.isArray(res) && res.length > 0) {
          subs = res;
        }

        this.subscriptions = subs || [];
        if (this.subscriptions.length === 0) {
          this.subscriptionsError = 'No Azure subscriptions found.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Could not fetch Azure subscriptions', err);
        this.subscriptions = [];
        this.subscriptionsError = err.error?.detail || err.error?.message || err.message || 'Failed to load Azure subscriptions.';
        this.cdr.detectChanges();
      }
    });
  }

  loadAzureSubscriptionData(subId: string) {
    this.loadSubscriptionMetrics(subId);
    this.loadAzureRangeMetrics(subId);
  }

  loadSubscriptionMetrics(subId: string) {
    this.isLoadingAzure = true;
    this.azureError = null;

    const total$ = this.azureApi.getTotalCost(subId, this.selectedAzureProject).pipe(
      catchError(err => {
        console.warn('Failed to load total cost', err);
        return of({ total_cost: 0, success: false });
      })
    );
    const budgets$ = this.azureApi.getBudgets(subId, this.selectedAzureProject).pipe(
      catchError(err => {
        console.warn('Failed to load budgets', err);
        return of({ budgets: [], success: false });
      })
    );

    combineLatest({ total: total$, budgets: budgets$ }).pipe(
      finalize(() => {
        this.isLoadingAzure = false;
        this.cdr.detectChanges();
      })
    ).subscribe({
      next: (res: any) => {
        this.totalCost = res.total?.total_cost ?? 0;
        this.budgets = Array.isArray(res.budgets?.budgets) ? res.budgets.budgets : [];
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Error loading Azure subscription summary', err);
        this.totalCost = 0;
        this.budgets = [];
        this.azureError = 'Failed to load Azure subscription summary.';
        this.cdr.detectChanges();
      }
    });
  }

  loadAzureRangeMetrics(subId: string) {
    const { from, to } = this.getUtcCostTrendRange();
    if (!from || !to) {
      return;
    }

    const seq = ++this.azureRangeLoadSeq;
    this.isLoadingAzureRange = true;
    this.isLoadingCostTrend = true;
    this.costTrendError = null;
    this.topResourcesError = null;
    this.serviceCostsError = null;
    this.syncCostTrendRangeLabel();

    const dailyRange$ = this.azureApi.getDailyCostsByRange(subId, from, to, this.selectedAzureProject).pipe(
      catchError(err => {
        const msg = err.error?.detail || err.error?.message || err.message || 'Failed to load daily costs.';
        console.warn('[Azure] daily-range error:', msg);
        return of({ success: false, points: [], count: 0, _error: msg });
      })
    );

    const topResources$ = this.azureApi.getTopResources(subId, from, to, this.selectedAzureProject).pipe(
      catchError(err => {
        const msg = err.error?.detail || err.error?.message || err.message || 'Failed to load top resources.';
        console.warn('[Azure] top-resources error:', msg);
        return of({ success: false, top_resources: [], rows: [], _error: msg });
      })
    );

    const services$ = this.azureApi.getServiceCosts(subId, from, to, this.selectedAzureProject).pipe(
      catchError(err => {
        const msg = err.error?.detail || err.error?.message || err.message || 'Failed to load service costs.';
        console.warn('[Azure] service-costs error:', msg);
        return of({ success: false, services: [], rows: [], _error: msg });
      })
    );

    combineLatest({
      dailyRange: dailyRange$,
      topResources: topResources$,
      services: services$,
    }).pipe(
      finalize(() => {
        if (seq !== this.azureRangeLoadSeq) return;
        this.isLoadingAzureRange = false;
        this.isSubmittingDateFilter = false;
        this.isLoadingCostTrend = false;
        this.cdr.detectChanges();
      })
    ).subscribe({
      next: (res: any) => {
        if (seq !== this.azureRangeLoadSeq) return;

        const rangeMeta = res.dailyRange || res.services || res.topResources;
        this.applyUtcRangeMeta(rangeMeta);

        // Daily cost trend
        this.costTrendPoints = Array.isArray(res.dailyRange?.points) ? res.dailyRange.points : [];
        if (res.dailyRange?.success === false || (res.dailyRange as any)?._error) {
          this.costTrendError = (res.dailyRange as any)?._error || res.dailyRange?.error || 'No daily cost data for the selected date range.';
        }

        // Top resources
        this.topResources = Array.isArray(res.topResources?.top_resources) ? res.topResources.top_resources : [];
        if (res.topResources?.success === false || (res.topResources as any)?._error) {
          this.topResourcesError = (res.topResources as any)?._error || res.topResources?.error || 'No resource data for the selected date range.';
        }

        // Service costs
        this.serviceCosts = Array.isArray(res.services?.services) ? res.services.services : [];
        if (res.services?.success === false || (res.services as any)?._error) {
          this.serviceCostsError = (res.services as any)?._error || res.services?.error || 'No service cost data for the selected date range.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        if (seq !== this.azureRangeLoadSeq) return;
        this.costTrendPoints = [];
        this.topResources = [];
        this.serviceCosts = [];
        this.costTrendError = err.error?.detail || err.error?.message || err.message || 'Failed to load cost data for the selected UTC date range.';
        this.cdr.detectChanges();
      }
    });
  }

  private getUtcCostTrendRange(): { from: string; to: string } {
    const clamped = clampUtcDateRange(
      this.costTrendFromDate,
      this.costTrendToDate,
      utcYesterdayDate()
    );
    this.costTrendFromDate = clamped.from;
    this.costTrendToDate = clamped.to;
    return clamped;
  }

  onCostTrendDateChange() {
    const clamped = clampUtcDateRange(
      this.pendingFromDate,
      this.pendingToDate,
      utcYesterdayDate()
    );
    this.pendingFromDate = clamped.from;
    this.pendingToDate = clamped.to;
  }

  applyDateFilter() {
    // C – Bug Fix: always fire even when dates match previous values
    if (!this.selectedSubscriptionId) return;
    const clamped = clampUtcDateRange(
      this.pendingFromDate,
      this.pendingToDate,
      utcYesterdayDate()
    );
    this.costTrendFromDate = clamped.from;
    this.costTrendToDate = clamped.to;
    this.pendingFromDate = clamped.from;
    this.pendingToDate = clamped.to;
    this.resourcesCurrentPage = 1;
    this.servicesCurrentPage = 1;
    this.isSubmittingDateFilter = true;
    // Always reload — no short-circuit equality check
    this.loadSubscriptionMetrics(this.selectedSubscriptionId);
    this.loadAzureRangeMetrics(this.selectedSubscriptionId);
  }

  get isReadyToSubmit(): boolean {
    return !!(this.selectedSubscriptionId && this.pendingFromDate && this.pendingToDate);
  }

  get selectedSubscriptionName(): string {
    if (!this.selectedSubscriptionId) return '';
    const sub = this.subscriptions.find(s => s.subscriptionId === this.selectedSubscriptionId);
    return sub ? (sub.displayName || sub.name || this.selectedSubscriptionId) : this.selectedSubscriptionId;
  }

  get costTrendMaxDate(): string {
    return utcYesterdayDate();
  }

  get costTrendRangeTotal(): number {
    if (!this.costTrendPoints || this.costTrendPoints.length === 0) return 0;
    return this.costTrendPoints.reduce((sum, p) => sum + (p.cost || 0), 0);
  }

  onSubscriptionChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const value = input.value;
    const sub = this.subscriptions.find(s => s.displayName === value || s.subscriptionId === value);
    const subId = sub ? sub.subscriptionId : '';
    this.selectedSubscriptionId = subId;
    this.subSearch = sub ? sub.displayName : '';

    this.resourcesCurrentPage = 1;
    this.servicesCurrentPage = 1;
    this.totalCost = 0;
    this.budgets = [];
    this.topResources = [];
    this.serviceCosts = [];
    this.costTrendPoints = [];
    this.costTrendRangeLabelUtc = '';
    this.azureRangeLoadSeq++;

    if (!subId) {
      return;
    }
    this.loadAzureSubscriptionData(subId);
  }

  onAzureProjectChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const proj = input.value;
    const match = this.azureProjects.find(p => p === proj);
    this.selectedAzureProject = match || '';
    this.projectSearch = match || '';
    this.subSearch = '';
    this.selectedSubscriptionId = '';
    this.subscriptions = [];
    this.resourcesCurrentPage = 1;
    this.servicesCurrentPage = 1;
    this.totalCost = 0;
    this.budgets = [];
    this.topResources = [];
    this.serviceCosts = [];
    this.costTrendPoints = [];
    this.costTrendRangeLabelUtc = '';
    this.azureRangeLoadSeq++;

    if (!this.selectedAzureProject) {
      this.loadGlobalOverview();
      return;
    }
    this.loadSubscriptions();
  }

  private niceFloor(value: number): number {
    if (value <= 0) return 0;
    const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
    const step = magnitude >= 1000 ? magnitude / 2 : magnitude;
    return Math.floor(value / step) * step;
  }

  private niceCeil(value: number): number {
    if (value <= 0) return 1;
    const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
    const step = magnitude >= 1000 ? magnitude / 2 : magnitude;
    return Math.ceil(value / step) * step;
  }

  private costTrendScaleValues(): number[] {
    const costs = this.costTrendPoints.map(p => p.cost);
    if (costs.length < 2) return costs;
    const sorted = [...costs].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    const filtered = sorted.filter(c => c >= median * 0.15);
    return filtered.length >= Math.ceil(sorted.length * 0.5) ? filtered : sorted;
  }

  get costTrendYMin(): number {
    if (!this.costTrendPoints.length) return 0;
    const values = this.costTrendScaleValues();
    const min = values[0];
    const max = values[values.length - 1];
    const range = max - min;
    if (range < max * 0.005) return Math.max(0, this.niceFloor(min * 0.92));
    return Math.max(0, this.niceFloor(min - range * 0.15));
  }

  get costTrendYMax(): number {
    if (!this.costTrendPoints.length) return 1;
    const values = this.costTrendScaleValues();
    const max = values[values.length - 1];
    const min = values[0];
    const range = max - min;
    if (range < max * 0.005) return this.niceCeil(max * 1.08);
    return this.niceCeil(max + range * 0.10);
  }

  get costTrendYLabels(): string[] {
    const yMin = this.costTrendYMin;
    const yMax = this.costTrendYMax;
    const range = yMax - yMin || 1;
    const steps = 5;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const val = yMax - (range / steps) * i;
      return '₹' + Math.round(val).toLocaleString();
    });
  }

  get costTrendPolyline(): string {
    const pts = this.costTrendPoints;
    if (!pts.length) return '';
    const W = 560; const H = 200; const LEFT = 60; const TOP = 20;
    const yMin = this.costTrendYMin;
    const range = (this.costTrendYMax - yMin) || 1;
    return pts.map((p, i) => {
      const x = LEFT + (i / Math.max(pts.length - 1, 1)) * W;
      const y = TOP + H - ((p.cost - yMin) / range) * H;
      return `${x},${y}`;
    }).join(' ');
  }

  get costTrendCircles(): any[] {
    const pts = this.costTrendPoints;
    if (!pts.length) return [];
    const W = 560; const H = 200; const LEFT = 60; const TOP = 20;
    const yMin = this.costTrendYMin;
    const range = (this.costTrendYMax - yMin) || 1;
    return pts.map((p, i) => ({
      x: LEFT + (i / Math.max(pts.length - 1, 1)) * W,
      y: TOP + H - ((p.cost - yMin) / range) * H,
      date: p.date,
      dateUtc: p.dateUtc || `${p.date}T00:00:00Z`,
      cost: p.cost
    }));
  }

  private buildPieSlices(rows: any[]): any[] {
    if (!rows?.length) return [];
    const filtered = rows.filter((r: any) => (r[0] || 0) > 0);
    if (!filtered.length) return [];
    const total = filtered.reduce((s: number, r: any) => s + (r[0] || 0), 0);
    if (!total) return [];

    const cx = 150, cy = 150, radius = 120;
    let angle = -Math.PI / 2;

    return filtered.map((row: any, i: number) => {
      const cost = row[0] || 0;
      const pct = cost / total;
      const sweep = pct * 2 * Math.PI;
      const end = angle + sweep;

      const x1 = cx + radius * Math.cos(angle);
      const y1 = cy + radius * Math.sin(angle);
      const x2 = cx + radius * Math.cos(end);
      const y2 = cy + radius * Math.sin(end);

      const lx = cx + (radius * 0.65) * Math.cos(angle + sweep / 2);
      const ly = cy + (radius * 0.65) * Math.sin(angle + sweep / 2);

      let path: string;
      if (pct >= 1) {
        const xMid = cx + radius * Math.cos(angle + Math.PI);
        const yMid = cy + radius * Math.sin(angle + Math.PI);
        path = [
          `M ${cx} ${cy}`,
          `L ${x1.toFixed(2)} ${y1.toFixed(2)}`,
          `A ${radius} ${radius} 0 1 1 ${xMid.toFixed(2)} ${yMid.toFixed(2)}`,
          `A ${radius} ${radius} 0 1 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`,
          `Z`
        ].join(' ');
      } else {
        const largeArc = pct > 0.5 ? 1 : 0;
        path = `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 ${largeArc} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
      }

      angle = end;
      return {
        name: row[1] || 'Unknown',
        cost,
        color: this.PIE_COLORS[i % this.PIE_COLORS.length],
        path,
        percentage: Math.round(pct * 100),
        lx: lx.toFixed(1),
        ly: ly.toFixed(1),
      };
    });
  }

  get topResourcesPieSlices(): any[] {
    return this.buildPieSlices(this.topResources);
  }

  get serviceCostsPieSlices(): any[] {
    const sorted = [...this.serviceCosts].sort((a, b) => (b[0] || 0) - (a[0] || 0));
    return this.buildPieSlices(sorted);
  }

  loadGlobalOverview() {
    this.isLoadingOverview = true;
    this.overviewError = null;
    this.azureApi.getGlobalOverview().subscribe({
      next: (res: any) => {
        if (res && res.success && Array.isArray(res.overview)) {
          this.overviewData = res.overview;
        } else {
          this.overviewError = 'Failed to load enterprise overview data.';
        }
        this.isLoadingOverview = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Could not fetch global overview', err);
        this.overviewError = err.error?.detail || err.error?.message || err.message || 'Failed to load enterprise overview data.';
        this.isLoadingOverview = false;
        this.cdr.detectChanges();
      }
    });
  }

  get globalOverviewTotalCost(): number {
    if (!this.overviewData || this.overviewData.length === 0) return 0;
    return this.overviewData.reduce((sum, d) => sum + (d.devTest || 0) + (d.production || 0), 0);
  }

  get overviewMaxCost(): number {
    if (!this.overviewData || this.overviewData.length === 0) return 100000;
    const vals = this.overviewData.map(d => Math.max(d.devTest || 0, d.production || 0));
    const maxVal = Math.max(...vals);
    return maxVal > 0 ? maxVal : 100000;
  }

  get overviewYMax(): number {
    return this.niceCeil(this.overviewMaxCost * 1.15);
  }

  get overviewYLabels(): string[] {
    const yMax = this.overviewYMax;
    const steps = 5;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const val = yMax - (yMax / steps) * i;
      return '₹' + Math.round(val).toLocaleString();
    });
  }

  getOverviewBarPath(x: number, y: number, w: number, h: number, r: number = 4): string {
    if (h <= 0) return '';
    if (h < r) r = h;
    return `M ${x},${y + h} L ${x},${y + r} A ${r},${r} 0 0 1 ${x + r},${y} L ${x + w - r},${y} A ${r},${r} 0 0 1 ${x + w},${y + r} L ${x + w},${y + h} Z`;
  }

  getOverviewBars(): any[] {
    if (!this.overviewData || this.overviewData.length === 0) return [];
    
    const W = 520; const H = 200; const LEFT = 80; const TOP = 20;
    const yMax = this.overviewYMax;
    
    const categoryWidth = W / this.overviewData.length;
    const barWidth = categoryWidth * 0.28;
    const gapBetweenBars = categoryWidth * 0.08;
    
    const bars: any[] = [];
    this.overviewData.forEach((d, i) => {
      const categoryX = LEFT + i * categoryWidth;
      
      // devTest bar (Left)
      const devTestCost = d.devTest || 0;
      const devTestHeight = (devTestCost / yMax) * H;
      const devTestX = categoryX + (categoryWidth - (barWidth * 2 + gapBetweenBars)) / 2;
      const devTestY = TOP + H - devTestHeight;
      
      // production bar (Right)
      const prodCost = d.production || 0;
      const prodHeight = (prodCost / yMax) * H;
      const prodX = devTestX + barWidth + gapBetweenBars;
      const prodY = TOP + H - prodHeight;
      
      bars.push({
        project: d.project,
        env: 'Dev/Test',
        cost: devTestCost,
        x: devTestX,
        y: devTestY,
        w: barWidth,
        h: devTestHeight,
        path: this.getOverviewBarPath(devTestX, devTestY, barWidth, devTestHeight),
        color: 'url(#devTestGrad)',
        rawColor: '#64748b',
        gradientId: 'devTestGrad'
      });
      
      bars.push({
        project: d.project,
        env: 'Production',
        cost: prodCost,
        x: prodX,
        y: prodY,
        w: barWidth,
        h: prodHeight,
        path: this.getOverviewBarPath(prodX, prodY, barWidth, prodHeight),
        color: 'url(#prodGrad)',
        rawColor: '#3b82f6',
        gradientId: 'prodGrad'
      });
    });
    return bars;
  }
  
  getOverviewXLabels(): any[] {
    if (!this.overviewData || this.overviewData.length === 0) return [];
    const W = 520; const LEFT = 80;
    const categoryWidth = W / this.overviewData.length;
    return this.overviewData.map((d, i) => ({
      text: d.project,
      x: LEFT + i * categoryWidth + categoryWidth / 2
    }));
  }
}