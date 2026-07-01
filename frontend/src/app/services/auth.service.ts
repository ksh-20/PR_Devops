import { Injectable } from '@angular/core';
import { AuthApiService } from './api/auth-api.service';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';
import { FrontendCacheService } from './frontend-cache.service';
import { DashboardService } from './dashboard.service';

@Injectable({
  providedIn: 'root'
})
export class AuthService {

  get isLoggedIn(): boolean {
    return localStorage.getItem('is_logged_in') === 'true' || localStorage.getItem('is_admin_logged_in') === 'true';
  }

  constructor(
    private authApi: AuthApiService,
    private cache: FrontendCacheService,
    private dashboardService: DashboardService
  ) {}


  login(credentials: any): Observable<any> {
    this.cache.clear();
    localStorage.removeItem('admin_token');
    localStorage.setItem('is_admin_logged_in', 'false');
    
    // Reset dashboard service active module and page to standard member defaults
    this.dashboardService.setModule('DevOps');
    this.dashboardService.selectedPage = 'home';
    
    return this.authApi.login(credentials).pipe(
      tap(res => {
        if (res && res.access_token) {
          localStorage.setItem('access_token', res.access_token);
        }
        localStorage.setItem('is_logged_in', 'true');
      })
    );
  }


  logout() {
    localStorage.removeItem('access_token');
    localStorage.setItem('is_logged_in', 'false');
    localStorage.removeItem('admin_token');
    localStorage.setItem('is_admin_logged_in', 'false');
    
    // Reset dashboard service active module and page to standard member defaults
    this.dashboardService.setModule('DevOps');
    this.dashboardService.selectedPage = 'home';
    
    this.cache.clear();
  }

}