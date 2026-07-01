import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminApiService } from '../../../../services/api/admin-api.service';

@Component({
  selector: 'app-admin-members',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-members.html',
  styleUrl: '../admin-crud.css',
})
export class AdminMembersComponent implements OnInit {

  items: any[] = [];
  totalCount = 0;
  loading = false;
  error: string | null = null;

  filterProjectId: number | null = null;
  page = 1;
  pageSize = 15;

  showModal = false;
  saving = false;
  modalError: string | null = null;
  isEditing = false;
  editingId: number | null = null;

  form: any = {};

  deleteId: number | null = null;
  deleting = false;

  constructor(private adminApi: AdminApiService) {}

  ngOnInit(): void { this.loadData(); }

  loadData(): void {
    this.loading = true;
    this.error = null;
    this.adminApi.getProjectMembers({
      project_id: this.filterProjectId ?? undefined,
      page: this.page,
      page_size: this.pageSize
    }).subscribe({
      next: (res) => {
        this.loading = false;
        if (res.success) { this.items = res.items || []; this.totalCount = res.total_count || 0; }
        else this.error = res.message || 'Failed to load members.';
      },
      error: (err) => { this.loading = false; this.error = err.error?.detail || err.message || 'Failed.'; }
    });
  }

  openCreate(): void {
    this.isEditing = false;
    this.editingId = null;
    this.form = { project_id: null, display_name: '', unique_name: '', azure_user_id: '', role: '' };
    this.showModal = true; this.modalError = null;
  }

  openEdit(item: any): void {
    this.isEditing = true;
    this.editingId = item.id;
    this.form = { ...item };
    this.showModal = true; this.modalError = null;
  }

  closeModal(): void { this.showModal = false; this.form = {}; }

  save(): void {
    if (!this.form.project_id) { this.modalError = 'Project ID is required.'; return; }
    if (!this.form.display_name?.trim()) { this.modalError = 'Display name is required.'; return; }
    this.saving = true; this.modalError = null;

    if (this.isEditing && this.editingId !== null) {
      this.adminApi.updateProjectMember(this.editingId, this.form).subscribe({
        next: (res) => { this.saving = false; if (res.success !== false) { this.closeModal(); this.loadData(); } else this.modalError = res.message || 'Failed.'; },
        error: (err) => { this.saving = false; this.modalError = err.error?.detail || err.message || 'Failed.'; }
      });
    } else {
      this.adminApi.createProjectMember(this.form).subscribe({
        next: (res) => { this.saving = false; if (res.success !== false) { this.closeModal(); this.loadData(); } else this.modalError = res.message || 'Failed.'; },
        error: (err) => { this.saving = false; this.modalError = err.error?.detail || err.message || 'Failed.'; }
      });
    }
  }

  confirmDelete(id: number): void { this.deleteId = id; }
  cancelDelete(): void { this.deleteId = null; }

  doDelete(): void {
    if (!this.deleteId) return;
    this.deleting = true;
    this.adminApi.deleteProjectMember(this.deleteId).subscribe({
      next: () => { this.deleting = false; this.deleteId = null; this.loadData(); },
      error: (err) => { this.deleting = false; this.error = err.error?.detail || err.message || 'Delete failed.'; this.deleteId = null; }
    });
  }

  get totalPages(): number { return Math.max(1, Math.ceil(this.totalCount / this.pageSize)); }
  prevPage(): void { if (this.page > 1) { this.page--; this.loadData(); } }
  nextPage(): void { if (this.page < this.totalPages) { this.page++; this.loadData(); } }
}
