import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';
import { FrontendCacheService } from '../frontend-cache.service';
import { API_BASE_URL } from '../../config';

@Injectable({
  providedIn: 'root'
})
export class ProjectsApiService {
  private baseUrl = `${API_BASE_URL}/api/projects`;

  constructor(
    private http: HttpClient,
    private cache: FrontendCacheService
  ) {}

  getProjects(page: number = 1, pageSize: number = 10, search: string = ''): Observable<any> {
    const cacheKey = `projects:all:page:${page}:${pageSize}:search:${search}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    let url = `${this.baseUrl}?page=${page}&page_size=${pageSize}`;
    if (search) {
      url += `&search=${encodeURIComponent(search)}`;
    }
    return this.http.get<any>(url).pipe(
      tap(data => {
        if (data && data.success && !data.is_loading) {
          this.cache.set(cacheKey, data);
        }
      })
    );
  }
}