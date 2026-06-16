import { Component, computed, inject, input, output, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { NavItem, NAV_ITEMS } from '../nav-item';
import { ThemeService } from '../../services/theme';

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive, LucideAngularModule],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent {
  private readonly themeService = inject(ThemeService);

  isOpen = input<boolean>(false);
  isMobile = input<boolean>(false);

  closeSidebar = output<void>();

  readonly theme = this.themeService.theme;

  navItems: NavItem[] = NAV_ITEMS;

  showSidebar = computed(() => !this.isMobile() || this.isOpen());

  onNavClick() {
    this.closeSidebar.emit();
  }

  toggleTheme() {
    this.themeService.toggleTheme();
  }
}
