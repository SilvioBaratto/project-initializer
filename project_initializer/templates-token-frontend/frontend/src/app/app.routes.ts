import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./auth/login/login').then((m) => m.LoginComponent),
    canActivate: [guestGuard],
    title: 'Login',
  },
  {
    path: '',
    loadComponent: () => import('./shared/layout/layout').then((m) => m.LayoutComponent),
    canActivate: [authGuard],
    children: [
      {
        path: '',
        loadComponent: () => import('./pages/chatbot/chatbot').then((m) => m.ChatbotComponent),
        title: 'Chatbot',
      },
    ],
  },
  {
    path: '**',
    redirectTo: '',
  },
];
