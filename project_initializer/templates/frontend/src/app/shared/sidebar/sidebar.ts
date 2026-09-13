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
import { LucideAngularModule } from 'lucide-angular';

import { ThemeMode, ThemeService } from '../../services/theme';
import { NavItem, NAV_ITEMS, RailActionsSheet, SidebarMode } from '../nav-item';
import { THEME_OPTIONS } from '../theme-options';

/** Re-exported for consumers that import the rail modes next to the component. */
export type { SidebarMode } from '../nav-item';

/**
 * Names of the compact bottom sheet that holds this rail's actions. The base scaffold has no
 * account, so the sheet holds only the theme choice and its names say so.
 */
export const RAIL_ACTIONS_SHEET: RailActionsSheet = {
  triggerLabel: 'Open theme settings',
  sheetLabel: 'Theme settings',
  triggerIcon: 'Settings2',
};

/**
 * Contents of the navigation rail: destinations, the theme choice and, in the auth
 * variants, the account actions. The base scaffold (`--auth none`) has no session, so it
 * shows no account row and no Sign out (`accountName` is null, `canSignOut` is false). The
 * auth overlays switch those on and sign out by overriding `onLogout()`.
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

  /** Rail form to render; see {@link SidebarMode}. */
  readonly mode = input<SidebarMode>('expanded');

  /** Asks the host to close the surface: the compact sheet dismisses after a destination or sign out. */
  readonly closeSidebar = output<void>();

  navItems: NavItem[] = NAV_ITEMS;

  readonly theme = this.themeService.theme;

  /** The theme choices: a menu in the docked rails, a single-selection list in the compact sheet. */
  readonly themeOptions = THEME_OPTIONS;

  /**
   * Name shown in the account row of the expanded rail and the compact sheet. There is no
   * signed-in user in the base scaffold, so this is null and the row is omitted rather
   * than showing a placeholder.
   */
  readonly accountName: Signal<string | null> = signal(null);

  /** Whether Sign out shows. An unavailable action is removed, not shown: there is no session here. */
  readonly canSignOut: Signal<boolean> = signal(false);

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

  /** No session to end in the base scaffold (Sign out doesn't render). Auth overlays sign out here. */
  onLogout(): void {
    this.closeSidebar.emit();
  }
}
