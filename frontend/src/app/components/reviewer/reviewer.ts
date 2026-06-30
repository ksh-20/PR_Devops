import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RepositoriesApiService } from '../../services/api/repositories-api.service';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

// ── 7-day rolling window ─────────────────────────────────────────────────────
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

@Component({
  selector: 'app-reviewer',
  imports: [CommonModule],
  templateUrl: './reviewer.html',
  styleUrl: './reviewer.css'
})
export class ReviewerComponent implements OnInit, OnDestroy {

  // ── Active PR list (all fetched from backend, full truth)  ───────────────
  activePRs: any[] = [];
  isLoadingPRs = false;
  prsError: string | null = null;

  // ── Timer handle to evict PRs that age past 7 days while page is open ───
  private _staleCleanupTimer: ReturnType<typeof setInterval> | null = null;

  // ── Selected PR ──────────────────────────────────────────────────────────
  selectedPR: any = null;

  // ── Review state ─────────────────────────────────────────────────────────
  isLoadingReview = false;
  reviewTriggered = false;
  diffFiles: any[] = [];
  aiReviewContent = '';
  reviewError: string | null = null;
  diffError: string | null = null;

  // ── 7-day filter helper ──────────────────────────────────────────────────
  /** Returns true if the PR was created within the last 7 days. */
  private isWithin7Days(pr: any): boolean {
    if (!pr?.creationDate) return false;
    const age = Date.now() - new Date(pr.creationDate).getTime();
    return age <= SEVEN_DAYS_MS;
  }

  /**
   * The visible list — only PRs created in the last 7 days.
   * The full `activePRs` array is kept as the source of truth so that
   * the long-poll merging logic stays simple and the stale-cleanup timer
   * only needs to filter `activePRs` in one place.
   */
  get recentActivePRs(): any[] {
    return this.activePRs.filter(pr => this.isWithin7Days(pr));
  }

  // ── Derived getters ──────────────────────────────────────────────────────
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

    // Long-polling is started only once on init.
    // It will NOT restart automatically on timeout — only on real PR events.
    this.startLongPolling();

    // Periodic stale-eviction: every 60 s, drop PRs older than 7 days
    // from the backing array and deselect if the current PR aged out.
    this._staleCleanupTimer = setInterval(() => {
      const before = this.activePRs.length;
      this.activePRs = this.activePRs.filter(pr => this.isWithin7Days(pr));

      // If the currently-selected PR just aged out, clear the selection
      if (this.selectedPR && !this.isWithin7Days(this.selectedPR)) {
        this.selectedPR = null;
        this.diffFiles = [];
        this.aiReviewContent = '';
        this.reviewError = null;
        this.diffError = null;
        this.reviewTriggered = false;
      }

      if (this.activePRs.length !== before) {
        this.cdr.detectChanges();
      }
    }, 60_000);
  }

  ngOnDestroy(): void {
    if (this._staleCleanupTimer !== null) {
      clearInterval(this._staleCleanupTimer);
      this._staleCleanupTimer = null;
    }
  }

  startLongPolling(): void {
    this.reposApi.getLongPollEvents().subscribe({
      next: (data: any) => {
        // Only process and re-poll when we receive a real PR event.
        // A timeout response ({ event: 'timeout' }) means no update — wait before retrying
        // to avoid a tight loop that hammers the server (and triggers LLM calls).
        if (data && data.event === 'pr_updated' && data.pr) {
          const pr = data.pr;
          const isClosed =
            pr.status === 'completed' ||
            pr.status === 'abandoned' ||
            pr.status === 'closed';

          if (isClosed) {
            // Remove regardless of age
            this.activePRs = this.activePRs.filter(
              item =>
                !(
                  String(item.pullRequestId ?? item.id) ===
                    String(pr.pullRequestId ?? pr.id) &&
                  item.repo_id === pr.repo_id
                )
            );
          } else {
            // Only add/update if the PR is within the 7-day window
            if (this.isWithin7Days(pr)) {
              const index = this.activePRs.findIndex(
                item =>
                  String(item.pullRequestId ?? item.id) ===
                    String(pr.pullRequestId ?? pr.id) &&
                  item.repo_id === pr.repo_id
              );
              if (index > -1) {
                this.activePRs[index] = { ...this.activePRs[index], ...pr };
              } else {
                this.activePRs = [pr, ...this.activePRs];
              }
            }
          }

          this.cdr.detectChanges();
          // Re-subscribe immediately only after a real PR event
          this.startLongPolling();
        } else {
          // Timeout or unknown event — wait 5 seconds before polling again
          // This prevents the tight recursive loop that caused thousands of LLM calls
          setTimeout(() => this.startLongPolling(), 5000);
        }
      },
      error: () => {
        // On error, wait before retrying
        setTimeout(() => this.startLongPolling(), 5000);
      }
    });
  }

  loadActivePRs(): void {
    this.isLoadingPRs = true;
    this.prsError = null;

    this.reposApi.getActivePRsAll().subscribe({
      next: (res: any) => {
        // Store the full list but only show the last 7 days via recentActivePRs getter
        this.activePRs = res?.pull_requests ?? [];
        this.isLoadingPRs = false;
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        this.prsError =
          err?.error?.message ?? 'Failed to load active pull requests.';
        this.isLoadingPRs = false;
        this.cdr.detectChanges();
      }
    });
  }

  // ── Select a PR card → auto-load review ─────────────────────────────────
  selectPR(pr: any): void {
    if (
      this.selectedPR?.pullRequestId === pr.pullRequestId &&
      this.selectedPR?.repo_id === pr.repo_id
    )
      return;
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
    return (
      this.selectedPR &&
      String(this.selectedPR.pullRequestId ?? this.selectedPR.id) ===
        String(pr.pullRequestId ?? pr.id) &&
      this.selectedPR.repo_id === pr.repo_id
    );
  }

  // ── Load diff + AI review ────────────────────────────────────────────────
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
      deltas: this.reposApi
        .getPRDeltas(repoId, prId, projectName)
        .pipe(
          catchError(() =>
            of({ success: false, message: 'Failed to fetch diffs.' })
          )
        ),
      review: this.reposApi
        .getPRReview(repoId, prId, projectName)
        .pipe(
          catchError(() =>
            of({ success: false, message: 'Failed to fetch AI review.' })
          )
        )
    }).subscribe({
      next: (res: any) => {
        if (res.deltas?.success) {
          this.diffFiles = res.deltas.files || [];
        } else {
          this.diffError =
            res.deltas?.message || 'Failed to load code diffs.';
        }

        if (res.review?.success) {
          this.aiReviewContent = res.review.review || '';
          this.reviewTriggered = true;
        } else {
          this.reviewError =
            res.review?.message || 'Failed to generate AI review.';
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

  // ── Config file extensions to skip ──────────────────────────────────────
  private readonly CONFIG_EXTS = [
    '.json', '.lock', '.yaml', '.yml', '.toml', '.ini', '.cfg',
    '.config', '.env', '.xml', '.properties', '.gitignore',
    '.editorconfig', '.prettierrc', '.eslintrc', '.babelrc'
  ];

  /** Returns deduplicated, non-config source files only. */
  getCodeFiles(): any[] {
    const seen = new Set<string>();
    return this.diffFiles.filter(file => {
      const p = (file.path || '').toLowerCase().trim();
      if (!p || p === '/') return false;
      const filename = p.split('/').pop() || '';
      if (!filename.includes('.')) return false;
      if (seen.has(p)) return false;
      if (this.CONFIG_EXTS.some(ext => p.endsWith(ext))) return false;
      seen.add(p);
      return true;
    });
  }

  /** Parses unified diff → [{lineNum, text}] with real line numbers. */
  getDiffLines(
    diff: string,
    side: 'old' | 'new'
  ): { lineNum: number; text: string }[] {
    if (!diff) return [];
    const lines = diff.split('\n');
    const result: { lineNum: number; text: string }[] = [];
    let oldLine = 1, newLine = 1;

    for (const line of lines) {
      if (line.startsWith('---') || line.startsWith('+++')) continue;
      if (line.startsWith('@@')) {
        const m = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
        if (m) { oldLine = +m[1]; newLine = +m[2]; }
        continue;
      }
      if (line.startsWith('-')) {
        if (side === 'old') result.push({ lineNum: oldLine, text: line.slice(1) });
        oldLine++;
      } else if (line.startsWith('+')) {
        if (side === 'new') result.push({ lineNum: newLine, text: line.slice(1) });
        newLine++;
      } else {
        const text = line.startsWith(' ') ? line.slice(1) : line;
        result.push({ lineNum: side === 'old' ? oldLine : newLine, text });
        oldLine++; newLine++;
      }
    }
    return result;
  }

  // ── Copy AI output ───────────────────────────────────────────────────────
  copyOutput(): void {
    const el = document.getElementById('rv-eval-content');
    if (el) navigator.clipboard.writeText(el.innerText).catch(() => {});
  }
}
