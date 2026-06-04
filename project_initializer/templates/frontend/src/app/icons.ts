import { LUCIDE_ICONS, LucideIconProvider } from 'lucide-angular';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleCheckBig,
  Info,
  Loader2,
  Menu,
  MessageSquare,
  Plus,
  Search,
  Settings,
  Settings2,
  SlidersVertical,
  SquareFunction,
  X,
} from 'lucide-angular';

// LucideIconProvider matches template names by converting kebab-case to PascalCase
// and looking up the result in this map's keys. Most entries use the icon's own
// PascalCase identifier as the key; the three aliased entries below map the
// deprecated kebab-based names (CheckCircle, Sliders, FunctionSquare) to their
// canonical (non-deprecated) counterparts in lucide-angular ≥ 0.477.
const icons = {
  CheckCircle: CircleCheckBig,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FunctionSquare: SquareFunction,
  Info,
  Loader2,
  Menu,
  MessageSquare,
  Plus,
  Search,
  Settings,
  Settings2,
  Sliders: SlidersVertical,
  X,
};

export type IconName = keyof typeof icons;

export const ICON_PROVIDER = {
  provide: LUCIDE_ICONS,
  multi: true,
  useValue: new LucideIconProvider(icons),
};
