import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RepositoriesApiService } from '../../services/api/repositories-api.service';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { API_BASE_URL } from '../../config';

@Component({
  selector: 'app-reviewer',
  imports: [CommonModule],
  templateUrl: './reviewer.html',
  styleUrl: './reviewer.css'
})
export class ReviewerComponent implements OnInit {

  // ── Active PR list ───────────────────────────────────────────────────
  activePRs: any[] = [];
  isLoadingPRs = false;
  prsError: string | null = null;

  // ── Selected PR ──────────────────────────────────────────────────────
  selectedPR: any = null;

  // ── Review state ─────────────────────────────────────────────────────
  isLoadingReview = false;
  reviewTriggered = false;
  diffFiles: any[] = [];
  aiReviewContent = '';
  reviewError: string | null = null;
  diffError: string | null = null;
  private eventSource: EventSource | null = null;

  // ── Derived getters ──────────────────────────────────────────────────
  get sourceTarget(): string {
    if (!this.selectedPR) return '';
    const srcRaw = this.selectedPR.sourceBranch || this.selectedPR.sourceRefName || '';
    const tgtRaw = this.selectedPR.targetBranch || this.selectedPR.targetRefName || '';
    const src = srcRaw.replace('refs/heads/', '');
    const tgt = tgtRaw.replace('refs/heads/', '');
    return src && tgt ? `${src} → ${tgt}` : '';
  }

  get lastUpdated(): string {
    if (!this.selectedPR) return '';
    const raw = this.selectedPR.closedDate
      ?? this.selectedPR.completionQueueTime
      ?? this.selectedPR.creationDate
      ?? '';
    if (!raw) return '';
    const d = new Date(raw);
    return isNaN(d.getTime()) ? '' : d.toLocaleString('en-GB', { hour12: false });
  }

  get prCreatedAt(): string {
    if (!this.selectedPR?.creationDate) return '';
    const d = new Date(this.selectedPR.creationDate);
    return isNaN(d.getTime()) ? '' : d.toLocaleString('en-GB', { hour12: false });
  }

  prAge(pr: any): string {
    if (!pr?.creationDate) return '';
    const diffMs = Date.now() - new Date(pr.creationDate).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  prAuthor(pr: any): string {
    return pr?.createdBy?.displayName || pr?.createdBy?.uniqueName || 'Unknown';
  }

  constructor(
    private reposApi: RepositoriesApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadActivePRs();
    this.connectSSE();
  }

  connectSSE(): void {
    const sseUrl = API_BASE_URL + '/api/ws/prs';
    this.eventSource = new EventSource(sseUrl);

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'pr_updated' && data.pr) {
          const pr = data.pr;
          const isClosed = pr.status === 'completed' || pr.status === 'abandoned' || pr.status === 'closed';
          if (isClosed) {
            this.activePRs = this.activePRs.filter(
              item => !(String(item.pullRequestId ?? item.id) === String(pr.pullRequestId ?? pr.id) && item.repo_id === pr.repo_id)
            );
          } else {
            const index = this.activePRs.findIndex(
              item => String(item.pullRequestId ?? item.id) === String(pr.pullRequestId ?? pr.id) && item.repo_id === pr.repo_id
            );
            if (index > -1) {
              this.activePRs[index] = { ...this.activePRs[index], ...pr };
            } else {
              this.activePRs = [pr, ...this.activePRs];
            }
          }
          this.cdr.detectChanges();
        }
      } catch (err) {}
    };
  }


  loadActivePRs(): void {
    this.isLoadingPRs = true;
    this.prsError = null;

    this.reposApi.getActivePRsAll().subscribe({
      next: (res: any) => {
        this.activePRs = res?.pull_requests ?? [];
        this.isLoadingPRs = false;
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        this.prsError = err?.error?.message ?? 'Failed to load active pull requests.';
        this.isLoadingPRs = false;
        this.cdr.detectChanges();
      }
    });
  }


  // ── Select a PR card → auto-load review ─────────────────────────────
  selectPR(pr: any): void {
    if (this.selectedPR?.pullRequestId === pr.pullRequestId && this.selectedPR?.repo_id === pr.repo_id) return;
    this.selectedPR = pr;
    this.reviewTriggered = false;
    this.diffFiles = [];
    this.aiReviewContent = '';
    this.reviewError = null;
    this.diffError = null;
    this.cdr.detectChanges();
    this.loadReview();
  }

  isSelected(pr: any): boolean {
    return this.selectedPR
      && String(this.selectedPR.pullRequestId ?? this.selectedPR.id) === String(pr.pullRequestId ?? pr.id)
      && this.selectedPR.repo_id === pr.repo_id;
  }

  // ── Load diff + AI review ────────────────────────────────────────────
  loadReview(): void {
    if (!this.selectedPR) return;

    const repoId      = this.selectedPR.repo_id;
    const prId        = this.selectedPR.pullRequestId ?? this.selectedPR.id;
    const projectName = this.selectedPR.project_name;

    this.isLoadingReview = true;
    this.reviewTriggered = false;
    this.diffFiles = [];
    this.aiReviewContent = '';
    this.reviewError = null;
    this.diffError = null;
    this.cdr.detectChanges();

    forkJoin({
      deltas: this.reposApi.getPRDeltas(repoId, prId, projectName)
        .pipe(catchError(() => of({ success: false, message: 'Failed to fetch diffs.' }))),
      review: this.reposApi.getPRReview(repoId, prId, projectName)
        .pipe(catchError(() => of({ success: false, message: 'Failed to fetch AI review.' })))
    }).subscribe({
      next: (res: any) => {
        if (res.deltas?.success) {
          this.diffFiles = res.deltas.files || [];
        } else {
          this.diffError = res.deltas?.message || 'Failed to load code diffs.';
        }

        if (res.review?.success) {
          this.aiReviewContent = res.review.review || '';
          this.reviewTriggered = true;
        } else {
          this.reviewError = res.review?.message || 'Failed to generate AI review.';
        }

        this.isLoadingReview = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.isLoadingReview = false;
        this.cdr.detectChanges();
      }
    });
  }

  // ── Copy AI output ───────────────────────────────────────────────────
  copyOutput(): void {
    const el = document.getElementById('rv-eval-content');
    if (el) navigator.clipboard.writeText(el.innerText).catch(() => {});
  }
}