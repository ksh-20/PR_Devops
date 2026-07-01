import { Routes } from '@angular/router';

import { Home } from './pages/home/home';
import { About } from './pages/about/about';
import { Login } from './pages/login/login';
import { AdminLogin } from './pages/admin-login/admin-login';
import { authGuard } from './guards/auth-guard';

export const routes: Routes = [

  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full'
  },

  {
    path: 'login',
    component: Login
  },

  {
    path: 'admin-login',
    component: AdminLogin
  },

  {
    path: 'home',
    component: Home,
    canActivate: [authGuard]
  },

  {
    path: 'about',
    component: About,
    canActivate: [authGuard]
  },

];