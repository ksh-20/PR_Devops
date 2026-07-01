import { Injectable } from '@angular/core';
import { DashboardService } from './dashboard.service';

const ADMIN_TOKEN_KEY = 'admin_token';
const ADMIN_LOGGED_IN_KEY = 'is_admin_logged_in';

@Injectable({
  providedIn: 'root'
})
export class AdminAuthService {

  isAdminLoggedIn = false;

  constructor(
    private dashboardService: DashboardService
  ) {
    this.isAdminLoggedIn = localStorage.getItem(ADMIN_LOGGED_IN_KEY) === 'true';
  }

  setAdminToken(token: string): void {
    localStorage.removeItem('access_token');
    localStorage.setItem('is_logged_in', 'false');

    localStorage.setItem(ADMIN_TOKEN_KEY, token);
    localStorage.setItem(ADMIN_LOGGED_IN_KEY, 'true');
    this.isAdminLoggedIn = true;
  }


  getAdminToken(): string | null {
    return localStorage.getItem(ADMIN_TOKEN_KEY);
  }

  adminLogout(): void {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.setItem(ADMIN_LOGGED_IN_KEY, 'false');
    this.isAdminLoggedIn = false;

    // Reset dashboard service module and page to standard member defaults
    this.dashboardService.setModule('DevOps');
    this.dashboardService.selectedPage = 'home';
  }

  getAuthHeader(): string {
    const token = this.getAdminToken();
    return token ? `Bearer ${token}` : '';
  }
}

