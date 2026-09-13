import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { LucideAngularModule } from 'lucide-angular';

import { ThemeMode, ThemeService } from '../../services/theme';
import { THEME_OPTIONS } from '../../shared/theme-options';

@Component({
  selector: 'app-settings',
  imports: [LucideAngularModule, MatButtonToggleModule, MatCardModule],
  templateUrl: './settings.html',
  styleUrl: './settings.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  private readonly themeService = inject(ThemeService);

  readonly theme = this.themeService.theme;

  readonly options = THEME_OPTIONS;

  select(mode: ThemeMode) {
    this.themeService.setTheme(mode);
  }
}
