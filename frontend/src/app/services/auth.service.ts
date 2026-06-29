import { Injectable } from '@angular/core';
import { AuthApiService } from './api/auth-api.service';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';
import { FrontendCacheService } from './frontend-cache.service';

@Injectable({
  providedIn: 'root'
})
export class AuthService {

  isLoggedIn = false;

  constructor(
    private authApi: AuthApiService,
    private cache: FrontendCacheService
  ) {
    this.isLoggedIn = localStorage.getItem('is_logged_in') === 'true';
  }

  login(credentials: any): Observable<any> {
    this.cache.clear();
    return this.authApi.login(credentials).pipe(
      tap(res => {
        if (res && res.access_token) {
          localStorage.setItem('access_token', res.access_token);
        }
        localStorage.setItem('is_logged_in', 'true');
        this.isLoggedIn = true;
      })
    );
  }

  logout() {
    localStorage.removeItem('access_token');
    localStorage.setItem('is_logged_in', 'false');
    this.isLoggedIn = false;
    this.cache.clear();
  }

}