import type { IconName } from '../icons';
import type { ThemeMode } from '../services/theme';

/** One theme choice: the mode, its visible name and its icon. */
export interface ThemeOption {
  mode: ThemeMode;
  label: string;
  icon: IconName;
}

/**
 * The theme choices in display order, shared by the Settings page (segmented button) and the
 * navigation rail (theme menu, and the compact sheet's single-selection list), so their names
 * and icons can't drift. Lives at the `shared/` root because the auth overlays replace
 * sidebar.ts but inherit this file.
 */
export const THEME_OPTIONS: readonly ThemeOption[] = [
  { mode: 'system', label: 'System', icon: 'Monitor' },
  { mode: 'light', label: 'Light', icon: 'Sun' },
  { mode: 'dark', label: 'Dark', icon: 'Moon' },
];
