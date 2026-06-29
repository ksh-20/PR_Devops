import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';
import { FrontendCacheService } from './frontend-cache.service';
import { API_BASE_URL } from '../config';

@Injectable({
  providedIn: 'root'
})
export class PipelineService {

  private apiUrl = `${API_BASE_URL}/pipelines`;

  constructor(
    private http: HttpClient,
    private cache: FrontendCacheService
  ) {}

  getPipelines(): Observable<any> {
    const cacheKey = 'pipeline:all';
    const cachedData = this.cache.get(cacheKey);
    if (cachedData) {
      return of(cachedData);
    }
    return this.http.get<any>(this.apiUrl).pipe(
      tap(data => this.cache.set(cacheKey, data))
    );
  }
}