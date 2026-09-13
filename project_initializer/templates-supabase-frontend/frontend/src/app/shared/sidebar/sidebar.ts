import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
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
import { MatProgressSpinner } from '@angular/material/progress-spinner';
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
 * Contents of the navigation rail: destinations, the theme choice and the account
 * actions (Supabase overlay). It matches the base sidebar (and uses the base sidebar.css)
 * except for the account area: the signed-in user's email names the account, and
 * Sign out (paired with the login page's "Sign in") ends the Supabase session before
 * returning to the login page.
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
    MatProgressSpinner,
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

  /** Destinations show in the docked rails only; the compact bar already lists them. */
  readonly showDestinations = computed(() => this.mode() !== 'modal');
  readonly collapsed = computed(() => this.mode() === 'collapsed');
  /** M3 swaps menus for bottom sheets below 600px, so the compact sheet lists the theme choices inline. */
  readonly modal = computed(() => this.mode() === 'modal');

  /**
   * Name shown in the account row: the signed-in email. Null (no row) while no session is
   * loaded, rather than a placeholder, the same contract as the token and Entra rails.
   */
  readonly accountName = computed<string | null>(() => this.authService.currentUser()?.email || null);

  /**
   * True from the Sign out activation until the login page has replaced the shell (or that
   * navigation has failed). While true, Sign out shows a progress indicator in place of its
   * icon, carries aria-busy, and ignores further activations. It stays enabled and focusable,
   * so focus stays inside the bottom sheet's focus trap.
   */
  readonly signingOut = signal(false);

  onNavClick(): void {
    this.closeSidebar.emit();
  }

  setTheme(mode: ThemeMode): void {
    this.themeService.setTheme(mode);
  }

  /**
   * Signs out of Supabase, then replaces the current entry with /login and asks the host to
   * close the surface.
   * Navigation waits for the sign-out: guestGuard on /login sends a still-authenticated
   * user back to '/'. AuthService.logout() clears the local session even when the Supabase
   * call fails, so the login page is reached either way and the failure still surfaces.
   * A second activation while a sign-out is in flight does nothing.
   */
  async onLogout(): Promise<void> {
    if (this.signingOut()) {
      return;
    }
    this.signingOut.set(true);
    try {
      await this.authService.logout();
    } finally {
      const navigated = this.router.navigate(['/login'], { replaceUrl: true });
      // Emitted before the navigation destroys the shell, so the output is still live.
      this.closeSidebar.emit();
      void navigated.finally(() => this.signingOut.set(false));
    }
  }
}
