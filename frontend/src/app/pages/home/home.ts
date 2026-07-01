import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DashboardService } from '../../services/dashboard.service';

// Sub-components imports
import { DashboardHomeComponent } from './components/dashboard-home/dashboard-home';
import { ProjectsComponent } from './components/projects/projects';
import { ProjectDetailComponent } from './components/project-detail/project-detail';
import { ReposComponent } from './components/repos/repos';
import { PipelinesComponent } from './components/pipelines/pipelines';
import { BoardsComponent } from './components/boards/boards';
import { TestplansComponent } from './components/testplans/testplans';
import { AzureComponent } from './components/azure/azure';
import { ReviewerComponent } from '../../components/reviewer/reviewer';
import { AdminPortal } from '../admin/admin';
import { AdminAuthService } from '../../services/admin-auth.service';

@Component({
  selector: 'app-home',
  imports: [
    CommonModule,
    DashboardHomeComponent,
    ProjectsComponent,
    ProjectDetailComponent,
    ReposComponent,
    PipelinesComponent,
    BoardsComponent,
    TestplansComponent,
    AzureComponent,
    ReviewerComponent,
    AdminPortal
  ],
  templateUrl: './home.html',
  styleUrl: './home.css'
})
export class Home {

  constructor(
    public dashboardService: DashboardService,
    public adminAuth: AdminAuthService
  ) {}
}