import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Router } from '@angular/router';
import { DashboardService } from '../../../../services/dashboard.service';

// API Services imports
import { ProjectsApiService } from '../../../../services/api/projects-api.service';
import { RepositoriesApiService } from '../../../../services/api/repositories-api.service';
import { PipelinesApiService } from '../../../../services/api/pipelines-api.service';
import { AzureApiService } from '../../../../services/api/azure-api.service';
import { StatusApiService } from '../../../../services/api/status-api.service';
import { BoardsApiService } from '../../../../services/api/boards-api.service';

@Component({
  selector: 'app-dashboard-home',
  templateUrl: './dashboard-home.html',
  styleUrl: '../../home.css',
  imports: [CommonModule, FormsModule]
})
export class DashboardHomeComponent implements OnInit {

  // Real data arrays
  projects: any[] = [];
  totalProjectsCount = 0;   // global total from API (never paginated)
  repositories: any[] = [];
  azureProjects: string[] = [];
  homeProjSearch = '';

  get filteredHomeProjects(): string[] {
    if (!this.homeProjSearch) return this.azureProjects;
    const query = this.homeProjSearch.toLowerCase();
    return this.azureProjects.filter(proj => proj.toLowerCase().includes(query));
  }
  servicesStatus: any[] = [];
  projectDistribution: any[] = [];
  projectPieSlices: any[] = [];
  hoveredProject: any = null;

  // Loader / States
  isLoadingProjects = false;
  isLoadingRepos = false;
  isLoadingYearlyCost = false;
  isLoadingCostTrend = false;
  activePipelinesCount = 0;
  yearlyCost = 0;

  // Global aggregate combined cost
  combinedYearlyCost = 0;
  isLoadingCombinedCost = false;
  combinedCostError: string | null = null;

  // Multi-project cost trend properties
  isLoadingMultiTrend = false;
  multiTrendError: string | null = null;
  projectTrends: any[] = [];

  // Selections
  selectedHomeAzureProject = '';
  selectedHomeSubscriptionId = '';
  selectedTrendMonth = '';
  monthlyCostTotal = 0;

  // Chart Properties
  pieChartStyle = '';
  yAxisLabels: string[] = [];
  trendMonths: string[] = [];

  // Pie legend filter
  pieSearchQuery = '';

  // Pie chart pagination
  pieCurrentPage = 1;
  piePageSize = 5;

  get pieTotalPages(): number {
    const dist = this.projectDistribution.filter(p => p.count > 0);
    return Math.max(1, Math.ceil(dist.length / this.piePageSize));
  }

  get paginatedProjectDistribution(): any[] {
    const dist = this.projectDistribution.filter(p => p.count > 0);
    const start = (this.pieCurrentPage - 1) * this.piePageSize;
    return dist.slice(start, start + this.piePageSize);
  }

  get filteredProjectDistribution(): any[] {
    if (!this.pieSearchQuery?.trim()) return this.paginatedProjectDistribution;
    const q = this.pieSearchQuery.trim().toLowerCase();
    return this.paginatedProjectDistribution.filter(item => item.name.toLowerCase().includes(q));
  }

  // Project distribution popup
  showProjectDistributionDetails = false;
  repoSortOrder = 'default';

  get sortedProjectDistribution(): any[] {
    if (this.repoSortOrder === 'desc') {
      return [...this.projectDistribution].sort((a, b) => b.count - a.count);
    }
    if (this.repoSortOrder === 'asc') {
      return [...this.projectDistribution].sort((a, b) => a.count - b.count);
    }
    return this.projectDistribution;
  }

  // Error States
  projectsError: string | null = null;
  reposError: string | null = null;
  activePipelinesError: string | null = null;
  yearlyCostError: string | null = null;
  servicesStatusError: string | null = null;

  modalCurrentPage = 1;
  pageSize = 10;
  get Math() { return Math; }

  get paginatedModalDistribution(): any[] {
    const start = (this.modalCurrentPage - 1) * this.pageSize;
    return this.sortedProjectDistribution.slice(start, start + this.pageSize);
  }
  get modalTotalPages(): number {
    return Math.ceil(this.sortedProjectDistribution.length / this.pageSize);
  }

  reposResolved = false;
  servicesResolved = false;

  checkAndReload() {
    if (this.reposResolved && this.servicesResolved) {
      this.calculateProjectDistribution();
      this.cdr.markForCheck();
      this.cdr.detectChanges();
      
      if (!this.dashboardService.hasReloadedDashboard) {
        this.dashboardService.hasReloadedDashboard = true;
        const currentUrl = this.router.url;
        this.router.navigateByUrl('/', { skipLocationChange: true }).then(() => {
          this.router.navigate([currentUrl]);
        });
      }
    }
  }

  constructor(
    private projectsApi: ProjectsApiService,
    private reposApi: RepositoriesApiService,
    private pipelinesApi: PipelinesApiService,
    private azureApi: AzureApiService,
    private statusApi: StatusApiService,
    private boardsApi: BoardsApiService,
    private cdr: ChangeDetectorRef,
    private router: Router,
    public dashboardService: DashboardService
  ) {}

  ngOnInit() {
    this.loadProjects();
    this.loadRepositories();
    this.loadActivePipelinesCount();
    this.loadCombinedYearlyCost();
    this.loadMultiProjectTrends();
    this.loadServicesStatus();
    this.loadAzureProjects();
  }

  loadAzureProjects() {
    forkJoin({
      azureRes: this.azureApi.getAzureProjects().pipe(catchError(() => of({ projects: [] }))),
      devopsRes: this.projectsApi.getProjects(1, 999).pipe(catchError(() => of({ projects: [] })))
    }).subscribe({
      next: (res: any) => {
        let azureNames: string[] = [];
        if (res.azureRes && res.azureRes.projects) {
          azureNames = res.azureRes.projects;
        }

        let devopsNames: string[] = [];
        if (res.devopsRes && res.devopsRes.projects) {
          devopsNames = res.devopsRes.projects.map((p: any) => p.name || p);
        } else if (res.devopsRes && Array.isArray(res.devopsRes)) {
          devopsNames = res.devopsRes.map((p: any) => p.name || p);
        }

        const seenNormal = new Set<string>();
        const combined: string[] = [];

        const addProject = (name: string) => {
          if (!name) return;
          const normalized = name.toLowerCase().trim().replace(/[-_\s]/g, '');
          if (!seenNormal.has(normalized)) {
            seenNormal.add(normalized);
            combined.push(name);
          }
        };

        azureNames.forEach(name => addProject(name));
        devopsNames.forEach(name => addProject(name));

        this.azureProjects = combined;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Failed to load Azure projects', err);
      }
    });
  }

  loadProjects() {
    this.isLoadingProjects = true;
    this.projectsError = null;
    // Fetch ALL projects (large page size) so the distribution pie is complete
    this.projectsApi.getProjects(1, 999).subscribe({
      next: (res: any) => {
        let projs = [];
        let total = 0;
        if (res && res.success && res.projects) {
          projs = res.projects;
          total = res.total_count ?? projs.length;
        } else if (res && res.projects) {
          projs = res.projects;
          total = res.total_count ?? projs.length;
        }

        this.projects = projs || [];
        this.totalProjectsCount = total || this.projects.length;
        this.isLoadingProjects = false;
        this.calculateProjectDistribution();
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Could not fetch projects from backend', err);
        this.projects = [];
        this.totalProjectsCount = 0;
        this.projectsError = err.error?.detail || err.error?.message || err.message || 'Failed to load projects from backend.';
        this.isLoadingProjects = false;
        this.calculateProjectDistribution();
        this.cdr.detectChanges();
      }
    });
  }

  loadRepositories() {
    this.isLoadingRepos = true;
    this.reposError = null;
    this.reposApi.getAllRepositories().subscribe({
      next: (res: any) => {
        if (res && res.repositories && res.repositories.length > 0) {
          this.repositories = res.repositories;
        } else {
          this.repositories = [];
          this.reposError = 'No repositories found on backend.';
        }
        this.isLoadingRepos = false;
        this.reposResolved = true;
        this.checkAndReload();
      },
      error: (err) => {
        console.warn('Could not fetch repositories from backend', err);
        this.repositories = [];
        this.reposError = err.error?.detail || err.error?.message || err.message || 'Failed to load repositories.';
        this.isLoadingRepos = false;
        this.reposResolved = true;
        this.checkAndReload();
      }
    });
  }

  loadHomeSubscriptions(project: string) {
    this.azureApi.getSubscriptions(project).subscribe({
      next: (res: any) => {
        let subs = [];
        if (res && res.subscriptions && res.subscriptions.length > 0) {
          subs = res.subscriptions;
        } else if (res && Array.isArray(res) && res.length > 0) {
          subs = res;
        }

        if (subs && subs.length > 0) {
          this.selectedHomeSubscriptionId = subs[0].subscriptionId;
          this.loadHomeYearlyCost(this.selectedHomeSubscriptionId, project);
        } else {
          this.selectedHomeSubscriptionId = '';
          this.yearlyCost = 0;
        }
      },
      error: () => {
        this.selectedHomeSubscriptionId = '';
        this.yearlyCost = 0;
      }
    });
  }

  loadHomeYearlyCost(subId: string, project: string) {
    this.isLoadingYearlyCost = true;
    this.yearlyCostError = null;
    this.azureApi.getYearlyCosts(subId, project).subscribe({
      next: (res: any) => {
        const rows = res?.rows || res?.yearly_costs || [];
        if (rows && rows.length > 0 && rows[0].length > 0) {
          this.yearlyCost = rows.reduce((sum: number, row: any[]) => sum + (row[0] || 0), 0);
        } else {
          this.yearlyCost = 0;
        }
        this.isLoadingYearlyCost = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.yearlyCost = 0;
        this.yearlyCostError = err.error?.detail || err.error?.message || err.message || 'Failed to load yearly cost.';
        this.isLoadingYearlyCost = false;
        this.cdr.detectChanges();
      }
    });
  }

  loadActivePipelinesCount() {
    this.activePipelinesError = null;
    this.pipelinesApi.getActivePipelinesCount().subscribe({
      next: (res: any) => {
        if (res && res.success && res.count !== undefined) {
          this.activePipelinesCount = res.count;
        } else if (res && !res.success) {
          this.activePipelinesCount = 0;
          this.activePipelinesError = res?.message || 'Failed to get active pipelines count.';
        } else {
          this.activePipelinesCount = 0;
          this.activePipelinesError = 'Invalid response format for active pipelines count.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.activePipelinesCount = 0;
        this.activePipelinesError = err.error?.detail || err.error?.message || err.message || 'Failed to get active pipelines count.';
        this.cdr.detectChanges();
      }
    });
  }

  loadCombinedYearlyCost() {
    this.isLoadingCombinedCost = true;
    this.combinedCostError = null;
    this.azureApi.getCombinedYearlyCost().subscribe({
      next: (res: any) => {
        if (res && res.success) {
          this.combinedYearlyCost = res.yearly_cost;
        } else {
          this.combinedYearlyCost = 0;
        }
        this.isLoadingCombinedCost = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Failed to load combined yearly cost', err);
        this.combinedYearlyCost = 0;
        this.combinedCostError = err.error?.detail || err.error?.message || err.message || 'Failed to load combined yearly cost.';
        this.isLoadingCombinedCost = false;
        this.cdr.detectChanges();
      }
    });
  }

  loadMultiProjectTrends() {
    this.isLoadingMultiTrend = true;
    this.multiTrendError = null;

    const projNames = ['AiDocFlo', 'TimeFlow', 'Integrelity'];
    const colors: { [key: string]: string } = {
      'AiDocFlo': '#2563eb',     // Blue
      'TimeFlow': '#16a34a',     // Green
      'Integrelity': '#f59e0b'   // Amber
    };

    const requests = projNames.map(proj => this.azureApi.getCostTrend(proj));

    forkJoin(requests).subscribe({
      next: (results: any[]) => {
        const trends: any[] = [];
        let allMonths: string[] = [];

        results.forEach((res, index) => {
          const projName = projNames[index];
          const color = colors[projName] || '#6b7280';
          const points = res && res.trend ? res.trend : [];
          
          if (points.length > 0 && allMonths.length === 0) {
            allMonths = points.map((p: any) => p.month);
          }

          trends.push({
            projectName: projName,
            color: color,
            points: points,
            polylinePoints: '',
            circlePoints: []
          });
        });

        this.projectTrends = trends;
        this.trendMonths = allMonths;
        this.generateMultiLineChartPoints();
        this.isLoadingMultiTrend = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Failed to load multi-project cost trends', err);
        this.multiTrendError = 'Failed to load multi-project cost trends.';
        this.isLoadingMultiTrend = false;
        this.cdr.detectChanges();
      }
    });
  }

  loadServicesStatus(project?: string) {
    this.servicesStatusError = null;
    this.statusApi.getServicesStatus(project).subscribe({
      next: (res: any) => {
        if (res && res.length > 0) {
          this.servicesStatus = res;
        } else {
          this.servicesStatus = [];
          this.servicesStatusError = 'No services status data found.';
        }
        this.servicesResolved = true;
        this.checkAndReload();
      },
      error: (err) => {
        console.warn('Failed to load services status', err);
        this.servicesStatus = [];
        this.servicesStatusError = err.error?.detail || err.error?.message || err.message || 'Failed to load services status.';
        this.servicesResolved = true;
        this.checkAndReload();
      }
    });
  }

  calculateProjectDistribution() {
    if (!this.repositories.length) {
      this.projectDistribution = [];
      this.projectPieSlices = [];
      this.pieChartStyle = '';
      return;
    }

    const colors = ['#2563eb', '#16a34a', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#3b82f6'];
    const greyColor = '#d1d5db';
    const dist: any[] = [];
    const gradientParts: string[] = [];

    // Build counts from ALL repositories (not just from this.projects)
    const counts: { [key: string]: number } = {};
    this.projects.forEach(p => { counts[p.name] = 0; });
    this.repositories.forEach(r => {
      if (r.project) {
        counts[r.project] = (counts[r.project] || 0) + 1;
      }
    });

    const totalRepos = this.repositories.length;
    let accumulatedDegrees = 0;
    let colorIndex = 0;

    // First: add all API projects (in their original order)
    const knownProjectNames = new Set(this.projects.map((p: any) => p.name));
    this.projects.forEach((proj: any) => {
      const count = counts[proj.name] || 0;
      const percentage = totalRepos > 0 ? (count / totalRepos) : 0;
      const degrees = Math.round(percentage * 360);
      const isSelected = !this.selectedHomeAzureProject || proj.name === this.selectedHomeAzureProject;
      const originalColor = colors[colorIndex % colors.length];
      const color = isSelected ? originalColor : greyColor;
      colorIndex++;

      dist.push({ name: proj.name, count, color, isSelected });

      if (count > 0) {
        const nextDegrees = accumulatedDegrees + degrees;
        gradientParts.push(`${color} ${accumulatedDegrees}deg ${nextDegrees}deg`);
        accumulatedDegrees = nextDegrees;
      }
    });

    // Second: add any 'orphan' projects found in repos but not in this.projects
    Object.keys(counts).forEach(projName => {
      if (knownProjectNames.has(projName)) return;  // already handled above
      const count = counts[projName];
      if (!count) return;
      const percentage = count / totalRepos;
      const degrees = Math.round(percentage * 360);
      const isSelected = !this.selectedHomeAzureProject || projName === this.selectedHomeAzureProject;
      const originalColor = colors[colorIndex % colors.length];
      const color = isSelected ? originalColor : greyColor;
      colorIndex++;

      dist.push({ name: projName, count, color, isSelected });

      const nextDegrees = accumulatedDegrees + degrees;
      gradientParts.push(`${color} ${accumulatedDegrees}deg ${nextDegrees}deg`);
      accumulatedDegrees = nextDegrees;
    });

    if (gradientParts.length > 0 && accumulatedDegrees > 0) {
      const lastIndex = gradientParts.length - 1;
      const part = gradientParts[lastIndex];
      const match = part.match(/^(.+?)\s+(\d+)deg\s+(\d+)deg$/);
      if (match) {
        gradientParts[lastIndex] = `${match[1]} ${match[2]}deg 360deg`;
      }
    }

    this.projectDistribution = dist;
    this.projectPieSlices = this.buildProjectPieSlices(dist);
    this.pieChartStyle = gradientParts.length > 0 ? `conic-gradient(${gradientParts.join(', ')})` : 'gray';
    this.pieCurrentPage = 1;
  }

  buildProjectPieSlices(distribution: any[]): any[] {
    if (!distribution || !distribution.length) return [];
    
    const filtered = distribution.filter(p => (p.count || 0) > 0);
    if (!filtered.length) return [];
    
    const total = filtered.reduce((sum, p) => sum + (p.count || 0), 0);
    if (!total) return [];
    
    const cx = 110, cy = 110, radius = 100;
    let angle = -Math.PI / 2;
    
    return filtered.map((p: any) => {
      const count = p.count || 0;
      const pct = count / total;
      const sweep = pct * 2 * Math.PI;
      const end = angle + sweep;
      
      const x1 = cx + radius * Math.cos(angle);
      const y1 = cy + radius * Math.sin(angle);
      const x2 = cx + radius * Math.cos(end);
      const y2 = cy + radius * Math.sin(end);
      
      let path: string;
      if (pct >= 0.999) {
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
      
      const slice = {
        name: p.name,
        count: count,
        color: p.color,
        path: path,
        percentage: Math.round(pct * 100)
      };
      
      angle = end;
      return slice;
    });
  }

  get paginatedPieSlices(): any[] {
    return this.buildProjectPieSlices(this.paginatedProjectDistribution);
  }

  get visibleTrends(): any[] {
    if (!this.selectedHomeAzureProject) {
      return this.projectTrends;
    }
    return this.projectTrends.filter(t => t.projectName === this.selectedHomeAzureProject);
  }

  generateMultiLineChartPoints(): void {
    if (!this.projectTrends || this.projectTrends.length === 0) {
      this.yAxisLabels = [];
      return;
    }

    let globalMax = 0;
    this.projectTrends.forEach(trend => {
      trend.points.forEach((p: any) => {
        if (p.cost > globalMax) {
          globalMax = p.cost;
        }
      });
    });

    const maxVal = this.getNiceMax(globalMax);
    this.generateYAxisLabels(maxVal);

    const chartLeft = 55;
    const chartRight = 585;
    const chartTop = 30;
    const chartBottom = 255;

    const chartWidth = chartRight - chartLeft;
    const chartHeight = chartBottom - chartTop;

    this.projectTrends.forEach(trend => {
      const points: string[] = [];
      const circles: any[] = [];
      const totalPoints = trend.points.length;

      trend.points.forEach((item: any, index: number) => {
        const cx = totalPoints > 1
          ? chartLeft + (index * chartWidth) / (totalPoints - 1)
          : chartLeft + chartWidth / 2;

        const cy = chartBottom - (item.cost / maxVal) * chartHeight;
        points.push(`${cx},${cy}`);

        circles.push({
          cx,
          cy,
          cost: item.cost,
          month: item.month
        });
      });

      trend.polylinePoints = points.join(' ');
      trend.circlePoints = circles;
    });
  }

  private getNiceMax(value: number): number {
    if (value <= 0) return 1000;
    const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
    const normalized = value / magnitude;
    let niceNormalized: number;
    if (normalized <= 1) niceNormalized = 1;
    else if (normalized <= 2) niceNormalized = 2;
    else if (normalized <= 5) niceNormalized = 5;
    else niceNormalized = 10;
    return niceNormalized * magnitude;
  }

  generateYAxisLabels(maxVal: number): void {
    const intervals = 5;
    this.yAxisLabels = [];
    for (let i = intervals; i >= 0; i--) {
      const value = (maxVal * i) / intervals;
      this.yAxisLabels.push(this.formatYAxisValue(value));
    }
  }

  private formatYAxisValue(value: number): string {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) {
      const k = value / 1000;
      return Number.isInteger(k) ? `${k}K` : `${k.toFixed(1)}K`;
    }
    return Math.round(value).toString();
  }

  // Work-Item Status Breakdown properties
  isLoadingWorkItemStates = false;
  workItemStatesError: string | null = null;
  workItemStates: any[] = [];
  workItemPieSlices: any[] = [];
  hoveredWorkItemState: string | null = null;

  loadWorkItemStatusDistribution(project: string) {
    this.isLoadingWorkItemStates = true;
    this.workItemStatesError = null;
    this.workItemStates = [];
    this.workItemPieSlices = [];
    this.hoveredWorkItemState = null;
    this.cdr.detectChanges();

    this.boardsApi.getWorkItems(project, 1, 200).subscribe({
      next: (res: any) => {
        if (res && res.success && res.value) {
          const counts: { [key: string]: number } = {};
          res.value.forEach((item: any) => {
            const state = item.fields?.['System.State'];
            if (state) {
              counts[state] = (counts[state] || 0) + 1;
            }
          });

          this.workItemStates = Object.keys(counts).map(state => ({
            state: state,
            count: counts[state]
          }));

          this.workItemPieSlices = this.buildWorkItemPieSlices(this.workItemStates);
        } else {
          this.workItemStates = [];
          this.workItemPieSlices = [];
          this.workItemStatesError = res?.message || 'Failed to load work item status distribution.';
        }
        this.isLoadingWorkItemStates = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Failed to load work item status distribution', err);
        this.workItemStates = [];
        this.workItemPieSlices = [];
        this.workItemStatesError = err.error?.detail || err.error?.message || err.message || 'Failed to load work item status distribution.';
        this.isLoadingWorkItemStates = false;
        this.cdr.detectChanges();
      }
    });
  }

  buildWorkItemPieSlices(states: any[]): any[] {
    if (!states || !states.length) return [];
    
    const filtered = states.filter(s => (s.count || 0) > 0);
    if (!filtered.length) return [];
    
    const total = filtered.reduce((sum, s) => sum + (s.count || 0), 0);
    if (!total) return [];
    
    const cx = 110, cy = 110, radius = 90;
    let angle = -Math.PI / 2;
    
    const stateColors: { [key: string]: string } = {
      'New': '#94a3b8',
      'Proposed': '#94a3b8',
      'To Do': '#94a3b8',
      'Active': '#2563eb',
      'In Progress': '#2563eb',
      'Doing': '#2563eb',
      'Closed': '#10b981',
      'Done': '#10b981',
      'Resolved': '#f59e0b',
      'Removed': '#ef4444'
    };
    const defaultColors = ['#94a3b8', '#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#ec4899'];
    
    return filtered.map((s: any, i: number) => {
      const count = s.count || 0;
      const pct = count / total;
      const sweep = pct * 2 * Math.PI;
      const end = angle + sweep;
      
      const x1 = cx + radius * Math.cos(angle);
      const y1 = cy + radius * Math.sin(angle);
      const x2 = cx + radius * Math.cos(end);
      const y2 = cy + radius * Math.sin(end);
      
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
      
      const color = stateColors[s.state] || defaultColors[i % defaultColors.length];
      
      angle = end;
      return {
        state: s.state,
        count: count,
        color: color,
        path: path,
        percentage: Math.round(pct * 100)
      };
    });
  }

  onHomeAzureProjectChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const proj = input.value;
    const match = this.azureProjects.find(p => p === proj);
    this.selectedHomeAzureProject = match || '';
    this.homeProjSearch = match || '';
    this.selectedHomeSubscriptionId = '';
    this.yearlyCost = 0;

    this.calculateProjectDistribution();

    if (!this.selectedHomeAzureProject) {
      this.yearlyCost = 0;
      this.servicesStatus = [];
      this.workItemStates = [];
      this.workItemPieSlices = [];
      this.loadServicesStatus();
      return;
    }
    this.loadHomeSubscriptions(this.selectedHomeAzureProject);
    this.loadServicesStatus(this.selectedHomeAzureProject);
    this.loadWorkItemStatusDistribution(this.selectedHomeAzureProject);
  }

  getProjectDescription(projName: string): string {
    const p = this.projects.find(x => x.name === projName);
    return p ? p.description || 'N/A' : 'N/A';
  }

  getProjectState(projName: string): string {
    const p = this.projects.find(x => x.name === projName);
    return p ? p.state || 'Active' : 'Active';
  }

  getProjectVisibility(projName: string): string {
    const p = this.projects.find(x => x.name === projName);
    return p ? p.visibility || 'Private' : 'Private';
  }

  openProjectDistributionDetailsModal() {
    this.showProjectDistributionDetails = true;
  }

  closeProjectDistributionDetailsModal() {
    this.showProjectDistributionDetails = false;
  }

  getSelectedProjectRepoCount(): number {
    if (!this.selectedHomeAzureProject) return 0;
    const item = this.projectDistribution.find(p => p.name === this.selectedHomeAzureProject);
    return item ? item.count : 0;
  }
}