import { IconName } from '../icons';

/**
 * Navigation destination shared by the navigation rail (app-sidebar) and the
 * navigation bar (app-bottom-tab-bar).
 * Lives at the `shared/` root (peer to both components) so neither leaf
 * component owns the contract the other depends on.
 */
export interface NavItem {
  name: string;
  route: string;
  icon: IconName;
}

/**
 * Which form of the M3 navigation rail `app-sidebar` renders. The shell
 * (LayoutComponent) picks it from the window size class and binds it to the
 * sidebar's `mode` input. Declared here, not in sidebar.ts, because the auth
 * overlays replace sidebar.ts while the shell keeps depending on this type.
 * - `modal`: compact contents of the modal bottom sheet the top app bar opens. It holds
 *   only the rail's actions (theme, and account and sign out in the auth variants), never
 *   the navigation bar's destinations.
 * - `collapsed`: collapsed rail (96px, wider only when enlarged text needs it),
 *   icon-over-label destinations, icon-button actions.
 * - `expanded`: 280px expanded rail, `mat-nav-list` destinations with labels beside icons.
 */
export type SidebarMode = 'modal' | 'collapsed' | 'expanded';

/**
 * Accessible names and icon of the compact bottom sheet holding the rail's actions, and of
 * the top app bar button that opens it. Each layer's sidebar.ts exports its own value as
 * `RAIL_ACTIONS_SHEET`, because the sheet's contents differ per layer (theme only in the
 * base scaffold; theme and account in the auth variants). Declared here, like SidebarMode,
 * because the shell depends on the type while the auth overlays replace sidebar.ts.
 */
export interface RailActionsSheet {
  /** Name of the top app bar button that opens the sheet. */
  triggerLabel: string;
  /** Name of the sheet (the dialog's aria-label). */
  sheetLabel: string;
  /** Icon of the top app bar button. */
  triggerIcon: IconName;
}

/**
 * Single source of truth for primary navigation. The compact navigation bar and
 * the medium-and-up navigation rail render the same destinations, so the two
 * surfaces cannot drift out of sync. M3 navigation bars hold 3–5 destinations.
 * Every page routed under the shell is listed here, except the /components catalog,
 * which is a developer reference rather than a primary view.
 */
export const NAV_ITEMS: NavItem[] = [
  { name: 'Home', route: '/home', icon: 'Home' },
  { name: 'Dashboard', route: '/dashboard', icon: 'LayoutDashboard' },
  { name: 'Chat', route: '/chat', icon: 'MessageSquare' },
  { name: 'Settings', route: '/settings', icon: 'Settings' },
];
