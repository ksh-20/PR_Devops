import { Component } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule, NgForm } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AdminApiService } from '../../services/api/admin-api.service';
import { AdminAuthService } from '../../services/admin-auth.service';
import { DashboardService } from '../../services/dashboard.service';

@Component({
  selector: 'app-admin-login',
  standalone: true,
  imports: [FormsModule, CommonModule, RouterLink],
  templateUrl: './admin-login.html',
  styleUrl: './admin-login.css',
})
export class AdminLogin {
  errorMessage: string | null = null;
  isLoading = false;

  constructor(
    private router: Router,
    private adminApi: AdminApiService,
    private adminAuth: AdminAuthService,
    private dashboardService: DashboardService
  ) {}

  onSubmit(form: NgForm): void {
    const data = form.value;
    this.errorMessage = null;

    if (!data.username || !data.password) {
      this.errorMessage = 'Please enter username and password.';
      return;
    }

    this.isLoading = true;
    this.adminApi.login(data).subscribe({
      next: (res) => {
        this.isLoading = false;
        if (res?.access_token) {
          this.adminAuth.setAdminToken(res.access_token);
          this.dashboardService.setModule('Admin');
          this.dashboardService.selectedPage = 'admin';
          this.dashboardService.sidebarVisible = false;
          this.router.navigate(['/home']);
        } else {
          this.errorMessage = 'Login failed. No token received.';
        }


      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage =
          err.error?.detail ||
          err.error?.message ||
          err.message ||
          'Admin login failed. Please check your credentials.';
      }
    });
  }
}
