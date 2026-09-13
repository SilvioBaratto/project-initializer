import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./auth/login/login').then((m) => m.LoginComponent),
    canActivate: [guestGuard],
    title: 'Sign in',
  },
  {
    path: 'auth/forgot-password',
    loadComponent: () => import('./auth/forgot-password/forgot-password').then((m) => m.ForgotPasswordComponent),
    canActivate: [guestGuard],
    title: 'Reset your password',
  },
  {
    path: 'auth/update-password',
    loadComponent: () => import('./auth/update-password/update-password').then((m) => m.UpdatePasswordComponent),
    title: 'Update password',
  },
  {
    // Same destinations as the base layer, behind the guard, so every item in the
    // navigation bar and rail (NAV_ITEMS) resolves to its page.
    path: '',
    loadComponent: () => import('./shared/layout/layout').then((m) => m.LayoutComponent),
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'home', pathMatch: 'full' },
      {
        path: 'home',
        loadComponent: () => import('./pages/home/home').then((m) => m.HomeComponent),
        title: 'Home',
      },
      {
        path: 'dashboard',
        loadComponent: () => import('./pages/dashboard/dashboard').then((m) => m.DashboardComponent),
        title: 'Dashboard',
      },
      {
        path: 'settings',
        loadComponent: () => import('./pages/settings/settings').then((m) => m.SettingsComponent),
        title: 'Settings',
      },
      {
        path: 'chat',
        loadComponent: () => import('./pages/chatbot/chatbot').then((m) => m.ChatbotComponent),
        title: 'Chat',
      },
      {
        path: 'components',
        loadComponent: () => import('./pages/components/components').then((m) => m.ComponentsComponent),
        title: 'Components',
      },
    ],
  },
  {
    path: '**',
    redirectTo: '',
  },
];
