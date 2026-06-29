import { Component, OnInit, ChangeDetectorRef, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DashboardService } from '../../../../services/dashboard.service';
import { RepositoriesApiService } from '../../../../services/api/repositories-api.service';

@Component({
  selector: 'app-project-detail',
  imports: [CommonModule],
  templateUrl: './project-detail.html',
  styleUrl: '../../home.css'
})
export class ProjectDetailComponent implements OnInit {

  selectedProjectRepos: any[] = [];
  selectedRepoForDetails: any = null;
  activeRepoDetailsTab = '';
  repoCommits: any[] = [];
  repoPRs: any[] = [];
  repoBranches: any[] = [];
  repoBranchesCount: number | null = null;
  repoPushes: any[] = [];
  
  isLoadingRepoDetails = false;
  isLoadingRepos = false;
  reposError: string | null = null;
  repoDetailsError: string | null = null;

  pageSize = 10;
  get Math() { return Math; }

  reposCurrentPage = 1;
  commitsCurrentPage = 1;
  prsCurrentPage = 1;
  branchesCurrentPage = 1;
  pushesCurrentPage = 1;

  totalReposCount = 0;
  totalCommitsCount = 0;
  totalPRsCount = 0;
  totalBranchesCount = 0;
  totalPushesCount = 0;

  get reposTotalPages(): number {
    return Math.ceil(this.totalReposCount / this.pageSize);
  }

  get commitsTotalPages(): number {
    return Math.ceil(this.totalCommitsCount / this.pageSize);
  }

  get prsTotalPages(): number {
    return Math.ceil(this.totalPRsCount / this.pageSize);
  }

  get branchesTotalPages(): number {
    return Math.ceil(this.totalBranchesCount / this.pageSize);
  }

  get pushesTotalPages(): number {
    return Math.ceil(this.totalPushesCount / this.pageSize);
  }

  @ViewChild('repoDetailsAnchor') repoDetailsAnchor!: ElementRef;

  constructor(
    public dashboardService: DashboardService,
    private reposApi: RepositoriesApiService,
    private cdr: ChangeDetectorRef
  ) {}

  get selectedProject() {
    return this.dashboardService.selectedProject;
  }

  ngOnInit() {
    if (this.selectedProject) {
      this.loadProjectRepos(this.selectedProject.name);
    }
  }

  loadProjectRepos(projectName: string) {
    this.reposError = null;
    this.isLoadingRepos = true;
    this.reposApi.getRepositoriesByProject(projectName, this.reposCurrentPage, this.pageSize).subscribe({
      next: (res: any) => {
        if (res && res.success && res.repositories) {
          this.selectedProjectRepos = res.repositories;
          this.totalReposCount = res.total_count || 0;
        } else if (res && res.repositories) {
          this.selectedProjectRepos = res.repositories;
          this.totalReposCount = res.total_count || res.repositories.length;
        } else {
          this.selectedProjectRepos = [];
          this.totalReposCount = 0;
          this.reposError = 'No repositories found in this project.';
        }
        this.isLoadingRepos = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.warn('Failed to load project repositories', err);
        this.selectedProjectRepos = [];
        this.totalReposCount = 0;
        this.reposError = err.error?.detail || err.error?.message || err.message || 'Failed to load repositories.';
        this.isLoadingRepos = false;
        this.cdr.detectChanges();
      }
    });
  }

  goBackToProjects() {
    this.dashboardService.selectedProject = null;
    this.dashboardService.selectedRepoForDetails = null;
    this.dashboardService.selectedPage = 'projects';
  }

  navigateBack() {
    this.dashboardService.isNavigatingHistory = true;
    const res = this.dashboardService.getPreviousProject();
    if (res.found) {
      if (res.project) {
        this.dashboardService.selectedProject = res.project;
        this.dashboardService.selectedPage = 'project-detail';
        this.loadProjectRepos(res.project.name);
      } else {
        this.goBackToProjects();
      }
    }
    this.dashboardService.isNavigatingHistory = false;
  }

  navigateForward() {
    this.dashboardService.isNavigatingHistory = true;
    const res = this.dashboardService.getNextProject();
    if (res.found) {
      if (res.project) {
        this.dashboardService.selectedProject = res.project;
        this.dashboardService.selectedPage = 'project-detail';
        this.loadProjectRepos(res.project.name);
      } else {
        this.goBackToProjects();
      }
    }
    this.dashboardService.isNavigatingHistory = false;
  }

  viewRepoCommits(repo: any) {
    this.selectedRepoForDetails = repo;
    this.activeRepoDetailsTab = 'commits';
    this.isLoadingRepoDetails = true;
    this.repoDetailsError = null;
    this.reposApi.getCommits(this.selectedProject.name, repo.name, this.commitsCurrentPage, this.pageSize).subscribe({
      next: (res: any) => {
        if (res && res.success && res.commits) {
          this.repoCommits = res.commits;
          this.totalCommitsCount = res.total_count || 0;
        } else {
          this.repoCommits = [];
          this.totalCommitsCount = 0;
          this.repoDetailsError = 'No commits found or failed to parse response.';
        }
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      },
      error: (err) => {
        console.warn('Failed to load commits', err);
        this.repoCommits = [];
        this.totalCommitsCount = 0;
        this.repoDetailsError = err.error?.detail || err.error?.message || err.message || 'Failed to fetch commits.';
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      }
    });
  }

  viewRepoPRs(repo: any) {
    this.selectedRepoForDetails = repo;
    this.activeRepoDetailsTab = 'prs';
    this.isLoadingRepoDetails = true;
    this.repoDetailsError = null;
    this.reposApi.getPullRequests(this.selectedProject.name, repo.name, this.prsCurrentPage, this.pageSize).subscribe({
      next: (res: any) => {
        if (res && res.success && res.pullRequests) {
          this.repoPRs = res.pullRequests;
          this.totalPRsCount = res.total_count || 0;
        } else {
          this.repoPRs = [];
          this.totalPRsCount = 0;
          this.repoDetailsError = 'No pull requests found or failed to parse response.';
        }
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      },
      error: (err) => {
        console.warn('Failed to load pull requests', err);
        this.repoPRs = [];
        this.totalPRsCount = 0;
        this.repoDetailsError = err.error?.detail || err.error?.message || err.message || 'Failed to fetch pull requests.';
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      }
    });
  }

  viewRepoBranches(repo: any) {
    this.selectedRepoForDetails = repo;
    this.activeRepoDetailsTab = 'branches';
    this.isLoadingRepoDetails = true;
    this.repoDetailsError = null;
    this.reposApi.getBranches(this.selectedProject.name, repo.name, this.branchesCurrentPage, this.pageSize).subscribe({
      next: (res: any) => {
        if (res && res.success && res.branches) {
          this.repoBranches = res.branches;
          this.totalBranchesCount = res.total_count || res.branches.length;
          this.repoBranchesCount = res.total_count ?? res.branches.length;
        } else {
          this.repoBranches = [];
          this.totalBranchesCount = 0;
          this.repoBranchesCount = null;
          this.repoDetailsError = 'No branches found or failed to parse response.';
        }
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      },
      error: (err) => {
        console.warn('Failed to load branches', err);
        this.repoBranches = [];
        this.totalBranchesCount = 0;
        this.repoDetailsError = err.error?.detail || err.error?.message || err.message || 'Failed to fetch branches.';
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      }
    });
  }

  viewRepoPushes(repo: any) {
    this.selectedRepoForDetails = repo;
    this.activeRepoDetailsTab = 'pushes';
    this.isLoadingRepoDetails = true;
    this.repoDetailsError = null;
    this.reposApi.getPushes(this.selectedProject.name, repo.name, this.pushesCurrentPage, this.pageSize).subscribe({
      next: (res: any) => {
        if (res && res.success && res.pushes) {
          this.repoPushes = res.pushes;
          this.totalPushesCount = res.total_count || 0;
        } else {
          this.repoPushes = [];
          this.totalPushesCount = 0;
          this.repoDetailsError = 'No pushes found or failed to parse response.';
        }
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      },
      error: (err) => {
        console.warn('Failed to load pushes', err);
        this.repoPushes = [];
        this.totalPushesCount = 0;
        this.repoDetailsError = err.error?.detail || err.error?.message || err.message || 'Failed to fetch pushes.';
        this.isLoadingRepoDetails = false;
        this.cdr.detectChanges();
        this.scrollToRepoDetails();
      }
    });
  }

  changeReposPage(dir: number) {
    this.reposCurrentPage += dir;
    this.loadProjectRepos(this.selectedProject.name);
  }

  changeCommitsPage(dir: number) {
    this.commitsCurrentPage += dir;
    this.viewRepoCommits(this.selectedRepoForDetails);
  }

  changePRsPage(dir: number) {
    this.prsCurrentPage += dir;
    this.viewRepoPRs(this.selectedRepoForDetails);
  }

  changeBranchesPage(dir: number) {
    this.branchesCurrentPage += dir;
    this.viewRepoBranches(this.selectedRepoForDetails);
  }

  changePushesPage(dir: number) {
    this.pushesCurrentPage += dir;
    this.viewRepoPushes(this.selectedRepoForDetails);
  }

  private scrollToRepoDetails() {
    setTimeout(() => {
      this.repoDetailsAnchor?.nativeElement?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }
}
