import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';
import { FrontendCacheService } from '../frontend-cache.service';
import { API_BASE_URL } from '../../config';

@Injectable({
  providedIn: 'root'
})
export class RepositoriesApiService {
  private baseUrl = `${API_BASE_URL}/api`;

  constructor(
    private http: HttpClient,
    private cache: FrontendCacheService
  ) {}

  getAllRepositories(): Observable<any> {
    const cacheKey = 'repos:all';
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(`${this.baseUrl}/repos`).pipe(
      tap(data => {
        if (data && data.success && !data.is_loading) {
          this.cache.set(cacheKey, data);
        }
      })
    );
  }

  getRepositoriesByProject(projectName: string, page: number = 1, pageSize: number = 10, owner: string = 'All'): Observable<any> {
    const cacheKey = `repos:project:${projectName}:page:${page}:${pageSize}:owner:${owner}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    let url = `${this.baseUrl}/projects/${projectName}/repos?page=${page}&page_size=${pageSize}`;
    if (owner && owner !== 'All') {
      url += `&owner=${encodeURIComponent(owner)}`;
    }
    return this.http.get<any>(url).pipe(
      tap(data => {
        if (data && data.success && !data.is_loading) {
          this.cache.set(cacheKey, data);
        }
      })
    );
  }

  getFiles(projectName: string, repoName: string): Observable<any> {
    const cacheKey = `repos:files:${projectName}:${repoName}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(`${this.baseUrl}/projects/${projectName}/repos/${repoName}/files`).pipe(
      tap(data => this.cache.set(cacheKey, data))
    );
  }

  getCommits(projectName: string, repoName: string, page: number = 1, pageSize: number = 10): Observable<any> {
    const cacheKey = `repos:commits:${projectName}:${repoName}:page:${page}:${pageSize}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(`${this.baseUrl}/projects/${projectName}/repos/${repoName}/commits?page=${page}&page_size=${pageSize}`).pipe(
      tap(data => this.cache.set(cacheKey, data))
    );
  }

  getPushes(projectName: string, repoName: string, page: number = 1, pageSize: number = 10): Observable<any> {
    const cacheKey = `repos:pushes:${projectName}:${repoName}:page:${page}:${pageSize}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(`${this.baseUrl}/projects/${projectName}/repos/${repoName}/pushes?page=${page}&page_size=${pageSize}`).pipe(
      tap(data => this.cache.set(cacheKey, data))
    );
  }

  getBranches(projectName: string, repoName: string, page: number = 1, pageSize: number = 10): Observable<any> {
    const cacheKey = `repos:branches:${projectName}:${repoName}:page:${page}:${pageSize}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(`${this.baseUrl}/projects/${projectName}/repos/${repoName}/branches?page=${page}&page_size=${pageSize}`).pipe(
      tap(data => this.cache.set(cacheKey, data))
    );
  }

  getTags(projectName: string, repoName: string): Observable<any> {
    const cacheKey = `repos:tags:${projectName}:${repoName}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(`${this.baseUrl}/projects/${projectName}/repos/${repoName}/tags`).pipe(
      tap(data => this.cache.set(cacheKey, data))
    );
  }

  getPullRequests(projectName: string, repoName: string, page: number = 1, pageSize: number = 10): Observable<any> {
    const cacheKey = `repos:pullrequests:${projectName}:${repoName}:page:${page}:${pageSize}`;
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(`${this.baseUrl}/projects/${projectName}/repos/${repoName}/pullrequests?page=${page}&page_size=${pageSize}`).pipe(
      tap(data => this.cache.set(cacheKey, data))
    );
  }

  getActivePRsAll(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/pr/active-all`);
  }

  getLongPollEvents(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/ws/prs`);
  }

  getPRReview(repoId: string, prId: number, projectName: string): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/pr_review?repo_id=${repoId}&pr_id=${prId}&project=${encodeURIComponent(projectName)}`);
  }

  getPRDeltas(repoId: string, prId: number, projectName: string): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/pr_deltas?repo_id=${repoId}&pr_id=${prId}&project=${encodeURIComponent(projectName)}`);
  }

  postPRReview(repoId: string, prId: number, review: string, projectName: string): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/post_review`, {
      repo_id: repoId,
      pr_id: prId,
      review: review,
      project: projectName
    });
  }
}