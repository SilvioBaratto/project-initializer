import { ChangeDetectionStrategy, Component, Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { LUCIDE_ICONS, LucideDynamicIcon } from '@lucide/angular';

import { ICON_PROVIDER, IconName } from './icons';

// A Record over IconName fails to compile when icons.ts gains or loses a name, so this list
// cannot drift from the registry it checks.
const ICON_NAMES: Record<IconName, true> = {
  ArrowLeft: true,
  Bell: true,
  Check: true,
  ChevronDown: true,
  ChevronLeft: true,
  ChevronRight: true,
  ChevronsLeft: true,
  ChevronsRight: true,
  ChevronUp: true,
  CircleAlert: true,
  CircleCheckBig: true,
  CircleX: true,
  Copy: true,
  EllipsisVertical: true,
  Eye: true,
  EyeOff: true,
  House: true,
  Inbox: true,
  Info: true,
  LayoutDashboard: true,
  LoaderCircle: true,
  Lock: true,
  LogOut: true,
  Mail: true,
  Menu: true,
  Minus: true,
  Monitor: true,
  Moon: true,
  PanelLeftClose: true,
  PanelLeftOpen: true,
  Pencil: true,
  Plus: true,
  Search: true,
  Settings: true,
  Settings2: true,
  SlidersVertical: true,
  SquareFunction: true,
  Sun: true,
  SunMoon: true,
  Trash2: true,
  TriangleAlert: true,
  User: true,
  X: true,
};

@Component({
  imports: [LucideDynamicIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg lucideIcon="NotAnIcon"></svg>`,
})
class UnregisteredIconHostComponent {}

@Component({
  imports: [LucideDynamicIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg lucideIcon="Menu" class="probe-icon"></svg>`,
})
class DecorativeIconHostComponent {}

@Component({
  imports: [LucideDynamicIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<svg lucideIcon="CircleAlert" title="Error"></svg>`,
})
class TitledIconHostComponent {}

function renderedSvg(host: Type<unknown>): SVGElement {
  const fixture = TestBed.createComponent(host);
  fixture.detectChanges();
  return (fixture.nativeElement as HTMLElement).querySelector('svg')!;
}

describe('ICON_PROVIDER', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [ICON_PROVIDER] });
  });

  describe('when the registry is read', () => {
    it('resolves every IconName', () => {
      const registry = TestBed.inject(LUCIDE_ICONS);

      const missing = Object.keys(ICON_NAMES).filter((name) => !(name in registry));

      expect(missing).toEqual([]);
    });

    it('resolves the renamed icons by their current kebab-case names', () => {
      const registry = TestBed.inject(LUCIDE_ICONS);

      expect(registry['house']?.name).toBe('house');
      expect(registry['circle-exclamation-point']?.name).toBe('circle-exclamation-point');
      expect(registry['triangle-exclamation-point']?.name).toBe('triangle-exclamation-point');
      expect(registry['trash']?.name).toBe('trash');
    });

    it('maps each renamed PascalCase key to the icon of its current class', () => {
      const registry = TestBed.inject(LUCIDE_ICONS);

      expect(registry['CircleAlert']?.name).toBe('circle-exclamation-point');
      expect(registry['TriangleAlert']?.name).toBe('triangle-exclamation-point');
      expect(registry['Trash2']?.name).toBe('trash');
    });

    it('resolves the older names that Lucide keeps as aliases', () => {
      const registry = TestBed.inject(LUCIDE_ICONS);

      expect(registry['home']?.name).toBe('house');
      expect(registry['check-circle']?.name).toBe('circle-check-big');
      expect(registry['circle-alert']?.name).toBe('circle-exclamation-point');
      expect(registry['triangle-alert']?.name).toBe('triangle-exclamation-point');
    });
  });

  describe('when an icon renders', () => {
    it('throws for an unregistered icon name', () => {
      const fixture = TestBed.createComponent(UnregisteredIconHostComponent);

      expect(() => fixture.detectChanges()).toThrowError("Unable to resolve icon 'NotAnIcon'");
    });

    it('renders the svg itself, with the icon class and the classes passed in', () => {
      const svg = renderedSvg(DecorativeIconHostComponent);

      expect(svg.classList).toContain('lucide-menu');
      expect(svg.classList).toContain('probe-icon');
      expect(svg.getAttribute('width')).toBe('24');
      expect(svg.getAttribute('stroke-width')).toBe('2');
    });

    it('writes no inline style attribute, so the CSP needs no unsafe-inline for it', () => {
      const svg = renderedSvg(DecorativeIconHostComponent);

      expect(svg.hasAttribute('style')).toBe(false);
      svg.querySelectorAll('*').forEach((child) => expect(child.hasAttribute('style')).toBe(false));
    });

    it('hides a decorative icon from assistive technology', () => {
      const svg = renderedSvg(DecorativeIconHostComponent);

      expect(svg.getAttribute('aria-hidden')).toBe('true');
    });

    it('exposes an icon that has a title to assistive technology', () => {
      const svg = renderedSvg(TitledIconHostComponent);

      expect(svg.getAttribute('aria-hidden')).toBe('false');
      expect(svg.querySelector('title')?.textContent).toBe('Error');
    });
  });
});
