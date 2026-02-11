import { Component, signal, ChangeDetectionStrategy } from '@angular/core';

interface StatCard {
  label: string;
  value: string;
  change: string;
}

interface ActivityItem {
  text: string;
  time: string;
  color: 'success' | 'info' | 'warning';
}

@Component({
  selector: 'app-home',
  templateUrl: './home.html',
  styleUrl: './home.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeComponent {
  stats = signal<StatCard[]>([
    { label: 'Total users', value: '1,284', change: '+12%' },
    { label: 'Active sessions', value: '342', change: '+8%' },
    { label: 'Error rate', value: '0.12%', change: '-3%' },
    { label: 'Avg response', value: '45ms', change: '-18%' },
  ]);

  activity = signal<ActivityItem[]>([
    { text: 'New user registered', time: '2 min ago', color: 'success' },
    { text: 'Deployment completed', time: '15 min ago', color: 'info' },
    { text: 'API rate limit reached', time: '1 hr ago', color: 'warning' },
    { text: 'Database backup finished', time: '3 hrs ago', color: 'success' },
    { text: 'SSL certificate renewed', time: '5 hrs ago', color: 'info' },
  ]);

  quickStart = signal([
    { step: '1', text: 'Connect your API by updating the environment config' },
    { step: '2', text: 'Add routes in app.routes.ts for your feature pages' },
    { step: '3', text: 'Create components with ng generate component' },
    { step: '4', text: 'Run ng serve and start building' },
  ]);
}
