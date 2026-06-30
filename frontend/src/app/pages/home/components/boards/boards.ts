import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DashboardService } from '../../../../services/dashboard.service';
import { ProjectsApiService } from '../../../../services/api/projects-api.service';
import { BoardsApiService } from '../../../../services/api/boards-api.service';
import { CustomSelectComponent, SelectOption } from '../../../../components/custom-select/custom-select';

@Component({
  selector: 'app-boards',
  imports: [CommonModule, FormsModule, CustomSelectComponent],
  templateUrl: './boards.html',
  styleUrl: '../../home.css'
})
export class BoardsComponent implements OnInit {

  projects: any[] = [];
  workItems: any[] = [];
  workItemSprints: string[] = [];
  isLoadingWorkItems = false;
  isLoadingProjects = false;
  workItemsError: string | null = null;

  // Recent state-change activity feed
  recentChanges: any[] = [];
  isLoadingChanges = false;
  changesError: string | null = null;

  projectsSearchTerm = '';

  currentPage = 1;
  changesCurrentPage = 1;
  projectsCurrentPage = 1;
  pageSize = 10;
  totalProjectsCount = 0;
  totalWorkItemsCount = 0;
  totalChangesCount = 0;

  boardUniqueTypes: string[] = [];
  boardUniqueStates: string[] = [];
  boardUniqueAssignees: string[] = [];

  get Math() { return Math; }

  get paginatedProjects(): any[] {
    const start = (this.projectsCurrentPage - 1) * 10;
    return this.projects.slice(start, start + 10);
  }

  get projectsTotalPages(): number {
    return Math.ceil(this.totalProjectsCount / 10);
  }

  get paginatedRecentChanges(): any[] {
    return this.recentChanges;
  }

  get changesTotalPages(): number {
    return Math.ceil(this.totalChangesCount / 10);
  }

  get workItemsTotalPages(): number {
    return Math.ceil(this.totalWorkItemsCount / this.pageSize);
  }

  boardFilterSprint = '';
  boardFilterType = '';
  boardFilterState = '';
  boardFilterAssigned = '';

  sprintSearch = '';
  typeSearch = '';
  stateSearch = '';
  assignedSearch = '';

  get filteredSprints(): string[] {
    return this.sprintOptions.map(o => o.value).filter(val => val !== '');
  }

  get filteredTypes(): string[] {
    return this.typeOptions.map(o => o.value).filter(val => val !== '');
  }

  get filteredStates(): string[] {
    return this.stateOptions.map(o => o.value).filter(val => val !== '');
  }

  get filteredAssignees(): string[] {
    return this.assigneeOptions.map(o => o.value).filter(val => val !== '');
  }

  get sprintOptions(): SelectOption[] {
    return [
      { label: 'All Sprints', value: '' },
      ...this.workItemSprints.map(s => ({ label: s, value: s }))
    ];
  }

  get typeOptions(): SelectOption[] {
    return [
      { label: 'All Types', value: '' },
      ...this.boardUniqueTypes.map(t => ({ label: t, value: t }))
    ];
  }

  get stateOptions(): SelectOption[] {
    return [
      { label: 'All States', value: '' },
      ...this.boardUniqueStates.map(s => ({ label: s, value: s }))
    ];
  }

  get assigneeOptions(): SelectOption[] {
    return [
      { label: 'All Assignees', value: '' },
      ...this.boardUniqueAssignees.map(a => ({ label: a, value: a }))
    ];
  }

  onSprintSelect(value: string) {
    this.boardFilterSprint = value || '';
    this.sprintSearch = value || '';
    this.onFilterChange();
  }

  onTypeSelect(value: string) {
    this.boardFilterType = value || '';
    this.typeSearch = value || '';
    this.onFilterChange();
  }

  onStateSelect(value: string) {
    this.boardFilterState = value || '';
    this.stateSearch = value || '';
    this.onFilterChange();
  }

  onAssignedSelect(value: string) {
    this.boardFilterAssigned = value || '';
    this.assignedSearch = value || '';
    this.onFilterChange();
  }

  onSprintChange(event: Event) {
    const input = event.target as HTMLInputElement;
    this.onSprintSelect(input.value);
  }

  onTypeChange(event: Event) {
    const input = event.target as HTMLInputElement;
    this.onTypeSelect(input.value);
  }

  onStateChange(event: Event) {
    const input = event.target as HTMLInputElement;
    this.onStateSelect(input.value);
  }

  onAssignedChange(event: Event) {
    const input = event.target as HTMLInputElement;
    this.onAssignedSelect(input.value);
  }
  collapsedSprints: Set<string> = new Set();

  constructor(
    public dashboardService: DashboardService,
    private projectsApi: ProjectsApiService,
    private boardsApi: BoardsApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadProjects();
    if (this.dashboardService.selectedProject) {
      this.loadWorkItems(this.dashboardService.selectedProject.name);
      this.loadRecentChanges(this.dashboardService.selectedProject.name);
    }
  }

  onProjectsSearchChange(value: string) {
    this.projectsSearchTerm = value;
    this.projectsCurrentPage = 1;
    this.loadProjects();
  }

  loadProjects() {
    this.isLoadingProjects = true;
    this.projectsApi.getProjects(this.projectsCurrentPage, 10, this.projectsSearchTerm).subscribe({
      next: (res: any) => {
        let projs = [];
        let total = 0;
        if (res && res.success) {
          projs = res.projects;
          total = res.total_count;
        } else if (res && res.projects) {
          projs = res.projects;
          total = res.total_count || projs.length;
        }
        this.projects = projs || [];
        this.totalProjectsCount = total || this.projects.length;
        this.isLoadingProjects = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Failed to load projects', err);
        this.isLoadingProjects = false;
        this.cdr.detectChanges();
      }
    });
  }

  loadWorkItems(projName: string) {
    this.isLoadingWorkItems = true;
    this.workItemsError = null;
    this.boardsApi.getWorkItems(
      projName,
      this.currentPage,
      this.pageSize,
      this.boardFilterSprint,
      this.boardFilterType,
      this.boardFilterState,
      this.boardFilterAssigned
    ).subscribe({
      next: (res: any) => {
        if (res && res.success) {
          this.workItems = (res.value || []).map((item: any) => {
            const f = item.fields || {};
            const assignedTo = f['System.AssignedTo'];
            return {
              id: item.id,
              rev: item.rev,
              title: f['System.Title'],
              type: f['System.WorkItemType'],
              state: f['System.State'],
              boardColumn: f['System.BoardColumn'],
              assignedTo: assignedTo?.displayName || null,
              priority: f['Microsoft.VSTS.Common.Priority'],
              severity: f['Microsoft.VSTS.Common.Severity'] || null,
              stateChangedDate: f['Microsoft.VSTS.Common.StateChangeDate'] || null,
              startDate: f['Microsoft.VSTS.Scheduling.StartDate'] || null,
              targetDate: f['Microsoft.VSTS.Scheduling.TargetDate'] || null,
              sprint: f['_sprint'] || 'No Sprint',
            };
          });
          this.workItemSprints = res.sprints || [];
          this.boardUniqueTypes = res.types || [];
          this.boardUniqueStates = res.states || [];
          this.boardUniqueAssignees = res.assignees || [];
          this.totalWorkItemsCount = res.total_count || 0;
        } else {
          this.workItems = [];
          this.workItemSprints = [];
          this.boardUniqueTypes = [];
          this.boardUniqueStates = [];
          this.boardUniqueAssignees = [];
          this.totalWorkItemsCount = 0;
          this.workItemsError = res?.message || 'Failed to load work items from backend.';
        }
        this.isLoadingWorkItems = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn(`Could not load work items for project ${projName}`, err);
        this.workItems = [];
        this.workItemSprints = [];
        this.boardUniqueTypes = [];
        this.boardUniqueStates = [];
        this.boardUniqueAssignees = [];
        this.totalWorkItemsCount = 0;
        this.workItemsError = err.error?.detail || err.error?.message || err.message || `Failed to load work items for project ${projName}.`;
        this.isLoadingWorkItems = false;
        this.cdr.detectChanges();
      }
    });
  }

  loadRecentChanges(projName: string) {
    this.isLoadingChanges = true;
    this.changesError = null;
    this.boardsApi.getRecentChanges(projName, 30, 25, this.changesCurrentPage, 10).subscribe({
      next: (res: any) => {
        if (res && res.success) {
          this.recentChanges = res.changes || [];
          this.totalChangesCount = res.total_count || 0;
        } else {
          this.recentChanges = [];
          this.totalChangesCount = 0;
          this.changesError = res?.message || 'Could not load recent changes.';
        }
        this.isLoadingChanges = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn(`Could not load recent changes for project ${projName}`, err);
        this.recentChanges = [];
        this.totalChangesCount = 0;
        this.changesError = err.error?.detail || err.message || 'Failed to load recent changes.';
        this.isLoadingChanges = false;
        this.cdr.detectChanges();
      }
    });
  }

  selectProject(project: any) {
    this.currentPage = 1;
    this.changesCurrentPage = 1;
    this.projectsCurrentPage = 1;
    this.dashboardService.selectedProject = project;
    this.sprintSearch = '';
    this.typeSearch = '';
    this.stateSearch = '';
    this.assignedSearch = '';
    this.loadWorkItems(project.name);
    this.loadRecentChanges(project.name);
  }

  changeProject() {
    this.currentPage = 1;
    this.changesCurrentPage = 1;
    this.projectsCurrentPage = 1;
    this.dashboardService.selectedProject = null;
    this.workItems = [];
    this.workItemSprints = [];
    this.recentChanges = [];
    this.totalWorkItemsCount = 0;
    this.totalChangesCount = 0;
    this.workItemsError = null;
    this.changesError = null;
    this.sprintSearch = '';
    this.typeSearch = '';
    this.stateSearch = '';
    this.assignedSearch = '';
    this.loadProjects();
  }

  navigateBack() {
    this.dashboardService.isNavigatingHistory = true;
    const res = this.dashboardService.getPreviousProject();
    if (res.found) {
      if (res.project) {
        this.selectProject(res.project);
      } else {
        this.changeProject();
      }
    }
    this.dashboardService.isNavigatingHistory = false;
  }

  navigateForward() {
    this.dashboardService.isNavigatingHistory = true;
    const res = this.dashboardService.getNextProject();
    if (res.found) {
      if (res.project) {
        this.selectProject(res.project);
      } else {
        this.changeProject();
      }
    }
    this.dashboardService.isNavigatingHistory = false;
  }

  onFilterChange() {
    this.currentPage = 1;
    if (this.dashboardService.selectedProject) {
      this.loadWorkItems(this.dashboardService.selectedProject.name);
    }
  }

  clearFilters() {
    this.boardFilterSprint = '';
    this.boardFilterType = '';
    this.boardFilterState = '';
    this.boardFilterAssigned = '';
    this.sprintSearch = '';
    this.typeSearch = '';
    this.stateSearch = '';
    this.assignedSearch = '';
    this.onFilterChange();
  }

  get filteredWorkItems(): any[] {
    return this.workItems;
  }

  get groupedWorkItems(): { sprint: string; items: any[] }[] {
    const items = this.filteredWorkItems;
    const map = new Map<string, any[]>();
    for (const item of items) {
      const sprint = item.sprint || 'No Sprint';
      if (!map.has(sprint)) map.set(sprint, []);
      map.get(sprint)!.push(item);
    }
    return Array.from(map.entries()).map(([sprint, items]) => ({ sprint, items }));
  }

  toggleSprintCollapse(sprint: string) {
    if (this.collapsedSprints.has(sprint)) {
      this.collapsedSprints.delete(sprint);
    } else {
      this.collapsedSprints.add(sprint);
    }
  }

  isSprintCollapsed(sprint: string): boolean {
    return this.collapsedSprints.has(sprint);
  }

  /** Format an ISO timestamp to a human-friendly local date-time string. */
  formatChangedAt(iso: string | null): string {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch {
      return iso;
    }
  }

  /** State → badge colour map. */
  stateColor(state: string | null): { bg: string; fg: string } {
    if (!state) return { bg: '#f1f5f9', fg: '#475569' };
    const s = state.toLowerCase();
    if (s === 'done' || s === 'closed' || s === 'resolved') return { bg: '#dcfce7', fg: '#15803d' };
    if (s === 'active' || s === 'in progress' || s === 'committed') return { bg: '#dbeafe', fg: '#1d4ed8' };
    if (s === 'new' || s === 'proposed') return { bg: '#fef9c3', fg: '#854d0e' };
    if (s === 'removed' || s === 'cancelled') return { bg: '#fee2e2', fg: '#b91c1c' };
    return { bg: '#f1f5f9', fg: '#475569' };
  }
}
