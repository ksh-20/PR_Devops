import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DashboardService } from '../../../../services/dashboard.service';
import { ProjectsApiService } from '../../../../services/api/projects-api.service';
import { RepositoriesApiService } from '../../../../services/api/repositories-api.service';

import { FormsModule } from '@angular/forms';
import { CustomSelectComponent, SelectOption } from '../../../../components/custom-select/custom-select';

@Component({
  selector: 'app-repos',
  imports: [CommonModule, FormsModule, CustomSelectComponent],
  templateUrl: './repos.html',
  styleUrl: '../../home.css'
})
export class ReposComponent implements OnInit, OnDestroy {

  pollingSubscription: any;
  projects: any[] = [];
  repositories: any[] = [];
  reposError: string | null = null;
  isLoadingProjects = false;
  isLoadingRepos = false;

  currentPage = 1;
  projectsCurrentPage = 1;
  pageSize = 10;
  totalProjectsCount = 0;
  totalReposCount = 0;
  ownersList: string[] = [];
  ownerSearch = '';
  selectedOwner = 'All';
  projectsSearchTerm = '';
  get Math() { return Math; }

  get reposTotalPages(): number {
    return Math.ceil(this.totalReposCount / this.pageSize);
  }

  get projectsTotalPages(): number {
    return Math.ceil(this.totalProjectsCount / this.pageSize);
  }

  constructor(
    public dashboardService: DashboardService,
    private projectsApi: ProjectsApiService,
    private reposApi: RepositoriesApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadProjects();
    if (this.dashboardService.selectedProject) {
      this.loadProjectRepositories();
    }
    this.startSmartPolling();
  }

  ngOnDestroy() {
    if (this.pollingSubscription) {
      this.pollingSubscription.unsubscribe();
    }
  }

  startSmartPolling() {
    if (this.pollingSubscription) {
      this.pollingSubscription.unsubscribe();
    }
    import('rxjs').then(({ interval }) => {
      this.pollingSubscription = interval(5000).subscribe(() => {
        let stillLoading = false;
        if (this.isLoadingProjects) {
          this.loadProjects();
          stillLoading = true;
        }
        if (this.isLoadingRepos) {
          this.loadProjectRepositories();
          stillLoading = true;
        }
        if (!stillLoading && this.pollingSubscription) {
          this.pollingSubscription.unsubscribe();
          this.pollingSubscription = null;
        }
      });
    });
  }

  loadProjects() {
    this.isLoadingProjects = true;
    this.projectsApi.getProjects(this.projectsCurrentPage, this.pageSize, this.projectsSearchTerm).subscribe({
      next: (res: any) => {
        if (res && res.is_loading) {
          this.isLoadingProjects = true;
          this.cdr.detectChanges();
          return;
        }
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

  onProjectsSearchChange(value: string) {
    this.projectsSearchTerm = value;
    this.projectsCurrentPage = 1;
    this.loadProjects();
  }

  loadProjectRepositories() {
    if (!this.dashboardService.selectedProject) return;
    const projName = this.dashboardService.selectedProject.name;
    this.reposError = null;
    this.isLoadingRepos = true;
    this.reposApi.getRepositoriesByProject(projName, this.currentPage, this.pageSize, this.selectedOwner).subscribe({
      next: (res: any) => {
        if (res && res.is_loading) {
          this.isLoadingRepos = true;
          this.cdr.detectChanges();
          return;
        }
        if (res && res.success) {
          this.repositories = res.repositories || [];
          this.totalReposCount = res.total_count || 0;
          this.ownersList = res.owners || [];
          this.reposError = null;
        } else {
          this.repositories = [];
          this.totalReposCount = 0;
          this.reposError = res?.message || 'No repositories found on backend.';
        }
        this.isLoadingRepos = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Could not fetch repositories from backend', err);
        this.repositories = [];
        this.totalReposCount = 0;
        this.reposError = err.error?.detail || err.error?.message || err.message || 'Failed to load repositories.';
        this.isLoadingRepos = false;
        this.cdr.detectChanges();
      }
    });
  }

  get uniqueOwners(): string[] {
    return this.ownersList;
  }

  get filteredUniqueOwners(): string[] {
    if (!this.ownerSearch) return this.ownersList;
    const query = this.ownerSearch.toLowerCase();
    return this.ownersList.filter(o => o.toLowerCase().includes(query));
  }

  get ownerSelectOptions(): SelectOption[] {
    return [
      { label: 'All Owners', value: 'All' },
      ...this.ownersList.map(o => ({ label: o, value: o }))
    ];
  }

  onOwnerSelect(owner: string) {
    this.selectedOwner = owner || 'All';
    this.ownerSearch = owner || '';
    this.currentPage = 1;
    this.loadProjectRepositories();
  }

  onOwnerChange(event: Event) {
    const input = event.target as HTMLInputElement;
    this.onOwnerSelect(input.value);
  }

  selectProject(project: any) {
    this.selectedOwner = 'All';
    this.ownerSearch = '';
    this.currentPage = 1;
    this.dashboardService.selectedProject = project;
    this.loadProjectRepositories();
  }

  changeProject() {
    this.selectedOwner = 'All';
    this.ownerSearch = '';
    this.currentPage = 1;
    this.projectsCurrentPage = 1;
    this.dashboardService.selectedProject = null;
    this.repositories = [];
    this.totalReposCount = 0;
    this.reposError = null;
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
}
