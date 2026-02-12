import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./shared/layout/layout').then((m) => m.LayoutComponent),
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
