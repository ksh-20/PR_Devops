import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DashboardService } from '../../../../services/dashboard.service';
import { ProjectsApiService } from '../../../../services/api/projects-api.service';

@Component({
  selector: 'app-projects',
  imports: [CommonModule],
  templateUrl: './projects.html',
  styleUrl: '../../home.css'
})
export class ProjectsComponent implements OnInit {

  projects: any[] = [];
  isLoadingProjects = false;
  projectsError: string | null = null;

  searchTerm = '';
  currentPage = 1;
  pageSize = 10;
  totalProjectsCount = 0;
  get Math() { return Math; }

  get totalPages(): number {
    return Math.ceil(this.totalProjectsCount / this.pageSize);
  }

  constructor(
    public dashboardService: DashboardService,
    private projectsApi: ProjectsApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadProjects();
  }

  loadProjects() {
    this.isLoadingProjects = true;
    this.projectsError = null;
    this.projectsApi.getProjects(this.currentPage, this.pageSize, this.searchTerm).subscribe({
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
        console.warn('Could not fetch projects from backend', err);
        this.projects = [];
        this.totalProjectsCount = 0;
        this.projectsError = err.error?.detail || err.error?.message || err.message || 'Failed to load projects from backend.';
        this.isLoadingProjects = false;
        this.cdr.detectChanges();
      }
    });
  }

  onSearchChange(value: string) {
    this.searchTerm = value;
    this.currentPage = 1;
    this.loadProjects();
  }

  openProject(project: any) {
    this.dashboardService.selectedProject = project;
    this.dashboardService.selectedRepoForDetails = null;
    this.dashboardService.selectedPage = 'project-detail';
  }
}
