import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../../config';
import { AdminAuthService } from '../admin-auth.service';

@Injectable({
  providedIn: 'root'
})
export class AdminApiService {

  private baseUrl = `${API_BASE_URL}/api/admin`;
  private authUrl = `${API_BASE_URL}/auth/admin`;

  constructor(
    private http: HttpClient,
    private adminAuth: AdminAuthService
  ) {}

  private get headers(): HttpHeaders {
    return new HttpHeaders({
      'Authorization': this.adminAuth.getAuthHeader(),
      'Content-Type': 'application/json'
    });
  }

  // ── Auth ─────────────────────────────────────────────────────────────────

  login(credentials: { username: string; password: string }): Observable<any> {
    return this.http.post<any>(`${this.authUrl}/login`, credentials);
  }

  // ── Project Members ───────────────────────────────────────────────────────

  getProjectMembers(params?: { project_id?: number; page?: number; page_size?: number }): Observable<any> {
    let url = `${this.baseUrl}/project-members`;
    const query: string[] = [];
    if (params?.project_id) query.push(`project_id=${params.project_id}`);
    if (params?.page) query.push(`page=${params.page}`);
    if (params?.page_size) query.push(`page_size=${params.page_size}`);
    if (query.length) url += '?' + query.join('&');
    return this.http.get<any>(url, { headers: this.headers });
  }

  createProjectMember(data: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/project-members`, data, { headers: this.headers });
  }

  updateProjectMember(id: number, data: any): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}/project-members/${id}`, data, { headers: this.headers });
  }

  deleteProjectMember(id: number): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}/project-members/${id}`, { headers: this.headers });
  }
}
