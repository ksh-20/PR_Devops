import { Component } from '@angular/core';
import { DashboardService } from '../../services/dashboard.service';

@Component({
  selector: 'app-sidebar',
  imports: [],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css'
})
export class Sidebar {

  showProjects = false;

  constructor(
    public dashboardService: DashboardService
  ) {}

  toggleProjects() {

    this.showProjects = !this.showProjects;

  }

}