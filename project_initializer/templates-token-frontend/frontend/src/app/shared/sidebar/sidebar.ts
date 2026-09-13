import {
  ChangeDetectionStrategy,
  Component,
  Signal,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatRipple } from '@angular/material/core';
import {
  MatActionList,
  MatListItem,
  MatListItemIcon,
  MatListItemMeta,
  MatListItemTitle,
  MatListOption,
  MatNavList,
  MatSelectionList,
} from '@angular/material/list';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatTooltip } from '@angular/material/tooltip';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { AuthService } from '../../services/auth';
import { ThemeMode, ThemeService } from '../../services/theme';
import { NavItem, NAV_ITEMS, RailActionsSheet, SidebarMode } from '../nav-item';
import { THEME_OPTIONS } from '../theme-options';

/** Re-exported for consumers that import the rail modes next to the component. */
export type { SidebarMode } from '../nav-item';

/** Names of the compact bottom sheet that holds this rail's theme and account actions. */
export const RAIL_ACTIONS_SHEET: RailActionsSheet = {
  triggerLabel: 'Open theme and account',
  sheetLabel: 'Theme and account',
  triggerIcon: 'User',
};

/**
 * Token-auth override of the navigation rail contents. It replaces only the base sidebar.ts
 * by path and keeps the base contract: `sidebar.html` and `sidebar.css` resolve to the base
 * layer's files, so they can't drift from it. The differences sit in the account area:
 * Sign out shows (`canSignOut`), `onLogout()` clears the stored token and returns to the
 * sign-in view, and the account row is omitted because a bearer token names no user
 * (see `accountName`).
 */
@Component({
  selector: 'app-sidebar',
  imports: [
    RouterLink,
    RouterLinkActive,
    MatRipple,
    MatIconButton,
    MatTooltip,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatNavList,
    MatActionList,
    MatSelectionList,
    MatListItem,
    MatListOption,
    MatListItemIcon,
    MatListItemMeta,
    MatListItemTitle,
    LucideAngularModule,
  ],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent {
  private readonly themeService = inject(ThemeService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  /** Rail form to render; see {@link SidebarMode}. */
  readonly mode = input<SidebarMode>('expanded');

  /** Asks the host to close the surface: the compact sheet dismisses after a destination or sign out. */
  readonly closeSidebar = output<void>();

  navItems: NavItem[] = NAV_ITEMS;

  readonly theme = this.themeService.theme;

  /** The theme choices: a menu in the docked rails, a single-selection list in the compact sheet. */
  readonly themeOptions = THEME_OPTIONS;

  /**
   * Name shown in the account row of the expanded rail and the compact sheet. A bearer token
   * identifies no user, so this is null and the row is omitted rather than showing a
   * placeholder. Point it at an identity source (a profile endpoint) to show the row.
   */
  readonly accountName: Signal<string | null> = signal(null);

  /** Sign out shows in every rail form: there is a stored token to clear. */
  readonly canSignOut: Signal<boolean> = signal(true);

  /** Destinations show in the docked rails only; the compact bar already lists them. */
  readonly showDestinations = computed(() => this.mode() !== 'modal');
  readonly collapsed = computed(() => this.mode() === 'collapsed');
  /** M3 swaps menus for bottom sheets below 600px, so the compact sheet lists the theme choices inline. */
  readonly modal = computed(() => this.mode() === 'modal');

  onNavClick(): void {
    this.closeSidebar.emit();
  }

  setTheme(mode: ThemeMode): void {
    this.themeService.setTheme(mode);
  }

  /**
   * Clears the token first, so guestGuard lets the sign-in route through, then replaces
   * the current history entry with /login (Back can't return to a guarded page) and
   * asks the host to close the surface.
   */
  onLogout(): void {
    this.authService.logout();
    void this.router.navigate(['/login'], { replaceUrl: true });
    this.closeSidebar.emit();
  }
}
