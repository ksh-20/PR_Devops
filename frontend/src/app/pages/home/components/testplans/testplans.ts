import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DashboardService } from '../../../../services/dashboard.service';
import { ProjectsApiService } from '../../../../services/api/projects-api.service';
import { TestPlansApiService } from '../../../../services/api/testplans-api.service';

@Component({
  selector: 'app-testplans',
  imports: [CommonModule, FormsModule],
  templateUrl: './testplans.html',
  styleUrl: '../../home.css'
})
export class TestplansComponent implements OnInit {

  projects: any[] = [];
  testPlans: any[] = [];
  isLoadingTestPlans = false;
  isLoadingProjects = false;
  testPlansError: string | null = null;
  testPlanSearch = '';

  projectsSearchTerm = '';

  currentPage = 1;
  projectsCurrentPage = 1;
  pageSize = 10;
  totalProjectsCount = 0;
  totalTestPlansCount = 0;
  get Math() { return Math; }

  get testPlansTotalPages(): number {
    return Math.ceil(this.totalTestPlansCount / this.pageSize);
  }

  get projectsTotalPages(): number {
    return Math.ceil(this.totalProjectsCount / this.pageSize);
  }

  constructor(
    public dashboardService: DashboardService,
    private projectsApi: ProjectsApiService,
    private testPlansApi: TestPlansApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadProjects();
    if (this.dashboardService.selectedProject) {
      this.loadTestPlans(this.dashboardService.selectedProject.name);
    }
  }

  onProjectsSearchChange(value: string) {
    this.projectsSearchTerm = value;
    this.projectsCurrentPage = 1;
    this.loadProjects();
  }

  loadProjects() {
    this.isLoadingProjects = true;
    this.projectsApi.getProjects(this.projectsCurrentPage, this.pageSize, this.projectsSearchTerm).subscribe({
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

  loadTestPlans(projName: string) {
    this.isLoadingTestPlans = true;
    this.testPlansError = null;
    this.testPlansApi.getTestPlans(projName, this.currentPage, this.pageSize, this.testPlanSearch).subscribe({
      next: (res: any) => {
        if (res && res.success) {
          this.testPlans = res.test_plans || [];
          this.totalTestPlansCount = res.total_count || 0;
        } else {
          this.testPlans = [];
          this.totalTestPlansCount = 0;
          this.testPlansError = res?.message || 'Failed to load test plans from backend.';
        }
        this.isLoadingTestPlans = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn(`Could not load test plans for project ${projName}`, err);
        this.testPlans = [];
        this.totalTestPlansCount = 0;
        this.testPlansError = err.error?.detail || err.error?.message || err.message || `Failed to load test plans for project ${projName}.`;
        this.isLoadingTestPlans = false;
        this.cdr.detectChanges();
      }
    });
  }

  selectProject(project: any) {
    this.currentPage = 1;
    this.projectsCurrentPage = 1;
    this.dashboardService.selectedProject = project;
    this.loadTestPlans(project.name);
  }

  changeProject() {
    this.currentPage = 1;
    this.projectsCurrentPage = 1;
    this.dashboardService.selectedProject = null;
    this.testPlans = [];
    this.totalTestPlansCount = 0;
    this.testPlansError = null;
    this.testPlanSearch = '';
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
