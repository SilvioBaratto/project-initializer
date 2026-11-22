import {
  LucideArrowLeft,
  LucideCheck,
  LucideChevronDown,
  LucideChevronLeft,
  LucideChevronRight,
  LucideChevronsLeft,
  LucideChevronsRight,
  LucideChevronUp,
  LucideCircleCheckBig,
  LucideCircleExclamationPoint,
  LucideCopy,
  LucideHouse,
  LucideInfo,
  LucideLayoutDashboard,
  LucideLogOut,
  LucideMail,
  LucideMenu,
  LucideMonitor,
  LucideMoon,
  LucidePanelLeftClose,
  LucideSettings,
  LucideSettings2,
  LucideSun,
  LucideSunMoon,
  LucideTriangleExclamationPoint,
  LucideUser,
  LucideX,
  provideLucideIcons,
  type LucideIcon,
  type LucideIconData,
} from '@lucide/angular';

// Inside Material text, filled, outlined or tonal buttons, add `matButtonIcon` to the icon's
// svg and pass [size]="18"; icon buttons size their svg to 24px on their own.
const icons = {
  ArrowLeft: LucideArrowLeft,
  Check: LucideCheck,
  ChevronDown: LucideChevronDown,
  ChevronLeft: LucideChevronLeft,
  ChevronRight: LucideChevronRight,
  ChevronsLeft: LucideChevronsLeft,
  ChevronsRight: LucideChevronsRight,
  ChevronUp: LucideChevronUp,
  CircleAlert: LucideCircleExclamationPoint,
  CircleCheckBig: LucideCircleCheckBig,
  Copy: LucideCopy,
  House: LucideHouse,
  Info: LucideInfo,
  LayoutDashboard: LucideLayoutDashboard,
  LogOut: LucideLogOut,
  Mail: LucideMail,
  Menu: LucideMenu,
  Monitor: LucideMonitor,
  Moon: LucideMoon,
  PanelLeftClose: LucidePanelLeftClose,
  Settings: LucideSettings,
  Settings2: LucideSettings2,
  Sun: LucideSun,
  SunMoon: LucideSunMoon,
  TriangleAlert: LucideTriangleExclamationPoint,
  User: LucideUser,
  X: LucideX,
} satisfies Record<string, LucideIcon>;

/**
 * Name of an icon that {@link ICON_PROVIDER} registers. Typing an icon field with it turns an
 * unregistered name into a build error instead of a render-time throw.
 */
export type IconName = keyof typeof icons;

/**
 * Registers the app's icons for `<svg lucideIcon>`: each one resolves by its {@link IconName},
 * by its kebab-case Lucide name and by the older names Lucide keeps as aliases.
 */
export const ICON_PROVIDER = provideLucideIcons(
  // provideLucideIcons files an icon under its own name and aliases and ignores the map key,
  // so the PascalCase key joins the aliases for IconName values to resolve.
  ...Object.entries(icons).map(
    ([key, icon]): LucideIconData => ({
      ...icon.icon,
      aliases: [...(icon.icon.aliases ?? []), key],
    }),
  ),
);
