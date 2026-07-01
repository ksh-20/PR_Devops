import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

const SESSION_KEY_MODULE = 'dashboard_selectedModule';
const SESSION_KEY_PAGE   = 'dashboard_selectedPage';

@Injectable({
  providedIn: 'root'
})
export class DashboardService {

  // Restore module from sessionStorage so refresh keeps the user on the same section
  selectedModule: string = (sessionStorage.getItem(SESSION_KEY_MODULE) === 'Admin' && localStorage.getItem('is_admin_logged_in') !== 'true')
    ? 'DevOps'
    : (sessionStorage.getItem(SESSION_KEY_MODULE) || '');

  private selectedPageSubject = new BehaviorSubject<string>(
    sessionStorage.getItem(SESSION_KEY_PAGE) || 'home'
  );
  selectedPage$ = this.selectedPageSubject.asObservable();

  get selectedPage(): string {
    const page = this.selectedPageSubject.value;
    if (page === 'admin' && localStorage.getItem('is_admin_logged_in') !== 'true') {
      return 'home';
    }
    return page;
  }

  set selectedPage(page: string) {
    if (page === 'admin' && localStorage.getItem('is_admin_logged_in') !== 'true') {
      page = 'home';
    }
    sessionStorage.setItem(SESSION_KEY_PAGE, page);
    this.selectedPageSubject.next(page);
  }

  // Override selectedModule setter to also persist to sessionStorage
  setModule(module: string): void {
    if (module === 'Admin' && localStorage.getItem('is_admin_logged_in') !== 'true') {
      module = 'DevOps';
    }
    this.selectedModule = module;
    sessionStorage.setItem(SESSION_KEY_MODULE, module);
  }


  sidebarVisible = false;

  // Shared state for page-specific selections/coordination
  private _selectedProject: any = null;
  selectedRepoForDetails: any = null;
  hasReloadedDashboard = false;

  // History tracking for back/forward project selection
  private projectHistory: any[] = [null]; // Start with null (no project selected)
  private historyIndex = 0;
  isNavigatingHistory = false;

  get selectedProject(): any {
    return this._selectedProject;
  }

  set selectedProject(project: any) {
    this._selectedProject = project;
    if (this.isNavigatingHistory) return;

    // Check if the project is different from the current point in history
    const current = this.projectHistory[this.historyIndex];
    if (this.isSameProject(current, project)) {
      return;
    }

    // Truncate forward history if we are in the middle
    if (this.historyIndex < this.projectHistory.length - 1) {
      this.projectHistory = this.projectHistory.slice(0, this.historyIndex + 1);
    }

    this.projectHistory.push(project);
    this.historyIndex = this.projectHistory.length - 1;
  }

  private isSameProject(p1: any, p2: any): boolean {
    if (!p1 && !p2) return true;
    if (!p1 || !p2) return false;
    return p1.id === p2.id || p1.name === p2.name;
  }

  canGoBack(): boolean {
    return this.historyIndex > 0;
  }

  canGoForward(): boolean {
    return this.historyIndex < this.projectHistory.length - 1;
  }

  getPreviousProject(): any {
    if (this.canGoBack()) {
      this.historyIndex--;
      return { found: true, project: this.projectHistory[this.historyIndex] };
    }
    return { found: false };
  }

  getNextProject(): any {
    if (this.canGoForward()) {
      this.historyIndex++;
      return { found: true, project: this.projectHistory[this.historyIndex] };
    }
    return { found: false };
  }
}