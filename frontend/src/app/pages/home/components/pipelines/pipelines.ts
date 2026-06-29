import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DashboardService } from '../../../../services/dashboard.service';
import { ProjectsApiService } from '../../../../services/api/projects-api.service';
import { PipelinesApiService } from '../../../../services/api/pipelines-api.service';

@Component({
  selector: 'app-pipelines',
  imports: [CommonModule, FormsModule],
  templateUrl: './pipelines.html',
  styleUrl: '../../home.css'
})
export class PipelinesComponent implements OnInit {

  projects: any[] = [];
  pipelines: any[] = [];
  isLoadingPipelines = false;
  isLoadingProjects = false;
  pipelinesError: string | null = null;
  pipelineSearch = '';

  currentPage = 1;
  projectsCurrentPage = 1;
  pageSize = 10;
  totalProjectsCount = 0;
  totalPipelinesCount = 0;
  get Math() { return Math; }

  get pipelinesTotalPages(): number {
    return Math.ceil(this.totalPipelinesCount / this.pageSize);
  }

  get projectsTotalPages(): number {
    return Math.ceil(this.totalProjectsCount / this.pageSize);
  }

  constructor(
    public dashboardService: DashboardService,
    private projectsApi: ProjectsApiService,
    private pipelinesApi: PipelinesApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadProjects();
    if (this.dashboardService.selectedProject) {
      this.loadPipelines(this.dashboardService.selectedProject.name);
    }
  }

  loadProjects() {
    this.isLoadingProjects = true;
    this.projectsApi.getProjects(this.projectsCurrentPage, this.pageSize).subscribe({
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

  loadPipelines(projName: string) {
    this.isLoadingPipelines = true;
    this.pipelinesError = null;
    this.pipelinesApi.getPipelines(projName, this.currentPage, this.pageSize, this.pipelineSearch).subscribe({
      next: (res: any) => {
        if (res && res.success) {
          this.pipelines = res.pipelines || [];
          this.totalPipelinesCount = res.total_count || 0;
        } else {
          this.pipelines = [];
          this.totalPipelinesCount = 0;
          this.pipelinesError = res?.message || 'Failed to load pipelines from backend.';
        }
        this.isLoadingPipelines = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn(`Could not load pipelines for project ${projName}`, err);
        this.pipelines = [];
        this.totalPipelinesCount = 0;
        this.pipelinesError = err.error?.detail || err.error?.message || err.message || `Failed to load pipelines for project ${projName}.`;
        this.isLoadingPipelines = false;
        this.cdr.detectChanges();
      }
    });
  }

  selectProject(project: any) {
    this.currentPage = 1;
    this.projectsCurrentPage = 1;
    this.dashboardService.selectedProject = project;
    this.loadPipelines(project.name);
  }

  changeProject() {
    this.currentPage = 1;
    this.projectsCurrentPage = 1;
    this.dashboardService.selectedProject = null;
    this.pipelines = [];
    this.totalPipelinesCount = 0;
    this.pipelinesError = null;
    this.pipelineSearch = '';
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
