import { Component, signal, ChangeDetectionStrategy } from '@angular/core';

interface SettingItem {
  label: string;
  description: string;
  value: string;
}

@Component({
  selector: 'app-settings',
  templateUrl: './settings.html',
  styleUrl: './settings.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  settings = signal<SettingItem[]>([
    { label: 'Language', description: 'Interface display language', value: 'English' },
    { label: 'Timezone', description: 'Used for dates and scheduling', value: 'UTC' },
    { label: 'Notifications', description: 'Email and push notifications', value: 'Enabled' },
    { label: 'API version', description: 'Backend API version in use', value: 'v1' },
    { label: 'Theme', description: 'Application color scheme', value: 'Light' },
  ]);
}
