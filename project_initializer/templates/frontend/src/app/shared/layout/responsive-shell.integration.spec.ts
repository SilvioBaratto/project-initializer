import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MediaMatcher } from '@angular/cdk/layout';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatBottomSheetHarness } from '@angular/material/bottom-sheet/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatSidenavContainer } from '@angular/material/sidenav';
import { MatSidenavHarness } from '@angular/material/sidenav/testing';
import { By } from '@angular/platform-browser';
import { Router, Routes, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { LucideIconConfig } from 'lucide-angular';

import { ICON_PROVIDER } from '../../icons';
import { WINDOW_SIZE_QUERIES, WindowSizeClass } from '../../services/window-size-class';
import { NAV_ITEMS } from '../nav-item';
import { RAIL_ACTIONS_SHEET } from '../sidebar/sidebar';
import { LayoutComponent, RAIL_EXPANDED_STORAGE_KEY } from './layout';

@Component({ selector: 'app-route-stub', template: '' })
class RouteStubComponent {}

type MediaListener = (event: { matches: boolean; media: string }) => void;

/**
 * MediaMatcher driven by a settable M3 window size class. jsdom evaluates no media
 * queries, so each class is simulated by which WINDOW_SIZE_QUERIES entry matches;
 * setSize() notifies BreakpointObserver like a real resize.
 */
class FakeMediaMatcher {
  private readonly notifiers: Array<() => void> = [];

  constructor(private size: WindowSizeClass) {}

  matchMedia(query: string): MediaQueryList {
    const listeners = new Set<MediaListener>();
    const matches = (): boolean => WINDOW_SIZE_QUERIES[this.size] === query;
    this.notifiers.push(() => listeners.forEach((listener) => listener({ matches: matches(), media: query })));
    return {
      media: query,
      get matches() {
        return matches();
      },
      addListener: (listener: MediaListener) => listeners.add(listener),
      removeListener: (listener: MediaListener) => listeners.delete(listener),
      addEventListener: (_type: string, listener: MediaListener) => listeners.add(listener),
      removeEventListener: (_type: string, listener: MediaListener) => listeners.delete(listener),
    } as unknown as MediaQueryList;
  }

  setSize(size: WindowSizeClass): void {
    this.size = size;
    this.notifiers.forEach((notify) => notify());
  }
}

/**
 * Cross-component integration: the shell swaps navigation per M3 window size class.
 * compact: top app bar + navigation bar, and a modal bottom sheet for the rail's actions
 * (Esc / scrim close, focus return); medium: docked collapsed rail; expanded and large:
 * collapsed rail with an expand toggle; extra-large: expanded rail. From 600px the rail is
 * the banner landmark. The user's toggle choice holds across size classes and new shells.
 */
describe('Responsive shell (integration)', () => {
  let fixture: ComponentFixture<LayoutComponent>;
  let component: LayoutComponent;
  let host: HTMLElement;
  let loader: HarnessLoader;
  let matcher: FakeMediaMatcher;

  const routes: Routes = NAV_ITEMS.map((item) => ({
    path: item.route.slice(1),
    component: RouteStubComponent,
    title: item.name,
  }));

  async function settle(): Promise<void> {
    // Two rounds: BreakpointObserver debounces changes by a timeout, the render then binds
    // the rail and the bar, and overlays (the bottom sheet) finish opening or closing in a
    // further task.
    for (let round = 0; round < 2; round++) {
      await new Promise((resolve) => setTimeout(resolve));
      fixture.detectChanges();
      await fixture.whenStable();
    }
  }

  async function render(size: WindowSizeClass): Promise<void> {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: (query: string) =>
        ({
          matches: false,
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
        }) as unknown as MediaQueryList,
    });
    matcher = new FakeMediaMatcher(size);

    await TestBed.configureTestingModule({
      imports: [LayoutComponent],
      providers: [
        provideRouter(routes),
        ICON_PROVIDER,
        LucideIconConfig,
        { provide: MediaMatcher, useValue: matcher },
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
      ],
    }).compileComponents();

    await create();
  }

  async function create(): Promise<void> {
    fixture = TestBed.createComponent(LayoutComponent);
    component = fixture.componentInstance;
    host = fixture.nativeElement;
    loader = TestbedHarnessEnvironment.loader(fixture);
    fixture.detectChanges();
    await settle();
  }

  async function resize(size: WindowSizeClass): Promise<void> {
    matcher.setSize(size);
    await settle();
  }

  function rail(): HTMLElement {
    return host.querySelector<HTMLElement>('mat-sidenav#app-rail')!;
  }

  /** Expand/collapse toggle of the docked rail (expanded size class and up). */
  function railToggle(): HTMLButtonElement | null {
    return rail().querySelector<HTMLButtonElement>('.rail-header app-hamburger button');
  }

  /** Compact top app bar button that opens the actions bottom sheet. */
  function actionsButton(): HTMLButtonElement {
    return host.querySelector<HTMLButtonElement>('app-navbar button.shell-actions-toggle')!;
  }

  /** The bottom sheet container, rendered in the body-level overlay container. */
  function sheet(): HTMLElement | null {
    return document.querySelector<HTMLElement>('.mat-bottom-sheet-container');
  }

  function pressEscape(target: HTMLElement): void {
    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    // MatDrawer and MatBottomSheet check the legacy keyCode, which jsdom's KeyboardEvent init does not set.
    Object.defineProperty(event, 'keyCode', { get: () => 27 });
    target.dispatchEvent(event);
  }

  function navLabels(): string[] {
    return Array.from(host.querySelectorAll('nav, [role="navigation"]')).map(
      (nav) => nav.getAttribute('aria-label') ?? '',
    );
  }

  /** Banner landmarks: explicit role="banner", or a <header> outside main (only app-navbar renders one). */
  function banners(): Element[] {
    return Array.from(host.querySelectorAll('[role="banner"], header'));
  }

  afterEach(() => {
    vi.restoreAllMocks();
    document.documentElement.classList.remove('dark', 'light', 'theme-transitioning');
    localStorage.clear();
  });

  describe('compact (< 600px)', () => {
    beforeEach(() => render('compact'));

    it('when compact, the top app bar and the navigation bar render and no rail docks', () => {
      expect(host.querySelector('app-navbar')).toBeTruthy();
      const bar = host.querySelector('app-bottom-tab-bar nav');
      expect(bar?.getAttribute('aria-label')).toBe('Primary');
      expect(bar?.querySelectorAll('a').length).toBe(NAV_ITEMS.length);

      expect(host.querySelector('mat-sidenav')).toBeNull();
      expect(component.sidebarMode()).toBe('modal');
      expect(sheet()).toBeNull();
    });

    it('when the actions button is clicked, a labelled bottom sheet opens with the rail actions and no destinations', async () => {
      const button = actionsButton();
      expect(button.getAttribute('aria-haspopup')).toBe('dialog');
      expect(button.getAttribute('aria-label')).toBe(RAIL_ACTIONS_SHEET.triggerLabel);
      // A dialog trigger, not a disclosure: no expanded state, and the sheet has no id to point at.
      expect(button.hasAttribute('aria-expanded')).toBe(false);
      expect(button.hasAttribute('aria-controls')).toBe(false);

      button.click();
      await settle();

      const harness = await TestbedHarnessEnvironment.documentRootLoader(fixture).getHarness(MatBottomSheetHarness);
      expect(await harness.getAriaLabel()).toBe(RAIL_ACTIONS_SHEET.sheetLabel);
      const container = sheet()!;
      expect(container.getAttribute('role')).toBe('dialog');
      expect(container.querySelector('app-shell-actions-sheet app-sidebar')).toBeTruthy();
      expect(container.querySelector('mat-selection-list.sidebar-theme-options')).toBeTruthy();
      expect(container.querySelectorAll('a').length).toBe(0);
      expect(container.querySelector('nav, mat-nav-list')).toBeNull();
      // Nothing promises navigation: no hamburger anywhere at compact.
      expect(document.querySelector('app-hamburger')).toBeNull();
    });

    it('when the sheet opens, focus moves into it, and Esc closes it and returns focus to the actions button', async () => {
      const button = actionsButton();
      button.focus();
      button.click();
      await settle();

      // In a browser the trap focuses the first tabbable action. jsdom lays nothing out, so the
      // CDK finds no visible tabbable element and focuses the sheet container: assert containment.
      const focused = document.activeElement as HTMLElement;
      expect(sheet()!.contains(focused)).toBe(true);

      pressEscape(focused);
      await settle();

      expect(sheet()).toBeNull();
      expect(document.activeElement).toBe(button);
    });

    it('when the scrim is clicked, the sheet closes', async () => {
      actionsButton().click();
      await settle();

      document.querySelector<HTMLElement>('.cdk-overlay-backdrop')!.click();
      await settle();

      expect(sheet()).toBeNull();
    });

    it('when compact, the navigation bar is the only navigation landmark and the top app bar the only banner', () => {
      expect(navLabels()).toEqual(['Primary']);
      const bannerElements = banners();
      expect(bannerElements.length).toBe(1);
      expect(bannerElements[0].closest('app-navbar')).toBeTruthy();
    });
  });

  describe('medium (600–839px)', () => {
    beforeEach(() => render('medium'));

    it('when medium, a collapsed rail is docked with no bar, no top app bar and no expand toggle', async () => {
      expect(host.querySelector('app-navbar')).toBeNull();
      expect(host.querySelector('app-bottom-tab-bar')).toBeNull();

      const sidenav = await loader.getHarness(MatSidenavHarness);
      expect(await sidenav.getMode()).toBe('side');
      expect(await sidenav.isOpen()).toBe(true);
      expect(railToggle()).toBeNull();
      expect(rail().classList.contains('rail-wide')).toBe(false);

      const nav = rail().querySelector('nav');
      expect(nav?.getAttribute('aria-label')).toBe('Primary');
      expect(nav?.querySelectorAll('a.rail-item').length).toBe(NAV_ITEMS.length);
      expect(rail().querySelector('mat-nav-list')).toBeNull();
    });

    it('when Esc is pressed in the docked rail, it stays open', async () => {
      const link = rail().querySelector<HTMLElement>('a.rail-item')!;
      link.focus();
      pressEscape(link);
      await settle();
      expect(await (await loader.getHarness(MatSidenavHarness)).isOpen()).toBe(true);
    });

    it('when medium, the rail is the one banner, holding the Primary navigation and the rail actions', () => {
      expect(navLabels()).toEqual(['Primary']);
      const bannerElements = banners();
      expect(bannerElements.length).toBe(1);
      const banner = bannerElements[0];
      expect(banner.classList.contains('rail-content')).toBe(true);
      expect(banner.querySelector('nav[aria-label="Primary"]')).toBeTruthy();
      expect(banner.querySelector('.sidebar-footer button.sidebar-theme-toggle')).toBeTruthy();
    });
  });

  for (const size of ['expanded', 'large'] as const) {
    describe(`${size}`, () => {
      beforeEach(() => render(size));

      it(`when ${size}, the rail starts collapsed and its toggle docks the expanded rail`, async () => {
        const toggle = railToggle()!;
        expect(toggle.getAttribute('aria-expanded')).toBe('false');
        expect(toggle.getAttribute('aria-label')).toBe('Expand navigation');
        expect(rail().querySelector('nav a.rail-item')).toBeTruthy();

        toggle.click();
        await settle();

        const sidenav = await loader.getHarness(MatSidenavHarness);
        expect(await sidenav.getMode()).toBe('side');
        expect(await sidenav.isOpen()).toBe(true);
        expect(rail().classList.contains('rail-wide')).toBe(true);
        expect(rail().querySelector('mat-nav-list')?.getAttribute('aria-label')).toBe('Primary');
        expect(railToggle()?.getAttribute('aria-expanded')).toBe('true');
        expect(railToggle()?.getAttribute('aria-label')).toBe('Collapse navigation');
        // The toggle and the brand sit in the banner with the destinations.
        expect(railToggle()?.closest('[role="banner"]')).toBeTruthy();
        expect(rail().querySelector('[role="banner"] .rail-brand')?.textContent?.trim()).toBe('Acme');
      });
    });
  }

  describe('extra-large (>= 1600px)', () => {
    beforeEach(() => render('extraLarge'));

    it('when extra-large, the rail starts expanded and the toggle collapses it', async () => {
      expect(rail().classList.contains('rail-wide')).toBe(true);
      expect(rail().querySelector('mat-nav-list')).toBeTruthy();
      expect(railToggle()?.getAttribute('aria-expanded')).toBe('true');

      railToggle()!.click();
      await settle();

      expect(rail().classList.contains('rail-wide')).toBe(false);
      expect(rail().querySelector('mat-nav-list')).toBeNull();
      expect(rail().querySelector('nav a.rail-item')).toBeTruthy();
    });
  });

  describe('across size classes', () => {
    it('when the user expands the rail, the choice holds at large, yields to the collapsed rail at medium and returns', async () => {
      await render('expanded');
      railToggle()!.click();
      await settle();
      expect(component.sidebarMode()).toBe('expanded');

      await resize('large');
      expect(component.sidebarMode()).toBe('expanded');

      await resize('medium');
      expect(component.sidebarMode()).toBe('collapsed');
      expect(railToggle()).toBeNull();

      await resize('expanded');
      expect(component.sidebarMode()).toBe('expanded');
    });

    it('when the user collapses the rail at extra-large, it stays collapsed at extra-large and large', async () => {
      await render('extraLarge');
      railToggle()!.click();
      await settle();
      expect(component.sidebarMode()).toBe('collapsed');

      await resize('large');
      await resize('extraLarge');
      expect(component.sidebarMode()).toBe('collapsed');
    });

    it('when the user collapses the rail, the choice is stored and a new shell (a reload or signing in again) starts collapsed', async () => {
      await render('extraLarge');
      railToggle()!.click();
      await settle();
      expect(localStorage.getItem(RAIL_EXPANDED_STORAGE_KEY)).toBe('false');

      fixture.destroy();
      await create();
      expect(component.sidebarMode()).toBe('collapsed');
      expect(rail().classList.contains('rail-wide')).toBe(false);
    });

    it('when storage is blocked, the size-class default applies and toggling still works', async () => {
      // Only the rail's key throws: auth clients in the overlay layers read their own keys
      // asynchronously, and a throw there would surface as an unrelated unhandled rejection.
      const getItem = Storage.prototype.getItem;
      const setItem = Storage.prototype.setItem;
      const blocked = (): DOMException => new DOMException('Site data is blocked', 'SecurityError');
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (this: Storage, key: string) {
        if (key === RAIL_EXPANDED_STORAGE_KEY) {
          throw blocked();
        }
        return getItem.call(this, key);
      });
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, key: string, value: string) {
        if (key === RAIL_EXPANDED_STORAGE_KEY) {
          throw blocked();
        }
        setItem.call(this, key, value);
      });

      await render('extraLarge');
      expect(component.sidebarMode()).toBe('expanded');

      railToggle()!.click();
      await settle();
      expect(component.sidebarMode()).toBe('collapsed');
    });

    it('when the window crosses 600px with the sheet open, the sheet closes and the docked rail replaces the bar', async () => {
      await render('compact');
      actionsButton().click();
      await settle();
      expect(sheet()).toBeTruthy();

      await resize('medium');
      expect(sheet()).toBeNull();
      expect(host.querySelector('app-bottom-tab-bar')).toBeNull();
      const sidenav = await loader.getHarness(MatSidenavHarness);
      expect(await sidenav.getMode()).toBe('side');
      expect(await sidenav.isOpen()).toBe(true);

      await resize('compact');
      expect(host.querySelector('app-bottom-tab-bar')).toBeTruthy();
      expect(host.querySelector('mat-sidenav')).toBeNull();
      expect(sheet()).toBeNull();
    });
  });

  /**
   * A size change that removes the focused shell control (the sheet and its trigger at 600px,
   * the rail toggle below 840px, the rail or the bar at 600px, the expanded rail's items when it
   * collapses) moves focus to the same control in the new form instead of dropping it to <body>.
   */
  describe('focus across size classes', () => {
    function railAction(selector: string): HTMLElement | null {
      return rail().querySelector<HTMLElement>(`.sidebar-footer ${selector}`);
    }

    function destination(container: Element | null, route: string): HTMLAnchorElement | null {
      const links = Array.from(container?.querySelectorAll<HTMLAnchorElement>('a[href]') ?? []);
      return links.find((link) => link.getAttribute('href') === route) ?? null;
    }

    it('when the window crosses 600px with focus in the actions sheet, focus moves to the same action in the docked rail', async () => {
      await render('compact');
      const trigger = actionsButton();
      trigger.focus();
      trigger.click();
      await settle();
      // A theme choice in the sheet maps to the rail's Change theme button, which opens the same choices.
      const sheetOption = sheet()!.querySelector<HTMLElement>('.sidebar-theme-options mat-list-option')!;
      sheetOption.focus();
      expect(document.activeElement).toBe(sheetOption);

      await resize('medium');
      await settle();

      expect(sheet()).toBeNull();
      expect(document.activeElement).not.toBe(document.body);
      expect(document.activeElement).toBe(railAction('button.sidebar-theme-toggle'));
    });

    it('when the window narrows below 840px with focus on the rail toggle, focus moves to the current destination', async () => {
      await render('expanded');
      await TestBed.inject(Router).navigateByUrl('/dashboard');
      await settle();
      railToggle()!.focus();

      await resize('medium');

      expect(railToggle()).toBeNull();
      const current = rail().querySelector('a.rail-item[aria-current="page"]');
      expect(current?.getAttribute('href')).toBe('/dashboard');
      expect(document.activeElement).toBe(current);
    });

    it('when the window crosses 600px with focus on a destination, focus follows it between the rail and the navigation bar', async () => {
      await render('medium');
      destination(rail(), '/chat')!.focus();

      await resize('compact');
      expect(document.activeElement).toBe(destination(host.querySelector('app-bottom-tab-bar'), '/chat'));

      await resize('medium');
      expect(document.activeElement).toBe(destination(rail(), '/chat'));
    });

    it('when the window crosses 600px with focus on a rail action, focus moves to the top app bar button that opens the actions, and back', async () => {
      await render('medium');
      railAction('button.sidebar-theme-toggle')!.focus();

      await resize('compact');
      expect(document.activeElement).toBe(actionsButton());

      await resize('medium');
      expect(document.activeElement).toBe(railAction('button.sidebar-theme-toggle'));
    });

    it('when the default expanded rail collapses at large, focus stays on the same destination', async () => {
      await render('extraLarge');
      destination(rail().querySelector('mat-nav-list'), '/settings')!.focus();

      await resize('large');

      expect(rail().classList.contains('rail-wide')).toBe(false);
      expect(document.activeElement).toBe(destination(rail().querySelector('nav'), '/settings'));
    });

    it('when focus is outside the shell controls, a size change leaves it where it is', async () => {
      await render('medium');
      const main = host.querySelector<HTMLElement>('main')!;
      main.focus();
      await resize('compact');
      expect(document.activeElement).toBe(main);

      main.blur();
      expect(document.activeElement).toBe(document.body);
      await resize('medium');
      expect(document.activeElement).toBe(document.body);
    });
  });

  describe('enlarged text', () => {
    it('when text is enlarged, the collapsed rail widens to its longest label word from a 96px floor instead of breaking the word', async () => {
      await render('medium');
      const css = Array.from(document.querySelectorAll('style'))
        .map((style) => style.textContent ?? '')
        .filter((text) => text.includes('.rail-content'))
        .join('\n');
      expect(css).toMatch(/\.rail(?:\[[^\]]+\])*\s*\{[^}]*--mat-sidenav-container-width:\s*min-content/);
      expect(css).toMatch(/\.rail(?:\[[^\]]+\])*\s*\{[^}]*min-inline-size:\s*calc\(96px \+ env\(safe-area-inset-left\)\)/);
      expect(css).toMatch(/\.rail\.rail-wide(?:\[[^\]]+\])*\s*\{[^}]*--mat-sidenav-container-width:\s*calc\(280px/);
    });

    it('when the rail changes size with no change detection (a web font loads, text is enlarged in place), the content offset is re-measured', async () => {
      type ObserverEntry = { callback: () => void; targets: Element[]; disconnected: boolean };
      const observers: ObserverEntry[] = [];
      vi.stubGlobal(
        'ResizeObserver',
        class {
          private readonly entry: ObserverEntry = { callback: () => undefined, targets: [], disconnected: false };
          constructor(callback: () => void) {
            this.entry.callback = callback;
            observers.push(this.entry);
          }
          observe(target: Element): void {
            this.entry.targets.push(target);
          }
          unobserve(): void {}
          disconnect(): void {
            this.entry.disconnected = true;
          }
        },
      );
      try {
        await render('medium');
        const railObserver = observers.find((o) => o.targets.includes(rail()) && !o.disconnected);
        expect(railObserver).toBeTruthy();

        const container = fixture.debugElement.query(By.directive(MatSidenavContainer))
          .componentInstance as MatSidenavContainer;
        const update = vi.spyOn(container, 'updateContentMargins');
        railObserver!.callback();
        expect(update).toHaveBeenCalledTimes(1);

        // No rail below 600px: the observer lets go of it.
        await resize('compact');
        expect(railObserver!.disconnected).toBe(true);
      } finally {
        vi.unstubAllGlobals();
      }
    });
  });
});
