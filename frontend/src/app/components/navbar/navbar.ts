import { Component } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { DashboardService } from '../../services/dashboard.service';
import { AdminAuthService } from '../../services/admin-auth.service';

@Component({
  selector: 'app-navbar',
  imports: [RouterLink],
  templateUrl: './navbar.html',
  styleUrl: './navbar.css',
})
export class Navbar {

  showLogout = false;

  showCloudOps = false;

  constructor(
    public authService: AuthService,
    private router: Router,
    public dashboardService: DashboardService,
    public adminAuthService: AdminAuthService
  ) {}

  isAdminActive(): boolean {
    return this.router.url.startsWith('/home') &&
           this.dashboardService.selectedModule === 'Admin' &&
           this.dashboardService.selectedPage === 'admin';
  }



  isDevOpsActive(): boolean {
    return this.router.url.startsWith('/home') &&
           this.dashboardService.selectedModule === 'DevOps' &&
           this.dashboardService.selectedPage !== 'home';
  }

  isAzureActive(): boolean {
    return this.router.url.startsWith('/home') &&
           this.dashboardService.selectedModule === 'Azure' &&
           this.dashboardService.selectedPage !== 'home';
  }

  isReviewerActive(): boolean {
    return this.router.url.startsWith('/home') &&
           this.dashboardService.selectedModule === 'Reviewer' &&
           this.dashboardService.selectedPage !== 'home';
  }

  isHomeActive(): boolean {
    return this.router.url.startsWith('/home') &&
           this.dashboardService.selectedPage === 'home';
  }

  isAboutActive(): boolean {
    return this.router.url.startsWith('/about');
  }

  toggleLogout() {

    this.showLogout = !this.showLogout;

  }

  toggleCloudOps() {

    this.showCloudOps = !this.showCloudOps;

  }

  selectDevOps() {

    this.dashboardService.setModule('DevOps');

    this.dashboardService.selectedPage = 'projects';

    this.dashboardService.sidebarVisible = true;

    this.showCloudOps = false;

    this.router.navigate(['/home']);

  }

  selectAzure() {

    this.dashboardService.setModule('Azure');

    this.dashboardService.selectedPage = 'azure';

    this.dashboardService.sidebarVisible = true;

    this.showCloudOps = false;

    this.router.navigate(['/home']);

  }

  selectReviewer() {

    this.dashboardService.setModule('Reviewer');

    this.dashboardService.selectedPage = 'reviewer';

    this.dashboardService.sidebarVisible = false;

    this.showCloudOps = false;

    this.router.navigate(['/home']);

  }

  selectAdmin() {

    this.dashboardService.setModule('Admin');

    this.dashboardService.selectedPage = 'admin';

    this.dashboardService.sidebarVisible = false;

    this.showCloudOps = false;

    this.router.navigate(['/home']);

  }

  logout() {

    this.authService.logout();

    this.router.navigate(['/login']);

  }

}