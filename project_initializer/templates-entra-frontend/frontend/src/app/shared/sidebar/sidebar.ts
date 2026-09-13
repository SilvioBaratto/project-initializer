import { ChangeDetectionStrategy, Component, Signal, computed, inject, input, output, signal } from '@angular/core';
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
import { RouterLink, RouterLinkActive } from '@angular/router';
import { MsalService } from '@azure/msal-angular';
import { LucideAngularModule } from 'lucide-angular';

import { AuthService } from '../../core/services/auth.service';
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
 * Entra variant of the navigation rail contents: destinations, the theme choice and the
 * account actions. It keeps the base app-sidebar contract, template and styles. This
 * overlay ships only the class, so `sidebar.html` and `sidebar.css` resolve to the base
 * layer's files and can't drift from them. What differs is the account area: the row names
 * the signed-in Microsoft account, Sign out shows, and `onLogout()` signs out through MSAL.
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
  private readonly msalService = inject(MsalService);

  /** Rail form to render; see {@link SidebarMode}. */
  readonly mode = input<SidebarMode>('expanded');

  /** Asks the host to close the surface: the compact sheet dismisses after a destination or sign out. */
  readonly closeSidebar = output<void>();

  navItems: NavItem[] = NAV_ITEMS;

  readonly theme = this.themeService.theme;

  /** The theme choices: a menu in the docked rails, a single-selection list in the compact sheet. */
  readonly themeOptions = THEME_OPTIONS;

  /**
   * Name shown in the account row: the active MSAL account's display name, else its username
   * (UPN or email). AuthService sets the active account before it marks the session
   * authenticated, so reading `isAuthenticated()` re-evaluates this when the session changes.
   * Null (no row) when signed out.
   */
  readonly accountName: Signal<string | null> = computed(() => {
    if (!this.authService.isAuthenticated()) {
      return null;
    }
    const account = this.msalService.instance.getActiveAccount();
    return account?.name || account?.username || null;
  });

  /** Sign out shows in every rail form: there is an MSAL session to end. */
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
   * Signs out through MSAL. logoutRedirect hands the browser to the Microsoft sign-out
   * page, so there is no in-app navigation to /login here. closeSidebar still fires, as
   * in every variant, so the compact sheet closes while the redirect starts.
   */
  onLogout(): void {
    this.authService.logout();
    this.closeSidebar.emit();
  }
}
